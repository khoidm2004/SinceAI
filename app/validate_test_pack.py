#!/usr/bin/env python3
"""Validate a synthetic test pack against the official metadata and synthetic-identifier conventions.

Checks (all recomputed from the files): headers identical to the official tables, every column catalogued in
metadata/field_catalog.csv, scenarios and attack specs resolvable (adversary + truth files present, first
adversary column = row id), identifier conventions (HETU 900-999 with check character, IBAN mod-97 with bank id 9,
test-BIN cards with Luhn, .example e-mail, Finnish-format phones), unique record ids, referential integrity, scenario
periods, PII span offsets/labels, and that the official Attack A baseline still reproduces 1622 / 1484 on the
OFFICIAL pack (read-only; its report is written only into this run's evidence folder).
"""
from __future__ import annotations

from python_version import require_python

require_python()
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_test_data import GENERATED_ADVERSARIES, SCHEMA, TEST_BINS, hetu_ok, iban_ok, luhn_ok, validate_spans  # noqa: E402
from normalize import normalize_phone  # noqa: E402
from synth_common import OFFICIAL_PACK, read_csv, read_header, read_json, run_dirs, utf8_stdout, write_json  # noqa: E402

SPAN_LABELS = {"PERSON", "NATIONAL_ID", "EMAIL", "PHONE", "ADDRESS", "IBAN", "PAYMENT_CARD", "ACCOUNT_NUMBER", "IP_ADDRESS", "LICENSE_PLATE",
               "USERNAME", "SECRET", "DEVICE_ID", "PROPERTY_ID", "URL", "AGE", "DATE", "LOCATION", "ORG", "HEALTH"}
RECORD_KEYS = {"ed_visits": "visit_id", "lab_results": "lab_id", "clinical_notes": "note_id", "customers": "customer_id", "cards": "card_ref_id",
               "card_transactions": "tx_id"}


def validate(pack: Path, official: Path = OFFICIAL_PACK) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = "", kind: str = "integrity") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail, "kind": kind})

    cat_rows, _ = read_csv(pack / "metadata" / "field_catalog.csv")
    catalogued = {(r["dataset"], r["table"], r["column"]) for r in cat_rows}
    data: Dict[tuple, list] = {}
    for (ds, tb), cols in SCHEMA.items():
        hdr = read_header(pack / "data" / ds / f"{tb}.csv")
        add(f"header identical to official {ds}/{tb}", hdr == read_header(official / "data" / ds / f"{tb}.csv"))
        add(f"all columns catalogued {ds}/{tb}", all((ds, tb, c) in catalogued for c in hdr), [c for c in hdr if (ds, tb, c) not in catalogued])
        rows, _ = read_csv(pack / "data" / ds / f"{tb}.csv")
        data[(ds, tb)] = rows
        ids = [r[RECORD_KEYS[tb]] for r in rows]
        add(f"unique record ids {ds}/{tb}", len(ids) == len(set(ids)) and all(ids), {"rows": len(ids)})
    ed, labs, notes = data[("health", "ed_visits")], data[("health", "lab_results")], data[("health", "clinical_notes")]
    cu, cards, tx = data[("finance", "customers")], data[("finance", "cards")], data[("finance", "card_transactions")]
    vids, cids, pans = {r["visit_id"] for r in ed}, {r["customer_id"] for r in cu}, {r["card_pan"] for r in cards}
    add("FK lab_results.visit_id -> ed_visits", all(r["visit_id"] in vids for r in labs))
    add("FK clinical_notes.visit_id -> ed_visits", all(r["visit_id"] in vids for r in notes))
    add("FK cards.customer_id -> customers", all(r["customer_id"] in cids for r in cards))
    add("FK card_transactions.card_pan -> cards", all(r["card_pan"] in pans for r in tx))
    hetus = [r["patient_hetu"] for r in ed if r["patient_hetu"]] + [r["hetu"] for r in cu]
    add("HETU: individual number 900-999, valid check character", all(hetu_ok(h) for h in hetus), {"checked": len(hetus)})
    add("HETU unique per finance customer", len({r["hetu"] for r in cu}) == len(cu))
    add("IBAN: FI, mod-97 valid, bank id starts with 9", all(i.startswith("FI") and i[4] == "9" and iban_ok(i) for i in (r["iban"] for r in cu)))
    add("cards: public test BIN + Luhn", all(p[:6] in TEST_BINS and luhn_ok(p) for p in pans))
    add("e-mail on reserved .example domains", all(e.endswith(".example") for e in (r["email"] for r in cu) if e))
    fi_mobile = re.compile(r"^0(4\d|50)\d{7}$")
    add("phones normalise to Finnish mobile format (or +46 for non-residents)",
        all(fi_mobile.match(normalize_phone(p)) or p.startswith("+46") for p in [r["phone"] for r in ed if r["phone"]] + [r["phone"] for r in cu if r["phone"]]))
    add("health period: arrivals in 2025", all(r["arrival_ts"][:4] == "2025" for r in ed))
    add("arrival after date of birth", all(not r["date_of_birth"] or r["arrival_ts"][:10] > r["date_of_birth"] for r in ed))
    add("finance period: transactions 2025-07-01..2025-12-31", all("2025-07-01" <= r["ts"][:10] <= "2025-12-31" for r in tx))
    add("readmit_30d numeric 0/1 or blank", all(r["readmit_30d"] in ("", "0", "1") for r in ed))
    add("H-U7 test code present (P-CRP)", any(r["test_code"] == "P-CRP" for r in labs))
    n_fraud_a = sum(1 for r in tx if r["is_fraud"] == "1" and r["ts"] < "2025-11-01")
    n_fraud_b = sum(1 for r in tx if r["is_fraud"] == "1" and r["ts"] >= "2025-11-01")
    # scorecard readiness: pets-eval task minimums (expected to fail for the tiny smoke profile; reported, not integrity)
    add("FIN-U1 minimum: >=10 frauds before 2025-11-01 and positives after", n_fraud_a >= 10 and n_fraud_b > 0, {"before": n_fraud_a, "after": n_fraud_b}, "readiness")
    add("FIN-U4 minimum: >=50 cards", len(cards) >= 50, {"cards": len(cards)}, "readiness")
    add("H-U7 minimum: >=30 P-CRP results", sum(1 for r in labs if r["test_code"] == "P-CRP") >= 30, {}, "readiness")
    # scenarios + attack specs + adversary/truth files
    scen = {s["id"] for s in read_json(pack / "metadata" / "scenarios.json")}
    add("scenarios HEALTH-S1 and FIN-S2 present", {"HEALTH-S1", "FIN-S2"} <= scen)
    specs = read_json(pack / "metadata" / "attack_specs.json")
    for a in specs["attacks"]:
        f = pack / "adversary" / f"{a['adversary']}.csv"
        t = pack / "truth" / f"adversary__{a['adversary']}.csv"
        hdr = read_header(f) if f.is_file() else []
        needed = {c for q in a["qis"] for c in q["adversary"]}
        add(f"attack {a['adversary']} -> {a['dataset']}/{a['table']}: adversary + truth files, columns",
            f.is_file() and t.is_file() and hdr[:1] == ["adv_row_id"] and needed <= set(hdr), sorted(needed - set(hdr)))
    for ds, tb in SCHEMA:
        add(f"record truth truth/{ds}__{tb}.csv", (pack / "truth" / f"{ds}__{tb}.csv").is_file())
    # spans
    texts = {"health__clinical_notes__note_text": ({r["note_id"]: r["note_text"] for r in notes}),
             "health__ed_visits__chief_complaint": ({r["visit_id"]: r["chief_complaint"] for r in ed})}
    for name, tmap in texts.items():
        errs, n, labels = 0, 0, set()
        with open(pack / "metadata" / "pii_spans" / f"{name}.jsonl", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                n += len(rec["spans"])
                labels |= {s["label"] for s in rec["spans"]}
                errs += len(validate_spans(tmap.get(rec["record_id"], ""), rec["spans"])) + (0 if rec["record_id"] in tmap else 1)
        add(f"PII spans {name}: offsets [start,end), text match, no overlap, known record ids, labels in taxonomy",
            errs == 0 and labels <= SPAN_LABELS, {"spans": n, "errors": errs, "labels": sorted(labels)})
    integ = [c for c in checks if c["kind"] == "integrity"]
    ready = [c for c in checks if c["kind"] == "readiness"]
    return {"checks": checks, "passed": sum(c["ok"] for c in checks), "failed": [c["check"] for c in checks if not c["ok"]],
            "all_ok": all(c["ok"] for c in integ), "integrity_passed": f"{sum(c['ok'] for c in integ)}/{len(integ)}",
            "scorecard_ready": all(c["ok"] for c in ready), "readiness_failed": [c["check"] for c in ready if not c["ok"]]}


def official_baseline(out_json: Path) -> Dict[str, Any]:
    """Run the unchanged official P0 baseline on the OFFICIAL pack; report goes to this run's evidence only."""
    p = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "measure_baseline.py"), "--out", str(out_json)],
                       capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
    rep = read_json(out_json) if out_json.is_file() else {}
    return {"returncode": p.returncode, "report": str(out_json.name), "verdict": rep.get("verdict"),
            "observed": {k: v.get("observed") for k, v in (rep.get("joins") or {}).items()},
            "expected": {k: v.get("expected") for k, v in (rep.get("joins") or {}).items()}}


def main(argv: Optional[Sequence[str]] = None) -> int:
    utf8_stdout()
    p = argparse.ArgumentParser(description="Validate a synthetic test pack (schemas, conventions, spans, metadata)")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--skip-official-baseline", action="store_true")
    a = p.parse_args(argv)
    d = run_dirs(a.run_dir.resolve())
    res = validate(d["pack"])
    if not a.skip_official_baseline:
        res["official_attack_a"] = official_baseline(d["evidence"] / "official_attack_a_baseline.json")
    write_json(d["evidence"] / "validation.json", res)
    print(f"validation: integrity {res['integrity_passed']} | scorecard-ready {res['scorecard_ready']}"
          + (f" (not ready: {res['readiness_failed']})" if res["readiness_failed"] else "")
          + (f"; INTEGRITY FAILED: {[c for c in res['failed'] if c not in res['readiness_failed']]}" if not res["all_ok"] else ""))
    if "official_attack_a" in res:
        print(f"official Attack A on the official pack: {res['official_attack_a']['verdict']} {res['official_attack_a']['observed']}")
    return 0 if res["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
