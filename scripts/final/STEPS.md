# SinceAI — step-by-step run guide

These are the user-facing shell entry points. Each one is a thin wrapper around
a module in `app/`, and each sources `../material/common.sh` for the repo-root
resolution and the shared OPS-1 guard. Implementation lives in `app/`; see
[`../../USAGE.md`](../../USAGE.md) for the full command table and
[`../../DEMO.md`](../../DEMO.md) for the five-minute jury walkthrough.

## Prerequisites

- **Always run from the repo root**, never from inside this directory:
  `bash scripts/final/<name>.sh`.
- **The whole project requires Python >=3.10** (`app/python_version.py`'s
  `require_python()` enforces this in every entry point except
  `run_scorecard.py`, which degrades gracefully instead — see below).
  `.python-version` pins `3.13.15`.
- **You do not need to activate this yourself.** `common.sh` picks a
  qualifying interpreter automatically: if ambient `python3` is already
  >=3.10 it's used as-is; otherwise, if the `pyenv` command is reachable
  at all (even without its shims on `PATH` — e.g. in non-interactive
  shells), it resolves this repo's pinned version directly and uses that.
  Its `bin/` directory is also added to `PATH` for that run, so
  `run_scorecard.sh` can find the `pets-eval` console script too. If
  neither is available, scripts fall back to ambient `python3`, and
  `require_python()` then explains exactly what's missing.
- **`run_scorecard.sh` additionally needs the vendored toolkit installed**
  for whichever interpreter gets picked above:
  `pip install -e resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/toolkit`
  (if `common.sh` is resolving a pyenv interpreter for you, install with
  that interpreter explicitly, e.g.
  `~/.pyenv/versions/3.13.15/bin/python3 -m pip install -e resources/.../toolkit`.)
- **Before `make_benchmark.sh`**: `pip install -r requirements-benchmark.txt`.
- **`keys/` is created automatically** by `run_protect.sh --init-key` on the
  first run — no manual setup. `keys/master.key` is gitignored and must never
  be committed.
- Never edit or write under `resources/` — it is the read-only TrustED pack.

## Execution phases

| Phase | Script | Purpose |
|---|---|---|
| P0 | `measure_baseline.sh` | Measure Attack A on the raw pack `data/` and lock the baseline at 1622 (HETU) / 1484 (normalised phone) |
| P1 | `run_protect.sh` | Build the protected releases under `clean_data/`; `--init-key` creates `keys/master.key` if missing |
| P2 | `run_attack_sim.sh` | Re-run Attack A against `clean_data/` (`--mode shadow`) |
| P3a | `mosaic_check.sh` | Deterministic mosaic gate: PASS-1 (cross-release joins 0) + PASS-2 (baseline still reproduces 1622 / 1484 on raw `data/`) |
| P3b | `run_scorecard.sh` | pets-eval per-scenario scorecard + check (needs the toolkit installed) |
| P4 | `make_benchmark.sh` | B1 mosaic-join chart; B2 score chart once scorecards exist (run P3b first) |
| P5 | `ops1_manifest.sh` | OPS-1 pack integrity — `build \| verify \| selftest` against committed `manifests/pack_data_sha256.json` |
| P6 | `run_release.sh` | Full release pipeline: OPS-1 verify → protect → shadow attack-sim → mosaic gate → OPS-1 verify |
| P7 | `run_demo.sh` | Narrated before/after Attack A walkthrough, wrapped in OPS-1 verify on both sides |

## First run from a clean checkout

```bash
# 1. OPS-1 — confirm the vendored pack is intact. Always first.
bash scripts/final/ops1_manifest.sh verify

# 2. Protect — once. Skip this if clean_data/ already exists.
bash scripts/final/run_protect.sh --init-key

# 3. Then whichever you actually need:
bash scripts/final/run_demo.sh --skip-protect   # narrated demo (jury path)
bash scripts/final/run_release.sh               # full release pipeline
bash scripts/final/measure_baseline.sh          # P0 baseline lock only
bash scripts/final/mosaic_check.sh              # P3 gate only
```

Pass-through arguments go straight to the Python CLI:

```bash
bash scripts/final/run_protect.sh --init-key --out-root clean_data
bash scripts/final/ops1_manifest.sh build|verify|selftest
bash scripts/final/run_attack_sim.sh --mode shadow
```

## Dependencies between phases

- `run_protect.sh` must have run (or `clean_data/` must already exist) before
  `run_attack_sim.sh`, `mosaic_check.sh`, `run_scorecard.sh` or
  `make_benchmark.sh` can do anything meaningful.
- `make_benchmark.sh` reads `clean_data/mosaic_check.json`, so run
  `mosaic_check.sh` (or `run_release.sh`) before it.
- `run_release.sh` already wraps protect → shadow attack-sim → mosaic gate
  itself, so running it standalone does **not** need a prior manual
  `run_protect.sh`.
- `run_demo.sh --skip-protect` assumes `clean_data/` already exists; drop the
  flag to let the demo build it.
- `ops1_manifest.sh verify` runs automatically before and after
  `run_release.sh`, `run_demo.sh` and `make_benchmark.sh` — you do not need to
  call it yourself around those three.

## Expected outcomes

- Baseline / PASS-2: HETU join **1622**, phone join **1484** —
  `VERDICT: PASS  (baseline locked at 1622 / 1484)`
- After protect / PASS-1: both joins **0**
- Mosaic gate and demo: `VERDICT: PASS` (exit 0)
- OPS-1 verify: `verify OK (50 files)` (exit 0)
- `make_benchmark.sh`: writes `benchmarks/B1_mosaic_joins.png` always, plus
  `benchmarks/B2_scores.png` once `run_scorecard.sh` has produced both
  releases' `scorecard.json` (if it hasn't run yet, B2 is skipped with a
  clear message instead of failing).

## Exit codes

- The six plain wrappers (`measure_baseline.sh`, `run_protect.sh`,
  `run_attack_sim.sh`, `mosaic_check.sh`, `run_scorecard.sh`,
  `ops1_manifest.sh`) `exec` their module, so the script's exit code **is** the
  module's exit code.
- `run_release.sh`, `run_demo.sh` and `make_benchmark.sh` run through
  `run_with_ops1_guard` in `../material/common.sh`: if the OPS-1 verify
  **before** the payload fails, the payload never runs and that code is
  returned; if the OPS-1 verify **after** the payload fails, **its** code wins
  over the payload's; otherwise the payload's own exit code is returned.
- `run_scorecard.sh` exits **4** ("unavailable") when pets-eval cannot be used.

## Troubleshooting

- **`ops1_manifest.sh verify` fails** — `resources/` has drifted from the
  committed `manifests/pack_data_sha256.json`. Investigate what changed. Do
  **not** run `ops1_manifest.sh build` just to make verify pass; that
  overwrites the committed evidence.
- **`run_scorecard.sh` exits 4 with `pets-eval unavailable: need Python
  >=3.10 + toolkit install`** — `common.sh` couldn't find a >=3.10
  interpreter (neither ambient `python3` nor `pyenv` resolved one) or the
  toolkit isn't installed for whichever interpreter it did pick. Install
  the toolkit with that exact interpreter (see Prerequisites). A *path*
  or *module-not-found* error instead of this message is a different,
  real problem.
- **Missing `keys/master.key`** — run `bash scripts/final/run_protect.sh
  --init-key` once.
- **`mosaic_check.sh` errors with a missing-CSV hint** — `clean_data/` is not
  built yet; run `bash scripts/final/run_protect.sh --init-key`.
- **`make_benchmark.sh` fails on an import** — `pip install -r
  requirements-benchmark.txt` (matplotlib) first.
- **Paths resolving oddly** — you are probably not in the repo root. `cd` to
  the repo root and re-run with the `scripts/final/` prefix.
