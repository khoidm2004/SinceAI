"""P8 A2 specialist nodes (Groq-backed, AR-4 guarded)."""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_contracts import PROMPT_VERSION, assert_clean  # noqa: E402
from field_classifier import classify  # noqa: E402
from groq_client import GroqClient, GroqUnavailable  # noqa: E402
from pet_pipeline import TOKENISE_IDENTIFIERS  # noqa: E402
from scenario_loader import get_scenario  # noqa: E402

AVAILABLE_SPECIALISTS = ("classify_assist", "minim_assist", "brief_writer")
A3_SPECIALISTS = ("redact_assist", "discover_assist")
DEFAULT_SPECIALISTS = list(AVAILABLE_SPECIALISTS)

_RELEASES = (
    ("HEALTH-S1", "health", "health_csv"),
    ("FIN-S2", "finance", "finance_csv"),
)


def _record(
    state: dict,
    name: str,
    *,
    status: str,
    output: Any = None,
    error: str | None = None,
    dropped: int = 0,
    latency_ms: int | None = None,
) -> None:
    state.setdefault("agent_log", {})[name] = {
        "status": status,
        "output": output,
        "error": error,
        "dropped": dropped,
        "latency_ms": latency_ms,
        "prompt_version": PROMPT_VERSION,
    }


def _client(state: dict) -> GroqClient | None:
    return state.get("_client")


def _enabled(state: dict) -> bool:
    return bool(state.get("agents_enabled"))


def _selected(state: dict, name: str) -> bool:
    return name in (state.get("selected_specialists") or [])


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        return json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _header_and_rowcount(csv_path: Path) -> tuple[list[str], int]:
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        cols = list(reader.fieldnames or [])
        n = sum(1 for _ in reader)
    return cols, n


def _table_name(csv_path: Path) -> str:
    return csv_path.stem


def _charset_class(samples: list[str]) -> str:
    if not samples:
        return "mixed"
    kinds: set[str] = set()
    for s in samples:
        if not s:
            continue
        if s.isdigit():
            kinds.add("digits")
        elif s.isalpha():
            kinds.add("alpha")
        elif s.isalnum():
            kinds.add("alnum")
        else:
            kinds.add("mixed")
    if len(kinds) == 1:
        return kinds.pop()
    return "mixed"


def _shape_summary(csv_path: Path, column: str) -> dict[str, Any]:
    vals: list[str] = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            v = (row.get(column) or "").strip()
            if v:
                vals.append(v)
    n = len(vals)
    if n == 0:
        return {
            "column": column,
            "n_nonempty": 0,
            "len_min": 0,
            "len_max": 0,
            "charset": "mixed",
            "distinct_bucket": "low",
        }
    lengths = [len(v) for v in vals]
    distinct = len(set(vals))
    ratio = distinct / n
    if ratio < 0.1:
        bucket = "low"
    elif ratio < 0.9:
        bucket = "mid"
    else:
        bucket = "high"
    sample = vals[:200]
    return {
        "column": column,
        "n_nonempty": n,
        "len_min": min(lengths),
        "len_max": max(lengths),
        "charset": _charset_class(sample),
        "distinct_bucket": bucket,
    }


def _load_catalog_vocab(pack_root: Path) -> tuple[set[str], set[str]]:
    roles: set[str] = set()
    subtypes: set[str] = set()
    path = pack_root / "metadata" / "field_catalog.csv"
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            roles.add(row["privacy_role"])
            subtypes.add(row["subtype"])
    return roles, subtypes


def _collect_numbers(payload: Any, acc: set[str]) -> None:
    if isinstance(payload, dict):
        for v in payload.values():
            _collect_numbers(v, acc)
    elif isinstance(payload, list):
        for v in payload:
            _collect_numbers(v, acc)
    elif isinstance(payload, bool):
        pass
    elif isinstance(payload, (int, float)):
        acc.add(str(int(payload) if isinstance(payload, float) and payload.is_integer() else payload))
        if isinstance(payload, float) and not payload.is_integer():
            acc.add(str(payload))
    elif isinstance(payload, str):
        for m in re.findall(r"\d+", payload):
            acc.add(m)


def supervisor_node(state: dict) -> dict:
    if not _enabled(state):
        return state

    health = Path(state["health_csv"])
    finance = Path(state["finance_csv"])
    h_cols, h_n = _header_and_rowcount(health)
    f_cols, f_n = _header_and_rowcount(finance)
    specialists_available = list(AVAILABLE_SPECIALISTS)
    if state.get("enable_a3"):
        specialists_available += list(A3_SPECIALISTS)
    manifest = {
        "mode": state["mode"],
        "source": "raw_pack" if state.get("raw_pack") else "clean_data",
        "releases": [
            {
                "scenario_id": "HEALTH-S1",
                "dataset": "health",
                "columns": h_cols,
                "row_count": h_n,
            },
            {
                "scenario_id": "FIN-S2",
                "dataset": "finance",
                "columns": f_cols,
                "row_count": f_n,
            },
        ],
        "specialists_available": specialists_available,
    }
    allowed_set = set(specialists_available)
    client = _client(state)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a routing supervisor for a privacy release pipeline. You receive "
                "schema names and row counts only. Choose which specialists apply. Reply "
                'with JSON only: {"specialists": [...], "why": "..."}. You may not skip '
                "human review or the deterministic gate."
            ),
        },
        {"role": "user", "content": json.dumps(manifest, ensure_ascii=False)},
    ]
    chosen = list(DEFAULT_SPECIALISTS)
    dropped = 0
    latency: int | None = None
    if client is None:
        _record(state, "supervisor", status="unavailable", error="no client")
    else:
        try:
            raw = client.chat(messages, node="supervisor")
            latency = client.last_latency_ms
            parsed = _parse_json_object(raw)
            raw_list = parsed.get("specialists", [])
            if not isinstance(raw_list, list):
                raw_list = []
            chosen = [s for s in raw_list if isinstance(s, str) and s in allowed_set]
            dropped = len(raw_list) - len(chosen)
            if "brief_writer" not in chosen:
                chosen.append("brief_writer")
            _record(
                state,
                "supervisor",
                status="ok",
                output={"specialists": chosen, "why": parsed.get("why")},
                dropped=dropped,
                latency_ms=latency,
            )
        except GroqUnavailable as exc:
            chosen = list(DEFAULT_SPECIALISTS)
            _record(state, "supervisor", status="unavailable", error=str(exc))
    state["selected_specialists"] = chosen
    return state


def classify_assist_node(state: dict) -> dict:
    if not _enabled(state):
        return state
    if not _selected(state, "classify_assist"):
        _record(state, "classify_assist", status="skipped")
        return state

    pack_root = Path(state["pack_root"])
    uncatalogued_by_release: list[dict[str, Any]] = []
    all_empty = True
    for sid, dataset, csv_key in _RELEASES:
        csv_path = Path(state[csv_key])
        cols, _ = _header_and_rowcount(csv_path)
        table = _table_name(csv_path)
        catalogued = classify(pack_root, dataset, table)
        uncatalogued = [c for c in cols if c not in catalogued]
        if uncatalogued:
            all_empty = False
        uncatalogued_by_release.append(
            {"scenario_id": sid, "dataset": dataset, "table": table, "uncatalogued": uncatalogued}
        )

    if all_empty:
        _record(
            state,
            "classify_assist",
            status="no_input",
            output={"uncatalogued": uncatalogued_by_release},
        )
        return state

    roles, subtypes = _load_catalog_vocab(pack_root)
    shapes: list[dict[str, Any]] = []
    uncatalogued_set: set[str] = set()
    for entry in uncatalogued_by_release:
        csv_path = Path(state["health_csv" if entry["dataset"] == "health" else "finance_csv"])
        for col in entry["uncatalogued"]:
            uncatalogued_set.add(col)
            shapes.append(_shape_summary(csv_path, col))

    payload = {
        "releases": uncatalogued_by_release,
        "shape_summaries": shapes,
        "privacy_roles": sorted(roles),
        "subtypes": sorted(subtypes),
    }
    client = _client(state)
    if client is None:
        _record(state, "classify_assist", status="unavailable", error="no client")
        return state
    messages = [
        {
            "role": "system",
            "content": (
                "Propose privacy_role and subtype for uncatalogued columns using only the "
                "shape summaries. Use only values from the provided closed vocabularies. "
                'Reply JSON: {"rows":[{"column","privacy_role","subtype","confidence"}]}'
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    try:
        raw = client.chat(messages, node="classify_assist")
        parsed = _parse_json_object(raw)
        rows_in = parsed.get("rows", [])
        if not isinstance(rows_in, list):
            rows_in = []
        kept: list[dict[str, Any]] = []
        dropped = 0
        for row in rows_in:
            if not isinstance(row, dict):
                dropped += 1
                continue
            col = row.get("column")
            pr = row.get("privacy_role")
            st = row.get("subtype")
            if col not in uncatalogued_set or pr not in roles or st not in subtypes:
                dropped += 1
                continue
            kept.append(row)
        _record(
            state,
            "classify_assist",
            status="ok",
            output={"rows": kept},
            dropped=dropped,
            latency_ms=client.last_latency_ms,
        )
    except GroqUnavailable as exc:
        _record(state, "classify_assist", status="unavailable", error=str(exc))
    return state


def minim_assist_node(state: dict) -> dict:
    if not _enabled(state):
        return state
    if not _selected(state, "minim_assist"):
        _record(state, "minim_assist", status="skipped")
        return state

    pack_root = Path(state["pack_root"])
    payloads: list[dict[str, Any]] = []
    tokenised_union: set[str] = set()
    for sid, dataset, csv_key in _RELEASES:
        csv_path = Path(state[csv_key])
        header_cols, _ = _header_and_rowcount(csv_path)
        tokenised = sorted(TOKENISE_IDENTIFIERS.get((dataset, sid), set()) & set(header_cols))
        tokenised_union.update(tokenised)
        scenario = get_scenario(pack_root, sid)
        payloads.append(
            {
                "scenario_id": sid,
                "purpose": scenario["purpose"],
                "utility_requirements": scenario["utility_requirements"],
                "suggested_privacy_targets": scenario["suggested_privacy_targets"],
                "notes": scenario.get("notes", ""),
                "released_columns": header_cols,
                "tokenised_columns": tokenised,
            }
        )

    client = _client(state)
    if client is None:
        _record(state, "minim_assist", status="unavailable", error="no client")
        return state
    messages = [
        {
            "role": "system",
            "content": (
                "Suggest minimisation drop candidates among tokenised columns only. "
                'Reply JSON: {"candidates":[{"column","action":"drop","reason"}]}'
            ),
        },
        {"role": "user", "content": json.dumps({"releases": payloads}, ensure_ascii=False)},
    ]
    try:
        raw = client.chat(messages, node="minim_assist")
        parsed = _parse_json_object(raw)
        candidates_in = parsed.get("candidates", [])
        if not isinstance(candidates_in, list):
            candidates_in = []
        kept: list[dict[str, Any]] = []
        dropped = 0
        for cand in candidates_in:
            if not isinstance(cand, dict):
                dropped += 1
                continue
            col = cand.get("column")
            action = cand.get("action")
            if col not in tokenised_union or action != "drop":
                dropped += 1
                continue
            kept.append(cand)
        _record(
            state,
            "minim_assist",
            status="ok",
            output={"candidates": kept},
            dropped=dropped,
            latency_ms=client.last_latency_ms,
        )
    except GroqUnavailable as exc:
        _record(state, "minim_assist", status="unavailable", error=str(exc))
    return state


def _mosaic_for_brief(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return None
    out: dict[str, Any] = {}
    if "verdict" in data:
        out["verdict"] = data["verdict"]
    for key in ("pass1", "pass2", "positive_control"):
        if key in data:
            out[key] = data[key]
    norm = data.get("normalisation")
    if isinstance(norm, dict):
        out["normalisation_rules"] = {
            "phone_norm": norm.get("phone", ""),
            "hetu_norm": norm.get("hetu", ""),
        }
    return out


def _scorecard_scalars(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return None
    return {
        k: v
        for k, v in data.items()
        if isinstance(v, (int, float, str, bool)) or v is None
    }


def brief_writer_node(state: dict) -> dict:
    if not _enabled(state):
        return state
    if not _selected(state, "brief_writer"):
        _record(state, "brief_writer", status="skipped")
        return state

    report = state.get("report") or {}
    numbers: dict[str, Any] = {
        "attack_sim": {
            "hetu_join": report.get("hetu_join", 0),
            "phone_join": report.get("phone_join", 0),
        },
    }
    mosaic_path = Path(state["clean_root"]) / "mosaic_check.json"
    mosaic_brief = _mosaic_for_brief(mosaic_path)
    if mosaic_brief is not None:
        numbers["mosaic"] = mosaic_brief
    clean_root = Path(state["clean_root"])
    scorecards: dict[str, Any] = {}
    for sid, rel in (("HEALTH-S1", "health__HEALTH-S1/scorecard.json"), ("FIN-S2", "finance__FIN-S2/scorecard.json")):
        sc = _scorecard_scalars(clean_root / rel)
        if sc is not None:
            scorecards[sid] = sc
    if scorecards:
        numbers["scorecards"] = scorecards

    client = _client(state)
    if client is None:
        _record(state, "brief_writer", status="unavailable", error="no client")
        return state
    messages = [
        {
            "role": "system",
            "content": (
                "Write a 120-word plain-English brief for a non-technical reviewer. "
                "Use only the numbers in the JSON you are given. Do not introduce any "
                "number that is not present. State what passed, and that the JSON report "
                "— not this brief — is the record. Reply as JSON: {\"brief\": \"...\"}."
            ),
        },
        {"role": "user", "content": json.dumps(numbers, ensure_ascii=False)},
    ]
    try:
        assert_clean(numbers, where="brief_writer:input")
        raw = client.chat(messages, node="brief_writer")
        parsed = _parse_json_object(raw)
        brief = str(parsed.get("brief", ""))
        allowed: set[str] = {"0", "1", "2", "100"}
        _collect_numbers(numbers, allowed)
        unknown = sorted(set(re.findall(r"\d+", brief)) - allowed)
        if unknown:
            print(
                f"warning: brief_writer produced numbers not in the source JSON: {unknown}",
                file=sys.stderr,
            )
        state["brief"] = brief
        _record(
            state,
            "brief_writer",
            status="ok",
            output={"brief": brief, "unknown_numbers": unknown},
            latency_ms=client.last_latency_ms,
        )
    except GroqUnavailable as exc:
        _record(state, "brief_writer", status="unavailable", error=str(exc))
    return state


def redact_assist_node(state: dict) -> dict:
    if not _enabled(state):
        return state
    if not state.get("enable_a3"):
        _record(
            state,
            "redact_assist",
            status="stub_disabled",
            output={"note": "A3 scope; free-text egress not implemented (AR-1)"},
        )
        return state
    _record(
        state,
        "redact_assist",
        status="stub_not_implemented",
        output={
            "note": "enable_a3 set, but A3 is out of P8/A2 scope — no free text is sent to any provider"
        },
    )
    return state


def discover_assist_node(state: dict) -> dict:
    if not _enabled(state):
        return state
    if not state.get("enable_a3"):
        _record(
            state,
            "discover_assist",
            status="stub_disabled",
            output={"note": "A3 scope; free-text egress not implemented (AR-1)"},
        )
        return state
    _record(
        state,
        "discover_assist",
        status="stub_not_implemented",
        output={
            "note": "enable_a3 set, but A3 is out of P8/A2 scope — no free text is sent to any provider"
        },
    )
    return state
