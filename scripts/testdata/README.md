# Synthetic test-pack entry points

This directory mirrors the attack -> defend -> gate -> metrics story of `INSTRUCTION.md`, but runs entirely on
`test_data/generated/<run_id>/`. The official pipeline under `scripts/final/`, `resources/`, `clean_data/` and `keys/`
is never touched or overwritten.

## Quick start (Git Bash, from repo root)

```bash
bash scripts/testdata/run_testdata.sh release
bash scripts/testdata/run_testdata.sh demo
```

## PowerShell (via Git Bash)

```powershell
& "C:\Program Files\Git\bin\bash.exe" scripts/testdata/run_testdata.sh release
```

## Step-by-step examples

```bash
bash scripts/testdata/run_testdata.sh generate --profile demo --people 2500 --seed 20261107
bash scripts/testdata/run_testdata.sh verify
bash scripts/testdata/run_testdata.sh measure
bash scripts/testdata/run_testdata.sh protect
bash scripts/testdata/run_testdata.sh attack
bash scripts/testdata/run_testdata.sh gate
bash scripts/testdata/run_testdata.sh scorecard
bash scripts/testdata/run_testdata.sh report
bash scripts/testdata/run_testdata.sh compare
bash scripts/testdata/run_testdata.sh latest
```

## Command mapping (official -> test_data)

| Official (`scripts/final`) | Test pack (`scripts/testdata`) |
|---|---|
| `run_release.sh` | `run_testdata.sh release` / `demo` |
| `run_protect.sh` | `run_testdata.sh protect` (`run_test_pack.py`) |
| `run_attack_sim.sh` | `run_testdata.sh measure` / `attack` |
| `mosaic_check.sh` | `run_testdata.sh gate` (`gate.py`) |
| `run_scorecard.sh` | `run_testdata.sh scorecard` |
| `ops1_manifest.sh` | `run_testdata.sh verify` |

## Expected values (demo profile)

- Raw attack: HETU 513, phone 337 (matches manifest).
- Protected: HETU 0 for both `current` and `relational`.
- Phone: `NOT_MEASURED` (health phone column dropped; not counted as 0).
- FIN-S2: 17 -> 15 (documented).
- Validation: 50/50 checks, `all_ok: true`, `scorecard_ready: true`.
- Tests: 20 passed.

## Caveats

- Phone join is `NOT_MEASURED` because the health phone column is dropped; it is not reported as 0.
- Free text is not redacted by the current pipeline.
- FIN-U4 varies (documented 0.75-0.93, observed 0.6966-0.8749).
- Runs are never overwritten; create a new run instead.

## Safety

All writes go only under `test_data/generated/<run_id>/`. The tooling refuses to write under `resources/`, `clean_data/` or `keys/`.
EOF