# IMPLEMENTATION PLAN — attack-first + FIN-S2 transform-not-drop

Match edits on **anchor strings**. If an anchor is missing, stop and report.

## Do not touch

`resources/`, `manifests/`, `app/agent_graph.py`, `app/agent_runtime.py`,
`app/normalize.py`, `app/pseudonym.py`, `app/measure_baseline.py`,
`app/mosaic_check.py`, `app/attack_sim.py`, `app/run_protect.py` (esp.
glue_survival_guard), `app/run_attack_sim.py`, `scripts/material/common.sh`,
anything under `scripts/` outside `scripts/final/`, `keys/`, `clean_data/`.
Never retune 1622/1484. Never add `phone` to HEALTH-S1 tokenise set.
Never tokenise FIN-S2 `full_name` / `street_address`.

Note: `findings/MVP_Plan.md` and `findings/IDEA.md` **do exist** (tracked).
`INSTRUCTION.md` may link them. Still gitignore `findings/agent_proposals/`
and `findings/agent_checkpoints/` (raw HETUs).

---

## Step 1 — `.gitignore`

Append:

```
# Attack + baseline evidence: raw-pack attack-sim writes real pack HETUs here
findings/agent_proposals/
findings/agent_checkpoints/
findings/baseline_overlap.json
```

## Step 2 — `app/pet_pipeline.py`

Replace TOKENISE_IDENTIFIERS block with:

```python
# Per-(dataset, scenario) key domains: the same person gets a different token
# in each release, so the columns stay usable inside a release but cannot be
# joined across releases (PET_PLAYBOOK "Joins across datasets").
# HEALTH-S1 must NOT list `phone`: normalize_phone() strips the hex letters out
# of a token, and the digits that survive can collide across releases.
TOKENISE_IDENTIFIERS: dict[tuple[str, str], set[str]] = {
    ("health", "HEALTH-S1"): {"patient_hetu"},
    ("finance", "FIN-S2"): {"hetu", "phone", "iban", "email"},
}
```

## Step 3 — `scripts/final/run_release.sh`

Replace `release_payload()` body so order is:

1. ATTACK unprotected: `run_attack_sim.py --mode shadow --raw-pack --thread-id ${stamp}-raw`
2. DEFEND: `run_protect.py --init-key`
3. RE-ATTACK protected: `run_attack_sim.py --mode shadow --thread-id ${stamp}-protected`
4. GATE: `mosaic_check.py`

Keep `|| return $?` on each line. Keep shebang/source/cd and
`run_with_ops1_guard release_payload` wrapper unchanged. Print four banners
`=== STEP N/4 — ... ===`.

## Step 4 — `app/run_demo.py`

1. Import `TOKENISE_IDENTIFIERS` from `pet_pipeline`.
2. Replace residual risk R-9 text with free-text / Groq gap (chief_complaint).
3. Rename banners:
   - Step 1: Two safe-looking extracts…
   - Step 2: ATTACK the unprotected data: the join SUCCEEDS
   - Step 3: DEFEND, then re-run the SAME attack: the join is closed
   - Step 4: Metrics, honest claim and residual risk
4. Change `_column_diff` to take `tokenised: set[str]` and return
   `(dropped, kept_tokenised)`. Add `_find_row_by_col`.
5. Pass `health, finance` into `_print_step3_defence`; print HEALTH/FIN
   tokenised vs dropped using TOKENISE_IDENTIFIERS; print protected row
   tokens for the Step-1 dossier (skip silently if lookup misses).
6. In step 4, print metrics block (1622/1484 → 0/0, mosaic JSON, B1,
   scorecard) before residual risks; say "see INSTRUCTION.md".

## Step 5 — `INSTRUCTION.md` (new)

Single runbook sections in order:

1. `# SinceAI — attack, defend, measure`
2. `## Before you start`
3. `## 0. Verify the pack is intact (OPS-1)`
4. `## 1. Attack the UNPROTECTED data` (measure_baseline + attack-sim --raw-pack; 1622/1484)
5. `## 2. Defend` (run_protect; expected FIN-S2: 17→15, drop full_name/street_address, tokenise email/hetu/iban/phone)
6. `## 3. Re-attack and gate` (0/0 + PASS-2)
7. `## 4. Metrics` (mosaic JSON, B1, scorecard)
8. `## One command for all of it` (run_release + run_demo)
9. `## What we do not claim`
10. `## Known gap — free text is not redacted (owned by the Groq agent)`
11. `## Troubleshooting`

## Steps 6–7 — stub `DEMO.md` and `USAGE.md` to point at INSTRUCTION.md

## Step 8 — `README.md`

Point at INSTRUCTION.md; run_release description =
`verify → attack raw → protect → re-attack → mosaic gate → verify`.

## Step 9 — `scripts/final/STEPS.md`

Update doc links, P6 row, dependencies, expected outcomes for STEP 1/4 vs 3/4.

## Step 10 — `CLAUDE.md`

Update P6 command line; usage doc → INSTRUCTION.md; invert FIN-S2 never-do
(now: do not *drop* glue — tokenise); add never add phone to HEALTH-S1
tokenise; never tokenise FIN-S2 names; never commit agent_proposals.

---

## Verification (coder runs; report real output)

**Re-run protect before mosaic** (stale clean_data hides the change).

```bash
bash scripts/final/ops1_manifest.sh verify
bash scripts/final/measure_baseline.sh
bash scripts/final/run_protect.sh --init-key
# FIN-S2: 17→15; dropped full_name,street_address; tokenised email,hetu,iban,phone
head -1 clean_data/finance__FIN-S2/customers.csv
bash scripts/final/mosaic_check.sh
bash scripts/final/run_release.sh
bash scripts/final/run_demo.sh --skip-protect
bash scripts/final/ops1_manifest.sh verify
```

PASS: baseline 1622/1484; mosaic PASS; release STEP1=1622/1484 STEP3=0/0;
demo shows FIN-S2 tokenised four glue cols; ops1 OK; no resources/ edits.
