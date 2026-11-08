#!/usr/bin/env python3
"""Run the official pets-eval toolkit (scorecard + check) on a synthetic test pack's protected releases.

Uses the locally installed pets-eval CLI (`python -m pets_eval`) unchanged. The scorer resolves metadata,
adversary, truth and span files from the synthetic pack via an explicit --root (PETS_ROOT is removed from the
child environment so it can never fall back to the official pack). Row maps are passed explicitly with
--rowmap table=path from <run>/private/rowmaps/ - they are never placed next to the release.

Verification: the scorecard's recorded original/protected paths, the released tables and row counts must match
the exact files scored, and the protected CSV hashes must be unchanged by scoring. Every utility task is listed
with its real status; a None score is reported as "not answerable" (never as 0) together with the toolkit's own
`detail.missing` explanation. This is a protected-release comparison (row maps present), not a DCR/MIA evaluation
of a synthetic-data generator.
"""
from __future__ import annotations

from python_version import require_python

require_python()
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from synth_common import RELEASE_TABLES, read_csv, refuse_forbidden, run_dirs, sha256_file, utf8_stdout, write_json  # noqa: E402

CHILD_ENV = {k: v for k, v in os.environ.items() if k != "PETS_ROOT"}
CHILD_ENV.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")


def _run(cmd, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), env=CHILD_ENV, capture_output=True, text=True, encoding="utf-8")


_SANITY_CACHE: Dict[str, Any] = {}


def _h_u7_groups(pack: Path) -> Dict[str, Any]:
    """Original-data check for H-U7's group term, using the toolkit's own derivation (pets_eval.utility.health)."""
    if "h_u7" not in _SANITY_CACHE:
        import pandas as pd
        from pets_eval.utility import health as H
        ed = pd.read_csv(pack / "data" / "health" / "ed_visits.csv", dtype=str, keep_default_na=False)
        lab = pd.read_csv(pack / "data" / "health" / "lab_results.csv", dtype=str, keep_default_na=False)
        dv = H.derive(ed)
        crp = lab[lab["test_code"] == "P-CRP"].copy()
        crp["crp"] = pd.to_numeric(crp["value"].str.replace("<", "", regex=False), errors="coerce")
        j = crp.merge(dv[["visit_id", "temp_c", "diagnosis_group"]], on="visit_id")
        j = j[(j["temp_c"] > 34) & (j["temp_c"] < 42.5) & j["crp"].notna()]
        counts = j.groupby("diagnosis_group").size()
        _SANITY_CACHE["h_u7"] = {"joined_rows_original": int(len(j)), "groups_with_30_rows": int((counts >= 30).sum()),
                                 "groups": {k: int(v) for k, v in counts.sort_values(ascending=False).items()}}
    return _SANITY_CACHE["h_u7"]


def task_sanity(u: Dict[str, Any], d: Dict[str, Path], dataset: str) -> Dict[str, Any]:
    """Flag scores that pets-eval clamps or that come from a degenerate (NaN) term - so a 1.0 is never misread."""
    det = u.get("detail") if isinstance(u.get("detail"), dict) else {}
    if u["id"] == "FIN-U1" and u.get("score") is not None:
        ap_p, ap_o = det.get("ap_protected"), det.get("ap_original")
        if ap_o is None or ap_o != ap_o:
            return {"flag": "DEGENERATE", "why": "AP on original is NaN (too few frauds): pets-eval then returns 1.0"}
        if ap_p is not None and ap_p > ap_o:
            return {"flag": "CAPPED", "why": f"protected-trained model AP {ap_p:.3f} > original-trained AP {ap_o:.3f}; score = min(1, ratio) "
                    "is capped at 1.0. Read as 'no measured loss', not as equal models; synthetic fraud may be easier to separate than real fraud."}
    if u["id"] == "H-U7" and u.get("score") is not None:
        g = _h_u7_groups(d["pack"])
        if g["groups_with_30_rows"] == 0:
            return {"flag": "DEGENERATE", "why": "no diagnosis group has >=30 joined CRP rows: the group term is NaN and pets-eval returns 1.0", **g}
        return {"flag": "OK", "why": f"{g['groups_with_30_rows']} diagnosis groups have >=30 joined CRP rows; both score terms measured", **g}
    if u.get("score") is None:
        return {"flag": "NOT_ANSWERABLE", "why": "required inputs missing in the protected release (see 'missing')"}
    return {"flag": "OK", "why": ""}


def score_release(d: Dict[str, Path], policy: str, sid: str) -> Dict[str, Any]:
    dataset, tables = RELEASE_TABLES[sid]
    rel = f"{dataset}__{sid}"
    prot = d["protected"] / policy / rel
    rm_dir = d["private"] / "rowmaps" / policy / rel
    out = d["evidence"] / "scorecards" / policy / rel
    refuse_forbidden(out, "scorecard output")
    out.mkdir(parents=True, exist_ok=True)
    before = {p.name: sha256_file(p) for p in sorted(prot.glob("*.csv"))}
    cmd = [sys.executable, "-m", "pets_eval", "scorecard", "--root", str(d["pack"]), "--original", str(d["pack"] / "data" / dataset),
           "--protected", str(prot), "--scenario", sid, "--out", str(out)]
    for t, _ in tables:
        cmd += ["--rowmap", f"{t}={rm_dir / f'rowmap_{t}.csv'}"]
    t0 = time.perf_counter()
    sc_proc = _run(cmd, d["run"])
    sc_secs = round(time.perf_counter() - t0, 3)
    t0 = time.perf_counter()
    ck_proc = _run([sys.executable, "-m", "pets_eval", "check", str(prot), "--out", str(out / "check.json")], d["run"])
    ck_secs = round(time.perf_counter() - t0, 3)
    after = {p.name: sha256_file(p) for p in sorted(prot.glob("*.csv"))}
    res: Dict[str, Any] = {"policy": policy, "scenario": sid, "command": " ".join(Path(c).name if os.sep in c or "/" in c else c for c in cmd),
                           "scorecard_returncode": sc_proc.returncode, "scorecard_seconds": sc_secs, "check_returncode": ck_proc.returncode,
                           "check_seconds": ck_secs, "protected_csv_sha256": before, "csv_unchanged_by_scoring": before == after}
    if sc_proc.returncode != 0:
        res["error_tail"] = sc_proc.stderr.strip().splitlines()[-3:]
    scj = out / "scorecard.json"
    if scj.is_file():
        sc = json.loads(scj.read_text(encoding="utf-8"))
        res["scorecard_sha256"] = sha256_file(scj)
        binding = []
        if Path(sc.get("protected", "")).resolve() != prot.resolve():
            binding.append("scorecard 'protected' path differs from the scored folder")
        if Path(sc.get("original", "")).resolve() != (d["pack"] / "data" / dataset).resolve():
            binding.append("scorecard 'original' path is not the synthetic pack")
        tables_out = {}
        for t, info in sc.get("tables", {}).items():
            entry = {"status": info.get("status"), "rows_original": info.get("rows_original"), "rows_protected": info.get("rows_protected"),
                     "columns_dropped": info.get("columns_dropped"), "risks": info.get("risks", {}),
                     "direct_identifiers_retained": info.get("direct_identifiers_retained"),
                     "k_anonymity": {k: (info.get("k_anonymity") or {}).get(k) for k in ("qis", "n", "n_classes", "min_k", "median_k", "share_below", "sample_uniqueness")} if info.get("k_anonymity") else None,
                     "linkage": {a: {k: v.get(k) for k in ("evaluated", "reason", "note", "qis_used", "n_targets_in_data", "reidentification_rate",
                                                            "claim_precision", "baseline_reidentification_rate_original")} if isinstance(v, dict) else v
                                 for a, v in (info.get("linkage") or {}).items()},
                     "free_text": info.get("free_text"), "hash_attack": {c: {k: v.get(k) for k in ("share_values_reversed",)} for c, v in (info.get("hash_attack") or {}).items()},
                     "regex_residuals": info.get("regex_residuals")}
            if info.get("status") == "released" and (prot / f"{t}.csv").is_file():
                n = len(read_csv(prot / f"{t}.csv")[0])
                if info.get("rows_protected") != n:
                    binding.append(f"{t}: rows_protected {info.get('rows_protected')} != file rows {n}")
            tables_out[t] = entry
        res.update(summary=sc.get("summary"), risk_components=sc.get("risk_components"), tables=tables_out, binding_problems=binding,
                   binding_ok=not binding and res["csv_unchanged_by_scoring"],
                   utility=[{"id": u["id"], "table": u.get("table"), "kind": u.get("kind"), "description": u.get("description"), "required": u.get("required"),
                             "score": u.get("score"), "metric": u.get("metric"), "answerable": u.get("score") is not None,
                             "missing": (u.get("detail") or {}).get("missing") if isinstance(u.get("detail"), dict) else None,
                             "detail": u.get("detail") if isinstance(u.get("detail"), dict) else None,  # aggregates only
                             "sanity": task_sanity(u, d, dataset)} for u in sc.get("utility", [])],
                   extra_protected_files=sc.get("extra_protected_files"), tool=sc.get("tool"))
    ck = out / "check.json"
    if ck.is_file():
        c = json.loads(ck.read_text(encoding="utf-8"))
        res["check"] = {"files_scanned": c.get("n_files_scanned"), "totals": c.get("totals"),
                        "per_file": {Path(k).name: v for k, v in (c.get("files") or {}).items() if v}}  # masked examples not kept
    return res


def main(argv: Optional[Sequence[str]] = None) -> int:
    utf8_stdout()
    p = argparse.ArgumentParser(description="pets-eval scorecard + check for a synthetic test pack")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--policy", choices=["current", "relational", "both"], default="both")
    a = p.parse_args(argv)
    d = run_dirs(a.run_dir.resolve())
    if _run([sys.executable, "-c", "import pets_eval"], d["run"]).returncode != 0:
        write_json(d["evidence"] / "scorecards.json", {"status": "BLOCKED", "reason": "pets-eval not importable in this interpreter; "
                                                       "install with scripts/final/install_pets_eval.sh (builds from a temp copy)"})
        print("BLOCKED: pets-eval is not installed in this environment", file=sys.stderr)
        return 3
    results: Dict[str, Any] = {}
    for pol in (["current", "relational"] if a.policy == "both" else [a.policy]):
        for sid in RELEASE_TABLES:
            r = score_release(d, pol, sid)
            results[f"{pol}/{sid}"] = r
            s = r.get("summary") or {}
            print(f"[{pol}] {sid}: rc={r['scorecard_returncode']} privacy={s.get('privacy')} utility={s.get('utility')} composite={s.get('composite')} "
                  f"bound={r.get('binding_ok')} {r['scorecard_seconds']}s")
            for u in r.get("utility", []):
                print(f"     {u['id']}: {'%.4f' % u['score'] if u['answerable'] else 'NOT ANSWERABLE'} [{u['sanity']['flag']}]"
                      + ("" if u["answerable"] else f"  missing={u['missing']}"))
    write_json(d["evidence"] / "scorecards.json", results)
    return 0 if all(r["scorecard_returncode"] == 0 for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
