#!/usr/bin/env python3
"""Custom synthetic Health + Finance demo: generate -> validate -> protect -> attack -> pets-eval -> report.

Separate from the official P7 demo (app/run_demo.py), whose defaults and expected values are untouched.
Every step is one of the test-pack CLIs, run as a subprocess so each stage is timed on its own; all output goes
into a new run directory under test_data/generated/<run_id>/ (never resources/, clean_data/ or keys/).

  uv run --no-sync python app/run_synthetic_demo.py --profile demo --people 2500 --seed 20261107 [--bench] [--tests]
  uv run --no-sync python app/run_synthetic_demo.py --run-dir <existing run> --narrate-only

The narration prints aggregates only (counts, columns, statuses, scores) - never a raw value.
"""
from __future__ import annotations

from python_version import require_python

require_python()
import argparse
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from synth_common import DEFAULT_GENERATED_ROOT, REPO_ROOT, list_files, read_json, refuse_forbidden, run_dirs, stats, utf8_stdout, write_json  # noqa: E402

APP = Path(__file__).resolve().parent
ENV = {k: v for k, v in os.environ.items() if k != "PETS_ROOT"}
ENV.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")


def step(name: str, args: List[str], quiet: bool = False) -> Dict[str, Any]:
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, str(APP / args[0]), *args[1:]], env=ENV, capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT))
    secs = round(time.perf_counter() - t0, 3)
    if not quiet:
        print(f"\n--- {name} ({secs} s, exit {p.returncode})")
        print("\n".join("  " + ln for ln in p.stdout.strip().splitlines()[-24:]))
    if p.returncode not in (0,) and p.stderr.strip():
        print("  stderr: " + " | ".join(p.stderr.strip().splitlines()[-3:]), file=sys.stderr)
    return {"name": name, "seconds": secs, "returncode": p.returncode, "stdout": p.stdout}


def pipeline(run_root: Path, run_id: str, profile: str, people: int, seed: int, quiet: bool = False, policies: str = "both",
             scorecards: bool = True, validate: bool = True) -> Dict[str, Any]:
    run = run_root / run_id
    steps = [step("1. generate synthetic population and tables", ["generate_test_data.py", "--profile", profile, "--people", str(people), "--seed", str(seed),
                                                                  "--out-root", str(run_root), "--run-id", run_id], quiet)]
    if steps[-1]["returncode"]:
        raise SystemExit("generation failed")
    if validate:
        steps.append(step("2. validate against official metadata + official Attack A baseline", ["validate_test_pack.py", "--run-dir", str(run)], quiet))
    steps.append(step("3. protect all scenario tables with the existing PET pipeline", ["run_test_pack.py", "--run-dir", str(run), "--init-key", "--policy", policies], quiet))
    steps.append(step("4. raw and protected cross-domain attack", ["run_test_attack.py", "--run-dir", str(run), "--policy", policies], quiet))
    if scorecards:
        steps.append(step("5. pets-eval scorecard + check", ["run_test_scorecards.py", "--run-dir", str(run), "--policy", policies], quiet))
    return {"run": run, "steps": steps}


def narrate(run: Path) -> None:
    d = run_dirs(run)
    ev = d["evidence"]
    m = read_json(ev / "manifest.json")
    ar = read_json(ev / "attack_raw.json")
    ap = read_json(ev / "attack_protected.json")
    print("\n================ SYNTHETIC HEALTH + FINANCE DEMO ================")
    print(f"Run {run.name}: {m['generator_version']}, seed {m['seed']}, {m['population']['size']:,} fictional people")
    print(f"\nStep 1 - two 'safe-looking' releases from one population: {m['population']['health_subjects']:,} ED patients, "
          f"{m['population']['finance_customers']:,} bank customers, {m['population']['shared_subjects']:,} people in both (ground truth).")
    print("\nStep 2 - attack on the unprotected tables (repository join code, app/attack_sim.py):")
    for k in ("hetu", "phone"):
        e = ar["keys"][k]
        print(f"  {k.upper():5} ed_visits.{e['health_column']} x customers.{e['finance_column']}: {e['join']:,} people joined "
              f"({e['true_person_links']:,} true links, {e['false_links']} false) - expected from manifest {ar['consistency'][f'manifest_{k}_overlap']:,}")
    print(f"  official Attack A constants untouched: {ar['official_attack_a_constants_unchanged']['EXPECTED_HETU']}/{ar['official_attack_a_constants_unchanged']['EXPECTED_PHONE']}"
          f" (not used for this pack)")
    for pol in ap:
        pe = read_json(ev / f"protection_{pol}.json")
        print(f"\nStep 3 - PET pipeline, policy '{pol}': {pe['description']}")
        for sid, r in pe["releases"].items():
            for t, tr in r["tables"].items():
                tok = tr["actions"]["tokenised"]
                print(f"  {sid} {t}: {tr['rows_in']:,} rows kept; columns {tr['columns_in']}->{tr['columns_out']}; dropped {tr['dropped'] or 'none'}; "
                      f"tokenised {tok or 'none'}; generalised {tr['actions']['generalised'] or 'none'}")
            for j in r["relationships"]:
                print(f"    join {j['child']} -> {j['parent']}: {j['status']}")
        print(f"  Step 4 - same attack on the protected releases ({pol}):")
        for k in ("hetu", "phone"):
            e = ap[pol]["keys"][k]
            print(f"    {k.upper():5} {e['status']}: join={e['join']} -> {e['verdict']}")
    if (ev / "scorecards.json").is_file():
        sc = read_json(ev / "scorecards.json")
        print("\nStep 5 - official pets-eval scorecards on the synthetic pack:")
        for key, r in sc.items():
            s = r.get("summary") or {}
            print(f"  {key}: privacy {s.get('privacy')}, utility {s.get('utility')}, composite {s.get('composite')} (bound to files: {r.get('binding_ok')})")
            for u in r["utility"]:
                state = f"{u['score']:.3f}" if u["answerable"] else "NOT ANSWERABLE (" + "; ".join(u["missing"] or []) + ")"
                print(f"     {u['id']}: {state} [{u['sanity']['flag']}]")
    print("\nWhat this demo does NOT claim: anonymity; protection of free text; k-anonymity (k<5 shares are reported as measured);"
          " results on the organisers' hidden attackers.")


def benchmark(run: Path, sizes: Sequence[int], reps: int, seed: int) -> Dict[str, Any]:
    root = run / "benchmark_runs"
    out: Dict[str, Any] = {"machine": f"{platform.platform()}, {os.cpu_count()} logical CPUs, Python {platform.python_version()}",
                           "repetitions": reps, "seed": seed, "sizes": []}
    for n in sizes:
        per: Dict[str, List[float]] = {k: [] for k in ("generate", "protect", "attack", "scorecards", "total")}
        mem: Dict[str, List[Optional[float]]] = {"generate": [], "protect": []}
        rates, prot_bytes, rows_p = [], 0, 0
        for i in range(1, reps + 1):
            res = pipeline(root, f"n{n}-r{i}", "bench", n, seed, quiet=True, policies="both", scorecards=True, validate=False)
            st = {s["name"].split(".")[0]: s for s in res["steps"]}
            per["generate"].append(st["1"]["seconds"])
            per["protect"].append(st["3"]["seconds"])
            per["attack"].append(st["4"]["seconds"])
            per["scorecards"].append(st["5"]["seconds"])
            per["total"].append(sum(s["seconds"] for s in res["steps"]))
            rd = run_dirs(res["run"])
            m = read_json(rd["evidence"] / "manifest.json")
            mem["generate"].append((m["runtime"]["peak_memory_bytes"] or 0) / 1e6 or None)
            pr = read_json(rd["evidence"] / "protection_relational.json")
            mem["protect"].append((pr.get("peak_memory_bytes") or 0) / 1e6 or None)
            rows_p = pr["rows_processed"]
            rates.append(rows_p / pr["seconds"])
            prot_bytes = sum(f.stat().st_size for f in list_files(rd["protected"] / "relational"))
            print(f"  bench n={n} rep {i}: total {per['total'][-1]:.1f} s")
        out["sizes"].append({"people": n, "rows_protected": rows_p, "stages": {k: stats(v) for k, v in per.items()},
                             "protect_rows_per_s": stats(rates), "protected_bytes": prot_bytes,
                             "peak_mb": {k: stats([round(x, 1) for x in v if x]) for k, v in mem.items()}})
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    utf8_stdout()
    p = argparse.ArgumentParser(description="End-to-end synthetic Health + Finance demo (separate from the official P7 demo)")
    p.add_argument("--profile", default="demo", choices=["smoke", "demo", "bench"])
    p.add_argument("--people", type=int, default=2500)
    p.add_argument("--seed", type=int, default=20261107)
    p.add_argument("--out-root", type=Path, default=DEFAULT_GENERATED_ROOT)
    p.add_argument("--run-dir", type=Path, default=None, help="narrate an existing run (with --narrate-only)")
    p.add_argument("--narrate-only", action="store_true")
    p.add_argument("--bench", action="store_true", help="also run the benchmark profile (sizes x repetitions)")
    p.add_argument("--bench-sizes", default="500,1000,2500")
    p.add_argument("--bench-reps", type=int, default=3)
    p.add_argument("--tests", action="store_true", help="run the pytest suite and attach the result to the report")
    a = p.parse_args(argv)
    if a.narrate_only:
        narrate(a.run_dir.resolve())
        return 0
    root = a.out_root if a.out_root.is_absolute() else REPO_ROOT / a.out_root
    refuse_forbidden(root, "generated runs")
    run_id = f"{a.profile}-n{a.people}-s{a.seed}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    t0 = time.perf_counter()
    res = pipeline(root, run_id, a.profile, a.people, a.seed)
    run = res["run"]
    if a.bench:
        print("\n--- 6. benchmark")
        write_json(run_dirs(run)["evidence"] / "benchmark.json", benchmark(run, [int(x) for x in a.bench_sizes.split(",")], a.bench_reps, a.seed))
    if a.tests:
        tp = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], env=ENV, capture_output=True, text=True,
                            encoding="utf-8", cwd=str(REPO_ROOT))
        write_json(run_dirs(run)["evidence"] / "tests.json", {"returncode": tp.returncode, "summary": (tp.stdout.strip().splitlines() or [""])[-1]})
        print(f"\n--- tests: {(tp.stdout.strip().splitlines() or [''])[-1]}")
    write_json(run_dirs(run)["evidence"] / "run_steps.json", {"steps": [{k: v for k, v in s.items() if k != "stdout"} for s in res["steps"]],
                                                               "total_seconds": round(time.perf_counter() - t0, 3)})
    step("7. HTML / JSON / methodology report", ["report_test_pack.py", "--run-dir", str(run)])
    narrate(run)
    print(f"\nrun directory: {run}\nreport: {run / 'reports' / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
