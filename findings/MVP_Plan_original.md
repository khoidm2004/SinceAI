> **Archived (v1) — superseded by `findings/MVP_Plan.md`.** This is the full, unabridged
> prior version of the MVP plan (646 lines), kept on disk purely for traceability — nothing
> in the current compact plan deleted content without pointing back here. See the current
> document's §10 References for exactly which section below each part of the compact plan
> came from. Do not treat this file as the current plan.

---

# MVP plan: defending the Proving Ground datasets against the cross-domain mosaic attack

**New finding — does not supersede an earlier one.** It builds on `findings/IDEA.md` (Attack A) and `findings/CHA_SUMMARY.md` (pack/challenge summary) and turns them into a buildable MVP. Attacker view first; every design decision below traces back to a named attacker capability.

---

## 1. Attacker view (reverse-engineered)

### 1.1 Who the attacker is

A **linkage attacker, not an intruder**: a curious analyst, data broker or journalist who has legitimately obtained several shared extracts from *different controllers* (`findings/IDEA.md:19`). They know every schema and every published method (Kerckhoffs's principle, `docs/THREAT_MODEL.md:46`), but they do **not** know our secret HMAC keys or seeds, and they cannot reach the original unreleased tables (`findings/IDEA.md:19`, `docs/THREAT_MODEL.md:46-49`).

The **victim** is any resident present in more than one domain. The **secondary victims** are the four controllers — hospital, DSO, bank, telecom — each of whom believed its own share was "fine alone" (`findings/IDEA.md:21-22`).

### 1.2 Preconditions

Exactly one precondition, stated at `findings/IDEA.md:71`:

> several releases still contain at least one of `phone` / `hetu` / `iban` (**or reversible hashes of them**). Names may already be dropped.

Note what this does *not* require: no names, no addresses, no breach, no insider. Dropping `patient_name` does nothing. The parenthetical — *or reversible hashes of them* — is why an unsalted digest is not a defence; the pack itself ships `enumerate_hetu` and `hash_dictionary_attack` to prove it (`toolkit/pets_eval/attacks.py:548`, `:517`).

### 1.3 The three join keys

From `findings/IDEA.md:39-43`:

1. **HETU** — exact match across health / energy / finance / customer_service.
2. **Phone** — normalise digits (`+35844…` → `044…`), then match.
3. **IBAN** — strip spaces, uppercase, match.

The keys do not even share a column name across datasets, which is why a naive scan misses one of the four:

| Dataset / table | HETU column | phone column | IBAN column | `metadata/field_catalog.csv` |
|---|---|---|---|---|
| `health/ed_visits` | **`patient_hetu`** | `phone` | *(none)* | `:3`, `:7` |
| `energy/customers` | `hetu` | `phone` | `iban` | `:132`, `:138`, `:146` |
| `finance/customers` | `hetu` | `phone` | `iban` | `:163`, `:170`, `:171` |
| `customer_service/customers` | `hetu` | `phone` | `iban` | `:441`, `:446`, `:452` |

All eleven columns are catalogued `privacy_role=direct_identifier` with `subtype` in `{NATIONAL_ID, PHONE, IBAN}` — so the pack's own field catalog is a machine-readable index of the attacker's glue.

### 1.4 Measured join yield in this pack

From `findings/IDEA.md:49-58`. **Independently re-measured for this plan and reproduced exactly, all eight numbers**, by normalising phones as *strip non-`[0-9+]` → `^\+358`→`0` → `^00358`→`0*` and IBANs as *strip spaces, uppercase*:

| Join | Overlap | Re-measured |
|---|---|---|
| HETU health ∩ finance | 1 622 | ✓ 1622 |
| Phone health ∩ finance | 1 484 | ✓ 1484 |
| Phone health ∩ customer_service | 2 296 | ✓ 2296 |
| Phone health ∩ energy | 195 | ✓ 195 |
| HETU health ∩ energy | 194 | ✓ 194 |
| IBAN energy ∩ finance | 15 | ✓ 15 |
| IBAN finance ∩ customer_service | 150 | ✓ 150 |
| People in health ∩ energy ∩ finance (`truth/*` `person_id`) | 19 | ✓ 19 |

Two further numbers measured here and **not** in `findings/IDEA.md`, from the `truth/` person maps — they quantify how *efficient* the glue is:

- Ground-truth co-present people: health ∩ finance **1 623**, health ∩ customer_service **2 421**, health ∩ energy **218**, all four domains **1**.
- So the HETU join recovers **1622 / 1623 = 99.9 %** of the truly shared people in health ∩ finance: HETU is a near-perfect key, not a lossy heuristic. The phone join recovers **2296 / 2421 = 94.8 %** in health ∩ customer_service; the ~5 % loss is blank and non-E.164 values (`metadata/field_catalog.csv:446`: "~8 % stored in non-E.164 formats").

The identifier space is small enough that these joins are cheap: 25 955 distinct HETUs in health, 6 315 in finance, 9 591 in customer_service, 671 in energy.

### 1.5 The attack steps

Verbatim structure from `findings/IDEA.md:73-83`:

| # | Step | Source |
|---|---|---|
| A1 | Load the CSV extracts with `dtype=str` so phones, HETUs and IBANs do not become numbers | `:73` |
| A2 | Normalise phones and IBANs; keep HETU as a string | `:74` |
| A3 | Inner-join **health ⋈ finance** on HETU or normalised phone | `:75` |
| A4 | Join **energy** on HETU / phone / IBAN; join **customer_service** the same way | `:76` |
| A5 | On each matched row, collect attributes the controllers never co-released — health → diagnoses, triage, free text; energy → `medical_device_priority`, address, arrears; finance → `income_band`, `pep_flag`, employer; CS → accessibility, products, contact channels | `:77-81` |
| A6 | Optionally confirm any surviving name/address against `adversary/public_directory.csv` | `:82` |
| A7 | Success = one person → **Art. 9-ish health and/or medical-priority** + **financial** + **contactable identity** | `:83` |

Step A1 is not a detail. Reading these columns as integers mangles leading zeros and century signs, which is why a hand-rolled pipeline that forgets `dtype=str` under-counts the joins and under-reports its own risk.

A5's payload is all catalogued Art. 9 or sensitive: `health,ed_visits,icd10_primary` (`metadata/field_catalog.csv:16`, Art. 9), `energy,customers,medical_device_priority` (`:149`, `HEALTH_DATA`, Art. 9, prevalence ~1-2 %), `finance,customers,income_band` (`:172`), `pep_flag` (`:175`), `employer` (`:174`), `customer_service,customers,accessibility_needs` (`:455`, `HEALTH_DATA`, Art. 9).

### 1.6 What success looks like

> *named (or uniquely QI'd) person + ED diagnosis + medical-device flag + income band + home address* — harmful precisely because each file alone looked "partially anonymised." — `findings/IDEA.md:89`

The pack contains a worked instance: `person_id` **P013174**, ED patient *Lehto Riku Viljami*, diagnosis **N20.0**, present in energy and finance with `income_band 15-30k` (`findings/IDEA.md:60-64`). A second illustration: ED *Petrov Vladimir* and finance *Vladimir Petrov* share the mobile `0443547786` / `+358443547786` and the same HETU (`findings/IDEA.md:65`) — the *name order differs*, so name-based matching would have failed and the phone still succeeds.

### 1.7 Why the pack's own scorer cannot see this

`findings/IDEA.md:95` states that `pets-eval scorecard` and `attack_specs.json` run **per-dataset** linkage and "do not score this cross-controller join". Verified here, and the reason is structural rather than a missing config row:

- `metadata/attack_specs.json` holds **16** `attacks` and **4** `trajectories`. Every entry's `"dataset"` is a **scalar string, never a list** — checked programmatically across all 16. Every entry's `"adversary"` names a file under `adversary/` (`public_directory.csv`, `leaked_customer_list.csv`, …); **no attack's adversary is another controller's dataset.**
- `metadata/scenarios.json` holds **27** scenarios, each likewise with a **scalar** `"dataset"`. The schema cannot express a release that spans controllers.
- `scorecard.run_scorecard(original_dir, protected_dir, …)` sets `domain = original_dir.name` (`toolkit/pets_eval/scorecard.py:286-290`), and the CLI exposes exactly one `--original` and one `--protected` (`toolkit/pets_eval/cli.py:112-113`). **One domain per invocation, by signature.** All seven privacy risk components (`docs/EVALUATION.md:22-34`) are computed inside that one pair and keyed per table (`scorecard.py:314`).

**The precise claim, stated carefully:** the pack *does* name the mosaic effect in prose — `docs/THREAT_MODEL.md:9`: "linking two weakly protected datasets can identify people that neither dataset identifies alone" — and `docs/PET_PLAYBOOK.md:29` prescribes the fix ("Different keys per recipient; per-dataset pseudonym domains … One global pseudonym for everyone: the mosaic effect re-identifies"). What the pack never does is **operationalise** it: no attack spec, no scenario, no scorecard component, no CLI path measures a join between two of *our own* releases. Attack A is novel against the pack's *metadata and tooling*, not against its documentation. That gap is precisely the hole this MVP fills.

---

## 2. Defensive requirements derived from the attack

Each requirement exists only because of the attacker capability in its row. Nothing here is a general best practice without a named cause.

| Attack step / capability | Requirement | ID |
|---|---|---|
| **A1** — attacker reads with `dtype=str`, preserving leading zeros and century signs (`IDEA.md:73`) | Every stage of our pipeline must read and write these columns as strings. A release whose own risk assessment was computed on numeric-coerced keys is unverified. | **R1** |
| **A2** — attacker normalises before matching (`IDEA.md:74`) | Our checker must normalise with the *same* recipe (strip non-`[0-9+]`, `^\+358`→`0`, `^00358`→`0`; IBAN strip-space + uppercase) before comparing, or it will under-count and pass a vulnerable release. Correctness test: the recipe must reproduce 1622 / 1484 / 2296 / 195 / 194 / 15 / 150 on raw `data/`. | **R2** |
| **A3 + A4** — exact-matches HETU, phone and IBAN **across controllers** (`IDEA.md:75-76`) | **No two outward releases may share a reversible identifier token for the same person.** Satisfied by per-recipient keyed HMAC-SHA-256 with a distinct key domain per `(dataset, scenario_id)` — `IDEA.md:105`, `docs/PET_PLAYBOOK.md:29`. | **R3** |
| Precondition — "**or reversible hashes of them**" (`IDEA.md:71`); attacker can hash candidate values (`docs/THREAT_MODEL.md:47`) and the pack ships `enumerate_hetu` / `hash_dictionary_attack` (`attacks.py:548`, `:517`) | **No unsalted or unkeyed digest of HETU, phone, IBAN or e-mail may ever leave the controller.** A keyed HMAC with a secret key is required; `sha256(hetu)` is enumerable over a tiny domain. `IDEA.md:106`. | **R4** |
| **A4** — joins on whichever of the three keys survives (`IDEA.md:76`) | Where the scenario's utility needs no stable person key at all, **drop the identifier rather than tokenise it** — minimisation shrinks the join surface to zero instead of to "zero if the key stays secret". `IDEA.md:104`, `:108`. | **R5** |
| **A5** — harvests free text (`IDEA.md:79`, "health → … free text if present") | Free-text redaction must target the **glue types**, not only names. The catalog's own traps say the glue is in there: `clinical_notes.note_text` "some personal identity codes" (`field_catalog.csv:47`), `energy dso_notes` (`:151`), `finance transfers.message` "child HETUs, phone numbers" (`:212`), `customer_service agent_note` "Agents copy ID codes, phone numbers" (`:470`), `customer_service turns.text` (`:476`). | **R6** |
| **A4** — a key re-exposed through a *second* released table | Token domains must be applied **consistently across every table in a release**. Concretely: `finance,transfers,from_iban` / `to_iban` carry the catalog trap "Customer IBANs link to customers.iban" (`field_catalog.csv:206`, `:208`) — tokenising `customers.iban` alone leaves the glue in `transfers`. | **R7** |
| **A6** — confirms via `adversary/public_directory.csv` (`IDEA.md:82`) | Keep the per-release linkage risk the scorecard *does* measure at target: each release must still pass `pets-eval scorecard --scenario <ID>`. Mosaic defence is **additive to**, never a substitute for, the pack's own checks. | **R8** |
| **A7** — success is the *combination* across releases (`IDEA.md:83`, `:89`) | A per-release green scorecard is not evidence of safety. We need a **cross-release** gate that no pack tool provides, with a stated pass criterion and a positive control. | **R9** |
| Attacker does **not** know our keys (`IDEA.md:19`, `docs/THREAT_MODEL.md:46`) | The whole of R3 rests on this. Keys must live outside the repo, be gitignored, be per-`(dataset, scenario_id)` derived from one master secret, and be rotatable — and the residual risk of key compromise must be stated, not hidden. | **R10** |
| Two releases of the **same** dataset to two recipients (`IDEA.md:107`, "Separate pseudonym spaces even when 'research' and 'vendor' both get microdata") | The key domain is `(dataset, scenario_id)` — **not** `dataset`. Two scenarios over one source table must produce two disjoint token spaces. | **R11** |

---

## 3. MVP scope

### 3.1 Datasets and scenario IDs — in scope

Attack A's measured overlaps land on exactly four datasets, so the MVP protects exactly those four, one scenario each (the pack's rule: "Pick one scenario per dataset you work on and design for it", `docs/SCENARIOS.md:3`).

| Dataset | Scenario ID | Title | Trust level | Recipient | Why this one, from the scenario's own fields |
|---|---|---|---|---|---|
| health | **HEALTH-S1** | Secondary-use research in a controlled environment | `controlled_research` | University research group studying ED crowding and revisits | The only health scenario that releases row-level microdata **and mandates a persistent person key** — `suggested_privacy_targets`: "consistent pseudonymous patient key"; `Notes`: "Revisit analysis needs a stable patient pseudonym" (`docs/SCENARIOS.md:17-18`). A stable person key is exactly what Attack A needs, so this is where the *key-domain* decision is load-bearing. Its redaction target also names PHONE and NATIONAL_ID — two of the three glue keys. |
| finance | **FIN-S2** | External AI vendor builds a fraud / spending model | `contractual` | AI vendor (processor) | The finance scenario that releases the **customer profile** — `suggested_privacy_targets`: "k-anonymity on customer profile" (`docs/SCENARIOS.md:167`) — which is precisely Attack A's finance payload: `income_band` (`field_catalog.csv:172`), `pep_flag` (`:175`), `employer` (`:174`). |
| energy | **ENERGY-S3** | Energy-poverty research dataset | `controlled_research` | University research group (controlled research environment) | Its purpose — "Relate heating type, payment problems and winter consumption", with the legal note "health flag needs special care (Art. 9)" (`docs/SCENARIOS.md:139-142`) — *is* Attack A's energy payload: `medical_device_priority`, address, arrears (`IDEA.md:79`). And its recipient is a **university research group**, the same recipient class as HEALTH-S1: a researcher holding both extracts is literally Attack A's "curious analyst with access to multiple shared extracts" (`IDEA.md:19`). HEALTH-S1 + ENERGY-S3 is therefore the sharpest demo pair — same recipient class, two controllers, one key domain each. |
| customer_service | **CS-S1** | Transcripts to an external LLM analytics vendor | `contractual` | Cloud AI vendor (processor, outside the EU possible) | Carries Attack A's **widest** glue: phone health ∩ CS = 2 296, the largest measured overlap (`IDEA.md:53`). It is the only CS scenario whose privacy target names the glue **by type** — "recall ≥ 0.98 on NATIONAL_ID, PAYMENT_CARD, IBAN, SECRET" (`docs/SCENARIOS.md:291`) — because here the glue lives in free text, not only in columns. Its threat model already says "insider can link with `leaked_customer_list.csv`" (`:288`): a single-adversary shadow of the same linkage. |

Why the alternatives were rejected — each on the scenario's own terms:

- **HEALTH-S2, FIN-S3, ENERGY-S1** are `public` and aggregate-only ("Aggregate only", `:28`; "Aggregate tables with ≥10 cardholders per cell", `:177`; "Aggregate ≥10 metering points per cell; no individual series", `:122`). **No row-level join surface, so Attack A is inapplicable** — protecting them teaches nothing about the mosaic.
- **HEALTH-S3** is fully synthetic (`:39`): the person link is broken by construction, so there is no token domain to get wrong.
- **FIN-S1 is the deliberate anti-pattern and is explicitly excluded.** Its target is "Keyed tokens (HMAC with **consortium key**) for PAN/device/IP **so the same card links across banks**", and its note says "Linkability across banks is the point — random tokens destroy it" (`docs/SCENARIOS.md:156-157`). That is a single key domain shared *across controllers* — the structural condition Attack A exploits. It is a legitimate, purpose-bound choice for fraud pooling, and it is out of MVP scope; see §7 R-8.
- **CS-S2** is `internal`; **CS-S3** drops `customer_id` and keeps `[NATIONAL_ID]` placeholders (`:313`), and typed placeholders are not glue.
- **ENERGY-S2** (`contractual`, flexibility aggregator, `docs/SCENARIOS.md:125-134`) is a genuinely useful second release of the *same* `energy/customers.csv` to a *different* recipient — the natural test of R11. Deferred to the M5 stretch so the MVP ships four releases, not five.

### 3.2 In scope

- The four tables that carry the glue: `data/health/ed_visits.csv`, `data/finance/customers.csv`, `data/energy/customers.csv`, `data/customer_service/customers.csv`, plus the free-text tables their scenarios require (`health/clinical_notes.csv` for HEALTH-S1's redaction target; `customer_service/turns.csv` for CS-S1).
- Requirements **R1-R11** in full.
- A cross-release mosaic checker with a positive control.
- One `pets-eval scorecard --scenario <ID>` run per dataset, plus `pets-eval check` on each release folder.

### 3.3 Explicit non-goals

1. **The other five datasets** — `mobility`, `smart_city`, `cyber`, `education`, `public_admin`. No Attack A overlap is measured for them in `findings/IDEA.md:49-58`.
2. **FIN-S1** (cross-bank consortium shared key). Structurally incompatible with R3; see §7 R-8.
3. **Differential privacy and synthetic-data generation.** Both belong to the `public` / synthetic scenarios we excluded in §3.1, and neither is what closes Attack A (`IDEA.md:100-109` names keying and minimisation, not DP).
4. **The behavioural tables** — `energy/meter_readings_hourly.csv`, `finance/card_transactions.csv`, `finance/transfers.csv` as *analytical* releases. `findings/IDEA.md:32` and `:34` mark these as value the attacker extracts *after* the identity bind, so they matter only once the join already succeeded. Exception: `transfers` IBAN columns are in scope for R7 if that table is ever released.
5. **`data/unseen/`.** A detection-only track with no sharing scenario (`findings/CHA_SUMMARY.md`, "Required vs optional" table); no protect-and-score loop applies.
6. **Cross-release quasi-identifier linkage** (birth date / postcode / sex / employer). The MVP *measures and reports* it; it does not close it. See §7 R-1.
7. **Any edit under `resources/`.** The pack is vendored and read-only. All new assets live in project-owned paths.
8. **A replacement scorer.** `pets-eval` remains the privacy/utility scorer; we add one cross-release gate beside it, we do not reimplement `docs/EVALUATION.md:34`.
9. **Production key management.** A local gitignored keyfile, not a KMS or HSM. See §7 R-5.

---

## 4. Software architecture for the MVP

### 4.1 Data flow

```text
     resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/   [VENDORED, READ-ONLY]
     +----------------------+----------------------+---------------------------+
     | data/<dataset>/*.csv | metadata/            | toolkit/pets_eval         |
     |  health, finance,    |  scenarios.json      |  scorecard  detect  text  |
     |  energy, cust_service|  field_catalog.csv   |  check      tasks   scen. |
     |                      |  attack_specs.json   |  (+ py modules: check,    |
     |                      |                      |   attacks, privacy)       |
     +-----------+----------+----------+-----------+-------------+-------------+
                 | read                | read                    | invoke / import
   +-------------v---------------------v--------------+          |
   | [1] scenario_loader      [2] field_classifier    |  REUSE   |
   |  scenario_id -> recipient,  catalog -> per-column|          |
   |  trust, utility reqs,       privacy_role+subtype |          |
   |  privacy targets            (glue-key index)     |          |
   +-------------+---------------------+--------------+          |
                 |                     |                         |
 keys/master.key |                     |                         |
 (GITIGNORED) -->+                     |                         |
                 v                     v                         |
   +-------------------------+  +---------------------------+     |
   | [3] pseudonym_service   |  | [5] text_redactor         |<----+ reuse
   |  HMAC-SHA-256           |  |  NER + regex + validators |   check.PATTERNS
   |  key domain =           |  |  typed placeholders       |   check.hetu_ok
   |  (dataset, scenario_id) |  |                           |   check.iban_ok
   |  NORMALISE then HMAC    |  |                           |   check.luhn_ok
   +-------------+-----------+  +-------------+-------------+     |
                 |                            |                   |
                 +------------+---------------+                   |
                              v                                   |
                 +------------------------------------+            |
                 | [4] pet_pipeline                   |   NEW      |
                 |  suppress | tokenise | generalise  |            |
                 |  redact   | round    | coarsen     |            |
                 |  driven by the scenario's targets  |            |
                 +------------------+-----------------+            |
                                    v                              |
                 +------------------------------------+            |
                 | [6] release_writer                 |   NEW      |
                 |  clean_data/<dataset>__<SID>/<tbl>.csv          |
                 |  + rowmap_<tbl>.csv  [PRIVATE,                  |
                 |    NEVER PUBLISHED]                |            |
                 +---------+-----------------+--------+            |
                           |                 |                     |
         +-----------------v---+          +--v--------------------------+
         | [7] mosaic_check    |  NEW     | [8] eval_runner    REUSE    |
         |  scripts/           |          |  pets-eval scorecard        |
         |   mosaic_check.py   |          |    --original data/<ds>     |
         |  cross-RELEASE join |          |    --protected clean_data/  |
         |  on hetu/phone/iban |          |    --scenario  <SID>        |
         |  + values recovered |          |  pets-eval check <rel dir>  |
         |    from free text   |          |  (ONE dataset per call)     |
         |  every release pair |          +--------------+--------------+
         +----------+----------+                         |
                    v                                    v
      clean_data/mosaic_check.json              clean_data/<ds>__<SID>/
      PASS iff every pair count == 0            scorecard.json + .html
      AND positive control on raw data/         privacy / utility / composite
      reproduces 1622 1484 2296 195
                 194 15 150
```

### 4.2 Components

`REUSE` = vendored pack asset used as-is. `NEW` = project code to write (outside `resources/`).

| # | Component | Reuse / new | Responsibility | Inputs | Outputs | Tech choice |
|---|---|---|---|---|---|---|
| 1 | `scenario_loader` | **REUSE** `metadata/scenarios.json` (27 entries); optional `pets-eval scenarios --dataset <ds>` (`cli.py:144-147`) | Resolve a scenario ID to recipient, `trust_level`, `utility_requirements`, `suggested_privacy_targets`. Locks what utility must survive. | `metadata/scenarios.json`, one scenario ID | In-memory `ScenarioSpec` | Python `json` + a dataclass. No new metadata format. |
| 2 | `field_classifier` | **REUSE** `metadata/field_catalog.csv` (476 rows); validated by `pets-eval detect --pred <labels.csv>` (`cli.py:120-126`) | Per-column `privacy_role` + `subtype`. Also yields the **glue-key index**: every column with `privacy_role=direct_identifier` and `subtype` in `{NATIONAL_ID, PHONE, IBAN}`. | `metadata/field_catalog.csv`, dataset + table name | Column → `(role, subtype)` map; glue-column list per dataset | `csv` / pandas, `dtype=str` (R1). Must key on `(dataset, table, column)` — health uses `patient_hetu`, the others `hetu`. |
| 3 | `pseudonym_service` | **NEW** | Deterministic per-recipient pseudonyms. Derive a subkey `K(d,s) = HMAC-SHA256(master_secret, f"{dataset}|{scenario_id}")`, then `token = HMAC-SHA256(K(d,s), normalise(value)).hexdigest()[:16]`. Satisfies R3, R4, R10, R11. | Normalised identifier string; `(dataset, scenario_id)`; `keys/master.key` | 16-hex-char token, stable within a release, disjoint across releases | Python `hmac` + `hashlib.sha256`. **Normalise before HMAC**, or `+358…` and `0…` yield two tokens for one person and intra-release joins break. 64 bits is ample for 100 000 residents (collision probability ≈ 2.7e-10). `keys/` is gitignored; never commit it. |
| 4 | `pet_pipeline` | **NEW** | Apply the scenario's targets column by column: suppress, tokenise (via 3), generalise, bin, round, coarsen, redact (via 5). Implements R5 and R7. | Source table (`dtype=str`), `ScenarioSpec`, classifier output | Protected DataFrame | pandas with `dtype=str` everywhere (R1). Keep original column names and the generalised value forms the scorer understands — `30-39`, `90+`, `201**`, `2025-W12` (`docs/EVALUATION.md:10-16`). |
| 5 | `text_redactor` | **NEW wrapper** over **REUSE** `pets_eval.check` | Detect and replace glue in free text with typed placeholders. Satisfies R6. | Text columns: `health/clinical_notes.note_text`, `customer_service/turns.text`, `energy/customers.dso_notes`, `finance/transfers.message` | Redacted text + a spans JSONL for scoring | Reuse `check.PATTERNS` (`check.py:17-27`) with validators `hetu_ok` (`:30`), `iban_ok` (`:37`), `luhn_ok` (`:50`) to cut false positives; add a NER pass for PERSON/ADDRESS. Score with `pets-eval text --gold metadata/pii_spans/... --pred <spans>` (`cli.py:127-135`). |
| 6 | `release_writer` | **NEW** | Write one release per `(dataset, scenario)` in the layout the scorer expects. | Protected tables + row indices | `clean_data/<dataset>__<SCENARIO-ID>/<table>.csv` plus `rowmap_<table>.csv` (`protected_row`, `original_record_id`) | Plain CSV. **`rowmap_*.csv` is for scoring only and must never be published** (`docs/EVALUATION.md:18`, `toolkit/README.md:21-22`). Same table filenames as the original (`docs/EVALUATION.md:7`). |
| 7 | `mosaic_check` | **NEW — `scripts/mosaic_check.py`; this is the net-new capability** | Cross-**release** join counting on hetu/phone/iban, including values recovered from free text. Closes the gap in R9 that no pack tool covers. | Every release directory under `clean_data/`, the glue-key index from (2), and raw `data/` for the positive control | `clean_data/mosaic_check.json` + non-zero exit on failure | Python stdlib `csv` + `re`, `dtype=str`. Reuses `check.PATTERNS` / `hetu_ok` / `iban_ok`. Normalisation **identical to R2** — the recipe verified to reproduce all seven baseline counts. |
| 8 | `eval_runner` | **REUSE** `toolkit/pets_eval` | Keep the pack's own self-assessment green (R8). | A release dir, its source `data/<dataset>`, its scenario ID | `scorecard.json` + `scorecard.html`; `check` report | Shell out to `pets-eval scorecard --original data/<ds> --protected clean_data/<ds>__<SID> --scenario <SID>` and `pets-eval check clean_data/<ds>__<SID>`. **One dataset per call** — `run_scorecard` sets `domain = original_dir.name` (`scorecard.py:290`), so four separate invocations. |

### 4.2a In plain English

The table above is written for whoever builds this. Here is the same eight steps without the jargon, for whoever has to explain or approve it:

1. **scenario_loader** — Before touching any data, look up who is receiving it and what they're allowed to see (a university research team? an outside vendor?). This sets the rules every later step has to follow.
2. **field_classifier** — Look at every column in the file and tag it: "this reveals exactly who someone is," "this is sensitive but not an ID," or "this is safe to share as-is." Uses a catalog made in advance instead of guessing column by column.
3. **pseudonym_service** — Give every person a scrambled code instead of their real ID number (national ID, phone, bank account). The important part: the *same* person gets a *different* scrambled code in the hospital's file than in the bank's file — so even if someone lines the two files up side by side, they can't tell it's the same person.
4. **pet_pipeline** — Blur or remove details so a file stays useful for its purpose but stops being identifying: an exact birthdate becomes "30–39 years old," an exact postcode becomes a wider area, a rare detail gets grouped with similar ones.
5. **text_redactor** — Scan through written notes (a doctor's notes, a support-chat transcript) and black out any name, phone number, or ID number someone typed into the free text by hand.
6. **release_writer** — Package up the final, protected files that actually go out the door. Also keeps a private "answer key" for our own records — never shared with anyone — that lets us trace a protected row back to the original if we ever need to check our own work.
7. **mosaic_check** — *(The new safety test this project adds.)* Take every file we're about to send out and try to play the attacker ourselves: attempt to match the same person across the hospital's file, the bank's file, the energy company's file, and the phone company's file. If any match succeeds, we catch it before the files ever leave the building, instead of an outsider catching it later.
8. **eval_runner** — Run the official "report card" that comes with the challenge's own toolkit, scoring how private and how useful each file is on its own. This is the same test every other team in the competition has to pass.

The short version: steps 1–2 figure out the rules and what's risky; 3–6 actually apply the protection; 7–8 are the two checks that both have to pass before anything is sent — 7 asks "can someone combine our files to find a person," 8 asks "does each file on its own meet the privacy bar."

### 4.3 What is reused versus net-new — the short version

| Pack asset | How the MVP uses it |
|---|---|
| `metadata/scenarios.json` | Reused as the configuration source for component 1. Not copied, not edited. |
| `metadata/field_catalog.csv` | Reused twice: PET selection, and as the glue-key index for the mosaic checker. |
| `metadata/attack_specs.json` | Reused **indirectly** — it drives the scorecard's `linkage re-identification` component. We do **not** extend it: it cannot express a cross-controller join (every `"dataset"` is a scalar), and it is vendored. Our custom entry lives in a project-owned overlay (§5a). |
| `toolkit/pets_eval` CLI | Reused as the scorer. The real subcommands are `scorecard`, `detect`, `text`, `check`, `tasks`, `scenarios` (`toolkit/pets_eval/cli.py:110-147`). There is **no `pets-eval attacks` subcommand** — `attacks` is a Python module (`toolkit/README.md:27-29`), importable but not callable from the CLI. |
| `toolkit/pets_eval/check.py` | Imported as a library: `PATTERNS`, `hetu_ok`, `iban_ok`, `luhn_ok`. |
| `toolkit/pets_eval/attacks.py` | Imported for the demo only: `hash_dictionary_attack` (`:517`) and `enumerate_hetu` (`:548`) prove R4 — that an unsalted HETU digest is reversible. |
| `truth/*.csv` | **Private verification only.** Used to confirm a join is a genuine mosaic (`IDEA.md:21`, `:96`). Never shipped in a release or a submission. |
| **Net-new** | Components 3, 4, 5, 6, 7 — above all `scripts/mosaic_check.py`, the only thing that measures the attack the pack cannot see. |

**See §8** for a proposed agentic validation layer built on this architecture. It adds no component to the eight above and changes none of them: it sits between component 6's staged output and the gates in components 7 and 8, as advisory triage in front of a gate that does not move.

---

## 5. Process for handling a novel attack or scenario

Attack A is novel against the pack's metadata and tooling, so we need a repeatable way to carry such a finding without forking the vendored pack. All three parts below use project-owned paths only.

### 5a. Recording it without editing the vendored pack

Create these three project-owned paths. Nothing under `resources/TRUSTED_SinceAI2026_FINAL/` is modified.

| Path | Role |
|---|---|
| `findings/custom_attacks.md` | **Human-readable register of novel attacks.** One section per attack with a project-local ID. First entry: `ATTACK-A-MOSAIC` — one-line summary, the three join keys, the measured overlaps, which requirement it produced (R1-R11 in §2), which check enforces it, and the date measured. Links back to `findings/IDEA.md` and to this plan. |
| `custom_metadata/attack_specs.custom.json` | **Machine-readable overlay, same shape as the pack's file but with one deliberate schema extension**: `"datasets": ["health","finance","energy","customer_service"]` — a *list* where the pack has a scalar `"dataset"` — plus `"join_keys": ["hetu","phone","iban"]`, `"baseline_counts": {...}` with the seven verified numbers, and `"check": "scripts/mosaic_check.py"`. Carries an explicit `"note"` field: *"Read only by scripts/mosaic_check.py. pets-eval does NOT read this file and the schema is intentionally incompatible with metadata/attack_specs.json — never merge or copy it into the vendored pack."* |
| `scripts/mosaic_check.py` | The executable check (§5c). |

**Cross-referencing in the safe direction.** We cannot add a pointer inside the pack, so the pointer goes *outward* from a file we own: add a short "Project-owned additions to the challenge pack" section to **`resources/NOTE.md`** — which sits at `resources/NOTE.md`, *above* the vendored `TRUSTED_SinceAI2026_FINAL/` tree and is therefore ours — listing the three paths above and stating that the pack itself is unmodified. Anyone who opens `resources/` to look for pack extensions finds the pointer without a single byte of the pack changing.

### 5b. The recurring loop for future novel attacks

Six steps, each with an owner artefact. Kept deliberately light — this must survive a hackathon week.

1. **Discover.** Notice a capability the pack does not score. Trigger: a new adversary file, a new release, a new dataset pair, or a scenario added to the MVP.
2. **Document in `findings/`.** One topic file with the attacker view first and `file:line` evidence — the `findings/IDEA.md` pattern, per `findings/README.md:8-14`. Measure the overlap; a finding without a number is an opinion.
3. **Derive the requirement.** Add rows to the §2 table: attack step → requirement → ID. If a step produces no requirement, say so and why.
4. **Add or extend a check.** Prefer extending `scripts/mosaic_check.py`; add a new script only for a genuinely different attack class. Register it in `findings/custom_attacks.md` and `custom_metadata/attack_specs.custom.json`.
5. **Re-run against protected output.** Both gates: the new/extended check *and* `pets-eval scorecard --scenario <ID>` for every affected dataset (a mosaic fix must not silently destroy scenario utility).
6. **Record the result.** Append the measured numbers, the date and the commit to `findings/custom_attacks.md`. Record failures too — a check that found nothing is only meaningful if its positive control passed.

### 5c. How and when to test for it — `scripts/mosaic_check.py`

**When it runs.** On every protected-output change, and immediately after each `pets-eval scorecard` pass. It is the second of two gates: the scorecard answers "is each release defensible alone?", the mosaic check answers "are they defensible together?". Neither verdict substitutes for the other.

**Inputs**

1. Every release directory under `clean_data/` (MVP: four — `health__HEALTH-S1`, `finance__FIN-S2`, `energy__ENERGY-S3`, `customer_service__CS-S1`).
2. The glue-key index from `metadata/field_catalog.csv`: columns where `privacy_role=direct_identifier` and `subtype` in `{NATIONAL_ID, PHONE, IBAN, EMAIL, PAYMENT_CARD}`.
3. Raw `data/health`, `data/finance`, `data/energy`, `data/customer_service` — for the positive control only.

**Algorithm**

1. Read every CSV with `dtype=str` (R1).
2. Per release, build a typed value set. Three sources, union of all three:
   - **catalogued glue columns** that survived into the release;
   - **any column** whose values match `pets_eval.check.PATTERNS` for `NATIONAL_ID` / `IBAN` / `PHONE` / `EMAIL` / `PAYMENT_CARD`, validator-confirmed by `hetu_ok` / `iban_ok` / `luhn_ok` — this catches a key that slipped through under an unexpected name;
   - **values extracted from free-text columns** by the same patterns — this is what catches CS-S1's residual 2 %.
   Also collect every pseudonym/token column as its own type, so key reuse across releases shows up as a token-value collision.
3. Normalise exactly as in R2: phones → strip non-`[0-9+]`, `^\+358`→`0`, `^00358`→`0`; IBANs → strip spaces, uppercase; HETU → string as-is. Discard empties.
4. For each of the 6 unordered release pairs × each type, compute `|A ∩ B|` on non-empty values.
5. Run the same code over raw `data/` as the positive control.

**Pass criteria — both must hold**

- **PASS-1 (the gate).** Every pairwise intersection count is **0**. In words: *the join count on hetu / phone / iban across every pair of released outputs must be 0, including values recovered from free text and including pseudonym-token collisions.*
- **PASS-2 (the positive control — this is what makes PASS-1 mean anything).** The identical code run against the **unprotected** `data/` must reproduce the seven verified baselines: HETU health∩finance **1622**, phone health∩finance **1484**, phone health∩CS **2296**, phone health∩energy **195**, HETU health∩energy **194**, IBAN energy∩finance **15**, IBAN finance∩CS **150**. Any deviation means the checker's normalisation is broken, and **PASS-1 must be treated as meaningless** — a checker that can find nothing always reports zero.

PASS-2 exists because PASS-1 passes vacuously in two failure modes that look identical to success: a checker whose normaliser is wrong, and a release pipeline that wrote empty tables. The positive control distinguishes a working defence from a broken instrument.

**Outputs**

- `clean_data/mosaic_check.json` — per pair and per type: `{count, verdict}`; a `positive_control` block with expected vs observed for all seven baselines; an overall `PASS` / `FAIL`.
- Exit code `0` on pass, non-zero on either failure, so it can gate a commit or a demo.
- A console table of the 6 pairs × 3 key types.

**Never** publish `truth/*` person IDs or `rowmap_*.csv` in this report. Private verification against `truth/` (the 19 people in health ∩ energy ∩ finance) may be used locally to confirm a demo join is a real mosaic (`findings/IDEA.md:96`), and stays out of any submission.

---

## 6. Milestones

| M | Deliverable | Done when |
|---|---|---|
| **M0** | **Scenarios locked and baselines captured.** Record the four IDs from §3.1 with their recipient, trust level and privacy targets. Reproduce the seven Attack A baseline counts from raw `data/` with the R2 normalisation. | The script prints 1622 / 1484 / 2296 / 195 / 194 / 15 / 150 and `19` for the `truth` triple overlap. This is the pre-fix "before" number for the demo. |
| **M1** | **Per-recipient HMAC pseudonymiser** (component 3). Master secret in gitignored `keys/`, subkey per `(dataset, scenario_id)`, normalise-then-HMAC, 16-hex tokens. | Unit tests: (a) the same HETU under HEALTH-S1 and FIN-S2 yields **different** tokens (R3, R11); (b) `+358443547786` and `0443547786` yield the **same** token within one release (R2/R3); (c) tokens are stable across two runs; (d) no unsalted digest is reachable from any code path (R4). |
| **M2** | **Scenario-driven PET pipeline** (components 1, 2, 4, 5, 6) for all four datasets → four release folders with row maps. ENERGY-S3 **drops** the person key rather than tokenising it (R5). IBAN tokenised consistently across `customers.iban`, `transfers.from_iban`, `transfers.to_iban` if `transfers` is released (R7). | Four folders exist under `clean_data/`, each with the original table filenames plus `rowmap_<table>.csv`; `pets-eval check clean_data/<dir>` reports no residual direct identifiers. |
| **M3** | **`scripts/mosaic_check.py` + its test.** Both pass criteria from §5c implemented, including free-text extraction and token-collision detection. | Positive control reproduces all seven baselines (PASS-2) **and** all 6 pairs × 3 types report 0 against `clean_data/` (PASS-1). Exit code 0. A deliberately key-reusing release must make it exit non-zero. |
| **M4** | **Wire up the pack scorer.** Four `pets-eval scorecard --original data/<ds> --protected clean_data/<ds>__<SID> --scenario <SID>` runs, plus `pets-eval detect` and `pets-eval text` for the redaction targets. | Four `scorecard.json` + `scorecard.html` produced; each scenario's required utility tasks are answerable (not scoring 0 for "not answerable", `docs/EVALUATION.md:38`); free-text recall meets HEALTH-S1's ≥0.95 and CS-S1's ≥0.98. |
| **M5** | **Demo + residual risk.** The four-step story from `findings/IDEA.md:112-117`: two safe-looking extracts → the join yields one enriched row → the same join against the protected releases returns 0 → one normal scorecard shown as self-assessment, with mosaic stated as an extra risk measured by hand. Covers the five jury items (`docs/PET_PLAYBOOK.md:37-41`). **Stretch:** add ENERGY-S2 as a fifth release and show that two releases of one dataset still join to 0 (R11). | Demo runs end to end from a clean checkout; §7 is presented verbatim, not softened. |
| **M6** | **Benchmark visualisations** — `scripts/make_benchmark.sh` (§9.2 step 4) renders the five figures **B1-B5** of §9.1 with `matplotlib` + `seaborn` into a project-owned `benchmarks/` directory, reading only `clean_data/` and the read-only original `data/` (OPS-1, §9.3). Depends on **M3**'s `clean_data/mosaic_check.json` and **M4**'s four `scorecard.json`, not on M5, so it can be built in parallel with M5 — and its figures are what M5's demo shows. | All five figures are produced as static PNG/SVG from one non-interactive invocation with no browser in the path; **B1** shows 1622 / 1484 / 2296 / 195 / 194 / 15 / 150 before and 0 after; every number in every figure is read from `mosaic_check.json`, a `scorecard.json` or `pets-eval text` output, and none is typed in by hand; no figure or caption reads `truth/*` or `rowmap_*.csv` (§5c); and the OPS-1 manifest verifies identical before and after the run. |

---

## 7. Residual risk

What the MVP does **not** close. Stated honestly, because `docs/PET_PLAYBOOK.md:41` makes "which attacks still work, at what rate" a jury item, and because a green mosaic check is a narrow claim.

| ID | Residual risk | Why the MVP does not close it | Deferred to |
|---|---|---|---|
| **R-1** | **Cross-release quasi-identifier mosaic.** Keyed tokens break *identifier* joins but leave probabilistic matching on birth date / age band / postcode / sex / municipality / employer. The catalog says so: `date_of_birth` is "Redundant with `patient_hetu`" (`field_catalog.csv:5`), energy `birth_date` "Complements hetu: the two columns together cover everyone" (`:133`), `employer` "Small employers + city + age often unique" (`:174`). `docs/PET_PLAYBOOK.md:20` warns that exact date plus postcode and sex is "often unique", and Sweeney's 87 % figure is cited at `:45`. HEALTH-S1's and ENERGY-S3's `k>=5` are **within-release** guarantees; the cross-release equivalence class can be smaller than either. `findings/IDEA.md` does not raise this, and no PET in its `:100-109` table addresses it. | Post-MVP: extend `mosaic_check.py` to report cross-release QI equivalence-class sizes and treat `k_cross < 5` as a warning. |
| **R-2** | **Free-text residual leakage.** CS-S1 targets recall **≥ 0.98** (`docs/SCENARIOS.md:291`), i.e. ~2 % of glue spans survive by design. Against 2 296 shared phones (`findings/IDEA.md:53`) that is roughly **46 individuals still joinable** from text alone. The precondition at `IDEA.md:71` is "at least one of phone / hetu / iban" — one surviving span per person is enough. | Post-MVP: raise the target toward 1.0 for the three glue types specifically, with validator-confirmed recall measured per type rather than averaged. |
| **R-3** | **Key-propagation gaps across tables.** `finance,transfers,from_iban` / `to_iban` re-expose customer IBANs (`field_catalog.csv:206`, `:208`); health's `patient_hetu` is named differently from everyone else's `hetu`. A hardcoded column name silently exempts a table from both the pipeline and the check. | Mitigated in M2/M3 by driving everything from the catalog, never from literals. Residual: an *uncatalogued* column in a new table. |
| **R-4** | **Behavioural re-linkage.** Hourly meter series plus known absence (`adversary/vacation_posts.csv`) and ED arrival timestamps can re-link the same household without any identifier. `docs/THREAT_MODEL.md:30` notes `vacation_posts.csv` is **not scored automatically**; `findings/IDEA.md:32` calls meter readings "behaviour after identity bind". Out of scope per §3.3 item 4. | Post-MVP, if `meter_readings_hourly.csv` is ever released. |
| **R-5** | **Key compromise.** The entire defence rests on `findings/IDEA.md:19` and `docs/THREAT_MODEL.md:46` — the attacker does not know our keys. A leaked `keys/master.key` restores global linkability across all four releases retroactively, because the tokens are deterministic. The MVP uses a local gitignored keyfile, not a KMS, and does not rotate. | Post-MVP: KMS/HSM custody, per-release rotation schedule, documented re-issue procedure. |
| **R-6** | **The pack's blind spot persists, and our check is unofficial.** `pets-eval` will still score a mosaic-vulnerable release as low-risk: every risk component in `docs/EVALUATION.md:22-34` is computed inside one `(original, protected)` pair and `run_scorecard` fixes `domain = original_dir.name` (`scorecard.py:290`). Meanwhile the organisers hold a **stronger private attacker set** including "a data-broker profile" (`docs/THREAT_MODEL.md:34-42`), which may well span domains. A green `mosaic_check.json` means "our four releases do not join on the three keys we tested" — not "no cross-domain attack works". | Ongoing: keep the §5b loop running as new adversary capabilities surface. |
| **R-7** | **Recipient collusion is governance, not a PET.** HEALTH-S1 and ENERGY-S3 both go to "a university research group" (`docs/SCENARIOS.md:11`, `:138`). If it is the *same* group, separate key domains stop token joins but cannot stop a recipient legitimately holding both extracts and matching on R-1's quasi-identifiers. `findings/IDEA.md:22` names controllers as secondary victims for exactly this reason. | Post-MVP: data-use agreements, a release register per recipient, and a "has this recipient already received another domain?" pre-release gate. |
| **R-8** | **FIN-S1 stays open by design.** Its target is a shared consortium HMAC key so one card links across banks, and its note insists "Linkability across banks is the point" (`docs/SCENARIOS.md:156-157`). That is structurally the condition Attack A exploits, deliberately chosen for fraud prevention. The MVP excludes it rather than pretending to solve it. | Post-MVP: a scoped analysis of what a consortium key *must* cover, and a proof that the key domain is bounded to PAN/device/IP and never reaches HETU, phone or IBAN. |
| **R-9** | **Minimisation is not audited.** `findings/IDEA.md:108` — "don't ship contacts when the scenario only needs aggregates or coarse QIs" — is applied by hand per scenario (ENERGY-S3 drops the person key under R5). Nothing automatically flags a column that was tokenised when it should have been dropped. Every tokenised key is join surface that survives only while the key stays secret (cf. R-5); a dropped key is join surface that is gone. | Post-MVP: a minimisation linter that cross-checks released columns against the scenario's `utility_requirements`. |

### The MVP's honest claim

> Against an attacker with our four protected releases, no public adversary file, and no access to our keys, the measured cross-release join count on HETU, phone and IBAN is **0**, down from a baseline of **1622 / 1484 / 2296 / 195 / 194 / 15 / 150** on the unprotected data — while each release still passes `pets-eval scorecard` for its own scenario.

Everything in the table above sits outside that sentence. That is the point of stating it so narrowly.

**See §8** for a proposed LangGraph agent layer aimed at narrowing `R-2`, `R-3`, `R-6` and `R-9` above — advisory only, with its own residual risks numbered `AR-1`…`AR-6` in §8.5, and with the gate in §5c left exactly where it is.

---

## 8. Agentic validation layer (LangGraph) — proposed, not built

Same convention as the rest of this plan: this is a design to be reviewed before anything is written. No LangGraph code exists yet and none is implied by §6's M0–M5.

The brief was: *where can AI agents help here, and does §4 need redesigning to fit them?* The answer below is deliberately conservative, because the subject matter is Art. 9 personal data and because §7 already states how narrow the MVP's claim is. **The deterministic gate does not move.** `scripts/mosaic_check.py` PASS-1 + PASS-2 (§5c) and `pets-eval scorecard` / `pets-eval check` (R8) remain the only things that can call a release safe. The agent layer is **advisory triage placed in front of that gate** — validate-before-test, never validate-instead-of-test.

LangGraph is fixed (§8.7). Everything else in the stack is open and is listed as such.

### 8.1 Where agents help — and where they must not

The rule applied here: **an agent is only proposed where this document already admits a gap.** If a step is solved deterministically, it stays deterministic. Every row below points at a specific `R-n` from §7 or a specific step of §5b; no row introduces a new vocabulary.

| § 4.2 step | Status today | Agent? | Gap it would narrow | Proposed node |
|---|---|---|---|---|
| **1** `scenario_loader` | A JSON lookup against `metadata/scenarios.json`. Exact, 27 known entries. | **No** | None admitted. | — |
| **2** `field_classifier` | Exact for the 476 catalogued columns. | **Yes, narrowly** | §7 **R-3**'s stated residual: "an *uncatalogued* column in a new table." A column absent from `metadata/field_catalog.csv` is silently exempt from both the pipeline and the check. | `classify_assist` |
| **3** `pseudonym_service` | HMAC-SHA-256, keyed, normalise-then-hash. | **No — and never** | None. See the prohibition below. | — |
| **4** `pet_pipeline` | Deterministic once the scenario's targets are fixed. | **Yes, narrowly** | §7 **R-9**: "Minimisation is not audited … Nothing automatically flags a column that was tokenised when it should have been dropped" (R5). | `minim_assist` |
| **5** `text_redactor` | `check.PATTERNS` + `hetu_ok` / `iban_ok` / `luhn_ok` + a NER pass. | **Yes** | §7 **R-2**: CS-S1 targets recall ≥ 0.98 *by design*, i.e. ~2 % of glue spans survive — "roughly **46 individuals still joinable** from text alone." | `redact_assist` |
| **6** `release_writer` | File I/O. | **No** | None. This is the step closest to the irreversible action; it stays dumb on purpose. | — |
| **7** `mosaic_check` — the PASS-1/PASS-2 arithmetic | Set intersection and a positive control. Exact. | **No — and never** | None. See the prohibition below. | — |
| **7** `mosaic_check` — *which hypotheses it tests* | Fixed by hand: 6 pairs × 3 key types. | **Yes** | §7 **R-6**: a green `mosaic_check.json` means "our four releases do not join on the three keys we tested", not "no cross-domain attack works". Also §7 **R-1** (cross-release QI mosaic) and **R-4** (behavioural re-linkage), both deferred. | `discover_assist` |
| **8** `eval_runner` | Shells out to `pets-eval`. Exact. | **No** for scoring; **yes** for explaining | §4.2a exists precisely because the numbers need a plain-English form "for whoever has to explain or approve it", and M5's done-criteria are the five jury items (`docs/PET_PLAYBOOK.md:37-41`). Nothing in M4/M5 turns `scorecard.json` + `mosaic_check.json` into that brief. | `brief_writer` |
| **§5b step 1 — "Discover"** | Purely manual: "Notice a capability the pack does not score." | **Yes** | The loop's own entry point has no tooling. Steps 2–6 then stay human/deterministic, unchanged. | `discover_assist` |

**Where an agent must not go, stated as plainly as §7 states its risks.**

- **Component 3, `pseudonym_service`.** Two independent reasons, either sufficient. (i) **Determinism is a correctness requirement, not a preference**: M1's acceptance tests demand that one HETU yield the *same* token across two runs and that `+358443547786` and `0443547786` collapse to one token (R2/R3/R11). A model cannot be given that property. (ii) **Putting a raw `hetu` / `phone` / `iban` in a prompt sends a catalogued `direct_identifier` to a third party** — the exact disclosure R4 and R10 exist to prevent. An LLM has no business in this path and §8.5 AR-4 makes the rule general.
- **Component 7's PASS-1/PASS-2 arithmetic.** PASS-2 exists because "a checker that can find nothing always reports zero" (§5c). Its whole value is that it is a *broken-instrument detector*. An instrument whose readings depend on a sampled model is not a control. The counts, the comparisons against 1622 / 1484 / 2296 / 195 / 194 / 15 / 150, and the exit code are arithmetic and stay arithmetic.
- **Component 6's write and the hand-off to a recipient.** See the invariant at the end of §8.5.
- **§7 R-5 (key compromise), R-7 (recipient collusion), R-8 (FIN-S1).** No agent is proposed for any of these. R-5 is key custody; R-8 is out of scope by design (§3.3 item 2); R-7's own deferral already names the right fix — "a release register per recipient, and a 'has this recipient already received another domain?' pre-release gate" — which is a lookup against a table we own, not a judgement call. Proposing an agent there would be padding.

### 8.2 Redesigned data flow

§4's eight components are **unchanged**: nothing is added to the §4.2 table, nothing is removed, and no component changes its inputs or outputs. The agent layer is a new band that sits between component 6's staged output and the gate in components 7–8.

```text
   DETERMINISTIC PIPELINE (§4.2) -- UNCHANGED BY THIS SECTION
   [1] scenario_loader   [2] field_classifier   [3] pseudonym_service
              |                     |                       |
              +----------+----------+-----------------------+
                         v
              [4] pet_pipeline <---> [5] text_redactor
                         |
                         v
              [6] release_writer
                         |
                         |  staged candidate release -- written locally,
                         |  NOT yet handed to any recipient:
                         |  clean_data/<ds>__<SID>/*.csv + rowmap_<tbl>.csv
                         v
 - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
   AGENT ORCHESTRATION LAYER -- LangGraph StateGraph      [PROPOSED, §8]
   reads the candidate; emits ONLY proposals and a brief; has no write
   access to clean_data/ and cannot alter any exit code
 - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
            +-------------------------+
   START -->| supervisor / router     |   add_conditional_edges: which
            +------------+------------+   specialists are in scope for
                         |                this (dataset, scenario_id)?
     +----------+-------+--+----------+
     v          v          v          v
 +--------+ +--------+ +--------+ +--------+
 |classify| | redact | |discover| | minim  |
 |_assist | |_assist | |_assist | |_assist |
 |        | |        | |        | |        |
 |  R-3   | |  R-2   | | R-6 +  | |  R-9   |
 |        | |        | | §5b.1  | |        |
 +--------+ +--------+ +--------+ +--------+
     +----------+-------+--+----------+
                         |
                         v
            +---------------------------------+
            | human_review  <-- interrupt()   |   §8.4 -- PRE-TEST REVIEW
            | state persisted by the          |   no reply / timeout
            | checkpointer; resumes on        |   => REJECT (fail closed)
            | Command(resume=...)             |
            +--+---------------------------+--+
               |                           |
   resume = accept(subset)      resume = proceed
               |                           |   (candidate untouched)
               v                           |
   re-run [2][4][5][6] DETERMINISTICALLY   |
   with the accepted proposal applied as   |
   an INPUT, never as an edit to the       |
   output: agents edit INPUTS, never       |
   OUTPUTS. Produces a NEW staged          |
   candidate, which re-enters at START.    |
                                           |
                                           v
            +-------------------------------------------+
            | THE RELEASE GATE -- UNCHANGED (§5c, R8)   |
            | [7] mosaic_check.py: PASS-1 AND PASS-2    |
            | [8] pets-eval scorecard + pets-eval check |
            | deterministic; no LLM anywhere in here    |
            +---------------------+---------------------+
                                  v
            +-------------------------------------------+
            | brief_writer (numbers only) -> the brief  |
            | human_signoff <-- interrupt()      (§8.4) |
            +---------------------+---------------------+
                                  v
            hand the release to the recipient
            -- the only irreversible action in this diagram
```

Three properties of that picture are load-bearing.

1. **Validate before test, not instead of test.** The agent pass runs on a *staged* candidate and finishes before the gate is trusted. Its output is a set of proposals and a reject/proceed decision — it can delay a release, never pass one.
2. **The gate keeps its authority.** The node that runs components 7 and 8 is a plain subprocess call — exactly the two commands in §4.2 row 8 — with no model in it. It copies the exit code into graph state; a conditional edge on a non-zero exit routes to `END` with a failure. The graph cannot rewrite that code. And the gate stays runnable **standalone**, by hand, with the whole agent layer switched off; §8.6 A4 requires that this be demonstrated, so the gate's independence is a tested property rather than an assertion.
3. **Agents edit inputs, never outputs.** An accepted proposal becomes a committed artefact (a catalog-overlay row, a span list, a PET-config change) and the deterministic pipeline re-runs from it. No agent ever mutates a file under `clean_data/`. This is what makes a release reproducible from the artefact without re-invoking a model (§8.5 AR-2).

### 8.3 Agent roles — the proposed LangGraph nodes

Six nodes: one router and five specialists. Each specialist maps to exactly one admitted gap from §8.1; there is no node here that does not.

| Node | Augments | Gap (§7 / §5b) | Reads | Proposes | Who acts on the output | Explicitly **not** trusted to |
|---|---|---|---|---|---|---|
| `supervisor` | orchestration only | — | The `ScenarioSpec` from component 1 and a manifest of the staged candidate (table and column *names*, row counts). | Which specialists are in scope for this `(dataset, scenario_id)`. | LangGraph's `add_conditional_edges` routing. | Skip `human_review`, skip the gate, or shorten the graph past either. Routing may select specialists; it may not select whether the release is checked. |
| `classify_assist` | **2** `field_classifier` | **R-3** | Table and column *names*, dtype, and **value-shape summaries only** — length histograms, charset classes, and `check.PATTERNS` hit counts — for columns **absent** from `metadata/field_catalog.csv`. **No raw values** (AR-4). | A candidate `privacy_role` + `subtype` row for each uncatalogued column, drawn from the catalog's existing closed vocabulary. | A human accepts it into a **project-owned overlay**, e.g. `custom_metadata/field_catalog.custom.csv` — following §5a's precedent for `attack_specs.custom.json`. The vendored `metadata/field_catalog.csv` is **never edited** (§3.3 item 7). Component 2 then re-reads deterministically, and the labels are scored with `pets-eval detect --pred <labels.csv>` (§4.2 row 2). | Downgrade or relax a label the catalog already carries. Its output may only **add** a column or **escalate** a role; a proposal that would weaken an existing `direct_identifier` label is dropped before the human sees it. |
| `redact_assist` | **5** `text_redactor` | **R-2** | The free-text columns, **as untrusted data** (AR-1): `health/clinical_notes.note_text`, `customer_service/turns.text`, `customer_service/conversations.agent_note`, `energy/customers.dso_notes`, `finance/transfers.message`. | **Additional candidate spans only** — offset, length, type — beyond what `check.PATTERNS` and the validators already found. | Spans are **unioned** into component 5's span set and scored by `pets-eval text --gold metadata/pii_spans/... --pred <spans>`, with recall measured **per glue type** rather than averaged (that is R-2's own stated deferral). | Delete, shrink or override a span the deterministic pass produced — the union is one-directional. It is also not trusted to declare HEALTH-S1's ≥ 0.95 or CS-S1's ≥ 0.98 met; `pets-eval text` decides that. |
| `discover_assist` | **§5b step 1**, and component **7**'s hypothesis space | **R-6**, **R-1**, **R-4** | `metadata/field_catalog.csv` (above all its `traps` column), the release manifests, the history of `clean_data/mosaic_check.json`, and `docs/THREAT_MODEL.md:34-42`'s list of the stronger private attacker set. | A **ranked list of testable hypotheses**: a candidate join key not yet in the 3-key set, a QI tuple worth measuring for R-1, an adversary-file pairing, each with a proposed baseline measurement. | A human picks one and runs §5b steps 2–6 unchanged: document in `findings/`, derive a requirement into §2, extend `scripts/mosaic_check.py`, re-run both gates, record the measured numbers in `findings/custom_attacks.md`. | Produce a count, touch `scripts/mosaic_check.py`, or declare any attack infeasible. §5b step 2 is the binding rule: "a finding without a number is an opinion." A hypothesis is not a measurement. |
| `minim_assist` | **4** `pet_pipeline` (its R5 decisions) | **R-9** | The scenario's `utility_requirements` and `suggested_privacy_targets` prose, plus the released column list — **names only**. | Columns that were **tokenised** but appear unused by the stated utility requirement, i.e. candidates for an R5 **drop** instead. | A human decides; if accepted, the scenario's PET config changes and components 4 and 6 re-run. | Drop a column itself, or assert that a column *is* needed. One-directional by design: it may only propose **removing** join surface, never retaining it. R-9's own reasoning — "a dropped key is join surface that is gone" — is why the asymmetry is safe. |
| `brief_writer` | **8** `eval_runner`'s output | §4.2a's stance; M5's jury items | `scorecard.json`, `clean_data/mosaic_check.json`, and the staged release manifest — **aggregate numbers only, no row data**. | A plain-English brief in §4.2a's register: what passed, which of §7's rows apply to this release, what the claim does and does not cover. | The human at `human_signoff` reads it **beside** the raw JSON, never in place of it. | Be the record. The JSON is the record. A brief whose numbers disagree with the JSON is a defect in the brief, and the JSON wins (AR-6). |

Note on `redact_assist`'s input list: §2 **R6** names five free-text columns, and all five are listed above. §4.2's component 5 declares only four as inputs — `customer_service/conversations.agent_note` is absent from that list. That omission is recorded here rather than silently patched; it is a candidate M2 follow-up, and `discover_assist` should be expected to re-surface it.

### 8.4 The human-in-the-loop checkpoint

**Mechanism.** LangGraph's documented primitive for this is a **graph interrupt**: calling `interrupt()` inside a node pauses execution at that point, persists the full graph state through a configured **checkpointer**, and surfaces a payload to whoever is running the graph; execution later resumes by passing **`Command(resume=...)`** back in — `resume=True` / `False` for approve / reject, or an edited value for review-and-edit. A checkpointer is mandatory for this to work (`InMemorySaver` in development, a durable backend in anything real), and the paused state is addressed by `config={"configurable": {"thread_id": ...}}`. Consulted: LangChain's LangGraph documentation on interrupts and checkpointers, and its graph-API reference for `StateGraph` / `add_node` / `add_edge` / `add_conditional_edges` / `compile(checkpointer=...)` — <https://docs.langchain.com/oss/python/langgraph/interrupts>, <https://docs.langchain.com/oss/python/langgraph/checkpointers>, <https://docs.langchain.com/oss/python/langgraph/use-graph-api> (checked November 2026). No other LangGraph API is named in this section; anything beyond this list should be re-verified against the docs before it is written down.

**Placement.** Two interrupts, one per phase.

1. **`human_review` — the pre-test checkpoint.** It sits on the single fan-in from every specialist, and it is the **only** path from the agent layer onward. No node that re-runs the deterministic pipeline, and no node that invokes the gate, is reachable without passing through it. This is the "validate first" gate: it reviews proposals *before* anything is re-run and *before* the gate is trusted.

   It is handed a diff-shaped payload: every proposed overlay row from `classify_assist`; every additional span from `redact_assist`, each tagged with its source column and marked as derived from untrusted text (AR-1); every proposed R5 drop from `minim_assist`; every hypothesis from `discover_assist`; and the provenance of all of it — model identifier, prompt version, and a hash of the staged candidate release.

   Four legal resume values: **accept-all**, **accept-subset**, **edit**, **reject**. Accepting anything triggers a deterministic re-run of components 2/4/5/6 and produces a *new* staged candidate, which re-enters the graph at `START`; it never edits the existing candidate in place. Rejecting leaves the candidate untouched and proceeds to the gate.

   **Fail closed.** If no human resume value arrives — unattended run, timeout, CI — the only legal outcome is **reject**. An agent proposal that nobody adjudicated is never applied. This is the behavioural difference between "a human is in the loop" and "a human was notified".

2. **`human_signoff` — the post-test release authorisation.** After the gate node has returned and `brief_writer` has produced its brief. Its payload is the raw exit codes, PASS-1's per-pair counts, PASS-2's expected-vs-observed table for all seven baselines, the four scorecards, **and** the brief — in that order, numbers first. Resuming here is what authorises handing the release to the recipient. Because it is an `interrupt()`, no agent and no routing decision can produce that resume value.

### 8.5 New residual risk this layer introduces (AR-1 … AR-6)

Numbered in the `AR-` series so these cross-reference the same way §7's `R-1`…`R-9` do. Stated as honestly as §7, for the same reason: `docs/PET_PLAYBOOK.md:41` makes "which attacks still work, at what rate" a jury item, and adding a model to a privacy pipeline adds attack surface.

| ID | New risk | Why it is real here, specifically | What bounds it |
|---|---|---|---|
| **AR-1** | **Prompt injection from attacker-authorable free text.** | `redact_assist` reads exactly the fields §2 **R6** flags, and two of them are authored by a party outside the controller: `finance,transfers,message` is "**Payer's** free-text message" (`field_catalog.csv:212`) and `customer_service,turns,text` is "**Utterance text** (chat, ASR transcript, or email body)" (`:476`). The §1.1 attacker can be the payer or the caller. The other three — `clinical_notes.note_text` (`:47`), `conversations.agent_note` (`:470`, "Agents copy ID codes, phone numbers … into notes"), `customers.dso_notes` (`:151`) — are staff-authored but transcribe what an outside party said. Poisoning this input requires no breach and no insider; it requires sending a bank transfer or opening a chat. | Treat every byte as **data, never instruction**. The node's output type is a **span list only** — offsets and types — a shape that cannot express an action. It gets no tools, no file-write, no network egress. Its spans may only **widen** redaction (§8.3), and the only things downstream of it are a human and `pets-eval text`. **Bound, stated plainly:** a successful injection can make `redact_assist` *miss* a span, degrading it to useless; it cannot make it *remove* one. Because component 5's `check.PATTERNS` + validators remain the floor, AR-1's worst case is **exactly R-2's existing residual, never worse** — and that bound holds only while the union-only rule holds. Break the union-only rule and this row becomes a critical finding. |
| **AR-2** | **Non-determinism on a sensitive decision path.** | The same candidate release, run twice, can yield two different proposal sets. If a proposal can reach a released artefact, the release stops being a function of its inputs — and §6 M1 demands reproducibility so strictly that "tokens are stable across two runs" is an acceptance test. Nothing in the agent layer can be given that property. | It is why the layer sits **outside** the gate and why no agent touches components 3, 6, or 7's arithmetic (§8.1). Every proposal is logged with model ID, prompt version and a hash of the candidate. The **accepted** proposal is committed as a deterministic artefact, so the release is reproducible **from the artefact** without ever re-running a model. The model is a source of suggestions, not a component of the build. |
| **AR-3** | **Hallucinated labels and fabricated evidence.** | `classify_assist` can invent a `subtype` outside the catalog's vocabulary; `discover_assist` can propose a join on a column that does not exist. Fluent and wrong is the failure mode that costs reviewer attention. | Validate mechanically **before** the human sees it, in the node's post-processing and not as a prompt instruction: closed-vocabulary check for labels, real-schema existence check for every column name, `clean_data/` path existence for every artefact referenced. Anything that fails is dropped and **counted** — the drop rate is part of the §8.6 A2 track record. Anything that cannot be mechanically validated is presented as a hypothesis, per §5b step 2. |
| **AR-4** | **Identifier and free-text egress to a model provider — a disclosure the §7 attacker never had.** | The agents read material this plan exists to protect. Sending a raw `hetu` / `phone` / `iban`, or a verbatim `note_text`, to a third-party endpoint is itself a disclosure — and it is the exact trust relationship CS-S1 already flags: "Cloud AI vendor (processor, outside the EU possible)" (§3.1). §7 has no row for this because §7's attacker never had access to our prompts, our logs or our traces. | A hard input contract. `classify_assist`, `minim_assist` and `brief_writer` receive **no row values** — names, schema, pattern-hit counts and aggregate numbers only. `redact_assist` and `discover_assist` do need text, so their deployment **constrains the hosting decision in §8.7**, and neither may ever be sent a catalogued `direct_identifier` column in the clear. The same contract binds everything derived: **graph state, the checkpointer's persisted state, the proposal log and any observability trace are all copies of their inputs** and inherit the rule. A trace of `redact_assist` would otherwise be a verbatim duplicate of `clinical_notes.note_text` sitting outside `clean_data/`. And `truth/*` and `rowmap_*.csv` never enter the agent layer at all, under §5c's standing prohibition. |
| **AR-5** | **Cost, latency, and the gate that gets skipped.** | §5c says the deterministic check runs "on every protected-output change" — a tight inner loop. Five specialists across four releases on that loop will be slow and expensive enough that, under hackathon pressure, it gets skipped. **A review step that is routinely skipped is worse than no review step**, because it creates a paper trail suggesting review happened. | Keep the agent pass **off** the inner loop: it runs per release *candidate*, not per edit. Components 7 and 8 stay standalone and remain the only things wired to a commit or demo gate (§5c: "so it can gate a commit or a demo"). Each run records a token and wall-clock budget in the proposal log, so "we skipped it because it was slow" becomes a measured claim rather than a habit. |
| **AR-6** | **Automation complacency — signing off on prose.** | §7's honest claim is deliberately narrow. A fluent brief from `brief_writer` invites a reviewer to approve the summary instead of PASS-1's counts, PASS-2's seven baselines, and the four scorecards. This risk grows precisely as the brief gets better. | The brief is always shown **beside** the raw JSON and must cite the numbers it describes. The `human_signoff` payload leads with raw exit codes and the expected-vs-observed baseline table, not with the brief's account of them (§8.4). A brief that disagrees with the JSON is a defect; the JSON wins. §8.6 A1 makes number-for-number agreement between brief and JSON its explicit done-criterion, for this reason. |

**The governing invariant. No agent output may trigger an irreversible action.** The irreversible action in this system is **handing a release to a recipient** — not writing to `clean_data/`, which is local staging. Nothing an agent proposes reaches a recipient without all four of:

1. a **deterministic re-run** of components 2/4/5/6 with the accepted proposal applied as an input (agents edit inputs, never outputs);
2. `scripts/mosaic_check.py` reporting **PASS-1 and PASS-2** per §5c;
3. `pets-eval scorecard` and `pets-eval check` per **R8**;
4. a human `Command(resume=...)` at **both** checkpoints in §8.4.

Remove any one of those four and the agent layer must be switched off. That is the condition under which §8 is safe to build, and it is not negotiable by a routing decision inside the graph.

### 8.6 Rollout — A0–A4, a parallel track that starts after M4

The agent layer starts with **no gating power at all** and earns its way forward. The A-milestones below are a **parallel track that begins after §6's M4**, not a replacement for any of M0–M5: the layer needs a candidate release (M2), a working mosaic check (M3) and real scorecard output (M4) before it has anything to read.

**The hard constraint on the relationship to §6: M5 must remain demonstrable with the agent layer entirely switched off.** If the M5 demo ever depends on an agent, the layer has acquired gating power by accident, and that is a defect to be fixed by removing the dependency — not by promoting the agent.

| A | Starts after | Deliverable | Mode | Done when |
|---|---|---|---|---|
| **A0** | **M4** | **Design review only — nothing runs.** This section reviewed, and each open item in §8.7 given a named decision. | No code. | Every row of §8.7 has a decision recorded, and §8.5's four-part invariant is accepted **as written**. Also agreed at A0 and written down: the accept-rate threshold a specialist must reach at A2 to advance. That number is a human judgement about acceptable reviewer load — it is set here deliberately and is **not** to be invented later or tuned to make A2 pass. |
| **A1** | A0 | **One specialist, no graph.** `brief_writer` only, run by hand against M3's `mosaic_check.json` and M4's four `scorecard.json`. Chosen first because it reads numbers, not data — the lowest AR-4 exposure in the set. | Advisory. Zero gating power. | A brief exists for all four releases, and a human has confirmed **every number in it matches the JSON**. Any mismatch is logged, not corrected silently (AR-6). |
| **A2** | A1 | **The graph exists, in shadow mode.** A `StateGraph` with `supervisor` + `classify_assist` + `minim_assist` + the `human_review` interrupt + `brief_writer`. These two specialists are chosen because neither needs row values (AR-4). Proposals are written to a project-owned path — e.g. `findings/agent_proposals/<date>__<ds>__<SID>.json` — and **nothing is applied**. | Shadow. Logs proposals, changes nothing. | Every specialist has a logged track record across all four releases; a human has adjudicated **every** proposal; the accept rate and the AR-3 mechanical-drop rate are both written down; and the accept rate meets the threshold agreed at A0. Plus the negative control: **PASS-1, PASS-2 and all four scorecards are byte-identical to M3/M4's** — proof the layer changed nothing. |
| **A3** | A2 | **Add the text-touching specialists, still in shadow.** `redact_assist` and `discover_assist`, i.e. the two carrying AR-1 and AR-4 exposure. Gated on A2's track record **and** on the §8.7 hosting decision being closed. | Shadow. Still no gating power. | `pets-eval text` recall **per glue type**, with the agent's unioned spans, is **greater than or equal to** deterministic-only recall for every one of the five free-text columns in §8.3 — this is the measured form of AR-1's stated bound, and a single column where it is lower means A3 fails and the union-only rule is broken. No proposal has ever been auto-applied. |
| **A4** | A3 | **Graduate to an advisory pre-test gate.** The agent pass becomes a required step in the release procedure: a candidate may not be presented at `human_signoff` until the pass has run and every proposal carries a recorded accept/reject decision. | Required, but **still not a release gate**: it can delay a release, never pass one. Components 7 and 8 remain the only things that can say PASS. | The release runbook names the agent pass as required; **and** the deliberately key-reusing release from M3's done-criteria is caught by component 7 *and* flagged by the agent pass; **and** a run is recorded in which component 7 still catches that release with the agent layer **disabled** — demonstrating the gate's independence rather than asserting it. |

There is no A5. Giving the agent layer power to **pass or block** a release is outside this plan and would need its own finding through §5b, including its own §2 requirement rows and its own entry in `findings/custom_attacks.md`.

### 8.7 Open tech-stack decisions, explicitly deferred

**Fixed, one decision only: LangGraph.** Specifically its `StateGraph` node/edge/state model, its conditional routing, and its checkpointer-backed `interrupt()` / `Command(resume=...)` pattern — which is the reason §8.4 can be specified concretely at all rather than hand-waved.

Everything else is open. These are listed, not chosen. Each carries the constraint any choice must satisfy, and in every case the constraint is **provider-agnostic by design** — which is what makes these genuinely deferred decisions rather than forced ones.

| Open decision | What any choice must satisfy |
|---|---|
| **LLM provider and model** | No output path into a release decision that bypasses §8.5's four-part invariant. For the text-touching specialists (A3): either self-hosting, or a processing agreement compatible with Art. 9 data (AR-4). Nothing in §8.1–§8.5 depends on a specific model's capabilities, so this choice is reversible. |
| **Whether a retrieval store is needed** | Only `discover_assist` might want one, for similar-past-attack lookup. Its corpus would be `findings/`, `metadata/field_catalog.csv`, and the `mosaic_check.json` history — all project-owned. It must index **no row data** from `data/` or `clean_data/`, and never `truth/*` or `rowmap_*.csv` (§5c). That corpus may simply be too small to need a store: decide **by measuring after A2** whether `discover_assist`'s proposals actually improve when given history, not by assuming they will. |
| **Hosting / runtime for the graph** | Must be somewhere the A3 specialists' raw free text may lawfully go — a local or self-hosted runtime satisfies this trivially; a hosted one inherits the provider question above. Must also support a **durable** checkpointer, because §8.4's interrupt can pause for hours waiting on a human. |
| **Checkpointer backend** | A sub-decision of hosting. Must survive process restarts, and the state it persists must contain **no raw identifiers and no raw free text** — only proposals, offsets, hashes and aggregate numbers (AR-4). This constrains what may appear in the graph's state schema, which is worth settling **before** any code is written rather than discovering it in a persisted store. |
| **Observability / tracing** | Traces must be redacted **by construction**, not by policy: an untreated trace of `redact_assist` is a verbatim copy of `clinical_notes.note_text` living outside `clean_data/`. Any tracing vendor inherits the same processor question as the LLM provider. |
| **Proposal-log location and format** | Must live in a project-owned path — §5a's rule stands, nothing under `resources/` is modified — and must be committable, because the accepted proposal **is** the reproducible artefact that AR-2 depends on. |

### The agent layer's honest claim

> Even at the most mature stage proposed here (A4), the sentence in §7 is unchanged. The release gate is still `scripts/mosaic_check.py` PASS-1 + PASS-2 and `pets-eval scorecard`, and the cross-release join count is still **measured**, not asserted by a model. The agent layer's own claim is far narrower: *it widened the set of hypotheses we tested and the set of spans we redacted, and it wrote down what it proposed so that a human could say no.*

Everything in §8.5 sits outside that sentence, for the same reason §7's table sits outside §7's.

---

## 9. Implementation workflow & tech stack

Sections 1-8 say what must be true of a release and what has to be measured. This section says what gets built, in what language, and in what order a human actually runs it. It adds **no** component to §4.2's eight and **no** node to §8.3's six: it is the operational packaging of what §6's milestones already deliver, plus one new milestone (**M6**) for the benchmark figures, plus one hard safeguard (**OPS-1**) that §3.3 item 7 and §5a already imply but never enforce.

### 9.1 Tech stack

**Core implementation language: Python.** This is a continuation, not a new decision. The vendored scorer is already a Python package — `toolkit/pyproject.toml` declares `name = "pets-eval"`, `requires-python = ">=3.10"` and the console script `pets-eval = "pets_eval.cli:main"` — and §4.2 already names Python for every net-new component: `hmac` + `hashlib.sha256` for component **3**, pandas with `dtype=str` everywhere for component **4** (R1), `pets_eval.check` imported as a library for component **5**, stdlib `csv` + `re` for component **7**. Writing the pipeline in anything else would mean re-implementing `check.PATTERNS` / `hetu_ok` / `iban_ok` / `luhn_ok` rather than importing them, which §4.3 explicitly rejects. The pack's own floor is Python ≥ 3.10 with `numpy`, `pandas`, `scipy`, `scikit-learn` (`toolkit/pyproject.toml`); the pipeline adds no runtime dependency beyond that.

The two shell scripts in §9.2 are **thin launchers only**: argument parsing, the OPS-1 check of §9.3, and a `python -m` call. No pipeline logic lives in shell.

**Benchmark-visualisation library: `matplotlib` + `seaborn` — recommended over `plotly`.** The reasoning is stated before any chart is specified, because it is the reason and not a post-hoc justification.

1. **Nothing in the pack has already chosen a plotting library, so this is a free choice and not a conflict.** Verified for this section: `grep -rniE "matplotlib|seaborn|plotly|kaleido|bokeh|altair"` over `resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/toolkit/` returns **no match at all**, and `toolkit/pyproject.toml`'s dependency list is exactly `["numpy>=1.24", "pandas>=2.0", "scipy>=1.10", "scikit-learn>=1.2"]`. The pack's only visual artefact, `scorecard.html`, is hand-written HTML string templating (`toolkit/pets_eval/scorecard.py:383`, its `_tile(...)` calls) with no charting library behind it. So this recommendation contradicts nothing already chosen and duplicates nothing already shipped.
2. **The deciding factor is that the output is a static artefact produced by a non-interactive script.** §9.2 step 4 is a shell script that runs to completion and leaves image files on disk — the before/after figure set for §6 **M5**'s demo and the five jury items at `docs/PET_PLAYBOOK.md:37-41`. matplotlib writes PNG/SVG straight from a headless process (`Agg` backend: no display, no browser). plotly's native output is an interactive HTML/JS figure; getting a static image out of it requires the extra `kaleido` dependency and a headless-browser round-trip — a second runtime to install and a second failure mode to debug, bought for an interactivity that nobody in this workflow consumes. If a live dashboard ever becomes a requirement, this decision should be revisited on its own terms; it is not one today.
3. **seaborn's defaults fit the shape of every comparison here with very little code.** All five figures below are either a grouped/paired bar (`barplot` with `hue`), a small-multiples grid (`catplot` with `col`), or a distribution overlay (`histplot` / `kdeplot` with `hue`) over a tidy pandas frame — and pandas is already a dependency. Nothing here needs a custom renderer.
4. **It keeps the figure path as boring as the gate.** §8.5 **AR-5**'s concern is that a step which is slow or awkward gets skipped under hackathon pressure. A plotting path with no browser in it is one that still runs on a laptop at demo time.

Scope note: this covers **benchmark figures only**. It is not a decision about `scorecard.html`, which stays exactly as the pack generates it (R8; §3.3 item 8 — we do not reimplement the scorer).

**The five figures the benchmark script must produce.** Labelled **B1-B5** so they are cross-referenceable the way `R-`, `AR-` and `M` already are. Every number in every figure is read from an artefact another milestone already writes; **none is typed in by hand**, and none reads `truth/*` or `rowmap_*.csv` (§5c's standing prohibition).

| # | Figure | What it shows, and which existing number it is | Where the numbers come from |
|---|---|---|---|
| **B1** | Grouped / paired bar — **cross-release mosaic join counts, before vs after** | The seven §1.4 baselines as "before" — HETU health∩finance **1622**, phone health∩finance **1484**, phone health∩CS **2296**, phone health∩energy **195**, HETU health∩energy **194**, IBAN energy∩finance **15**, IBAN finance∩CS **150** — against §5c **PASS-1**'s target of **0** as "after". This is the headline figure for §7's honest claim, and it is literally the sentence in §7 drawn as a picture. | `clean_data/mosaic_check.json`: the `positive_control` block (expected vs observed, all seven) for "before"; the per-pair-per-type `{count, verdict}` entries for "after" (§5c **Outputs**). |
| **B2** | Small-multiples / grouped bar — **privacy, utility and composite per dataset-scenario** | One panel or hue group per §3.1 pick — HEALTH-S1, FIN-S2, ENERGY-S3, CS-S1 — three bars each. The point it makes is R8's: the mosaic defence did not buy privacy by destroying scenario utility. The composite is the weighted harmonic mean of privacy (weight 30) and utility (weight 25), so it is "high only when both are high" (`docs/EVALUATION.md:42`). | each release's `clean_data/<ds>__<SID>/scorecard.json` → `summary.privacy`, `summary.utility`, `summary.composite` (`toolkit/pets_eval/scorecard.py:280`, assigned at `:317`; written into the protected dir at `:319-321`). |
| **B3** | Histogram or KDE overlay — **one quasi-identifier's distribution, before vs after** | One representative QI with the exact-value distribution overlaid on the generalised/banded one — utility retained at the *column* level, which is what §4.2 row **4** `pet_pipeline` does ("generalise, bin, round, coarsen"), in the value forms the scorer understands: `30-39`, `90+`, `201**`, `2025-W12` (`docs/EVALUATION.md:10-16`). Pick the column non-arbitrarily: take it from the catalogued QI list the scorer itself kept, `scorecard.json` → `tables.<table>.k_anonymity.qis`. | The original table under `data/<ds>/` (opened read-only, §9.3) and the corresponding table under `clean_data/<ds>__<SID>/`, both read with `dtype=str` (R1). |
| **B4** | Bar chart with reference lines — **free-text redaction recall per glue type against its target** | Per-type recall for the glue types, plus CS-S1's `PAYMENT_CARD` and `SECRET`, with each scenario's stated target drawn as a reference line: **HEALTH-S1 ≥ 0.95** and **CS-S1 ≥ 0.98** (§6 **M4**'s done-criteria, and §8.3's `redact_assist` row; CS-S1's target is quoted in §3.1 from `docs/SCENARIOS.md:291`: "recall ≥ 0.98 on NATIONAL_ID, PAYMENT_CARD, IBAN, SECRET"). **Per type, never averaged** — that is §7 **R-2**'s own stated deferral, and an averaged bar would hide exactly the ~2 % that R-2 is about. | `pets-eval text --gold metadata/pii_spans/... --pred <spans>` output: the per-label `recall` entries, with `_micro` shown only as a separate, clearly-labelled aggregate (`toolkit/pets_eval/text.py:71-73`). |
| **B5** | Bar chart — **k-anonymity group-size distribution, before vs after** | Per release and per table, the share of records in an equivalence class with **k < 5**, original vs protected — the pack's own risk component "records with k<5: Share of rows in equivalence classes smaller than 5 on the catalogued quasi-identifiers that you kept" (`docs/EVALUATION.md:28`). This is the number §7 **R-1** is about, and FIN-S2's target is "k-anonymity on customer profile" (`docs/SCENARIOS.md:167`, §3.1). **The figure must carry R-1's limitation in its caption:** these are *within-release* k values, and the cross-release equivalence class can be smaller than either — so B5 shows what the MVP closed, not what R-1 leaves open. | `scorecard.json` → `tables.<table>.k_anonymity_original.share_below["k<5"]` for "before" and `tables.<table>.k_anonymity.share_below["k<5"]` for "after" (`toolkit/pets_eval/scorecard.py:104-107`), with `min_k` / `median_k` / `sample_uniqueness` available from the same blocks (`toolkit/pets_eval/privacy.py:36-41`). **No new computation is required** — the pack already computes both sides. |

### 9.2 Operational workflow

Four steps. Two of them are a human, two of them are a shell script.

1. **A human provides the inputs.** A config naming, at minimum: (a) which of §3.1's four `(dataset, scenario_id)` pairs to run — `health__HEALTH-S1`, `finance__FIN-S2`, `energy__ENERGY-S3`, `customer_service__CS-S1`; (b) whichever agent-layer mode is currently active for the §8.6 rollout stage the project has actually reached — nothing at **A0**, by-hand `brief_writer` at **A1**, **shadow** at **A2**/**A3**, required-but-non-gating **advisory pre-test gate** at **A4**; and (c) any parameters the scenario's PET targets need (the generalisation bands, the k target, the redaction recall target). The key material itself is *not* config: it stays in gitignored `keys/` per R10. The still-open stack choices of §8.7 — provider, hosting, checkpointer backend — are inputs to this config too, and until they are decided per **A0**, (b) is simply "off".
2. **A shell script launches the multi-agent system to clean (protect) the dataset.** One script — call it `scripts/run_release.sh` — that launches the §8.2 LangGraph `StateGraph`: the `supervisor` router, the deterministic pipeline components **1-6** of §4.2, whichever of §8.3's specialists are in scope for this `(dataset, scenario_id)`, and the `human_review` `interrupt()` checkpoint of §8.4 — which **fails closed**: no resume value means reject. The script ends by running the gate that §8.2 leaves exactly where it was: component **7** `scripts/mosaic_check.py` (PASS-1 **and** PASS-2, §5c) and component **8** `pets-eval scorecard` + `pets-eval check` (R8). The script may **not** reorder those: the gate runs last and its exit code is the script's exit code.
3. **The protected output lands in `clean_data/`.** Per-release layout exactly as §4.2 row **6** `release_writer` already specifies and unchanged by this section: `clean_data/<dataset>__<SCENARIO-ID>/<table>.csv` with the **same table filenames as the original** (`docs/EVALUATION.md:7`), plus the private `rowmap_<table>.csv` (`protected_row`, `original_record_id`) that **is never published** (`docs/EVALUATION.md:18`, `toolkit/README.md:21-22`). The cross-release report lands at `clean_data/mosaic_check.json`, and `pets-eval` writes each `scorecard.json` + `scorecard.html` into the release directory itself (`toolkit/pets_eval/scorecard.py:319-321`).
4. **A second shell script generates the benchmark figures.** `scripts/make_benchmark.sh` renders **B1-B5** of §9.1, comparing the **original** dataset — read-only, **OPS-1**, §9.3 — against the contents of `clean_data/`. It is non-interactive, runs to completion, and writes static images into a project-owned `benchmarks/` directory. It reads no `truth/*` and no `rowmap_*.csv` (§5c).

**Which existing milestones this is.** This is deliberately not a third milestone track.

- **Script 1 is the operational packaging of §6's M1-M4.** M1 is component 3 (the HMAC pseudonymiser), M2 is components 1/2/4/5/6 (the PET pipeline and the four release folders), M3 is component 7 (`scripts/mosaic_check.py`, both pass criteria), M4 is component 8 (the four `pets-eval scorecard` runs plus `detect` and `text`). **M0** is not packaged into the script as a separate step because it already lives inside it: M0's seven baselines are re-measured on every run as §5c's **PASS-2** positive control. And once §8.6's rollout reaches **A2** or beyond, script 1 is also the operational packaging of the agent layer — shadow at A2/A3, required advisory pass at A4. It must stay runnable with the agent layer entirely switched off, because §8.6's hard constraint on M5 requires that and §8.6's **A4** done-criteria require it to be *demonstrated*, not asserted.
- **Script 2 is genuinely new, and gets its own milestone: M6**, added to §6's table in sequence. It is the only thing in this section that §6 did not already cover. It depends on M3 and M4 only — not on M5 — so it can be built alongside M5, and its figures are what M5's demo shows.
- **No A-milestone changes.** §8.6's A0-A4 track is untouched by this section; §9.2 only says which script invokes it, and in which mode.

### 9.3 Hard constraint: the original dataset is read-only

**The constraint.** The original dataset under `resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/data/` — verified for this section to contain exactly ten domain subfolders: `health`, `energy`, `finance`, `customer_service` (the four in §3.1's scope) plus `cyber`, `education`, `mobility`, `public_admin`, `smart_city` and `unseen` (the six the MVP does not target, §3.3 items 1 and 5) — **must never be modified, overwritten, moved, renamed or deleted, under any circumstances, by either script in §9.2.** All outputs go to `clean_data/`, `benchmarks/`, or another project-owned directory outside `resources/`.

This is not a new idea. §3.3 item 7 already makes "any edit under `resources/`" a non-goal, and §5a already treats the pack as vendored and read-only ("Nothing under `resources/TRUSTED_SinceAI2026_FINAL/` is modified"), down to routing the cross-reference *outward* into `resources/NOTE.md` rather than inward. What is new is that it stops being a stated intention and becomes an **enforced, testable safeguard in the scripts**.

| ID | The rule | Why | How it is enforced |
|---|---|---|---|
| **OPS-1** | **The original dataset root is read-only. Both §9.2 scripts verify a SHA-256 manifest of `resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/data/` immediately before the run and again immediately after, and any difference — content, file set, or path — is a hard, immediate failure with a non-zero exit, never a warning.** | Every number this plan claims is a comparison against that data. §7's honest claim is "down from a baseline of 1622 / 1484 / 2296 / 195 / 194 / 15 / 150 on the unprotected data"; §5c's **PASS-2** is meaningless if the "unprotected data" it reproduces those counts from has drifted. A single accidental in-place `to_csv` would invalidate M0's baselines, PASS-2's positive control, and **B1**, **B3** and **B5** of §9.1 at once — and would do it silently, because the pipeline would still run and still report numbers. The pack is also the common reference every other team is scored against; a locally mutated copy makes our results incomparable as well as wrong. | The manifest is the committed reference `custom_metadata/original_data.sha256` — a project-owned path, following §5a's precedent for `attack_specs.custom.json` and §8.7's "must be committable" rule. It lists one `sha256  relative/path` line per file, sorted, for all **50** files under `data/`. Both scripts recompute it at start and at end and compare against the committed copy; a mismatch at the start aborts before any work, a mismatch at the end fails the run even if the gate passed. Cost is not an argument against it: measured over all 50 files (441 MB), a full SHA-256 pass takes **0.19 s** — well below the §8.5 **AR-5** threshold at which a check starts getting skipped. The manifest check has a positive control in the §5c PASS-2 style: copy the tree to a scratch path, touch one byte, and confirm the check exits non-zero. A check that cannot detect a change is not a control. |

**Why the manifest is the primary mechanism, and not the path guard.** A path-resolution guard only binds the code that remembers to call it — which is the same failure shape §7 **R-3** already names, where "a hardcoded column name silently exempts a table from both the pipeline and the check". The manifest binds every write path there is: a stray pandas `to_csv`, a shell redirect, an `mv`, an `rm`, a future agent-layer node, a third-party library's cache file. And it is *verifiable* rather than *trusted*, which is the same reason §5c has a positive control at all. It is detective rather than preventive, and the plan accepts that trade deliberately: `resources/` is tracked in git (265 files), so a detected modification is recoverable, whereas an undetected one poisons every number downstream of it.

**Two complementary mechanisms, both required, neither primary.**

- **A path-resolution guard before any write.** One helper, shared by both scripts, that resolves the target path (symlinks included) and refuses to proceed if it lies under the original dataset root — or anywhere under `resources/` at all. This is the cheap, preventive, fail-fast half: it stops the common mistake before it happens, while the manifest catches the uncommon one after. Every write in both scripts goes through it; a write that bypasses it is a defect, and the manifest is what reveals that defect.
- **Open the original strictly read-only wherever it is loaded.** Every read of `data/` uses read-only file modes, and in any containerised or CI run the original dataset root is mounted read-only at the OS level. This also makes the intent legible at the call site rather than only in this document.

**What OPS-1 does not cover.** It protects the original dataset's bytes, not its secrets. The standing prohibitions elsewhere in this plan are unaffected and still bind: `truth/*` and `rowmap_*.csv` never leave local verification and never enter the agent layer (§5c, §8.5 **AR-4**), and `rowmap_*.csv` is never published (§4.2 row 6). OPS-1 is about integrity; those are about confidentiality, and neither substitutes for the other.
