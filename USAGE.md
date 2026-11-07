# How to use SinceAI

**Start here:** [`INSTRUCTION.md`](INSTRUCTION.md) — attack on raw data, defend,
re-attack, metrics, and troubleshooting.

This file is a short index. Step-by-step script phases: [`scripts/final/STEPS.md`](scripts/final/STEPS.md).

## Layout

| Path | Role |
|---|---|
| `app/` | All Python (protect, attack, gate, demo, OPS-1, …) |
| `scripts/final/` | Shell entry points — call these from the terminal |
| `scripts/material/` | Shared bash helpers (`common.sh`) — sourced, not run |
| `resources/` | Read-only TrustED pack (never edit) |
| `clean_data/` | Protected releases (gitignored) |
| `keys/` | HMAC master key (gitignored) |

Always run from the **repo root**. Python **≥3.10** required.

## Command index

| Goal | Command |
|---|---|
| Verify pack (OPS-1) | `bash scripts/final/ops1_manifest.sh verify` |
| Baseline lock 1622 / 1484 | `bash scripts/final/measure_baseline.sh` |
| Attack raw pack | `bash scripts/final/run_attack_sim.sh --mode shadow --raw-pack` |
| Build protected releases | `bash scripts/final/run_protect.sh --init-key` |
| Shadow attack on `clean_data/` | `bash scripts/final/run_attack_sim.sh --mode shadow` |
| Mosaic gate | `bash scripts/final/mosaic_check.sh` |
| Full release pipeline | `bash scripts/final/run_release.sh` |
| Narrated demo | `bash scripts/final/run_demo.sh` / `--skip-protect` |
| Benchmarks (B1) | `pip install -r requirements-benchmark.txt` then `bash scripts/final/make_benchmark.sh` |
| pets-eval scorecard | `bash scripts/final/run_scorecard.sh` |
| Agent pass (advisory, A2) | `bash scripts/final/run_agents.sh --agents auto --mode shadow` |
| Agent contract self-test | `bash scripts/final/run_agents.sh --selftest` |

Pass-through args go to the Python CLI, e.g. `bash scripts/final/run_protect.sh --init-key --out-root clean_data`.

Do not add Python under `scripts/` — keep that directory shell-only.
