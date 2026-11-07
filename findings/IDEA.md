# IDEA — Attack A: Phone / IBAN / HETU glue (cross-domain mosaic)

**Status:** Novel vs pack metadata — **not** listed as an attack in `metadata/attack_specs.json` and **not** a named sharing scenario in `metadata/scenarios.json`.  
**World:** TrustED PETs Proving Ground 2026 (synthetic Southwest Finland population; same people across domains).  
**Pack root:** `resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/`

---

## One-liner

An attacker who obtains several **weakly protected releases from different controllers** joins them on durable identifiers (`phone`, `hetu`, `iban`) and builds a dossier no single release was meant to expose.

---

## Roles

| Role | Who |
|------|-----|
| **Attacker** | Curious analyst, data broker, or journalist with access to multiple shared extracts (not a network intruder — a **linkage** attacker). Knows schemas and published methods; does **not** know secret HMAC keys/seeds or the original unreleased tables. |
| **Target (asset)** | A **unified personal profile**: health attributes + home/energy flags + income/PEP + telecom products. |
| **Victim** | The resident who appears in more than one domain (same synthetic person; verifiable via shared `person_id` in `truth/` — scoring only, never publish). |
| **Secondary victims** | Controllers who thought each share was “fine alone” (hospital, DSO, bank, telecom). |

---

## Datasets to inspect

| Domain | Path | Join-relevant / sensitive columns |
|--------|------|-----------------------------------|
| Health | `data/health/ed_visits.csv` | `patient_hetu`, `phone`, `patient_name`, `icd10_*`, triage, vitals |
| Energy | `data/energy/customers.csv` | `hetu`, `phone`, `iban`, address, `medical_device_priority`, payment flags |
| Energy (optional) | `data/energy/meter_readings_hourly.csv` | `metering_point_id`, `ts`, `kwh` (behaviour after identity bind) |
| Finance | `data/finance/customers.csv` | `hetu`, `phone`, `iban`, `income_band`, `pep_flag`, `employer` |
| Finance (optional) | `data/finance/card_transactions.csv`, `transfers.csv` | spend / counterparty graph once `customer_id` known |
| Telecom CS | `data/customer_service/customers.csv` | `hetu`, `phone`, `iban`, `accessibility_needs`, products |
| Public boost | `adversary/public_directory.csv` | name, address, postcode, phone |
| Verify only | `truth/health__ed_visits.csv`, `truth/energy__customers.csv`, `truth/finance__customers.csv`, `truth/customer_service__customers.csv` | `record_id` → `person_id` |

Join keys the attacker uses (cleartext / poorly masked):

1. **HETU** — exact match across health / energy / finance / CS  
2. **Phone** — normalize digits (`+35844…` → `044…`) then match  
3. **IBAN** — strip spaces, uppercase, match  

---

## Measured overlap in this pack (attacker-visible joins)

| Join | Approx. overlap |
|------|-----------------|
| HETU health ∩ finance | 1 622 |
| Phone health ∩ finance | 1 484 |
| Phone health ∩ customer_service | 2 296 |
| Phone health ∩ energy | 195 |
| HETU health ∩ energy | 194 |
| IBAN energy ∩ finance | 15 |
| IBAN finance ∩ CS | 150 |
| People in health ∩ energy ∩ finance (`truth` person_id) | 19 |

**Worked glue example** (`person_id` P013174, for demo verification only):

- Health: patient **Lehto Riku Viljami**, diagnosis **N20.0**  
- Same person in energy + finance with **income_band 15-30k**

Another phone/HETU illustration: ED **Petrov Vladimir** / finance **Vladimir Petrov** share the same mobile (`0443547786` / `+358443547786`) and HETU.

---

## How to attack (step-by-step)

**Preconditions:** several releases still contain at least one of `phone` / `hetu` / `iban` (or reversible hashes of them). Names may already be dropped.

1. Load the CSV extracts above with `dtype=str` (phones, HETUs, IBANs must not become numbers).
2. Normalize phones and IBANs; keep HETU as string.
3. Inner-join **health ⋈ finance** on HETU or normalized phone.
4. Join **energy** on HETU / phone / IBAN; join **customer_service** the same way.
5. On each matched victim row, collect attributes the controllers never co-released:
   - health → diagnoses, triage, free text if present  
   - energy → `medical_device_priority`, address, arrears  
   - finance → `income_band`, `pep_flag`, employer  
   - CS → accessibility, products, contact channels  
6. Optional: if any name/address survived, confirm with `adversary/public_directory.csv`.
7. Success = one person → **Art. 9-ish health and/or medical-priority** plus **financial** plus **contactable identity**.

---

## What success looks like

A dossier such as: *named (or uniquely QI’d) person + ED diagnosis + medical-device flag + income band + home address* — harmful precisely because each file alone looked “partially anonymised.”

---

## Relation to pack scoring

- `pets-eval scorecard` / `attack_specs.json` run **per-dataset** linkage (e.g. directory → energy `medical_device_priority`). They do **not** score this cross-controller join.
- Demo this attack **manually** (script/notebook); use `truth/*/person_id` only privately to prove the join is a true mosaic, never in a public submission.

---

## PETs that break Attack A

| Measure | Why |
|---------|-----|
| Drop or vault `phone` / `hetu` / `iban` in every outward share | Removes the glue |
| **Per-recipient keyed HMAC** (different key/domain per controller) | Same person ≠ same token across hospital vs bank vs DSO |
| No unsalted hashes of HETU/phone/email | Stops dictionary reverse across releases |
| Separate pseudonym spaces even when “research” and “vendor” both get microdata | Stops mosaic by design (`docs/PET_PLAYBOOK.md` — joins across datasets) |
| Minimise: don’t ship contacts when the scenario only needs aggregates or coarse QIs | Shrinks join surface |

---

## Demo sketch (hackathon)

1. Show two “safe-looking” extracts (names removed, HETU or phone kept).  
2. Run a small join → one enriched row (diagnosis + income + medical flag).  
3. Contrast with a protected design: per-dataset HMAC, contacts removed → join fails.  
4. Optionally still run a normal `pets-eval scorecard` on **one** domain to show self-assessment, and say mosaic is an **extra** residual risk you measured by hand.
