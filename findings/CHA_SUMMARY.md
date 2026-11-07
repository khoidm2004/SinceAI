# Challenge summary: TrustED PETs Transformer

**Event:** Since AI Hackathon 2026 · Turku · 6–8 November 2026  
**Challenge title:** TrustED PETs Transformer — *Protect the data, keep its value.*  
**Inspiration:** EU Horizon Europe TrustED (GA 101168467), coordinated by Gradiant.  
**Sources:** `resources/TRUSTED_SinceAI2026_FINAL/` (challenge PDF, brief DOCX, presentation) and the Proving Ground pack under `…/TRUSTED_PETS_PROVING_GROUND_2026/` (`START_HERE.md`, `docs/*`). Large local-only files are listed in `resources/NOTE.md`.

---

## Resources architecture

How `resources/` is laid out and how the pieces fit the detect → select → transform → demonstrate loop.

```
resources/
├── NOTE.md                          # Local-only large files (not in git remote)
└── TRUSTED_SinceAI2026_FINAL/       # Challenge delivery bundle
    ├── Challenge_TRUSTED_PETs_Transformer_EN … .pdf     # One-pager challenge sheet
    ├── TrustED_PETs_Transformer_Challenge_Brief_….docx  # Full brief (demo, judging, PETs)
    ├── 2026.11_SinceAI_TrustEDpresentation-en-US.docx   # Partner intro (transcript)
    ├── 2026.11_SinceAI_TrustEDpresentation.mp4          # LOCAL ONLY (~95 MB) — see NOTE.md
    ├── TRUSTED_PETS_PROVING_GROUND_2026 (1).zip          # LOCAL ONLY (~111 MB) — see NOTE.md
    └── TRUSTED_PETS_PROVING_GROUND_2026/                 # Working pack (in git)
        ├── START_HERE.md | START_HERE.html              # Entry point
        ├── README.md | NOTICE.md | LICENSE* | MANIFEST.json
        │
        ├── data/<dataset>/          # INPUT: 10 domains to protect
        │   health | mobility | smart_city | energy | finance
        │   cyber | education | public_admin | customer_service | unseen
        │
        ├── metadata/                # LABELS & SPECS for detection / attacks / scenarios
        │   field_catalog.csv        # Gold privacy roles per column
        │   scenarios.json           # 27 sharing scenarios
        │   attack_specs.json        # Linkage / trajectory attacks
        │   pii_spans/               # Gold free-text PII spans
        │   dp_query_workload_health.json
        │   taxonomy.md | pii_span_guidelines.md
        │
        ├── adversary/               # PUBLIC attacker knowledge (what they know)
        ├── truth/                   # Ground truth: record ↔ person (scoring only)
        ├── holdout/                 # Non-members for membership-inference tests
        │
        ├── toolkit/pets_eval/       # EVAL ENGINE: pets-eval CLI + library
        ├── baselines/               # B0–B4 reference protectors to beat
        ├── results/                 # Precomputed baseline scorecards (b0, b2, b2k, b4…)
        ├── examples/                # quickstart.py
        ├── tests/                   # Package integrity + toolkit tests
        └── docs/                    # Human guides (scenarios, threat model, PETs, eval…)
```

### How layers connect

```text
                    ┌─────────────────────────────────────┐
                    │  Brief / PDF / presentation         │
                    │  (what to build & demo for jury)    │
                    └─────────────────┬───────────────────┘
                                      │
                                      ▼
┌──────────────┐   detect    ┌──────────────┐   select PETs   ┌──────────────┐
│ data/*       │────────────▶│ metadata/*   │────────────────▶│ your tool    │
│ (raw tables) │             │ field catalog│  docs/PET_*     │ (transform)  │
└──────────────┘             │ scenarios    │  docs/SCENARIOS │              │
                             └──────────────┘                 └──────┬───────┘
                                                                     │ protected/
                                                                     ▼
┌──────────────┐  attacks    ┌──────────────┐   scorecard     ┌──────────────┐
│ adversary/*  │────────────▶│ toolkit/     │────────────────▶│ results /    │
│ truth/*      │  unicity    │ pets-eval    │  privacy+utility│ demo evidence│
│ holdout/*    │  MI / DCR   │              │                 │              │
└──────────────┘             └──────▲───────┘                 └──────────────┘
                                    │
                             baselines/*  = floor to beat
```

| Layer | Role in the challenge |
|-------|------------------------|
| Challenge PDF + brief DOCX | Problem, objective steps, PET menu, 5 demo items, judging |
| `NOTE.md` + ignored zip/mp4 | Teammates keep archive/video locally; extracted pack is enough for work |
| `data/*` | Synthetic datasets you protect |
| `metadata/*` | Gold labels, scenarios, attack specs — train/score detectors and redaction |
| `adversary/` + `truth/` | Measurable re-identification (public attacker); never publish truth/rowmaps |
| `holdout/` | Non-member rows for synthetic-data membership inference |
| `toolkit/` | Self-assessment: `detect`, `text`, `check`, `scorecard` |
| `baselines/` + `results/` | Simple floors (B0–B4) and their scorecards |
| `docs/` | Scenario design, threat model, PET playbook, evaluation rules |

**Entry path for the team:** open `TRUSTED_PETS_PROVING_GROUND_2026/START_HERE.md` first; use the brief/PDF for jury framing; keep zip/mp4 out of git (`resources/NOTE.md`).

---

## Problem

Organisations must share, analyse or publish valuable data without exposing personal, sensitive or restricted information. Dropping names is rarely enough; over-protecting destroys patterns, trends and relationships. The job is to **balance privacy and utility** for a concrete sharing purpose.

## Guiding question

How might we **automatically identify privacy risks** in a synthetic dataset, **select suitable PETs**, and **demonstrate** that the protected result still supports a defined analytical purpose?

## What we must build

A working prototype that, for chosen data and a sharing scenario:

1. **Detect / classify** data types (direct IDs, quasi-identifiers, sensitive attributes, technical IDs, free text, etc.).
2. **Select** proportionate PETs per type and scenario (justify each choice).
3. **Transform** the dataset into a protected release or view.
4. **Demonstrate** before/after utility and residual risk honestly.

Possible PETs (from the challenge sheet): masking, pseudonymisation, tokenisation, generalisation, binning, suppression, aggregation, synthetic data, free-text redaction, location coarsening, timestamp rounding, differential privacy for aggregates.

### Deliverable (yes — with one nuance)

**Yes:** the project output is a **working solution** that takes synthetic `data/*`, protects it for **one chosen scenario per dataset** from `docs/SCENARIOS.md`, then **self-evaluates** with `pets-eval` as specified in `docs/EVALUATION.md` (scorecard = privacy risk removed + utility kept for that scenario).

**Nuance — not mere “cleaning”:** scrubbing columns is only one PET. The scenario decides whether you aggregate, pseudonymise, redact, synthesise, add differential privacy, or even **share less**. Utility for that scenario’s tasks must survive; residual risk must be stated honestly.

```text
data/<dataset>/  +  SCENARIOS.md (pick 1 ID)
        │
        ▼
  our tool: detect → select PETs → transform
        │
        ▼
  protected output/  (+ private rowmaps for scoring)
        │
        ▼
  EVALUATION.md via pets-eval scorecard --scenario <ID>
        │
        ├─ privacy_score / utility_score / composite   (self-assessment)
        └─ demo evidence for jury (5 items) + sinceai.app submission
              Official judging = Since AI process (scorecard is not the official mark)
```

**Ship:** working prototype + short demo video + description/repo on sinceai.app, showing identified types, PET choices, protected data, before/after utility, and the sharing scenario.

#### Required vs optional when testing

| Track | What | How evaluated |
|-------|------|----------------|
| **Required (core)** | For each dataset you tackle: pick **one** scenario from `docs/SCENARIOS.md` → transform → `pets-eval scorecard --scenario <ID>` per `docs/EVALUATION.md` | Privacy + **that scenario’s** utility tasks + composite (self-assessment). Demo the five jury items. |
| **Optional (organiser checks)** | `data/unseen/` detection labels; hidden attackers; `customer_service` eval redaction | **On request** during the event (`docs/EVALUATION.md`). Put outputs in `pets_submission/`. |

`unseen` is **not** “scenario + 1 mandatory transform.” It has **no** sharing scenario in `SCENARIOS.md`. It is a **detection** challenge (headers `c01…c26`, no labels): show your detector works on never-seen columns; organisers can score `unseen_field_labels.csv` against private gold. You do **not** run a normal protect+scorecard loop on it unless you invent your own demo path.

```text
REQUIRED                     OPTIONAL stretch
─────────                    ────────────────
pick dataset(s)              data/unseen/ → field labels (detection)
pick 1 scenario each         (+ optional text spans)
transform for that scenario  customer_service eval redaction
scorecard --scenario <ID>    hidden attackers on your protected tables
demo 5 jury items            → pets_submission/ if you want organiser scoring
```

## Final demo checklist (jury)

| # | Must show |
|---|-----------|
| 1 | Data types identified in the original |
| 2 | PETs selected per data type (tied to scenario) |
| 3 | Transformed / protected output (not only screenshots) |
| 4 | Utility before vs after (measurable) |
| 5 | Sharing scenario the release is fit for + residual risks |

**Official judging** follows Since AI criteria: technical implementation, innovation, impact (privacy ↑ with utility kept), presentation. The pack’s `pets-eval scorecard` is **self-assessment**, not the official score.

**Submission:** one working prototype on sinceai.app + short demo video (English narration recommended) + description / repo materials. No real sensitive data or secrets in public materials.

---

## The Proving Ground (our materials)

Package path: `resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/`.

Everything is **synthetic** (CC BY 4.0 data, MIT code). One synthetic population of **100,000** Southwest Finland residents appears across domains — cross-dataset linkage (mosaic effect) is a real risk.

### Scale (from `START_HERE.md`)

- **10 datasets:** 9 labelled domains + 1 unlabelled surprise (`unseen`)
- ~**4.7M** rows, **475** catalogued columns, **354k** labelled PII spans in free text
- **27** sharing scenarios, **13** public attacker-knowledge files
- Toolkit: `pets-eval` (detect, privacy metrics, attacks, utility tasks, HTML/JSON scorecard)
- Baselines **B0–B4** to beat (`docs/BENCHMARK.md`)

### Datasets at a glance

All rows under `data/<dataset>/` are **synthetic** and are the intended material to protect and score (not real personal data). Pick **one** scenario per dataset, transform those tables, then `pets-eval scorecard --scenario <ID>`. Smoke test: `examples/quickstart.py` on `health/ed_visits` → `HEALTH-S1`.

| Dataset | Fictional controller | Example tables you can test | Scenarios | Typical hard problems |
|---|---|---|---|---|
| `health` | Regional hospital emergency department | `ed_visits`, `lab_results`, `clinical_notes`, `published_weekly_stats` | HEALTH-S1 / S2 / S3 | HETU (Finnish personal identity code, *henkilötunnus*) encodes date of birth/sex; rare diagnoses; clinical free text; differential-privacy dashboards |
| `mobility` | Transit cards + city bikes | `taps`, `cards`, `bike_trips` (+ `stops`, `bike_stations`) | MOB-S1 / S2 / S3 | Trajectory unicity (~98% of cards with 4 points); home inference |
| `smart_city` | Wi‑Fi / automatic number-plate recognition | `wifi_probes`, `anpr_parking`, `footfall_15min` (+ `sensors`) | CITY-S1 / S2 / S3 | Static MACs, SSIDs with surnames, plates, purpose limitation |
| `energy` | Smart meters | `meter_readings_hourly`, `customers` (+ `weather_hourly`) | ENERGY-S1 / S2 / S3 | Occupancy / vacation inference; medical-device priority (GDPR Article 9 special-category data) |
| `finance` | Bank cards / transfers | `card_transactions`, `transfers`, `customers` (+ `cards`) | FIN-S1 / S2 / S3 | Tokenisation vs re-link via receipts; fraud utility |
| `cyber` | SOC logs | `proxy_logs`, `dns_logs`, `signin_logs`, `email_gateway` (+ more under `data/cyber/`) | CYBER-S1 / S2 / S3 | Cross-log joins; prefix-preserving IPs; secrets in URLs |
| `education` | Schools | `course_grades`, `students`, `counsellor_notes` (+ `absences`, `matriculation_results`) | EDU-S1 / S2 / S3 | Small classes; proxies in course codes; counsellor notes |
| `public_admin` | Service centre | `service_requests`, `building_permits` | PUB-S1 / S2 / S3 | Open free text; neighbours named; repeat reporters |
| `customer_service` | Telecom contact centre | `turns`, `conversations` (+ `customers`) | CS-S1 / S2 / S3 | Redaction benchmark: spoken numbers, spelled emails, passwords; hidden evaluation split |
| `unseen` | Obfuscated human-resources/payroll export | `export_2025_q4` (headers `c01..c26`) | *(none — detection only)* | Detect without labels; organisers can score field labels vs private gold |

> **Redaction (note):** removing or replacing sensitive bits *inside free text* (names, phones, emails, IDs, passwords) so the rest of the message stays readable — often with typed placeholders such as `[PERSON]` or `[PHONE]`. Unlike dropping a whole column, redaction keeps the prose useful while hiding identifiers; spoken digits and spelled-out emails are easy to miss.

### Suggested attack surfaces / paths

Each path is a focus area; the mini illustration shows what the method does on example values.

#### 1. Free-text redaction → `customer_service`, `health/clinical_notes`, `public_admin`

Scrub identifiers *inside* prose; keep meaning.

```text
BEFORE  "Hi, I'm Aino Virtanen, call me at 040 123 4567, password was Summer2024!"
AFTER   "Hi, I'm [PERSON], call me at [PHONE], password was [SECRET]!"
```

#### 2. Tabular de-identification under linkage → `health/ed_visits`, `finance/customers`, `education/students`

Drop or coarsen columns that, together, pin down one person (quasi-identifiers); stop public-directory / news linkage.

```text
BEFORE  name=Aino Virtanen | birth=1991-03-14 | postcode=20100 | sex=F | diagnosis=J18.9
AFTER   name=(removed)     | age_band=30-39  | postcode=201** | sex=F | diagnosis=J18
        → many patients share the same QI group (aim k ≥ 5), so linkage fails
```

#### 3. Location / trajectories → `mobility`, `smart_city`

Coarsen places and times so a few known (place, hour) points no longer single out one card/device.

```text
BEFORE  card=C8821  stop=Market Square  time=2025-10-03 08:17:42  → home tip visible
        card=C8821  stop=Campus        time=2025-10-03 08:41:03
AFTER   card=hmac…  zone=centre-N      time=2025-10-03 08:15       → snapped / rounded
        card=hmac…  zone=campus        time=2025-10-03 08:45
        (4 exact points no longer unique ~98% of cards)
```

#### 4. Pseudonyms that keep joins → `cyber`

Replace identifiers with a **keyed** pseudonym so the same user still matches across log tables — without a reversible hash.

```text
BEFORE  proxy: user=aino.virtanen@meridian.fi  ip=91.153.12.40
        dns:   user=aino.virtanen@meridian.fi  query=malware.example
AFTER   proxy: user=U_7f3a9c…                 ip=91.153.12.0/24   (prefix-preserving)
        dns:   user=U_7f3a9c…                 query=malware.example
        same key → join still works; unsalted sha256(email) would be dictionary-attacked
```

#### 5. Differential privacy for published stats → `health/published_weekly_stats` (+ DP workload) or energy neighbourhood load

Publish noisy aggregates, not rows; one person cannot swing the released number much.

```text
TRUE COUNT     flu-like visits, Raisio, week 12  =  17
ε-DP RELEASE   Laplace noise →  15  (or 19 next draw)
               mechanism + ε + contribution bound stated; cells not published raw
```

#### 6. Synthetic data + membership-inference tests → any table + `holdout/`

Train a generator; release fake rows that keep distributions. Check they are not copies and that an attacker cannot tell training members from `holdout/` non-members.

```text
ORIGINAL   row ≈ real patient  →  do not release
SYNTHETIC  new row from model  →  similar age/diagnosis mix, no exact clone
TEST       distance-to-closest-record + membership inference AUC ≈ 0.5 (coin flip)
```

#### 7. Automatic detection showcase → `unseen` (organiser-scored)

Label obfuscated columns without relying on header names; organisers score against private gold labels.

```text
INPUT   c01,c02,c03,c04,…          (no useful headers)
YOU     c01=direct_identifier (email-like)
        c02=quasi_identifier (birth date)
        c03=sensitive_attribute (salary band)
        …
SCORE   pets-eval detect vs private field labels
```

### How protection is measured (`docs/EVALUATION.md`)

`pets-eval` is a **self-assessment** toolkit: it measures (1) how much **privacy risk** remains after your transform and (2) how much **utility** you kept. Official hackathon judging still follows Since AI’s process; judges expect the same before/after evidence the scorecard is built to produce. Which tables and scenario IDs to feed it are listed under **Datasets at a glance** above.

#### What you must put in the output folder

Protection is only scorable if the release follows pack conventions:

| Rule | Why it matters |
|------|----------------|
| Same table filenames as the original (e.g. `ed_visits.csv`) | Missing tables count as **withheld** |
| Keep original column names for columns you keep | Scorers know which fields to compare |
| Generalised values in accepted forms | Ages `30-39` / `90+`; postcodes `201**` or `201`; times rounded / `2025-03` / `2025-W12`; rounded coordinates; ICD-10 shortened to 3 characters or groups |
| Per released row-level table: `rowmap_<table>.csv` with `protected_row` (0-based) + `original_record_id` | Links protected rows back to originals for attack scoring — **never publish** |
| No row map and no original record ids | Treated as **synthetic data** → distance-to-closest-record (DCR) + membership inference vs `holdout/` |
| Health differential-privacy workload | Add `dp_answers.csv` (`id,value`) and document mechanism, ε, δ (if any), privacy unit, contribution bound |

```text
my_out/health/
  ed_visits.csv
  lab_results.csv
  rowmap_ed_visits.csv      ← scoring only, private
  rowmap_lab_results.csv
  dp_answers.csv            ← if answering the DP query workload
```

#### Privacy risk components (each in \[0, 1\])

Higher = worse. The scorecard runs these against your protected tables (and `adversary/` / `truth/` / gold spans where relevant):

| Component | What it measures | Intuition |
|-----------|------------------|-----------|
| **Direct identifiers retained** | Share of catalogued direct-identifier values that still appear **verbatim** | Name/HETU/email/phone still sitting in a cell |
| **Hashed ids reversible** | Share of “hashed” values recovered by hashing candidate lists (unsalted MD5 / SHA-1 / SHA-256) | `sha256(email)` without a secret key is not protection |
| **Records with k &lt; 5** | Share of rows whose quasi-identifier group has fewer than 5 people (on the QIs you kept) | Age+sex+postcode still unique → easy to link |
| **Linkage re-identification** | Worst re-id or attribute-inference rate over attacks in `metadata/attack_specs.json` | Public directory / receipts / news clips find the person |
| **Free-text identifier leakage** | Share of **gold** PII spans whose value still appears in your text | Redaction missed a phone or spelled-out email |
| **Trajectory unicity** | Share of subjects (cards, accounts, devices, vehicles) singled out by a few known (place, hour) points (`trajectories` in `attack_specs.json`) | Four taps uniquely identify ~98% of cards in the raw data |
| **Synthetic: DCR / membership inference** | Exact (or near) copies of original rows, and how much better than chance a membership attacker does vs `holdout/` | Generator memorised training people |

```text
risk components  r1, r2, … rn  ∈ [0, 1]
worst = max(ri)     mean = average(ri)

privacy_score = 1 − (0.5 × worst + 0.5 × mean)
```

**Worst risk is weighted equally with the mean on purpose:** one open door (e.g. reversible hashes while everything else looks fine) is enough for an attacker, so the privacy score stays low.

#### Utility score

Each dataset defines **6–11 utility tasks** (`pets-eval tasks`). For a chosen **sharing scenario**, only that scenario’s required tasks count.

1. Ask the **same analytical question** on original data and on protected data.
2. Score **agreement** in \[0, 1\] (how close the protected answer is to the original).
3. If the task is **not answerable** (you deleted or coarsened what it needs) → score **0** when the scenario requires it.
4. **Utility score** = mean over the scenario’s tasks.

```text
scenario HEALTH-S1 needs tasks H-U2, H-U4, …
each task:  agree(original_answer, protected_answer) → 0..1
utility = mean(those task scores)
```

So utility is not “how big the file still is” — it is “can the recipient still do the analyses the scenario promised?”

#### Composite score

```text
composite = weighted_harmonic_mean(privacy_score, utility_score)
            weights: privacy 30, utility 25
```

A harmonic mean with both weights stays high **only if both sides are high**. Releasing nothing (privacy↑ utility↓) or releasing everything (utility↑ privacy↓) both get a poor composite.

#### Detection and redaction scoring (separate from the scorecard’s privacy mix)

These evaluate **your detector / redactor**, not only the final tables:

| Command | Compares | Reports |
|---------|----------|---------|
| `pets-eval detect --pred my_labels.csv` | Your `dataset,table,column,privacy_role,subtype` vs `metadata/field_catalog.csv` | Per-role precision / recall / F1, macro-F1, subtype accuracy, confusion matrix |
| `pets-eval text --gold spans.jsonl --pred my_spans.jsonl` | Predicted PII spans vs gold | Precision, recall, **F2** per label (F2 weights **recall** higher — missing an identifier is worse than over-redacting) |
| `pets-eval text --gold spans.jsonl --protected redacted.csv` | Gold span **values** vs surviving text | Which identifiers still leak, regardless of redaction style (`[PHONE]` vs `XXX` vs deletion) |

In gold span files: a record **absent** from the JSONL, or present with an **empty** `spans` list, means **no labelled PII** in that text.

#### Optional organiser checks (cannot overfit)

On request at the event, organisers can score what you have not seen:

1. **Hidden attackers** — stronger private adversary per domain (data broker, human-resources knowledge, colleagues, merchant, municipal insiders) on your tables + row maps.
2. **`unseen` labels** — your field labels for `data/unseen/export_2025_q4.csv` vs private gold.
3. **`customer_service` eval redaction** — your redacted eval turns vs private gold spans.

To request these, put outputs under `pets_submission/` in the repo:

- `unseen_field_labels.csv`
- `customer_service_eval_redacted.csv` (`turn_id,text`) **or** `customer_service_eval_spans.jsonl`
- protected tables + row maps, one subfolder per dataset

#### End-to-end picture

```text
original data + your protected/ + scenario ID
        │
        ▼
 pets-eval scorecard
        │
        ├─▶ privacy risks (7 component families) ──▶ privacy_score
        ├─▶ scenario utility tasks               ──▶ utility_score
        └─▶ weighted harmonic mean               ──▶ composite
        │
 optional: detect / text / check
 optional: organiser hidden eval (pets_submission/)
```

Full normative detail: `resources/…/docs/EVALUATION.md`.

### Threat model (short)

Attackers know schema and published methods; can combine all public `adversary/` files and dictionary-hash candidates; do **not** know secret keys/seeds or the original data. Success = re-identification, attribute inference, membership inference (synthetic), or residual identifiers in text. A stronger private attacker set exists per domain — do not overfit the public files.

### Baseline lessons (`docs/BENCHMARK.md`)

- Dropping names ≠ anonymisation (e.g. B0 finance: receipts still re-id ~79% of targets).
- Generalise without checking **k** leaves rows unique; enforcing k≥5 closes risk at utility cost.
- **Keyed** pseudonyms keep joins; unsalted hashes and random tokens fail differently.
- Regex redaction misses spoken numbers, spelled emails, lowercase names — free text is a win condition.
- For DP: state ε, δ (if any), mechanism, contribution bound, and privacy unit.

---

## How we choose PETs (`docs/SCENARIOS.md`)

**Rule from the pack:** a PET is only right or wrong for a given **recipient** and **purpose**. Pick **one scenario per dataset** you work on and design for it. Then run `pets-eval scorecard --scenario <ID>` so utility is scored only on the tasks that scenario needs. Suggested privacy targets in `SCENARIOS.md` are design guides — not legal advice and not official judging thresholds.

Pair this with `docs/PET_PLAYBOOK.md` (techniques by data type). The scenario decides *how strong* and *what shape* the release is; the playbook decides *which transform* fits each column.

### Decision loop (per dataset)

```text
1. List scenarios for the dataset (pets-eval scenarios / SCENARIOS.md)
2. Pick ONE scenario ID  →  locks recipient, purpose, trust, threat, utility tasks
3. Read that scenario’s fields:
      Recipient + Purpose     → what utility must survive
      Trust level             → public vs contractual vs research vs internal
      Threat model            → which adversary/* files and attacks to beat
      Legal context           → anonymous vs pseudonymised personal data, Art. 9, etc.
      Suggested privacy targets → concrete PET knobs (k, ε, redact recall, aggregates…)
      Notes                   → joins / keys you must keep or must not keep
4. For every column, ask the playbook’s four questions
      (direct ID? QI? sensitive fact? needed at what resolution?)
5. Map answers → PETs that hit the scenario targets without killing its utility tasks
6. Score with --scenario <ID>; iterate if privacy or required tasks fail
```

### Trust level → typical PET shape

| Trust level (from scenarios) | Release shape | Typical PETs |
|------------------------------|---------------|--------------|
| **public** (open data portal) | Prefer **anonymous aggregates**; avoid row-level personal data | Aggregation; small-cell suppression; differential privacy on counts/sums; no card/MAC/user ids; heavy free-text redaction or no text |
| **contractual** (processor / vendor / consortium) | **Pseudonymised microdata** under a contract; minimise fields | Keyed HMAC tokens so joins survive; drop contacts; coarsen time/place; redact text; sometimes synthetic for vendor training |
| **controlled_research** | Pseudonymised research extract; publication of results must still be anonymous | Stable pseudonyms + QI generalisation (k≥5 or higher); redact notes; snap GPS; optional synthetic microdata |
| **internal** | Same controller / limited staff — still minimise | Keyed pseudonyms, drop contacts, redact text; sometimes the right PET is **share less** (CITY-S3) |

Same column, different scenario → different PET. Example: a travel **card id** is deleted/aggregated for MOB-S1 (public OD matrices) but kept as a **weekly-rotated HMAC** for MOB-S2 (consultancy needs same-day transfers).

### What each scenario block tells you to choose

When you open a scenario in `SCENARIOS.md`, map its bullets to PET choices like this:

| Scenario field | How it steers PET choice |
|----------------|--------------------------|
| **Recipient** | Who sees the data → how much trust / how much you can leave linkable |
| **Purpose** | Which patterns must survive → which columns stay at high resolution |
| **Threat model** | Which linkage attacks to design against (and which `adversary/` files) |
| **Legal context** | Need GDPR-style **anonymous** output (public) vs **pseudonymised** personal data (contract/research) |
| **Utility tasks** | Hard constraint: PETs that make a required task “not answerable” score 0 |
| **Suggested privacy targets** | Ready-made knobs: no direct IDs; k on named QI sets; ε; redact recall; aggregate-only; synthetic + membership-inference AUC ≈ 0.5 |
| **Notes** | Join/key requirements (e.g. stable patient key for revisits; do **not** mask attacker IPs in CYBER-S2) |

### Scenario catalogue → PET direction (cheat sheet)

| ID | Trust | PET direction (from suggested targets / notes) |
|----|-------|--------------------------------------------------|
| **HEALTH-S1** | controlled_research | Drop direct IDs; **stable keyed patient pseudonym** + joinable visit/lab keys; QI bands with **k≥5**; redact free text (recall ≥0.95) |
| **HEALTH-S2** | public | **Aggregates only**; differential privacy (state ε) or suppress cells &lt;5; do not publish raw weekly micro-stats |
| **HEALTH-S3** | contractual | **Synthetic** or strongly generalised training table, no free text; check DCR + membership inference vs `holdout/` |
| **MOB-S1** | public | No row-level / no card ids; OD matrices; suppress or noise cells &lt;10; consider ε-DP |
| **MOB-S2** | contractual | HMAC card ids (rotate weekly); drop holder fields; times 5–15 min; trajectory unicity &lt;5% @ 4 points |
| **MOB-S3** | controlled_research | No email-like accounts; GPS ends ≥250 m grid; k≥5 on home/work/card type |
| **CITY-S1** | public | Hourly zone counts only; suppress/noise &lt;5; no MACs/SSIDs |
| **CITY-S2** | contractual | Daily-rotating HMAC for MAC/plate; drop SSID/payment; times → 15 min |
| **CITY-S3** | internal | Mostly **minimise disclosure** (case-specific extract), not heavier transforms |
| **ENERGY-S1** | public | ≥10 meters per cell; no individual series; optional DP on hourly sums |
| **ENERGY-S2** | contractual | HMAC metering point; no contacts; ≥3-digit postcode; keep series linkable over time |
| **ENERGY-S3** | controlled_research | k≥5 on housing QIs; remove/noise medical flag; daily may beat hourly |
| **FIN-S1** | contractual | Consortium-keyed tokens for PAN/device/IP (**link across banks**); no names; time → minute |
| **FIN-S2** | contractual | Tokenised card; generalise sensitive merchants; k on profile; consider synthetic + DCR/MIA |
| **FIN-S3** | public | Aggregate ≥10 cardholders/cell; merchant dominance rules; DP on sums |
| **CYBER-S1** | contractual | **Same HMAC** across all log tables; strip secrets from URLs; generalise sensitive web categories |
| **CYBER-S2** | controlled_research | Share **attacker IoCs only**; keep attacker IPs exact; no employee/internal ids |
| **CYBER-S3** | public | Prefix-preserving IPs (discard key); coarsen/shift time; redact tickets; labelled campaigns must stay detectable |
| **EDU-S1** | public | Stats tables; suppress n&lt;5 or DP; no microdata |
| **EDU-S2** | contractual | No direct IDs/text; drop or justify special categories; k≥5; keyed student join across tables |
| **EDU-S3** | controlled_research | k≥10 or synthetic microdata; no counsellor notes |
| **PUB-S1** | public | Full redaction of text (incl. third parties); coarsen place/time; no account ids |
| **PUB-S2** | internal | Stable HMAC for reporters (repeat issues); redact text; no contacts |
| **PUB-S3** | controlled_research | k≥5 on area/category/month/language; no or redacted text |
| **CS-S1** | contractual | Hard redaction (recall ≥0.98 on IDs/cards/secrets); strip health mentions; keep utterance intent |
| **CS-S2** | internal | Typed placeholders or **surrogate** names for fluency; no secrets in training text |
| **CS-S3** | contractual | Mask IDs but keep audit evidence (e.g. `[NATIONAL_ID]` shows verification); drop customer_id; time → week |

### Worked micro-example

Same health table, three scenarios → three PET stacks:

```text
ed_visits.csv
  │
  ├─ HEALTH-S1 (research)     → keyed patient_id + age band + redact notes + keep diagnosis for revisit stats
  ├─ HEALTH-S2 (public dash)  → do not release rows; publish noisy weekly counts by age×municipality (ε-DP)
  └─ HEALTH-S3 (AI vendor)    → synthetic triage features only; no notes; MI ≈ chance on holdout
```

List IDs anytime with `pets-eval scenarios`. Full narrative for each: `resources/…/docs/SCENARIOS.md`.

---

## Working loop (practical)

1. Pick **dataset(s) + one scenario** per dataset (`docs/SCENARIOS.md` / `pets-eval scenarios`).
2. Detect fields → choose PETs using the scenario loop above (`SCENARIOS.md` targets + `docs/PET_PLAYBOOK.md` per column).
3. Transform; keep original column names where possible; add private `rowmap_*.csv` for scoring (**never publish**).
4. Score: `pets-eval scorecard --original … --protected … --scenario <ID>`; also `detect` / `text` / `check`.
5. Demo with the five jury items above and honest residual risk.

Quickstart (from pack root):

```bash
pip install -e ./toolkit
python3 examples/quickstart.py
pets-eval scorecard --original data/health --protected my_out/health --scenario HEALTH-S1
```

Read CSVs with `dtype=str` first (phones, postcodes, IDs break as numbers).

---

## Constraints / rules of the road

- Use only this synthetic data, public data, or data you are explicitly allowed to use.
- Never publish `rowmap_*.csv`.
- Claims like “anonymised” or “differentially private” need method + parameters.
- Licences: data CC BY 4.0, code MIT, © Since AI ry.

## Where to look next in-repo

| Need | Path |
|------|------|
| Start here | `…/TRUSTED_PETS_PROVING_GROUND_2026/START_HERE.md` |
| Scenarios | `…/docs/SCENARIOS.md` |
| Threat model | `…/docs/THREAT_MODEL.md` |
| PET choices | `…/docs/PET_PLAYBOOK.md` |
| Scoring | `…/docs/EVALUATION.md` |
| Floors to beat | `…/docs/BENCHMARK.md` |
| Local-only large files | `resources/NOTE.md` |
| Challenge one-pager | `resources/TRUSTED_SinceAI2026_FINAL/Challenge_TRUSTED_PETs_Transformer_EN (1) (1).pdf` |
| Full brief | `resources/TRUSTED_SinceAI2026_FINAL/TrustED_PETs_Transformer_Challenge_Brief_FINAL_REVIEW (1).docx` |
