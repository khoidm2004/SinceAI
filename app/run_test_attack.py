#!/usr/bin/env python3
"""Custom cross-domain attack (Attack A logic) on a synthetic test pack: raw and protected.

Uses the repository's own join code and normalisation (app/attack_sim.simulate_attack,
app/normalize.normalize_hetu / normalize_phone). The expected raw overlap is computed dynamically from the
generated files and checked against the generator manifest and the private ground truth. The official
Attack A constants (measure_baseline.EXPECTED_HETU = 1622, EXPECTED_PHONE = 1484) are NOT used for this pack
and are not modified; they are only read to prove they are unchanged.

A join is MEASURED only when both columns exist. If a column is missing the result is NOT_MEASURED - a zero
caused by a missing column is never reported as protection.
"""
from __future__ import annotations

from python_version import require_python

require_python()
import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure_baseline  # noqa: E402  (read-only: official constants)
from attack_sim import simulate_attack  # noqa: E402
from normalize import HETU_RECIPE, PHONE_RECIPE, normalize_hetu, normalize_phone  # noqa: E402
from synth_common import peak_memory_bytes, read_csv, read_header, read_json, run_dirs, utf8_stdout, write_json  # noqa: E402

COLUMNS = {"health_hetu_col": "patient_hetu", "finance_hetu_col": "hetu", "health_phone_col": "phone", "finance_phone_col": "phone"}
OFFICIAL_ATTACK_A = {"EXPECTED_HETU": 1622, "EXPECTED_PHONE": 1484}


def _truth(path: Path) -> Dict[str, str]:
    return {r["record_id"]: r["person_id"] for r in read_csv(path)[0]} if path.is_file() else {}


def attack(health_csv: Path, finance_csv: Path, *, truth_dir: Optional[Path] = None, label: str = "") -> Dict[str, Any]:
    t0 = time.perf_counter()
    h_hdr, f_hdr = read_header(health_csv), read_header(finance_csv)
    res = simulate_attack(health_csv, finance_csv, sample_limit=0, **COLUMNS)  # repository join code (no samples kept)
    out: Dict[str, Any] = {"label": label, "health_csv": str(health_csv), "finance_csv": str(finance_csv),
                           "normalisation": {"hetu": HETU_RECIPE, "phone": PHONE_RECIPE}, "keys": {}}
    h_rows = f_rows = None
    for key, hcol, fcol, norm in (("hetu", COLUMNS["health_hetu_col"], COLUMNS["finance_hetu_col"], normalize_hetu),
                                  ("phone", COLUMNS["health_phone_col"], COLUMNS["finance_phone_col"], normalize_phone)):
        present = {"health": hcol in h_hdr, "finance": fcol in f_hdr}
        entry: Dict[str, Any] = {"health_column": hcol, "finance_column": fcol, "columns_present": present}
        if not all(present.values()):
            entry.update(status="NOT_MEASURED", join=None,
                         why="column missing on " + ", ".join(k for k, v in present.items() if not v) + "; a zero here would not be evidence of protection")
            out["keys"][key] = entry
            continue
        join = int(res[f"{key}_join"])
        entry.update(status="MEASURED", join=join)
        if truth_dir is not None:  # ground truth: do the joined values belong to the same synthetic person?
            if h_rows is None:
                h_rows, f_rows = read_csv(health_csv)[0], read_csv(finance_csv)[0]
            th, tf = _truth(truth_dir / "health__ed_visits.csv"), _truth(truth_dir / "finance__customers.csv")
            hv: Dict[str, set] = {}
            for r in h_rows:
                v = norm(r.get(hcol))
                if v:
                    hv.setdefault(v, set()).add(th.get(r.get("visit_id", ""), ""))
            fv: Dict[str, set] = {}
            for r in f_rows:
                v = norm(r.get(fcol))
                if v:
                    fv.setdefault(v, set()).add(tf.get(r.get("customer_id", ""), ""))
            common = hv.keys() & fv.keys()
            same = sum(1 for k in common if (hv[k] & fv[k]) - {""})
            entry.update(true_person_links=same, false_links=len(common) - same,
                         distinct_values={"health": len(hv), "finance": len(fv)})
        out["keys"][key] = entry
    out["seconds"] = round(time.perf_counter() - t0, 3)
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    utf8_stdout()
    p = argparse.ArgumentParser(description="Raw and protected cross-domain attack on a synthetic test pack")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--policy", choices=["current", "relational", "both"], default="both")
    a = p.parse_args(argv)
    d = run_dirs(a.run_dir.resolve())
    man = read_json(d["evidence"] / "manifest.json")
    truth = d["pack"] / "truth"
    raw = attack(d["pack"] / "data" / "health" / "ed_visits.csv", d["pack"] / "data" / "finance" / "customers.csv", truth_dir=truth, label="raw")
    shared = man["population"]["shared_subjects"]
    raw["consistency"] = {
        "manifest_hetu_overlap": man["overlaps"]["hetu_overlap"], "manifest_phone_overlap": man["overlaps"]["phone_overlap_normalised"],
        "hetu_matches_manifest": raw["keys"]["hetu"]["join"] == man["overlaps"]["hetu_overlap"],
        "phone_matches_manifest": raw["keys"]["phone"]["join"] == man["overlaps"]["phone_overlap_normalised"],
        "ground_truth_shared_subjects": shared,
        "hetu_recall_of_shared_subjects": round(raw["keys"]["hetu"]["true_person_links"] / max(1, shared), 4),
        "phone_recall_of_shared_subjects": round(raw["keys"]["phone"]["true_person_links"] / max(1, shared), 4),
    }
    raw["official_attack_a_constants_unchanged"] = {
        "EXPECTED_HETU": measure_baseline.EXPECTED_HETU, "EXPECTED_PHONE": measure_baseline.EXPECTED_PHONE,
        "unchanged": measure_baseline.EXPECTED_HETU == OFFICIAL_ATTACK_A["EXPECTED_HETU"] and measure_baseline.EXPECTED_PHONE == OFFICIAL_ATTACK_A["EXPECTED_PHONE"],
        "used_for_this_pack": False}
    raw["peak_memory_bytes"] = peak_memory_bytes()
    write_json(d["evidence"] / "attack_raw.json", raw)
    print(f"RAW  HETU join {raw['keys']['hetu']['join']} (true links {raw['keys']['hetu']['true_person_links']}, false {raw['keys']['hetu']['false_links']})"
          f" | phone join {raw['keys']['phone']['join']} (true {raw['keys']['phone']['true_person_links']}, false {raw['keys']['phone']['false_links']})"
          f" | manifest match {raw['consistency']['hetu_matches_manifest']}/{raw['consistency']['phone_matches_manifest']}")
    prot: Dict[str, Any] = {}
    for pol in (["current", "relational"] if a.policy == "both" else [a.policy]):
        base = d["protected"] / pol
        r = attack(base / "health__HEALTH-S1" / "ed_visits.csv", base / "finance__FIN-S2" / "customers.csv", label=f"protected:{pol}")
        for key in ("hetu", "phone"):
            e = r["keys"][key]
            if e["status"] == "MEASURED":
                e["verdict"] = "PROTECTED (transformed values do not join)" if e["join"] == 0 else f"LEAK ({e['join']} values still join)"
            else:
                e["verdict"] = "NOT_MEASURED (column dropped - not counted as protection)"
        prot[pol] = r
        print(f"PROT [{pol}] HETU: {r['keys']['hetu']['status']} join={r['keys']['hetu']['join']} -> {r['keys']['hetu']['verdict']}"
              f" | phone: {r['keys']['phone']['status']} join={r['keys']['phone']['join']} -> {r['keys']['phone']['verdict']}")
    write_json(d["evidence"] / "attack_protected.json", prot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
