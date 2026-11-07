# MVP plan — defend by simulating the attack first

**Compact version (v3).** This replaces a 646-line predecessor, kept unabridged at
`findings/MVP_Plan_original.md`, and extends v2's collapsed "one agent" note into a
**multi-agent orchestration layer** with **Groq** as the LLM provider (model id and
API credentials specified later — see §5.3 / §7). Core attack analysis is unchanged
from `findings/IDEA.md`. If a detail is missing, it is in the original — see §10.
ID prefixes: **R*n*** = defensive requirement (§3), **R-_n_** = residual risk (§8),
**AR-_n_** = agent-layer residual (§5.3), **P*n*** = build phase (§6), **B*n*** =
benchmark figure (§7).

---

## 1. Core idea

**We defend the system by simulating the attack first.** We measure the real attack's
yield against the unprotected data before building anything, and then we re-run that
same attack against each candidate protected release before it ships — the attack is
both our baseline and our test instrument. Testing your own locks before a burglar does.

---

## 2. The attack (summary — `findings/IDEA.md` is the canonical account)

A **linkage attacker, not an intruder** (`IDEA.md:19`): a curious analyst, broker or
journalist holding several legitimately-obtained extracts from _different_ controllers.
They know every schema and published method; they do **not** know our keys.

**Three join keys** (`IDEA.md:39-43`): **HETU** (exact match), **phone** (normalise
`+35844…` → `044…` then match), **IBAN** (strip spaces, uppercase, match). The single
precondition (`IDEA.md:71`): several releases still carry at least one of these
_or a reversible hash of one_. Dropping `patient_name` does nothing.

**Headline measured overlap: HETU health ∩ finance = 1622 people** (`IDEA.md:51`;
re-verified for this plan). Ground truth says 1623 people are genuinely co-present, so
the HETU join recovers **99.9 %** of them — a near-perfect key, not a heuristic. The
other six measured joins (phone health∩finance 1484, phone health∩CS 2296, phone
health∩energy 195, HETU health∩energy 194, IBAN energy∩finance 15, IBAN finance∩CS 150)
are at `IDEA.md:49-58`.

**Worked example, person `P013174`** (`IDEA.md:60-64`): ED patient _Lehto Riku Viljami_,
diagnosis **N20.0**; the same HETU appears in finance as _Riku Viljami Lehto_ with
`income_band 15-30k`. Note the **name order is reversed** between the two files — name
matching would have failed on this person, and the HETU still succeeds.

**Why the pack's own scorer cannot see this:** `pets-eval scorecard` takes one
`--original` and one `--protected`, and `run_scorecard` fixes `domain = original_dir.name`
(`scorecard.py:290`). Every entry in `attack_specs.json` and `scenarios.json` has a
**scalar** `"dataset"`. One domain per invocation, by signature — so no pack tool can
express, let alone measure, a join between two of _our own_ releases. The pack names the
mosaic effect in prose (`docs/THREAT_MODEL.md:9`) but never operationalises it. That gap
is what this MVP fills. Full derivation: `MVP_Plan_original.md` §1.

---

## 3. Requirements

Each requirement exists only because of a named attacker capability. The five
load-bearing ones first.

| ID     | From                                                                      | Requirement                                                                                                                                                                                                                                                                                                       |
| ------ | ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R3** | A3+A4 — exact-matches the keys _across controllers_ (`IDEA.md:75-76`)     | **No two outward releases may share a reversible identifier token for the same person.** Satisfied by per-recipient keyed **HMAC-SHA-256** with a distinct key domain per `(dataset, scenario_id)`. This is the one requirement that closes the 1622 join.                                                        |
| **R4** | The precondition's "_or reversible hashes of them_" (`IDEA.md:71`)        | **No unsalted or unkeyed digest of HETU, phone, IBAN or e-mail may ever leave the controller.** `sha256(hetu)` is enumerable over a tiny domain; the pack ships `enumerate_hetu` and `hash_dictionary_attack` (`attacks.py:548`, `:517`) to prove it. A keyed HMAC with a secret key is the only acceptable form. |
| **R2** | A2 — attacker normalises before matching (`IDEA.md:74`)                   | Our checker must normalise with the **same** recipe (strip non-`[0-9+]`, `^\+358`→`0`, `^00358`→`0`; IBAN strip-space + uppercase). Correctness test: it must reproduce **1622** and **1484** on raw `data/`. A checker that normalises differently under-counts and passes a vulnerable release.                 |
| **R8** | A6 — confirms matches via `adversary/public_directory.csv` (`IDEA.md:82`) | Every release must still pass `pets-eval scorecard --scenario <ID>`. Mosaic defence is **additive to**, never a substitute for, the pack's own checks — the scorecard stays exactly the gate it already is.                                                                                                       |
| **R9** | A7 — success is the _combination_ across releases (`IDEA.md:83`)          | A per-release green scorecard is not evidence of safety. We need a **cross-release** gate that no pack tool provides, with a stated pass criterion **and a positive control** (§5, Part 1, component 6).                                                                                                          |

**The remaining six, one line:** read and write every key column as a **string**, never
numeric-coerced (**R1**); where the scenario needs no stable person key, **drop** the
identifier rather than tokenise it (**R5**); redact free text for the **glue types**, not
only names (**R6**); apply each token domain **consistently across every table** in a
release, or a second table re-exposes the key (**R7**); keep keys outside the repo,
gitignored, derived per-`(dataset, scenario_id)` from one master secret, and rotatable
(**R10**); the key domain is `(dataset, scenario_id)`, **not** `dataset`, so two scenarios
over one source table get disjoint token spaces (**R11**). Full justifications with
`file:line` evidence: `MVP_Plan_original.md` §2.

---

## 4. MVP scenario: health + finance

### 4.1 The two releases

| Release       | Table                        | Trust level           | Recipient / purpose                                                                | Key decision                                                                                                                                           |
| ------------- | ---------------------------- | --------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **HEALTH-S1** | `data/health/ed_visits.csv`  | `controlled_research` | University research group; analyse length of stay, revisits and diagnosis patterns | Its targets **mandate** a "consistent pseudonymous patient key" — so HETU must be **tokenised** (R3), it cannot be dropped                             |
| **FIN-S2**    | `data/finance/customers.csv` | `contractual`         | AI vendor (processor); train a fraud / spending model                              | Glue keys (`hetu`, `phone`, `iban`, `email`) are **keyed-tokenised** under the FIN-S2 subkey (R3/R4) so columns stay usable inside the release but cannot join HEALTH-S1; names / street addresses stay dropped |

Exactly these two tables. The attack-simulation path needs no third table: the 1622-person
join is `ed_visits.patient_hetu` ⋈ `customers.hetu`, and both columns are in these files.
`truth/health__ed_visits.csv` and `truth/finance__customers.csv` are used for **private
verification only** and never ship.

### 4.2 Before and after — the number this whole plan turns on

| Measurement                                                  | Unprotected `data/` | Protected `clean_data/` |
| ------------------------------------------------------------ | ------------------- | ----------------------- |
| HETU join, health ∩ finance                                  | **1622 people**     | **0**                   |
| Phone join, health ∩ finance                                 | **1484 people**     | **0**                   |
| Person `P013174` recoverable as _N20.0 + income_band 15-30k_ | **yes**             | **no**                  |

Non-goals: the other seven datasets (no measured Attack A overlap); **FIN-S1**, whose
shared consortium key is the mosaic condition chosen deliberately for fraud pooling;
differential privacy and synthetic data (neither is what closes Attack A); any edit under
`resources/`, which is vendored and read-only (§7, OPS-1).

### 4.3 Extending to a new scenario

Energy (**ENERGY-S3**, `data/energy/customers.csv`) + customer_service (**CS-S1**,
`data/customer_service/customers.csv`) are the natural next pair — ENERGY-S3 carries
Attack A's `medical_device_priority` payload, and CS-S1 carries its widest glue (phone
health∩CS = 2296, the largest measured overlap). Re-pointing the system at them takes
five steps and no new architecture:

- **Measure first.** A finding without a number is an opinion: get the baseline join count
  on the raw data before protecting anything.
- **Derive the requirement.** Add a row to §3: attack step → requirement → ID. If a step
  produces no requirement, say so and why.
- **Extend, don't fork.** Add the dataset pair to `scripts/mosaic_check.py` and record it
  in project-owned `findings/custom_attacks.md` + `custom_metadata/attack_specs.custom.json`.
  Nothing under `resources/` is ever edited.
- **Re-point the same two gates.** The agent re-runs the join on the new pair; PASS-1 still
  demands 0 and PASS-2 still demands the new baseline be reproduced.
- **Record the result, including failures.** A check that found nothing is only meaningful
  if its positive control passed.

**One caveat specific to widening scope.** Adding either of these revives a risk that does
_not_ apply to health+finance: glue surviving free-text redaction. `turns.text` carries
5120 `NATIONAL_ID`, 4217 `PHONE` and 1473 `IBAN` gold spans, and `clinical_notes.note_text`
carries 1637 and 4877 — all of it outside the two-file MVP. See §8.

---

## 5. System design

### Part 1 — Architecture graph (technical)

```text
 resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/  [VENDORED, READ-ONLY]
   data/health/ed_visits.csv   data/finance/customers.csv
   metadata/{scenarios.json, field_catalog.csv}   toolkit/pets_eval   truth/* (verify only)
           |                          |                         |
           | read, dtype=str (R1)     | read                    | import / invoke
           v                          v                         |
 +--------------------------+  +---------------------------+    |
 | [1] scenario_loader      |  | [2] field_classifier      |    |
 |  SID -> recipient, trust |  |  catalog -> role+subtype  |    |
 |  utility, privacy target |  |  + the GLUE-KEY INDEX     |    |
 +------------+-------------+  +------------+--------------+    |
              |                             |                   |
 keys/master.key  [GITIGNORED]              |                   | reuse
              v                             v                   | check.PATTERNS
 +--------------------------+  +---------------------------+    | hetu_ok iban_ok
 | [3] pseudonym_service    |  | [4] pet_pipeline          |<---+
 |  HMAC-SHA-256; key domain|->|  suppress | tokenise      |
 |  = (dataset, scenario_id)|  |  generalise | bin | round |
 |  NORMALISE then HMAC     |  |  R2 R3 R4 R5 R7 R10 R11   |
 +--------------------------+  +------------+--------------+
                                            v
                               +---------------------------+
                               | [5] release_writer        |
                               |  clean_data/<ds>__<SID>/  |
                               |   <table>.csv             |
                               |  + rowmap_<table>.csv     |
                               |    [PRIVATE, NEVER SHIPS] |
                               +------------+--------------+
                                            v
                     STAGED CANDIDATE RELEASE -- local only, not handed to anyone
                                            v
 = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
   MULTI-AGENT LAYER  (LangGraph StateGraph + Groq LLM)     see §5.3
   Advisory only: can delay a release, never pass one. Edits INPUTS, never clean_data/.

   [A0] attack_sim (DETERMINISTIC — not an LLM node)
        Re-runs Attack A's HETU/phone join (IDEA.md:75) on raw data/ and/or the
        staged candidate. Emits join counts, samples, diff-shaped proposals.
        This is "simulate the attack first" — the instrument, not a model call.

   [A1] supervisor / router  (Groq) — which specialists apply to this (ds, SID)?
        May select specialists; may NOT skip human_review or the deterministic gate.

        +-- classify_assist (Groq)  uncatalogued columns → role/subtype proposals
        +-- redact_assist   (Groq)  free-text → extra PII spans (union-only)
        +-- minim_assist    (Groq)  tokenised-but-unused cols → drop candidates
        +-- discover_assist (Groq)  new join/QI hypotheses (opinions, not counts)
        +-- brief_writer    (Groq)  plain-English brief from JSON numbers only

            human_review  <-- interrupt()   FAIL CLOSED if no resume
            accept → re-run [2][4][5] with proposal as INPUT → NEW candidate
            reject / timeout → candidate untouched; proceed to gate

   Shadow first (log proposals under findings/agent_proposals/), then advisory.
   LLM provider: **Groq**. Model id + API base/key: **TBD** (env / config; never commit).
 = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
                                            v
 +---------------------------------------------------------------------------------+
 | THE DETERMINISTIC GATE -- no model anywhere inside this box                     |
 | [6] app/mosaic_check.py       PASS-1: every cross-release join count == 0       |
 |                               PASS-2: the SAME code on raw data/ reproduces     |
 |                                       1622 and 1484 (positive control)          |
 | [7] pets-eval scorecard --original data/<ds> --protected clean_data/<ds>__<SID> |
 |                         --scenario <SID>        (ONE dataset per call)          |
 |     pets-eval check clean_data/<ds>__<SID>                                      |
 +---------------------------------+-----------------------------------------------+
                                   v
   exit 0   -> benchmarks/ B1 + B2 -> release handed to the recipient (irreversible)
   exit !=0 -> STOP. Nothing ships.
```

PASS-2 is not optional decoration: **a checker that can find nothing always reports zero**,
so without the positive control, PASS-1 passes identically for a working defence and for a
broken instrument.

### Part 2 — Data flow, in plain language

_Follow the arrows. No background needed._

```text
[1] We take a copy of the hospital's visit records and the bank's customer list. We never
    work on the originals, and we check at the end that the originals are untouched.
 -> [2] We remove names and street addresses that buy no analytical value, and we prepare
    the remaining identifier columns for keyed scrambling (not a shared hash).
 -> [3] The hospital's researchers still need to tell that two visits were the same
    patient, so we scramble the ID with a keyed recipe -- and we use a DIFFERENT key
    domain for the hospital's copy than for the bank's copy. The same person therefore
    comes out as two unrelated codes. Names and street addresses that buy no utility are
    removed; other glue on the bank side is scrambled the same way rather than blanked
    so the vendor still has a stable-looking column that cannot join the hospital file.
 -> [4] We blur what is left: details that mean nothing alone but identify someone when
    combined. An exact birth date becomes an age range. An exact postcode becomes a wider
    area. A rare job title gets grouped with similar ones.
 -> [5] The two protected files go into a holding area. Nothing has been sent to anyone.
 -> [6] First a fixed counter plays the burglar on the unprotected originals (so we know
    the attack works: 1,622 people on HETU). Then the same counter runs on the holding-area
    files and must find nobody. That is testing your own locks before a burglar does.
 -> [7] Optionally, a team of specialist assistants (routed by a supervisor, powered by
    Groq) suggests tighter redaction, better field labels, or new attack hypotheses. They
    write proposals only; they cannot change the holding-area files or approve a ship.
 -> [8] A person reads those proposals (if any) and the burglar report. No reply means no.
    Accepted ideas become new settings and we rebuild the holding-area files from scratch.
 -> [9] Two fixed automatic tests run. They are the same every time and involve no model
    and no judgement. The first counts how many people can be matched across the two
    protected files; the answer has to be none. The second runs that exact same count
    against the untouched originals, where it has to find the 1,622 people we already know
    are there -- because a broken counter would also say "none", and that is how we tell a
    real defence apart from a test that simply cannot see anything.
 -> [10] Only if both tests come out right do the two protected files leave the building.
    Handing them over is the one step that cannot be undone.
```

---

### Part 3 — Multi-agent system (Groq) — design to implement

**Status today.** P0–P7 deterministic path is built (`app/`, `scripts/final/`). P2 ships a
**stdlib LangGraph-shaped shim** (`app/agent_runtime.py`) with two nodes —
`attack_sim` → `human_review` — and **no LLM calls**. This subsection is the plan to
grow that graph into a real multi-agent system without moving the gate.

**Governing rules** (non-negotiable; full AR table in `MVP_Plan_original.md` §8.5):

1. **Validate before test, not instead of test.** Agents run on a staged candidate; the
   gate still decides PASS/FAIL.
2. **The gate keeps its authority.** `mosaic_check` + `pets-eval` stay subprocesses with
   no model inside; runnable with the agent layer switched off.
3. **Agents edit inputs, never outputs.** Accepted proposals become artefacts; the
   deterministic pipeline re-runs. No agent writes under `clean_data/`.
4. **Fail closed.** No human resume → reject. An unread proposal is never applied.
5. **No irreversible action from an agent.** Handing a release to a recipient still
   requires: deterministic re-run + PASS-1/PASS-2 + scorecard + human sign-off.

**Where agents help — and where they must not**

| Node | LLM? | Narrows | Reads (contract) | Must not |
|---|---|---|---|---|
| `attack_sim` | **No** — deterministic join code | Attack instrument | Staged / raw CSVs | Set exit codes; write `clean_data/` |
| `supervisor` | Groq | Routing only | Scenario id, column *names*, row counts | Skip review or gate |
| `classify_assist` | Groq | Uncatalogued columns (R-3-class gap) | Names + shape summaries; **no raw values** | Weaken existing `direct_identifier` labels |
| `redact_assist` | Groq | Free-text glue / NER gap (HEALTH `chief_complaint` now; CS/energy later) | Free text as **untrusted data** | Override deterministic spans (union-only) |
| `minim_assist` | Groq | Minimisation audit | Utility prose + column *names* | Drop columns itself |
| `discover_assist` | Groq | Blind-spot hypotheses (R-6) | Catalog traps, threat model, prior mosaic JSON | Invent join *counts* |
| `brief_writer` | Groq | Jury-facing explanation | Aggregate JSON only | Replace JSON as the record |
| `human_review` / `human_signoff` | No | HITL | Proposal payload / gate numbers | Auto-resume |

**Hard prohibitions for any Groq call:** never send raw `hetu` / `phone` / `iban` /
`email` or `keys/master.key`; never put `truth/*` or `rowmap_*.csv` in prompts; never
call Groq from `pseudonym_service` or from PASS-1/PASS-2 arithmetic.

**Provider configuration (placeholders — fill when credentials exist)**

| Knob | Value |
|---|---|
| Provider | **Groq** |
| API base URL | _TBD_ (e.g. `https://api.groq.com/openai/v1`) |
| Model id | _TBD_ (e.g. a current Groq chat model; pin a version string in config) |
| Auth | `GROQ_API_KEY` in environment / local secret store — **gitignored**, never committed |
| Client | OpenAI-compatible HTTP client or official Groq SDK; wrap behind `app/` adapter so swapping hosts does not rewrite every node |
| Temperature / max tokens | Conservative defaults; logged per proposal with model id + prompt version |
| Offline / CI | Agent layer **off** unless key present; release path must still pass with agents disabled |

**Rollout (parallel to the deterministic phases)**

| Stage | Mode | Done when |
|---|---|---|
| **A0** | Design only | This §5.3 + AR bounds accepted; model/API placeholders replaced with named values |
| **A1** | `brief_writer` only, hand-run | Brief numbers match `mosaic_check.json` / `scorecard.json` |
| **A2** | Graph in **shadow**: supervisor + classify + minim + human_review + brief | Proposals logged; accept rate recorded; gate byte-identical to agent-off run |
| **A3** | Add `redact_assist` + `discover_assist` (still shadow) | Union-only redaction does not lower glue recall vs deterministic floor |
| **A4** | Advisory pre-test required in runbook | Can delay release; still cannot PASS one; gate-alone catch of a known-bad release still works |

Implementation home: extend `app/agent_graph.py` / `app/agent_runtime.py` (or replace the
shim with real LangGraph once pinned), keep `attack_sim` as the deterministic first node,
and store proposals under gitignored `findings/agent_proposals/`. Full node contracts and
AR-1…AR-6: `MVP_Plan_original.md` §8.


## 6. Scope: build phases

| Phase  | What gets built                                                                                                                                               | Hours     |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| **P0** | Re-measure the baseline attack yield on raw `data/` with the R2 normalisation; lock 1622 / 1484 as the "before" numbers                                       | 1         |
| **P1** | Deterministic PET pipeline for the two releases — components [1]-[5]: scenario loader, field classifier, HMAC pseudonym service, PET pipeline, release writer | 4-5       |
| **P2** | Deterministic `attack_sim` + `human_review` interrupt (fail-closed, shadow) — **stdlib graph shim first**; no LLM required for joins                          | 2-3       |
| **P3** | Wire the deterministic gate: `app/mosaic_check.py` (PASS-1 + PASS-2) and `pets-eval scorecard` / `pets-eval check`                                           | 2         |
| **P4** | The two benchmark charts, **B1** and **B2** (§7)                                                                                                              | 2         |
| **P5** | OPS-1 SHA-256 manifest safeguard, with its own positive control                                                                                               | 1         |
| **P6** | End-to-end wiring: `scripts/final/run_release.sh` (attack raw → protect → re-attack → gate) and `make_benchmark.sh`                                           | 2         |
| **P7** | Demo / `INSTRUCTION.md` buffer                                                                                                                                | 1         |
| **P8** | **Multi-agent layer on Groq** (§5.3): provider adapter, supervisor + specialists, shadow→advisory rollout A0–A4; model/API filled when available              | 4-6       |
|        | **Total (P0–P7)**                                                                                                                                             | **15-17** |
|        | **With P8**                                                                                                                                                   | **19-23** |

Operational workflow, one line each: a human supplies the config (which `(dataset,
scenario_id)` pairs, PET parameters, agent mode — HMAC keys and `GROQ_API_KEY` are _not_
committed config, they stay gitignored / env); `run_release.sh` runs attack-on-raw,
components [1]-[5], re-attack, optional agent pass, then the gate, and the gate's exit
code **is** the script's exit code; output lands in `clean_data/<dataset>__<SID>/` with
the original table filenames plus the never-published `rowmap_<table>.csv`;
`make_benchmark.sh` renders B1 and B2 into `benchmarks/`.

---

## 7. Tech stack

**Python ≥3.10**, continuing the vendored scorer's own stack — `pets-eval` requires ≥3.10,
and every net-new deterministic component reuses it directly (`hmac` + `hashlib` for the
pseudonym service, pandas with `dtype=str` everywhere for R1 where needed, `pets_eval.check`
patterns as a library, stdlib `csv` + `re` for the mosaic check). Shell entry points live
under `scripts/final/` with shared helpers in `scripts/material/`. **`matplotlib`** for
**B1** (paired bar: cross-release joins before vs after) and **B2** (privacy / utility /
composite per release). Both read every number from `mosaic_check.json` or
`scorecard.json`; none is typed by hand. **OPS-1:** committed SHA-256 manifest of pack
`data/` verified before and after every release/demo/benchmark run.

**Multi-agent / LLM (P8):**

| Piece | Choice |
|---|---|
| Orchestration | LangGraph `StateGraph` (replace or wrap today's `app/agent_runtime.py` shim) |
| LLM provider | **Groq** |
| Model | **TBD** — pin an explicit model id in config when chosen |
| API | **TBD** — OpenAI-compatible Groq endpoint; auth via `GROQ_API_KEY` (env) |
| Adapter | Thin `app/` client module so nodes call one interface (`chat(messages, …)`), not raw HTTP scattered across specialists |
| Persistence | File checkpointer under `findings/agent_checkpoints/` (gitignored); proposals under `findings/agent_proposals/` (gitignored) |
| Kill switch | `agent mode=off` / missing API key → graph reduces to deterministic `attack_sim` (+ optional human_review) so P0–P7 demos never depend on Groq |

Never put Art. 9 identifiers or master keys in prompts (AR-4). Never let a model write
`clean_data/` or flip the gate exit code.

---

## 8. Residual risk

What the MVP does **not** close, stated plainly, because a green mosaic check is a narrow
claim and "which attacks still work, at what rate" is a jury item.

| ID      | Residual risk                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R-1** | **Cross-release quasi-identifier mosaic.** Keyed tokens break _identifier_ joins but leave probabilistic matching on birth date / age band / postcode / city / sex / employer — and the catalog says so itself: `employer` is flagged "small employers + city + age often unique". The k-anonymity targets are _within-release_; the cross-release equivalence class can be smaller than either. Measured and reported, not closed. |
| **R-5** | **Key compromise.** The entire defence rests on the attacker not knowing our keys. A leaked `keys/master.key` restores global linkability across both releases _retroactively_, because the tokens are deterministic. The MVP uses a local gitignored keyfile, not a KMS, and does not rotate.                                                                                                                                      |
| **R-6** | **The pack's blind spot persists and our check is unofficial.** `pets-eval` will still score a mosaic-vulnerable release as low-risk, and the organisers hold a stronger private attacker set including a data-broker profile. A green `mosaic_check.json` means "our two releases do not join on the keys we tested" — not "no cross-domain attack works".                                                                         |
| **R-9** | **Minimisation / free-text still need judgement.** Catalogued FIN-S2 glue is now keyed-tokenised (not blank-dropped), but nothing automatically audits whether a column should have been dropped instead, and HEALTH `chief_complaint` still ships without NER redaction. Closing that gap is exactly what `minim_assist` / `redact_assist` (§5.3) are for — under human review, not as silent auto-edits. |

**Free text in this scope.** `data/finance/customers.csv` has no free-text column.
`data/health/ed_visits.csv` has `chief_complaint`; gold spans there are `LOCATION` /
`ORG` only (no HETU/phone/IBAN/EMAIL in the annotated set). Glue-bearing free text in
CS/energy/clinical notes sits outside the two-file MVP (§4.3) but is the first place
`redact_assist` (Groq) earns its keep when scope widens. Deterministic PET code must not
fake LLM redaction.

**Agent-layer residuals (summary).** Full AR-1…AR-6 live in `MVP_Plan_original.md` §8.5.
The load-bearing ones for Groq: **AR-1** prompt injection from attacker-authored text;
**AR-2** non-determinism (proposals must become artefacts, not build steps); **AR-4**
identifier egress to the provider (hard input contracts); **AR-6** signing off on prose
instead of JSON. Gate independence remains a tested property (A4), not an assertion.

### The MVP's honest claim

> Against an attacker with our two protected releases, no public adversary file, and no
> access to our keys, the measured cross-release join count on HETU, phone and IBAN is
> **0**, down from a baseline of **1622** on the unprotected data — while each release
> still passes `pets-eval scorecard` for its own scenario.

Everything in the table above sits outside that sentence. That is the point of stating it
so narrowly.

---

## 9. Enhancements worth making next

- **Fill Groq placeholders** (§5.3 / §7): model id, API base, and secret-handling runbook
  once the teammate supplies them; add a one-page `findings/agent_groq.md` pin.
- **Implement P8 A0→A4** without making the M5/P7 demo depend on an API key.
- **Wire `redact_assist` to HEALTH `chief_complaint` first** (lowest scope free-text),
  then widen to CS/energy columns when those releases enter scope.
- **Mark every residual risk in §8 with the phase that would close it**, so the table reads
  as a backlog rather than a disclaimer list.
- **Promote §4.2's before/after table into the document's header block**, so 1622 → 0 is
  visible without scrolling.
- **Keep a short changelog at the bottom** — one line per revision — so the next pass does
  not re-derive this one's reasoning.

### Changelog

| Rev | Note |
|---|---|
| v2 | Compact plan; agent layer collapsed to one `attack_sim` node |
| v3 | Multi-agent + Groq design restored into §5.3; FIN-S2 keyed-tokenise; P8 phase; gate paths updated to `app/` / `scripts/final/` |

---

## 10. References

**`findings/IDEA.md`** — the attack narrative. Source for §1 (core idea), §2 (the attack
summary: the three keys, the 1622 overlap and the other six numbers, the `P013174` worked
example, why the pack's scorer misses it), §4.2's before/after numbers, and step [6] of §5
Part 2's data flow.

**`findings/MVP_Plan_original.md`** — **the complete, unabridged prior version of this
document (646 lines), kept on disk specifically so that any detail compressed or cut here
can be recovered.** Source for everything else. What happened to each of its nine sections:

| Original section                                        | Disposition                                                                                                                    | Lands in         |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ---------------- |
| §1 Attacker view (93 lines)                             | Cut to a ~15-line summary that cites `IDEA.md` instead of re-deriving it                                                       | §2               |
| §2 Requirements R1-R11                                  | One line per row; the five load-bearing ones (R3, R4, R2, R8, R9) keep a half-line of justification                            | §3               |
| §3 Scope (4 datasets, 9 non-goals)                      | Narrowed to 2 datasets; ENERGY-S3 + CS-S1 relocated, not cut; non-goals to 4 clauses                                           | §4.1, §4.2, §4.3 |
| §4 Architecture (8 components + diagram + reuse table)  | Merged into one unified diagram showing the modules **and** the agent together                                                 | §5 Part 1        |
| §4.2a "In plain English" panel                          | Superseded by the arrow-by-arrow plain-language data flow — same spirit, different shape                                       | §5 Part 2        |
| §5 Novel-attack process (~65 lines)                     | Compressed to five bullets                                                                                                     | §4.3             |
| §6 Milestones M0-M6                                     | Replaced entirely by an hour-budget phase table                                                                                | §6               |
| §7 Residual risk R-1..R-9 + honest claim                | Top four risks only — **R-2 replaced by R-9**, reasoning stated in §8 — with the honest-claim blockquote carried near-verbatim | §8               |
| §8 Agentic layer (6 LangGraph nodes, A0-A4, AR-1..AR-6) | **v3:** restored as multi-agent + **Groq** in §5.3 (compact); full contracts stay in the original | §5 Part 1, §5.3, §6 P8, §7 |
| §9 Tech stack (figures B1-B5, 4-step workflow, OPS-1)   | B1 and B2 kept; Groq provider row added; paths → `app/` + `scripts/final/`                                                     | §7, §6           |

Nothing was deleted without a trace. Full agent node contracts, interrupt semantics, and
AR-1…AR-6 remain authoritative in **`MVP_Plan_original.md` §8** — v3 §5.3 is the
implementation brief for wiring Groq, not a replacement of that evidence.
