# Task

Build **P0** from `findings/MVP_Plan.md` §6: a baseline-measurement script
that re-measures Attack A's health∩finance join yield on the unprotected
raw pack data, using the **R2 normalisation** recipe, and **locks** the
two "before" numbers **1622** (HETU) and **1484** (phone) as a runnable
positive control. This is the first real project-owned code; there is
currently no `scripts/` directory.

## 0. Analysis (done by the coordinator — do not re-derive the scoping)

**What P0 is.** Compact plan §6 phase P0 (1 hour): *"Re-measure the
baseline attack yield on raw `data/` with the R2 normalisation; lock
1622 / 1484 as the 'before' numbers."* It is **not** yet the full
`scripts/mosaic_check.py` (that is P3: PASS-1 against `clean_data/` +
PASS-2). P0 only needs the measurement + the positive-control assertion
that later becomes PASS-2's health∩finance rows.

**Why this exists.** Core idea of the plan: defend by simulating the
attack first. Without a locked baseline, a later checker that reports
"0 joins on the protected release" is meaningless — a broken normaliser
also reports 0. PASS-2 / this script is the broken-instrument detector.

**Coordinator re-measurement (just now, stdlib `csv` + `re`, no pandas):**

| Join | With R2 | Without phone norm | Locked target |
|---|---|---|---|
| HETU health ∩ finance (distinct non-empty keys) | **1622** | n/a (exact string) | **1622** |
| Phone health ∩ finance (distinct non-empty keys) | **1484** | **383** | **1484** |

The 383-without-norm figure is the load-bearing proof that R2 is not
optional: a script that skips normalisation under-counts by ~4× and
would later green-light a vulnerable release.

**Worked example still present** (for optional demo print, not a pass
criterion): person `P013174` — health `ED25-022833` /
`patient_hetu=021280-9730` / name `Lehto Riku Viljami` / phone
`0508000433` / `icd10_primary=N20.0`; finance `SB88296612` /
`hetu=021280-9730` / name `Riku Viljami Lehto` (order reversed) / phone
`+358508000433` / `income_band=15-30k`. Same HETU; phones only match
after R2.

**Column map (from `MVP_Plan_original.md` §1.3 / field catalog):**

| Table | Path under pack `data/` | HETU col | Phone col |
|---|---|---|---|
| health ED visits | `health/ed_visits.csv` | `patient_hetu` | `phone` |
| finance customers | `finance/customers.csv` | `hetu` | `phone` |

Pack root (vendored, **read-only** — OPS-1):
`resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/`

**R2 recipe** (must match plan §3 R2 / original §1.4 exactly):

- Phone: strip characters outside `[0-9+]`; then `^\+358` → `0`; then
  `^00358` → `0`. Discard empty results.
- HETU: keep as string, strip surrounding whitespace only; discard empties.
  Do **not** validate checksum for the join count (the attacker joins on
  whatever string is present).
- Load every identifier column as a **string** (stdlib `csv` is fine;
  never let a numeric coerce drop leading zeros / century signs).
- Overlap = size of the **set intersection of distinct keys**, not a
  row-count of an inner join (one person can appear in many ED visits).

## 1. Deliverables

1. **`scripts/measure_baseline.py`** — a runnable CLI that:
   - Resolves the pack root relative to the repo root (do not hard-code
     an absolute `/Users/...` path).
   - Reads the two CSVs above with string columns.
   - Applies R2, computes the two distinct-key intersections.
   - Prints a clear human-readable report that includes at least:
     `hetu_health_finance=<n>` and `phone_health_finance=<n>`.
   - **Exit code 0** iff both counts equal the locked targets
     (1622 and 1484); **non-zero** otherwise, with the expected vs
     observed values on stderr/stdout so a broken recipe is obvious.
   - Opens pack files read-only; writes nothing under `resources/`.
   - Uses **stdlib only** (`csv`, `re`, `argparse`/`sys`, `pathlib`) —
     no pandas, no pets-eval import required for P0. (pandas is not
     installed in the ambient environment the coordinator just checked.)
   - Optional but useful: a `--show-example` flag that prints the
     P013174 HETU/phone pair above (read from the two data files by
     HETU `021280-9730`, not from `truth/` — truth stays private).

2. **`scripts/r2_normalize.py`** — a tiny shared module exporting
   `normalize_phone(value: str) -> str` and (if useful)
   `normalize_hetu(value: str) -> str`, so P3's future
   `mosaic_check.py` can import the **same** recipe instead of
   re-implementing it. `measure_baseline.py` must import from here —
   one source of truth for R2.

3. **Update `CLAUDE.md` Commands** — replace the `<fill in>` placeholders
   that this phase makes real:
   - Dev / run baseline: `python3 scripts/measure_baseline.py`
   - Test (P0): same command; exit 0 is the check
   - Note under Folder structure that `scripts/` holds project-owned
     tooling and that `resources/` is vendored read-only
   - Under "Things Claude must never do": edit anything under
     `resources/TRUSTED_SinceAI2026_FINAL/...` in place; invent a second
     phone-normalisation recipe that disagrees with R2

Do **not** create `scripts/mosaic_check.py`, `clean_data/`, `keys/`,
benchmark charts, agents, or shell wrappers — those are later phases.

## 2. Verification (coder runs these; coordinator re-runs)

```bash
python3 scripts/measure_baseline.py
echo exit:$?
# expect: prints both locked counts, exit 0

python3 -c "from scripts.r2_normalize import normalize_phone; \
  assert normalize_phone('+358508000433') == '0508000433'; \
  assert normalize_phone('050 800 0433') == '0508000433'; \
  assert normalize_phone('00358508000433') == '0508000433'; \
  print('norm-ok')"

# OPS-1 smoke: script must not create/modify anything under resources/
# (coder: note mtime of pack data dir before/after, or simply confirm
# the script has no write path into resources/)
```

PASS only if: exit 0, both printed counts are exactly 1622 and 1484,
`normalize_phone` unit asserts pass, and nothing under `resources/` was
written.

## 3. What this task does NOT do

- Does not implement PASS-1 / protected-release checking.
- Does not measure the other five Attack A joins (energy/CS) — out of
  MVP scope per compact plan §4; may be noted as a future extension in
  a one-line comment, not implemented.
- Does not read or depend on `truth/` for the pass/fail decision
  (`truth/` is verify-only and never ships; the locked numbers are the
  public positive control).
- Does not edit `findings/*`, `resources/*`, or invent new normalisation
  variants.
- Does not add third-party dependencies or a `requirements.txt` for P0.

## 4. Research before writing

- Read `findings/MVP_Plan.md` §2 (R2), §4.1–4.2 (tables + before/after
  numbers), §6 P0 row, and Part 1's PASS-2 note (~lines 187–201).
- Read `findings/IDEA.md` §Measured overlap and §How to attack steps
  A1–A3.
- Confirm the two CSV paths exist under the pack root and that the
  column names match the table above (do not assume — open the header
  line).
- Re-measure 1622/1484 yourself once with the planned R2 functions
  before declaring the script done; the coordinator's table above is
  the expected answer, not a substitute for the script working.

# Notes

- `CLAUDE.md` currently has unfilled command placeholders — updating
  them is in scope for this task (see deliverable 3). After that update,
  the verification command above *is* the project's Test entry for P0.
- Prefer a small, boring script a cheaper model can maintain. No classes
  unless they clearly help; functions + `main()` is enough.
- Repo trunk is `main`. Findings/Artifacts are gitignored; `scripts/`
  and the `CLAUDE.md` update are what must land as real tracked files
  (`CLAUDE.md` is listed in `.gitignore` today — if it still is, the
  coder should still update the working-tree file so agents read the
  new commands; do **not** fight `.gitignore` in this task).
