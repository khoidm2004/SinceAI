"""P2 Attack A re-measurement on staged CSVs (read-only)."""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalize_hetu, normalize_phone, unique_nonempty  # noqa: E402

HEALTH_ROW_ID_COL = "visit_id"
FINANCE_ROW_ID_COL = "customer_id"


def _read_optional_column(path: Path, col: Optional[str]) -> List[Optional[str]]:
    if not col:
        return []
    with open(path, encoding="utf-8-sig", newline="", mode="r") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or col not in reader.fieldnames:
            return []
        return [row.get(col) for row in reader]


def _index_by_normalized(
    path: Path,
    col: str,
    normalizer,
    row_id_col: str,
) -> Dict[str, str]:
    """Map normalised key -> first row id (string)."""
    out: Dict[str, str] = {}
    with open(path, encoding="utf-8-sig", newline="", mode="r") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or col not in reader.fieldnames:
            return out
        has_id = row_id_col in reader.fieldnames
        for row in reader:
            key = normalizer(row.get(col))
            if not key or key in out:
                continue
            out[key] = str(row.get(row_id_col, "")) if has_id else ""
    return out


def _build_proposals(
    hetu_join: int,
    phone_join: int,
    columns_used: dict[str, Any],
) -> List[dict[str, str]]:
    proposals: List[dict[str, str]] = []
    if hetu_join > 0:
        hcol = columns_used.get("health_hetu_col")
        fcol = columns_used.get("finance_hetu_col")
        if hcol and columns_used.get("health_hetu_present"):
            proposals.append(
                {
                    "action": "drop",
                    "column": hcol,
                    "reason": f"HETU cross-release join is {hetu_join}; drop glue column on health release",
                }
            )
        if fcol and columns_used.get("finance_hetu_present"):
            proposals.append(
                {
                    "action": "drop",
                    "column": fcol,
                    "reason": f"HETU cross-release join is {hetu_join}; drop glue column on finance release",
                }
            )
    if phone_join > 0:
        for side, key in (("health", "health_phone_col"), ("finance", "finance_phone_col")):
            col = columns_used.get(key)
            present_key = f"{side}_phone_present"
            if col and columns_used.get(present_key):
                proposals.append(
                    {
                        "action": "re-tokenise",
                        "column": col,
                        "reason": (
                            f"phone cross-release join is {phone_join}; "
                            "re-tokenise with distinct key domain"
                        ),
                    }
                )
    return proposals


def _collect_samples(
    health_csv: Path,
    finance_csv: Path,
    column_map: dict[str, Any],
    hetu_join: int,
    phone_join: int,
    sample_limit: int,
) -> List[dict[str, Any]]:
    if hetu_join == 0 and phone_join == 0:
        return []

    samples: List[dict[str, Any]] = []
    h_hetu = column_map.get("health_hetu_col")
    f_hetu = column_map.get("finance_hetu_col")
    h_phone = column_map.get("health_phone_col")
    f_phone = column_map.get("finance_phone_col")

    if hetu_join > 0 and h_hetu and f_hetu:
        health_by = _index_by_normalized(health_csv, h_hetu, normalize_hetu, HEALTH_ROW_ID_COL)
        finance_by = _index_by_normalized(finance_csv, f_hetu, normalize_hetu, FINANCE_ROW_ID_COL)
        for key in sorted(health_by.keys() & finance_by.keys()):
            if len(samples) >= sample_limit:
                break
            samples.append(
                {
                    "hetu": key,
                    "health_row_id": health_by[key],
                    "finance_row_id": finance_by[key],
                }
            )

    if phone_join > 0 and h_phone and f_phone and len(samples) < sample_limit:
        health_by = _index_by_normalized(health_csv, h_phone, normalize_phone, HEALTH_ROW_ID_COL)
        finance_by = _index_by_normalized(finance_csv, f_phone, normalize_phone, FINANCE_ROW_ID_COL)
        for key in sorted(health_by.keys() & finance_by.keys()):
            if len(samples) >= sample_limit:
                break
            samples.append(
                {
                    "phone": key,
                    "health_row_id": health_by[key],
                    "finance_row_id": finance_by[key],
                }
            )

    return samples


def simulate_attack(
    health_csv: Path,
    finance_csv: Path,
    *,
    health_hetu_col: str,
    finance_hetu_col: str,
    health_phone_col: Optional[str],
    finance_phone_col: Optional[str],
    sample_limit: int = 3,
) -> dict:
    health_csv = Path(health_csv)
    finance_csv = Path(finance_csv)

    health_hetu_vals = _read_optional_column(health_csv, health_hetu_col)
    finance_hetu_vals = _read_optional_column(finance_csv, finance_hetu_col)
    health_phone_vals = _read_optional_column(health_csv, health_phone_col)
    finance_phone_vals = _read_optional_column(finance_csv, finance_phone_col)

    health_hetus = unique_nonempty(health_hetu_vals, normalize_hetu)
    finance_hetus = unique_nonempty(finance_hetu_vals, normalize_hetu)
    health_phones = unique_nonempty(health_phone_vals, normalize_phone)
    finance_phones = unique_nonempty(finance_phone_vals, normalize_phone)

    hetu_join = len(health_hetus & finance_hetus)
    phone_join = len(health_phones & finance_phones)

    columns_used = {
        "health_hetu_col": health_hetu_col,
        "finance_hetu_col": finance_hetu_col,
        "health_phone_col": health_phone_col,
        "finance_phone_col": finance_phone_col,
        "health_hetu_present": bool(health_hetu_vals),
        "finance_hetu_present": bool(finance_hetu_vals),
        "health_phone_present": bool(health_phone_vals),
        "finance_phone_present": bool(finance_phone_vals),
    }

    if hetu_join == 0 and phone_join == 0:
        return {
            "hetu_join": 0,
            "phone_join": 0,
            "samples": [],
            "proposals": [],
            "columns_used": columns_used,
        }

    proposals = _build_proposals(hetu_join, phone_join, columns_used)
    samples = _collect_samples(
        health_csv,
        finance_csv,
        columns_used,
        hetu_join,
        phone_join,
        sample_limit,
    )

    return {
        "hetu_join": hetu_join,
        "phone_join": phone_join,
        "samples": samples,
        "proposals": proposals,
        "columns_used": columns_used,
    }
