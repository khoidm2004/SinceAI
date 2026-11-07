# How to use SinceAI

Layout:

| Path | Role |
|---|---|
| `app/` | All Python (protect, attack, gate, demo, OPS-1, …) |
| `scripts/final/` | Shell entry points only — call these from the terminal (step-by-step guide: `scripts/final/STEPS.md`) |
| `scripts/material/` | Shared bash helpers sourced by `scripts/final/` (`common.sh`) — never run directly |
| `resources/` | Read-only TrustED pack (never edit) |
| `clean_data/` | Protected releases (gitignored; created by protect) |
| `keys/` | HMAC master key (gitignored) |

Always run commands from the **repo root**. Requires **Python >=3.10**
(`.python-version` pins `3.13.15` via pyenv) — every entry point except
`run_scorecard.sh` enforces this itself and fails fast with a clear
message on an older interpreter. You don't need to activate this
yourself: `scripts/material/common.sh` auto-picks a qualifying
interpreter even if pyenv's shims aren't on `PATH` — see
`scripts/final/STEPS.md` for exactly how.

## Quick start (jury / demo)

```bash
bash scripts/final/ops1_manifest.sh verify
bash scripts/final/run_protect.sh --init-key          # once, if clean_data/ is empty
bash scripts/final/run_demo.sh --skip-protect         # narrated Attack A before → after
```

Or open [`DEMO.md`](DEMO.md) for the five-minute walkthrough.

## Everyday commands

| Goal | Command |
|---|---|
| Verify pack integrity (OPS-1) | `bash scripts/final/ops1_manifest.sh verify` |
| Lock baseline 1622 / 1484 | `bash scripts/final/measure_baseline.sh` |
| Build protected releases | `bash scripts/final/run_protect.sh --init-key` |
| Shadow attack-sim on `clean_data/` | `bash scripts/final/run_attack_sim.sh --mode shadow` |
| Mosaic gate (PASS-1 + PASS-2) | `bash scripts/final/mosaic_check.sh` |
| Full release pipeline | `bash scripts/final/run_release.sh` |
| Narrated demo | `bash scripts/final/run_demo.sh` / `--skip-protect` |
| Benchmarks (B1 chart) | `pip install -r requirements-benchmark.txt` then `bash scripts/final/make_benchmark.sh` |
| pets-eval scorecard | `bash scripts/final/run_scorecard.sh` (needs the toolkit installed: `pip install -e resources/.../toolkit`) |

Pass-through args go to the Python CLI, e.g.:

```bash
bash scripts/final/run_protect.sh --init-key --out-root clean_data
bash scripts/final/ops1_manifest.sh build|verify|selftest
```

## Calling Python directly

Shell wrappers are preferred. If you need the module itself:

```bash
python3 app/run_demo.py --skip-protect
python3 app/mosaic_check.py
```

Do not put new Python under `scripts/` — keep that directory shell-only.

## Expected outcomes

- Baseline / PASS-2: HETU join **1622**, phone join **1484**
- After protect / PASS-1: both joins **0**
- Mosaic gate and demo: `VERDICT: PASS` (exit 0)
- OPS-1 verify: `verify OK` (exit 0)
