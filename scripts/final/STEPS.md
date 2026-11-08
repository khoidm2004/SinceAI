# Mosaic — step-by-step run guide

These are the user-facing shell entry points. Each one is a thin wrapper around
a module in `app/`, and each sources `../material/common.sh` for the repo-root
resolution and the shared OPS-1 guard. Implementation lives in `app/`; see
[`../../INSTRUCTION.md`](../../INSTRUCTION.md) for the attack → defend → measure
runbook and [`../../README.md`](../../README.md) for behaviour / agent overview.

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
| P2 | `run_attack_sim.sh` | Attack-sim shadow mode: `--raw-pack` on pack `data/` (baseline joins) or default on `clean_data/` (expects 0/0) |
| P3a | `mosaic_check.sh` | Deterministic mosaic gate: PASS-1 (cross-release joins 0) + PASS-2 (baseline still reproduces 1622 / 1484 on raw `data/`) |
| P3b | `run_scorecard.sh` | pets-eval per-scenario scorecard + check (needs the toolkit installed) |
| P4 | `make_benchmark.sh` | B1 mosaic-join chart; B2 score chart once scorecards exist (run P3b first) |
| P5 | `ops1_manifest.sh` | OPS-1 pack integrity — `build \| verify \| selftest` against committed `manifests/pack_data_sha256.json` |
| P6 | `run_release.sh` | Full release pipeline: OPS-1 verify → attack raw → protect → re-attack protected → mosaic gate → analyze HTML (`analyze/no_AI/`) → OPS-1 verify |
| P7 | `run_demo.sh` | Narrated before/after Attack A walkthrough, wrapped in OPS-1 verify on both sides |
| P8 | `run_agents.sh` | Advisory multi-agent pass (Groq). Off unless `GROQ_API_KEY` is set or `--llm-stub` is passed; never gates a release and never writes `clean_data/` |
| Analyze | `run_analyze.sh` | Build analyze HTML (demo-row raw↔protected, joins, scorecards). Default `--out-dir analyze/`; `run_release.sh` writes `analyze/no_AI/`. Compare notes: `analyze/Analyze.md` |

## First run from a clean checkout

```bash
# 1. OPS-1 — confirm the vendored pack is intact. Always first.
bash scripts/final/ops1_manifest.sh verify

# 2. See the attack succeed on raw data (1622 / 1484).
bash scripts/final/measure_baseline.sh
bash scripts/final/run_attack_sim.sh --mode shadow --raw-pack

# 3. Defend — once (or again after pipeline changes).
bash scripts/final/run_protect.sh --init-key

# 4. Then whichever you actually need:
bash scripts/final/run_demo.sh --skip-protect   # narrated demo (jury path)
bash scripts/final/run_release.sh               # full release pipeline (steps 2–4 automated)
bash scripts/final/mosaic_check.sh              # P3 gate only
```

See [`../../INSTRUCTION.md`](../../INSTRUCTION.md) for FIN-S2 expected columns (17→15,
drop names/addresses, tokenise glue).

Pass-through arguments go straight to the Python CLI:

```bash
bash scripts/final/run_protect.sh --init-key --out-root clean_data
bash scripts/final/ops1_manifest.sh build|verify|selftest
bash scripts/final/run_attack_sim.sh --mode shadow
```

## Dependencies between phases

- `run_attack_sim.sh --raw-pack` needs only the vendored pack under `resources/`.
- Protected-path tools need `clean_data/`: run `run_protect.sh` first for shadow attack
  on `clean_data/`, `mosaic_check.sh`, `run_scorecard.sh`, and `make_benchmark.sh`.
- `make_benchmark.sh` reads `clean_data/mosaic_check.json`, so run
  `mosaic_check.sh` (or `run_release.sh`) before it.
- `run_release.sh` runs raw attack → protect → protected attack → mosaic gate →
  analyze HTML (`analyze/no_AI/`) itself;
  you do not need a prior manual protect unless you are running the demo with
  `--skip-protect`.
- `run_demo.sh --skip-protect` assumes `clean_data/` already exists; drop the
  flag to let the demo build it.
- `ops1_manifest.sh verify` runs automatically before and after
  `run_release.sh`, `run_demo.sh` and `make_benchmark.sh` — you do not need to
  call it yourself around those three.

## Expected outcomes

- **STEP 1 / raw attack** (`measure_baseline.sh` or `run_attack_sim.sh --raw-pack`):
  HETU join **1622**, phone join **1484**
- Baseline / PASS-2: same **1622 / 1484** on raw `data/` inside the mosaic gate
- **STEP 3 / protected attack** and PASS-1: both joins **0**
- FIN-S2 protect summary: **17→15** columns; dropped `full_name`, `street_address`;
  tokenised `email`, `hetu`, `iban`, `phone`
- Mosaic gate and demo: `VERDICT: PASS` (exit 0)
- OPS-1 verify: `verify OK (50 files)` (exit 0)
- `make_benchmark.sh`: writes `benchmarks/B1_mosaic_joins.png` always, plus
  `benchmarks/B2_scores.png` once `run_scorecard.sh` has produced both
  releases' `scorecard.json` (if it hasn't run yet, B2 is skipped with a
  clear message instead of failing).
- `run_agents.sh --selftest`: `SELFTEST: PASS` (exit 0); `--agents off` and
  `--agents on --llm-stub` both exit 0 and leave `clean_data/mosaic_check.json`
  unchanged.

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
