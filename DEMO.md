# SinceAI — five-minute jury demo

SinceAI is a cross-release mosaic defence for the TrustED PETs proving ground: unprotected pack releases in, protected releases out that no longer join on HETU or normalised phone across controllers. The demo replays Attack A on raw `data/` vs `clean_data/` with the same code path as the release gate — no LangGraph agents required.

## Five-minute demo

1. **OPS-1** — confirm the vendored pack is intact:

   ```bash
   python3 scripts/ops1_manifest.py verify
   ```

2. **Protect** (skip if `clean_data/` already exists):

   ```bash
   python3 scripts/run_protect.py --init-key
   ```

3. **Narrated story** (before → after + honest claim):

   ```bash
   python3 scripts/run_demo.py --skip-protect
   ```

   Or the wrapped pipeline:

   ```bash
   bash scripts/run_demo.sh
   ```

4. **Full release path** (protect → shadow attack-sim → mosaic gate):

   ```bash
   bash scripts/run_release.sh
   ```

5. **Baseline lock** (positive control numbers only — same join code as the gate):

   ```bash
   python3 scripts/measure_baseline.py
   python3 scripts/mosaic_check.py
   ```

## PET playbook mapping (pack `docs/PET_PLAYBOOK.md` items 1–5)

| Jury item | What we show | Where |
|---|---|---|
| 1 — Field inventory with roles | Classifier + glue index drive drop vs tokenise | `scripts/field_classifier.py`, protect summary in `run_protect.py` |
| 2 — PET per field tied to scenario | HEALTH-S1 tokenises `patient_hetu`; FIN-S2 drops glue columns | Step 3 of `run_demo.py`, `scripts/pet_pipeline.py` |
| 3 — Protected output on disk | Real CSVs under `clean_data/` | `clean_data/health__HEALTH-S1/`, `clean_data/finance__FIN-S2/` |
| 4 — Utility before/after | B1 mosaic join chart; per-scenario B2 needs Py≥3.10 + pets-eval | `benchmarks/B1_mosaic_joins.png`; scorecard unavailable on 3.9 |
| 5 — Residual risk stated honestly | R-1, R-5, R-6, R-9 in demo step 4 | `findings/MVP_Plan.md` §8 |

## Honest claim

> Against an attacker with our two protected releases, no public adversary file, and no access to our keys, the measured cross-release join count on HETU, phone and IBAN is **0**, down from a baseline of **1622** on the unprotected data — while each release still passes `pets-eval scorecard` for its own scenario.

## What we do not claim

- **Anonymous** or “safe to publish together” — only that measured *identifier* joins on HETU and phone are zero between these two releases under stated assumptions.
- **Closed residual risk** — quasi-identifier mosaic (R-1), key compromise (R-5), pack blind spots (R-6), and minimisation gaps (R-9) remain.
- **Utility numbers we did not measure** — no invented B2 scorecard metrics on Python 3.9; B1 is the project-owned utility-of-attack figure when generated.
- **truth/ person_ids** — the public walkthrough uses pack `data/` rows only (e.g. HETU `021280-9730`), not private truth tables.

## Further reading

- Attack narrative: `findings/IDEA.md`
- Technical plan and gate criteria: `findings/MVP_Plan.md`
- End-to-end release: `bash scripts/run_release.sh`
