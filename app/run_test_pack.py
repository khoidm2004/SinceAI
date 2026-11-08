#!/usr/bin/env python3
"""Multi-table protection of a synthetic test pack with Mosaic's EXISTING PET implementation.

The official P1 runner (app/run_protect.py) protects one table per scenario
(HEALTH-S1 -> ed_visits, FIN-S2 -> customers) and writes to clean_data/. The scenario utility tasks
need more tables, so this test-only runner protects every table the tasks read, reusing the
unchanged functions:

  field_classifier.classify  ->  pet_pipeline.protect_table  ->  run_protect.glue_survival_guard
  pseudonym.derive_subkey (one key domain per (dataset, scenario))  ->  release_writer.write_release

Two policies are run and reported side by side (nothing is changed silently):

  current     exactly the current pipeline, table by table, no overrides.
  relational  the same pipeline with a documented classifier override for release-internal join keys:
              every column of a logical key (visit, customer, card) is treated as a
              technical_identifier, so protect_table tokenises all of them with the SAME release subkey.
              Tokens stay equal across tables (joins survive) but differ across releases (key domain =
              dataset|scenario). card_pan is tokenised, as FIN-S2's own privacy target asks ("tokenised card").

Row maps are written to <run>/private/rowmaps/ (scoring-only, never next to the release).
Never writes under resources/, clean_data/ or keys/.
"""
from __future__ import annotations

from python_version import require_python

require_python()
import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from field_classifier import classify  # noqa: E402
from normalize import normalize_hetu, normalize_iban, normalize_phone  # noqa: E402
from pet_pipeline import protect_table  # noqa: E402
from pseudonym import create_master_key, derive_subkey, load_master_key  # noqa: E402
from release_writer import write_release  # noqa: E402
from run_protect import glue_survival_guard, read_table_csv  # noqa: E402
from scenario_loader import get_scenario  # noqa: E402
from synth_common import (  # noqa: E402
    RELEASE_TABLES, peak_memory_bytes, read_csv, read_header, refuse_forbidden, run_dirs, sha256_file, utf8_stdout, write_json,
)

POLICIES = {
    "current": "Current Mosaic PET pipeline applied per table, no overrides (app/pet_pipeline.protect_table as-is).",
    "relational": "Current pipeline + documented classifier override: release-internal join-key columns are treated as "
                  "technical_identifier so all of them are tokenised with the same release subkey (joins survive inside the "
                  "release, not across releases); card_pan tokenised per FIN-S2 'tokenised card'.",
}
# Logical keys that the scenario utility tasks join on (pets-eval utility/health.py H-U7; finance.py FIN-U1/U4/U6).
JOIN_KEYS: Dict[str, List[tuple]] = {
    "health": [("visit", [("ed_visits", "visit_id"), ("lab_results", "visit_id"), ("clinical_notes", "visit_id")])],
    "finance": [("customer", [("customers", "customer_id"), ("cards", "customer_id")]),
                ("card", [("cards", "card_pan"), ("card_transactions", "card_pan")])],
}
HETU_RE = re.compile(r"(?<![0-9A-Za-z])(\d{6}[-+ABCDEFUVWXY]\d{3}[0-9A-Y])(?![0-9A-Za-z])")
PHONE_RE = re.compile(r"(?<![\d+])((?:\+358|00358|\b0)[ -]?(?:4\d|50)[ -]?\d{3,4}[ -]?\d{3,4})(?!\d)")
IBAN_RE = re.compile(r"(?<![A-Z0-9])(FI\d{2}(?: ?\d{4}){3}(?: ?\d{2}))(?![A-Z0-9])")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CARD_RE = re.compile(r"(?<!\d)(\d{16})(?!\d)")


def overrides_for(policy: str, dataset: str) -> Dict[str, Dict[str, Dict[str, str]]]:
    """table -> column -> override role/subtype. Empty for the 'current' policy."""
    if policy == "current":
        return {}
    out: Dict[str, Dict[str, Dict[str, str]]] = {}
    for _, cols in JOIN_KEYS.get(dataset, []):
        for table, col in cols:
            out.setdefault(table, {})[col] = {"role": "technical_identifier", "subtype": "JOIN_KEY"}
    return out


def _norm_kind(subtype: str):
    return {"NATIONAL_ID": normalize_hetu, "PHONE": normalize_phone, "IBAN": normalize_iban}.get(subtype, lambda v: (v or "").strip().casefold())


def identifier_index(pack: Path, dataset: str, tables: Sequence[str]) -> Dict[str, set]:
    """Normalised raw values of every catalogued direct identifier in ANY table of the release.

    Release-wide on purpose: a patient's HETU, phone or name typed into clinical_notes.note_text is a raw
    identifier of the release even though note_text's own table has no HETU column. Technical identifiers are
    excluded here (a passthrough record key equals the raw FK value by design; that is reported via the
    relationship check, not as leakage)."""
    values: Dict[str, set] = {}
    for table in tables:
        clf = classify(pack, dataset, table)
        cols = {c: m["subtype"] for c, m in clf.items() if m["role"] == "direct_identifier"}
        rows, _ = read_csv(pack / "data" / dataset / f"{table}.csv")
        for row in rows:
            for c, st in cols.items():
                v = _norm_kind(st)(row.get(c, ""))
                if len(v) >= 4:
                    values.setdefault(st, set()).add(v)
    return values


def raw_identifier_survival(values: Dict[str, set], out_rows, out_fields) -> Dict[str, Any]:
    """Raw direct-identifier values found in the protected table, as whole cells or inside text (counts only)."""
    hits: Dict[str, int] = {}
    for row in out_rows:
        for c in out_fields:
            cell = row.get(c) or ""
            if not cell:
                continue
            for st, vals in values.items():
                if _norm_kind(st)(cell) in vals:
                    hits[f"{c}:{st}:whole_cell"] = hits.get(f"{c}:{st}:whole_cell", 0) + 1
            if len(cell) > 20 or " " in cell:  # identifier patterns and names inside text
                for st, rx, norm in (("NATIONAL_ID", HETU_RE, normalize_hetu), ("PHONE", PHONE_RE, normalize_phone), ("IBAN", IBAN_RE, normalize_iban),
                                     ("EMAIL", EMAIL_RE, lambda v: v.casefold()), ("PAYMENT_CARD", CARD_RE, lambda v: v)):
                    for m in rx.finditer(cell):
                        if norm(m.group(0)) in values.get(st, ()):
                            hits[f"{c}:{st}:inside_text"] = hits.get(f"{c}:{st}:inside_text", 0) + 1
                if "\n" in cell or len(cell) > 40:  # full person names typed into free text
                    low = cell.casefold()
                    for line in low.split("\n"):
                        for chunk in re.split(r"[:,.;]", line):
                            if chunk.strip() in values.get("PERSON_NAME", ()):
                                hits[f"{c}:PERSON_NAME:inside_text"] = hits.get(f"{c}:PERSON_NAME:inside_text", 0) + 1
    return {"survivors": hits, "total": sum(hits.values())}


def protect_release(pack: Path, out_root: Path, rowmap_root: Path, master: bytes, sid: str, policy: str) -> Dict[str, Any]:
    dataset, tables = RELEASE_TABLES[sid]
    scenario = get_scenario(pack, sid)
    if scenario["dataset"] != dataset:
        raise ValueError(f"{sid}: scenario dataset {scenario['dataset']!r} != {dataset!r}")
    subkey = derive_subkey(master, dataset, sid)  # one key domain per (dataset, scenario), shared by its tables
    rel = f"{dataset}__{sid}"
    out_dir, rm_dir = out_root / rel, rowmap_root / rel
    refuse_forbidden(out_dir, "protected release")
    refuse_forbidden(rm_dir, "row maps")
    ov = overrides_for(policy, dataset)
    report: Dict[str, Any] = {"scenario": sid, "dataset": dataset, "policy": policy, "tables": {}, "overrides": ov}
    protected: Dict[str, Any] = {}
    id_values = identifier_index(pack, dataset, [t for t, _ in tables])
    for table, record_key in tables:
        t0 = time.perf_counter()
        rows, fields = read_table_csv(pack / "data" / dataset / f"{table}.csv")
        clf = classify(pack, dataset, table)
        clf_used = {c: dict(m) for c, m in clf.items()}
        for col, o in ov.get(table, {}).items():
            if col in clf_used:
                clf_used[col] = dict(o)
        out_rows, out_fields, actions = protect_table(rows, fields, dataset=dataset, table=table, scenario_id=sid, classifier=clf_used, subkey=subkey)
        guard = {"passed": True, "message": ""}
        try:
            glue_survival_guard(dataset, sid, pack, table, out_fields)  # existing release rule, unchanged
        except SystemExit as exc:
            guard = {"passed": False, "message": str(exc)}
        record_ids = [str(r.get(record_key, "")) for r in rows]
        write_release(out_dir, table, out_rows, out_fields, record_ids)
        rm_dir.mkdir(parents=True, exist_ok=True)
        os.replace(out_dir / f"rowmap_{table}.csv", rm_dir / f"rowmap_{table}.csv")  # row maps stay private
        written_rows, written_fields = read_csv(out_dir / f"{table}.csv")
        rm_rows, rm_fields = read_csv(rm_dir / f"rowmap_{table}.csv")
        expected_fields = [c for c in fields if c not in actions["dropped"]]
        col_actions = []
        for c in fields:
            role = clf.get(c, {}).get("role", "unclassified")
            act = next((k for k, v in actions.items() if c in v), "?")
            col_actions.append({"column": c, "catalog_role": role, "catalog_subtype": clf.get(c, {}).get("subtype", ""),
                                "override": ov.get(table, {}).get(c, {}).get("role", ""), "action": act})
        report["tables"][table] = {
            "record_key": record_key, "rows_in": len(rows), "rows_out": len(written_rows), "columns_in": len(fields), "columns_out": len(written_fields),
            "columns_out_list": written_fields, "dropped": actions["dropped"], "column_order_preserved": written_fields == expected_fields,
            "actions": {k: v for k, v in actions.items()}, "column_actions": col_actions,
            "glue_survival_guard": guard,
            "rowmap": {"rows": len(rm_rows), "header_ok": rm_fields == ["protected_row", "original_record_id"],
                       "aligned": len(rm_rows) == len(rows) and all(r["protected_row"] == str(i) and r["original_record_id"] == record_ids[i] for i, r in enumerate(rm_rows))},
            "raw_identifier_survival": raw_identifier_survival(id_values, written_rows, written_fields),
            "csv_sha256": sha256_file(out_dir / f"{table}.csv"), "seconds": round(time.perf_counter() - t0, 3),
        }
        protected[table] = (written_rows, written_fields)
    # release-internal relationships after protection
    joins = []
    for name, cols in JOIN_KEYS.get(dataset, []):
        parent_t, parent_c = cols[0]
        prows, pfields = protected[parent_t]
        for child_t, child_c in cols[1:]:
            crows, cfields = protected[child_t]
            if parent_c not in pfields or child_c not in cfields:
                missing = [f"{t}.{c}" for t, c, f in ((parent_t, parent_c, pfields), (child_t, child_c, cfields)) if c not in f]
                joins.append({"key": name, "parent": f"{parent_t}.{parent_c}", "child": f"{child_t}.{child_c}", "status": "BROKEN_COLUMN_DROPPED",
                              "missing": missing, "resolving_share": None})
                continue
            pvals = {r[parent_c] for r in prows if r[parent_c]}
            cvals = [r[child_c] for r in crows if r[child_c]]
            share = round(sum(1 for v in cvals if v in pvals) / max(1, len(cvals)), 4)
            joins.append({"key": name, "parent": f"{parent_t}.{parent_c}", "child": f"{child_t}.{child_c}",
                          "status": "PRESERVED" if share == 1.0 else ("BROKEN_INCONSISTENT_TRANSFORM" if share == 0 else "PARTIAL"), "resolving_share": share})
    report["relationships"] = joins
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    utf8_stdout()
    p = argparse.ArgumentParser(description="Protect a synthetic test pack with Mosaic's PET pipeline (all scenario tables)")
    p.add_argument("--run-dir", type=Path, required=True, help="run directory created by generate_test_data.py")
    p.add_argument("--policy", choices=["current", "relational", "both"], default="both")
    p.add_argument("--key-file", type=Path, default=None, help="default: <run>/private/master.key (temporary, per run)")
    p.add_argument("--init-key", action="store_true", help="create the key file if missing (never overwrites)")
    a = p.parse_args(argv)
    d = run_dirs(a.run_dir.resolve())
    key = (a.key_file or d["private"] / "master.key").resolve()
    for path, what in ((d["protected"], "protected output"), (key, "key file")):
        refuse_forbidden(path, what)
    if key.is_file():
        master = load_master_key(key)
    elif a.init_key:
        master = create_master_key(key)
    else:
        print(f"error: key file missing ({key}); pass --init-key to create a temporary one", file=sys.stderr)
        return 2
    policies = ["current", "relational"] if a.policy == "both" else [a.policy]
    for pol in policies:
        out_root = d["protected"] / pol
        if out_root.exists() and any(out_root.iterdir()):
            print(f"error: {out_root} already exists (never overwritten)", file=sys.stderr)
            return 2
        t0 = time.perf_counter()
        ev = {"policy": pol, "description": POLICIES[pol], "key_file": "private/master.key (temporary, per run)", "releases": {}}
        for sid in RELEASE_TABLES:
            ev["releases"][sid] = protect_release(d["pack"], out_root, d["private"] / "rowmaps" / pol, master, sid, pol)
        ev["seconds"] = round(time.perf_counter() - t0, 3)
        ev["peak_memory_bytes"] = peak_memory_bytes()
        ev["rows_processed"] = sum(t["rows_in"] for r in ev["releases"].values() for t in r["tables"].values())
        write_json(d["evidence"] / f"protection_{pol}.json", ev)
        print(f"=== policy {pol}: {ev['seconds']} s, {ev['rows_processed']} rows")
        for sid, r in ev["releases"].items():
            for t, tr in r["tables"].items():
                print(f"  {sid} {t}: rows {tr['rows_in']}->{tr['rows_out']} cols {tr['columns_in']}->{tr['columns_out']} "
                      f"dropped={tr['dropped'] or '-'} rowmap_aligned={tr['rowmap']['aligned']} raw_id_survivors={tr['raw_identifier_survival']['total']}")
            for j in r["relationships"]:
                print(f"  {sid} join {j['child']} -> {j['parent']}: {j['status']} (resolving {j['resolving_share']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
