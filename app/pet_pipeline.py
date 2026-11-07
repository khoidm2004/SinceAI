"""PET protection transforms for one catalogued table."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pseudonym import tokenise  # noqa: E402

# Per-(dataset, scenario) key domains: the same person gets a different token
# in each release, so the columns stay usable inside a release but cannot be
# joined across releases (PET_PLAYBOOK "Joins across datasets").
# HEALTH-S1 must NOT list `phone`: normalize_phone() strips the hex letters out
# of a token, and the digits that survive can collide across releases.
TOKENISE_IDENTIFIERS: dict[tuple[str, str], set[str]] = {
    ("health", "HEALTH-S1"): {"patient_hetu"},
    ("finance", "FIN-S2"): {"hetu", "phone", "iban", "email"},
}

KIND_BY_SUBTYPE: dict[str, str] = {
    "NATIONAL_ID": "hetu",
    "PHONE": "phone",
    "IBAN": "iban",
    "EMAIL": "raw",
}

GENERALISE_SUBTYPES = frozenset({"BIRTH_DATE", "POSTCODE", "TIMESTAMP", "DATE"})


def _generalise_birth_date(value: str | None) -> str:
    if value is None or not str(value).strip():
        return ""
    s = str(value).strip()
    if len(s) >= 4:
        return s[:4]
    return s


def _generalise_postcode(value: str | None) -> str:
    if value is None or not str(value).strip():
        return ""
    digits = "".join(c for c in str(value) if c.isdigit())
    if len(digits) < 3:
        return ""
    return digits[:3] + "**"


def _parse_datetime(value: str) -> datetime | None:
    s = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            if fmt == "%Y-%m-%d %H:%M:%S":
                return datetime.strptime(s[:19], fmt)
            return datetime.strptime(s[:10], fmt)
        except ValueError:
            continue
    return None


def _generalise_timestamp(value: str | None) -> str:
    if value is None or not str(value).strip():
        return ""
    dt = _parse_datetime(str(value))
    if dt is None:
        return str(value).strip()
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _generalise_date(value: str | None) -> str:
    if value is None or not str(value).strip():
        return ""
    s = str(value).strip()
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    return s


def _generalise_quasi(value: str | None, subtype: str) -> str:
    if subtype == "BIRTH_DATE":
        return _generalise_birth_date(value)
    if subtype == "POSTCODE":
        return _generalise_postcode(value)
    if subtype == "TIMESTAMP":
        return _generalise_timestamp(value)
    if subtype == "DATE":
        return _generalise_date(value)
    return "" if value is None else str(value)


def protect_table(
    rows: list[dict[str, Any]],
    fieldnames: list[str],
    *,
    dataset: str,
    table: str,
    scenario_id: str,
    classifier: dict[str, dict[str, str]],
    subkey: bytes,
) -> tuple[list[dict[str, Any]], list[str], dict[str, list[str]]]:
    """Apply drop / tokenise / generalise; preserve row order."""
    del table  # reserved for future multi-table releases
    tokenise_cols = TOKENISE_IDENTIFIERS.get((dataset, scenario_id), set())

    actions: dict[str, list[str]] = {
        "dropped": [],
        "tokenised": [],
        "generalised": [],
        "passthrough": [],
        "unclassified": [],
    }
    out_fieldnames: list[str] = []
    col_plan: dict[str, str] = {}  # col -> action key for transform

    for col in fieldnames:
        if col not in classifier:
            out_fieldnames.append(col)
            actions["unclassified"].append(col)
            col_plan[col] = "unclassified"
            continue

        role = classifier[col]["role"]
        subtype = classifier[col]["subtype"]

        if role == "direct_identifier":
            if col in tokenise_cols:
                out_fieldnames.append(col)
                actions["tokenised"].append(col)
                col_plan[col] = "tokenise_direct"
            else:
                actions["dropped"].append(col)
                col_plan[col] = "drop"
        elif role == "technical_identifier":
            # Tokenise so staff linkage within a release survives without raw ids.
            out_fieldnames.append(col)
            actions["tokenised"].append(col)
            col_plan[col] = "tokenise_raw"
        elif role == "quasi_identifier":
            out_fieldnames.append(col)
            if subtype in GENERALISE_SUBTYPES:
                actions["generalised"].append(col)
                col_plan[col] = f"generalise:{subtype}"
            else:
                actions["passthrough"].append(col)
                col_plan[col] = "passthrough"
        else:
            out_fieldnames.append(col)
            actions["passthrough"].append(col)
            col_plan[col] = "passthrough"

    for key in actions:
        actions[key] = sorted(actions[key])

    out_rows: list[dict[str, Any]] = []
    for row in rows:
        out_row: dict[str, Any] = {}
        for col in fieldnames:
            plan = col_plan.get(col, "unclassified")
            if plan == "drop":
                continue
            raw = row.get(col)
            if plan == "tokenise_direct":
                kind = KIND_BY_SUBTYPE.get(classifier[col]["subtype"], "raw")
                out_row[col] = tokenise(raw, subkey, kind=kind)
            elif plan == "tokenise_raw":
                out_row[col] = tokenise(raw, subkey, kind="raw")
            elif plan.startswith("generalise:"):
                st = plan.split(":", 1)[1]
                out_row[col] = _generalise_quasi(raw, st)
            else:
                out_row[col] = "" if raw is None else raw
        out_rows.append(out_row)

    return out_rows, out_fieldnames, actions
