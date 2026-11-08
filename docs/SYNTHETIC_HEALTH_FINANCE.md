# Synthetic Health + Finance test pack — methodology

This document explains the independent, fully synthetic Health + Finance dataset that SinceAI uses to test its
own protection pipeline, cross-domain attack and `pets-eval` evaluation, without touching the official TrustED
challenge data. Every run also writes a run-specific `reports/index.html`, `reports/report.json` and
`reports/methodology.md` with the measured numbers.

## 1. Why an independent dataset

The official pack (`resources/TRUSTED_SinceAI2026_FINAL/…`) is the source of truth for schemas, privacy roles,
scenarios and attacks, but it is a single fixed draw: one population, one set of overlaps (Attack A: 1622 HETU /
1484 phone joins). A generator lets the team:

- test the actual SinceAI code on data with **known ground truth** (who is who, who is in both domains);
- vary population size, overlap and missing-identifier rates and see the effect;
- run the full pipeline — protect → attack → `pets-eval` — repeatedly and reproducibly;
- demo the mosaic attack without exposing even synthetic official rows in slides.

The official pack, its baselines and the official P7 demo are **not modified**.

## 2. Why Health + Finance

They are the two domains of the project's Attack A (health ⋈ finance on HETU and normalised phone), and the two
scenarios the MVP protects: **HEALTH-S1** (secondary-use research, needs a stable patient pseudonym and
joinable visit/lab keys) and **FIN-S2** (external AI vendor, fraud + spending models, "tokenised card").

## 3. Population generation

`app/generate_test_data.py` (standard library only, seed-deterministic):

1. Draw `--people` fictional persons (default demo **2,500**; smoke 400). Each gets sex, birth date
   (age distribution by decade), municipality + postcode (weighted by the official municipality counts; real
   Southwest Finland names used as geography only), street address, mobile number, occupation, income band
   (conditional on occupation), employer, preferred language.
2. Assign domain membership by configured shares: both (20 %), Health only (40 %), Finance only (15 %),
   neither (25 %, appear only in public adversary data). Finance members are adults (≥ 18 on 2025-12-31).
3. Derive Health records (ED visits, labs, notes) for Health members and Finance records (customer, cards,
   transactions) for Finance members. A small holdout population (4 %) is generated the same way for
   `holdout/`.

Each stage uses its own RNG seeded by `"<seed>:<stage>"`, so the same seed reproduces identical files
(tested byte-for-byte).

## 4. Synthetic identity construction (pack `NOTICE.md` conventions)

| Identifier | Construction |
|---|---|
| HETU | `DDMMYY` + century sign (`-` 1900s, `A` 2000s) + individual number **900–999** (odd = male) + check character `"0123456789ABCDEFHJKLMNPRSTUVWXY"[int(DDMMYY+NNN) % 31]`; unique per person |
| Phone | random Finnish mobile number `0 4x/50 xxxxxxx`, unique; Health rows use the official 7 formats of the same number, Finance stores E.164 `+358…` |
| IBAN | `FI` + mod-97 check digits + 14-digit BBAN whose bank id starts with **9**; unique |
| Payment card | public test BINs 411111, 400000, 424242, 555555, 510510, 222300 + Luhn digit; unique |
| E-mail | `<name>@<inbox|nordmail|…>.example` |
| Names, streets, employers, merchants | composed from syllables / generic forenames; fictional |

The private `person_id` (`P` + 6 digits) is the ground-truth identity. It appears only in `truth/` (needed by
`pets-eval` to score linkage) and `private/population.csv` — never in a released table.

## 5. Cross-domain linkage construction

A person in both domains carries the **same HETU** in both, unless the Health registration lacks it
(`--health-hetu-missing`, 1 %). The Finance phone equals the Health phone with probability
`--finance-phone-same` (88 %), otherwise the person has a new number; phones are missing at the configured rates
(Health 25 % of patients, Finance 3.5 %). Non-resident ED visits (≈ 1.7 %) have no HETU, no postcode, a Swedish
or no phone, and no person in truth.

**The overlaps are not hard-coded.** The manifest re-reads the written files and computes, with the repository's
own normalisers (`app/normalize.py`): HETU overlap = |normalize_hetu(ed_visits.patient_hetu) ∩
normalize_hetu(customers.hetu)|, phone overlap = |normalize_phone(ed_visits.phone) ∩
normalize_phone(customers.phone)|, plus collisions (same value, different person — always 0 by construction).

## 6. Tables and relationships

Headers are byte-identical to the official tables (checked by `validate_test_pack.py`).

```
ed_visits (visit_id) 1 ──< n lab_results.visit_id          customers (customer_id) 1 ──< n cards.customer_id
          (visit_id) 1 ──< n clinical_notes.visit_id       cards (card_pan)        1 ──< n card_transactions.card_pan
ed_visits.patient_hetu / phone  ~~~ person ~~~  customers.hetu / phone      (cross-domain: Attack A)
```

- Health 2025: arrivals by official month and hour weights; seasonal influenza (Jan–Mar, Dec) and RSV;
  triage, disposition and LOS distributions from the official counts; `readmit_30d` computed from the
  person's next visit within 30 days of discharge; vitals with fever correlated to infectious diagnoses; ICD-10
  codes = the 50 keys of the toolkit's diagnosis groups. Labs: the 15 official test codes; **CRP is driven by
  temperature** so H-U7's CRP–temperature relationship exists. Notes: nurse and physician notes in fi/sv/en.
- Finance Jul–Dec 2025: 1–3 cards per customer; transactions with paydays (1st/15th/16th), weekends, Black
  Friday, December; MCC mix and channel rules from the official data; foreign travel; fraud incidents
  (card testing, skimming, lost/stolen, CNP cash-out, account takeover) that close the card and issue a
  replacement. The demo profile uses a 2.5 % fraud-card share (official ≈ 1.1 %) so FIN-U1 keeps ≥ 10 labelled
  frauds before 2025-11-01 at 2,500 people.

## 7. Metadata compatibility

`pets-eval` resolves everything relative to `--root` (the run's `pack/`):

| Path | Content |
|---|---|
| `metadata/field_catalog.csv` | official rows for health + finance, verbatim (all 9 columns, incl. `data_kind`) |
| `metadata/scenarios.json` | official HEALTH-S1 and FIN-S2 entries, verbatim (task selection + adversary choice depend on them) |
| `metadata/attack_specs.json` | official health/finance attacks, verbatim, for the adversaries regenerated here |
| `adversary/*.csv` | **synthetic** `public_directory`, `news_clips_health`, `social_posts_health`, `receipt_photos_ocr` built from this population (first column = row id) |
| `truth/adversary__*.csv`, `truth/<domain>__<table>.csv` | row → person maps (read by column position) |
| `holdout/<domain>/<table>.csv` | non-member records (same schema) |
| `metadata/pii_spans/*.jsonl` | gold spans for `ed_visits.chief_complaint` and `clinical_notes.note_text` |

The official adversary values are **not** reused: they describe other people and would make the attack
meaningless.

## 8. PII span generation

Free text is built piecewise; every inserted synthetic PII value (PERSON, NATIONAL_ID, PHONE, ADDRESS, AGE,
DATE, LOCATION, ORG) records its exact `[start, end)` offsets, label and text at insertion time. Records follow
`metadata/pii_span_guidelines.md` (`{"record_id", "spans":[{end,label,start,text}]}`). Line breaks inside notes
are written as `\n`, so offsets index the raw field (the official note file needs LF-normalisation; ours does
not). The validator re-checks every offset, the text at the offsets, non-overlap, record ids and labels.

## 9. Protection pipeline integration

The official P1 runner protects one table per scenario. `app/run_test_pack.py` protects every table the
scenario's tasks read (HEALTH-S1: ed_visits, lab_results, clinical_notes; FIN-S2: customers, cards,
card_transactions) by calling the **unchanged** functions `classify → protect_table → glue_survival_guard →
write_release`, with one key domain per (dataset, scenario) from `derive_subkey`.

Two policies are run and reported:

| Policy | What it is |
|---|---|
| `current` | the pipeline exactly as it is, table by table |
| `relational` | the same code with a documented classifier override: each release-internal join key (visit, customer, card) is treated as `technical_identifier`, so all its columns are tokenised with the same release key — equal tokens inside the release, different tokens across releases. `card_pan` is tokenised as FIN-S2 asks ("tokenised card"). |

Why two: under `current`, `ed_visits.visit_id` / `customers.customer_id` are `record_key` (passed through) while
the FKs `lab_results.visit_id` / `cards.customer_id` are `technical_identifier` (tokenised), so the joins break;
and `card_pan` is a direct identifier that FIN-S2 does not tokenise, so it is dropped. The runner measures this
instead of hiding it. Row maps go to `private/rowmaps/` and are passed to `pets-eval` with `--rowmap`.

Checks per table: rows in/out, columns and order, dropped columns, row-map alignment, the existing glue-survival
guard, foreign-key resolution after protection, and raw direct-identifier values of the release surviving
anywhere (whole cell or inside text; counts only).

## 10. Attack methodology

`app/run_test_attack.py` reuses `attack_sim.simulate_attack` and `normalize.py`: HETU `strip`; phone
`strip non-[0-9+]; ^+358 → 0; ^00358 → 0`. Raw: join counts, checked against the manifest and the ground truth
(true vs false person links). Protected: the same join on the transformed columns. If a column is missing the
result is **NOT_MEASURED** — a zero from a dropped column is never counted as protection. The official constants
`EXPECTED_HETU = 1622`, `EXPECTED_PHONE = 1484` are untouched and not used for this pack; the validator re-runs the
official Attack A on the official pack to show it still reproduces them.

## 11. Scorecard methodology

`app/run_test_scorecards.py` runs the unchanged CLI:
`python -m pets_eval scorecard --root <pack> --original <pack>/data/<ds> --protected <release> --scenario <ID>
--rowmap <table>=<private row map> …` and `pets-eval check <release>`. `PETS_ROOT` is removed from the child
environment so the scorer cannot fall back to the official pack. The runner verifies the scorecard's recorded
paths and row counts against the scored files and that scoring did not change them, and lists every task with its
real status. With row maps this is a **protected-release comparison**, not a DCR / membership-inference evaluation
of a synthetic-data generator (that path runs only for tables without row maps).

A sanity layer flags scores the toolkit clamps: FIN-U1 = `min(1, AP_protected / AP_original)` is marked
**CAPPED** when the protected-trained model scores higher; a NaN term that the toolkit turns into 1.0 is marked
**DEGENERATE** (e.g. H-U7 with no diagnosis group of ≥ 30 joined rows).

## 12. Metric definitions

**Privacy risk components** (0 = no risk, 1 = maximal; lower is better), per released table:

| Component | Definition |
|---|---|
| direct identifiers retained | share of values in catalogued direct-identifier columns that appear verbatim (normalised) in the release |
| hashed ids reversible | share of 32/40/64-hex values recovered by unsalted MD5/SHA-1/SHA-256 of candidate identifiers (keyed HMAC tokens are not) |
| records with k<5 | share of rows whose combination of kept quasi-identifiers occurs fewer than 5 times. *Equivalence class* = rows with identical QI values; *k* = its size; min / median k summarise the classes |
| linkage re-identification | max over the scenario's adversaries of (unique correct claims / adversary targets present) or the attribute-inference advantage `(success − base)/(1 − base)` |
| free-text identifier leakage | share of gold *identifying* span values (PERSON, NATIONAL_ID, PHONE, ADDRESS, …) still found in the released text. Regex coverage is not semantic name/place protection |

**Privacy score** = 1 − (0.5 × worst risk + 0.5 × mean risk). **Utility score** = mean of the scenario's
required tasks (an unanswerable required task counts as 0 in this mean; the report shows it as "not answerable",
never as a measured 0). **Composite** = (30 + 25) / (30 / privacy + 25 / utility) — a weighted harmonic mean:
releasing everything (privacy ≈ 0) or nothing (utility = 0) both give a low composite.

**Utility tasks** (0..1, higher is better):

| Task | Question | Needs | Metric |
|---|---|---|---|
| H-U2 | median LOS by triage | triage, los_minutes | 1 − mean relative error / 0.3 |
| H-U4 | diagnosis-group mix, top-8 municipalities | municipality, icd10_primary | 1 − mean TVD / 0.15 |
| H-U6 | 30-day revisit rate by age band | readmit_30d or consistent patient pseudonym; age | 1 − (mean |Δ| / overall rate) / 0.5 |
| H-U7 | CRP vs temperature; CRP by diagnosis group | lab_results ⋈ ed_visits on visit_id; temp_c; ≥ 30 joined rows | 0.5·(1 − |Δρ|/0.3) + 0.5·(1 − mean log-median gap) |
| H-U8 | hour-of-day arrival curve | arrival_ts with a time of day in > 50 % of values | 1 − TVD / 0.3 |
| FIN-U1 | fraud model (train Jul–Oct, test original Nov–Dec) | ts, amount_eur, mcc, channel, country, card_pan, is_fraud; ≥ 10 frauds | min(1, AP_prot / AP_orig) |
| FIN-U4 | card segmentation (k = 6) | consistent card_pan pseudonym; ≥ 50 cards | 0.5·centroid agreement + 0.5·(1 − size TVD) |
| FIN-U6 | monthly spend by income × age band | customers → cards → transactions joins | 1 − MAPE / 0.5 (cells ≥ 10 customers) |

**Cross-domain attack**: raw HETU / phone join = number of distinct normalised values present in both
releases; protected join = the same on the protected columns (NOT_MEASURED if absent). The custom baseline is
computed from this pack; official Attack A (1622 / 1484) is a different, fixed dataset.

**Performance**: wall-clock per stage (subprocess, includes interpreter start-up), rows/s = rows protected /
protection seconds, output bytes, and peak working set of the stage's own process (`GetProcessMemoryInfo` on
Windows, `ru_maxrss` elsewhere). Median / min / max over repetitions with the same seed and configuration.

## 13. Benchmark methodology

`run_synthetic_demo.py --bench --bench-sizes 500,1000,2500 --bench-reps 3` runs the full pipeline (generate,
protect both policies, attack, scorecards for both policies) for each size and repetition in its own run folder
under `<run>/benchmark_runs/`. Same seed and configuration per size; the machine is recorded in the report.

## 14. Limitations and known gaps

- Synthetic distributions follow the official counts but are simpler (e.g. fraud is easier to separate; FIN-U1
  can be capped at 1.0).
- Utility tasks that read unchanged fields score 1.0; that measures analytical fidelity, not safety.
- FIN-U4 is unstable between runs: with byte-identical data, each run's new temporary key changes the token
  values and hence the card ordering seen by the toolkit's k-means; in the 2,500-person benchmark it ranged
  0.75–0.93. Report it as a range. All other scores were identical across repetitions.
- H-U8 is not answerable under the current pipeline (timestamps generalised to ISO week).
- The current pipeline does not redact free text; `clinical_notes.note_text` leakage is measured, not fixed.
- k-anonymity on the kept QIs is very low (most rows unique); generalisation is generic, not scenario-specific.
- The receipt attack's last-4-digit QI can never match a tokenised `card_pan`, so a 0 there is a scorer artefact
  of the spec, not proof that time + amount matching fails.
- Linkage attacks use the synthetic adversaries generated here, not the organisers' hidden attackers.
- `transfers`, `published_weekly_stats` and the other domains are out of scope for this pack.

## 15. Reproduction

From the repository root, with the existing uv environment (no sync):

```bash
uv run --no-sync python app/run_synthetic_demo.py --profile demo --people 2500 --seed 20261107 --tests
uv run --no-sync python app/run_synthetic_demo.py --profile demo --people 2500 --bench           # + benchmark
uv run --no-sync python app/run_synthetic_demo.py --run-dir test_data/generated/<run_id> --narrate-only

# step by step (RUN = test_data/generated/<run_id>)
uv run --no-sync python app/generate_test_data.py --profile demo --people 2500 --seed 20261107
uv run --no-sync python app/validate_test_pack.py   --run-dir RUN
uv run --no-sync python app/run_test_pack.py        --run-dir RUN --init-key
uv run --no-sync python app/run_test_attack.py      --run-dir RUN
uv run --no-sync python app/run_test_scorecards.py  --run-dir RUN
uv run --no-sync python app/report_test_pack.py     --run-dir RUN
uv run --no-sync pytest -q -p no:cacheprovider tests
```

PowerShell: identical commands (set `$env:PYTHONIOENCODING = "utf-8"` if the console cannot print `ä/ö`).
Outputs land only in `test_data/generated/<run_id>/` (git-ignored); runs are never overwritten. The official
demo (`bash scripts/final/run_demo.sh`) is unchanged.
