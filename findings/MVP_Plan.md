# MVP plan — defend by simulating the attack first

**Compact version (v2).** This replaces a 646-line predecessor, kept unabridged at
`findings/MVP_Plan_original.md`. Nothing here is new analysis; everything is a
compression of that file plus `findings/IDEA.md`. If a detail is missing, it is in the
original — see §10. ID prefixes used throughout: **R*n*** = defensive requirement (§3),
**R-*n*** = residual risk (§8), **P*n*** = build phase (§6), **B*n*** = benchmark figure (§7).

---

## 1. Core idea

**We defend the system by simulating the attack first.** We measure the real attack's
yield against the unprotected data before building anything, and then we re-run that
same attack against each candidate protected release before it ships — the attack is
both our baseline and our test instrument. Testing your own locks before a burglar does.

---

## 2. The attack (summary — `findings/IDEA.md` is the canonical account)

A **linkage attacker, not an intruder** (`IDEA.md:19`): a curious analyst, broker or
journalist holding several legitimately-obtained extracts from *different* controllers.
They know every schema and published method; they do **not** know our keys.

**Three join keys** (`IDEA.md:39-43`): **HETU** (exact match), **phone** (normalise
`+35844…` → `044…` then match), **IBAN** (strip spaces, uppercase, match). The single
precondition (`IDEA.md:71`): several releases still carry at least one of these
*or a reversible hash of one*. Dropping `patient_name` does nothing.

**Headline measured overlap: HETU health ∩ finance = 1622 people** (`IDEA.md:51`;
re-verified for this plan). Ground truth says 1623 people are genuinely co-present, so
the HETU join recovers **99.9 %** of them — a near-perfect key, not a heuristic. The
other six measured joins (phone health∩finance 1484, phone health∩CS 2296, phone
health∩energy 195, HETU health∩energy 194, IBAN energy∩finance 15, IBAN finance∩CS 150)
are at `IDEA.md:49-58`.

**Worked example, person `P013174`** (`IDEA.md:60-64`): ED patient *Lehto Riku Viljami*,
diagnosis **N20.0**; the same HETU appears in finance as *Riku Viljami Lehto* with
`income_band 15-30k`. Note the **name order is reversed** between the two files — name
matching would have failed on this person, and the HETU still succeeds.

**Why the pack's own scorer cannot see this:** `pets-eval scorecard` takes one
`--original` and one `--protected`, and `run_scorecard` fixes `domain = original_dir.name`
(`scorecard.py:290`). Every entry in `attack_specs.json` and `scenarios.json` has a
**scalar** `"dataset"`. One domain per invocation, by signature — so no pack tool can
express, let alone measure, a join between two of *our own* releases. The pack names the
mosaic effect in prose (`docs/THREAT_MODEL.md:9`) but never operationalises it. That gap
is what this MVP fills. Full derivation: `MVP_Plan_original.md` §1.

---

## 3. Requirements

Each requirement exists only because of a named attacker capability. The five
load-bearing ones first.

| ID | From | Requirement |
|---|---|---|
| **R3** | A3+A4 — exact-matches the keys *across controllers* (`IDEA.md:75-76`) | **No two outward releases may share a reversible identifier token for the same person.** Satisfied by per-recipient keyed **HMAC-SHA-256** with a distinct key domain per `(dataset, scenario_id)`. This is the one requirement that closes the 1622 join. |
| **R4** | The precondition's "*or reversible hashes of them*" (`IDEA.md:71`) | **No unsalted or unkeyed digest of HETU, phone, IBAN or e-mail may ever leave the controller.** `sha256(hetu)` is enumerable over a tiny domain; the pack ships `enumerate_hetu` and `hash_dictionary_attack` (`attacks.py:548`, `:517`) to prove it. A keyed HMAC with a secret key is the only acceptable form. |
| **R2** | A2 — attacker normalises before matching (`IDEA.md:74`) | Our checker must normalise with the **same** recipe (strip non-`[0-9+]`, `^\+358`→`0`, `^00358`→`0`; IBAN strip-space + uppercase). Correctness test: it must reproduce **1622** and **1484** on raw `data/`. A checker that normalises differently under-counts and passes a vulnerable release. |
| **R8** | A6 — confirms matches via `adversary/public_directory.csv` (`IDEA.md:82`) | Every release must still pass `pets-eval scorecard --scenario <ID>`. Mosaic defence is **additive to**, never a substitute for, the pack's own checks — the scorecard stays exactly the gate it already is. |
| **R9** | A7 — success is the *combination* across releases (`IDEA.md:83`) | A per-release green scorecard is not evidence of safety. We need a **cross-release** gate that no pack tool provides, with a stated pass criterion **and a positive control** (§5, Part 1, component 6). |

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

| Release | Table | Trust level | Recipient / purpose | Key decision |
|---|---|---|---|---|
| **HEALTH-S1** | `data/health/ed_visits.csv` | `controlled_research` | University research group; analyse length of stay, revisits and diagnosis patterns | Its targets **mandate** a "consistent pseudonymous patient key" — so HETU must be **tokenised** (R3), it cannot be dropped |
| **FIN-S2** | `data/finance/customers.csv` | `contractual` | AI vendor (processor); train a fraud / spending model | Its target is "k-anonymity on customer profile" with **no** stable-key requirement — so `hetu`, `phone`, `iban`, `email` are **dropped outright** (R5) |

Exactly these two tables. The attack-simulation agent needs no third table: the 1622-person
join is `ed_visits.patient_hetu` ⋈ `customers.hetu`, and both columns are in these files.
`truth/health__ed_visits.csv` and `truth/finance__customers.csv` are used for **private
verification only** and never ship.

### 4.2 Before and after — the number this whole plan turns on

| Measurement | Unprotected `data/` | Protected `clean_data/` |
|---|---|---|
| HETU join, health ∩ finance | **1622 people** | **0** |
| Phone join, health ∩ finance | **1484 people** | **0** |
| Person `P013174` recoverable as *N20.0 + income_band 15-30k* | **yes** | **no** |

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
*not* apply to health+finance: glue surviving free-text redaction. `turns.text` carries
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
   [A] attack_sim  -- THE ONE AGENT  (LangGraph StateGraph)
       Re-runs Attack A's HETU/phone join (IDEA.md:75) against the staged candidate.
       THIS IS "SIMULATE THE ATTACK FIRST", REUSED AS THE PRE-TEST MECHANISM.
       Reads the candidate only. No write access to clean_data/. Cannot set an exit code.
       Emits: join count per key, any recovered pair, a diff-shaped proposal list.
                                            |
                                            v
            human_review  <-- interrupt()   |  ONE human checkpoint. Resumed with
            state persisted by checkpointer |  Command(resume=...).
            accept -> re-run [2][4][5] with the proposal as an INPUT, never as an
                      edit to the output; produces a NEW candidate, re-enters above
            reject / no reply / timeout -> FAIL CLOSED; candidate untouched
       Rollout: runs in shadow (log-only) first; flips to advisory once it has a clean
       track record against known-good releases. It can delay a release, never pass one.
 = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
                                            v
 +---------------------------------------------------------------------------------+
 | THE DETERMINISTIC GATE -- no model anywhere inside this box                     |
 | [6] scripts/mosaic_check.py   PASS-1: every cross-release join count == 0       |
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

*Follow the arrows. No background needed.*

```text
[1] We take a copy of the hospital's visit records and the bank's customer list. We never
    work on the originals, and we check at the end that the originals are untouched.
 -> [2] We delete the things that point straight at one person: names, home addresses,
    e-mail addresses, telephone numbers.
 -> [3] The hospital's researchers still need to tell that two visits were the same
    patient, so we cannot simply delete the patient's ID number there. Instead we scramble
    it -- and we use a DIFFERENT scrambling recipe for the hospital's copy than for the
    bank's copy. The same person therefore comes out as two completely unrelated codes in
    the two files, so holding both files up side by side proves nothing. The bank's copy
    does not need a patient code at all, so there we delete the ID number outright.
 -> [4] We blur what is left: details that mean nothing alone but identify someone when
    combined. An exact birth date becomes an age range. An exact postcode becomes a wider
    area. A rare job title gets grouped with similar ones.
 -> [5] The two protected files go into a holding area. Nothing has been sent to anyone.
 -> [6] A robot now plays the burglar. It takes the two files out of the holding area and
    tries exactly what a real snooper would try: find the people who appear in both, and
    build one record showing a person's medical problem next to their income. This is
    testing your own locks before a burglar does.
 -> [7] The robot writes down whatever it managed to find, and then stops. It cannot change
    the files and it cannot approve anything.
 -> [8] A person reads the robot's report and decides. If the robot got through, we go back
    to step 2 with tighter settings and start again. If nobody reads the report, the answer
    is automatically no -- we never let an unread report count as approval.
 -> [9] Two fixed automatic tests run. They are the same every time and involve no robot
    and no judgement. The first counts how many people can be matched across the two
    protected files; the answer has to be none. The second runs that exact same count
    against the untouched originals, where it has to find the 1,622 people we already know
    are there -- because a broken counter would also say "none", and that is how we tell a
    real defence apart from a test that simply cannot see anything.
 -> [10] Only if both tests come out right do the two protected files leave the building.
    Handing them over is the one step that cannot be undone.
```

---

## 6. Scope: a 15-17 hour build

| Phase | What gets built | Hours |
|---|---|---|
| **P0** | Re-measure the baseline attack yield on raw `data/` with the R2 normalisation; lock 1622 / 1484 as the "before" numbers | 1 |
| **P1** | Deterministic PET pipeline for the two releases — components [1]-[5]: scenario loader, field classifier, HMAC pseudonym service, PET pipeline, release writer | 4-5 |
| **P2** | The one `attack_sim` agent + the `human_review` `interrupt()` checkpoint, fail-closed, shadow mode | 2-3 |
| **P3** | Wire the deterministic gate: `scripts/mosaic_check.py` (PASS-1 + PASS-2) and `pets-eval scorecard` / `pets-eval check` | 2 |
| **P4** | The two benchmark charts, **B1** and **B2** (§7) | 2 |
| **P5** | OPS-1 SHA-256 manifest safeguard, with its own positive control | 1 |
| **P6** | End-to-end wiring of the two shell scripts, `scripts/run_release.sh` and `scripts/make_benchmark.sh` | 2 |
| **P7** | Demo buffer | 1 |
| | **Total** | **15-17** |

Operational workflow, one line each: a human supplies the config (which `(dataset,
scenario_id)` pairs, PET parameters, agent mode — keys are *not* config, they stay in
gitignored `keys/`); `run_release.sh` runs components [1]-[5], then the agent pass, then the
gate, and the gate's exit code **is** the script's exit code; output lands in
`clean_data/<dataset>__<SID>/` with the original table filenames plus the never-published
`rowmap_<table>.csv`; `make_benchmark.sh` renders B1 and B2 into `benchmarks/`.

---

## 7. Tech stack

**Python**, continuing the vendored scorer's own stack — `pets-eval` is a Python package
requiring ≥3.10, and every net-new component reuses it directly (`hmac` + `hashlib` for the
pseudonym service, pandas with `dtype=str` everywhere for R1, `pets_eval.check`'s
`PATTERNS` / `hetu_ok` / `iban_ok` imported as a library, stdlib `csv` + `re` for the mosaic
check). The two shell scripts are thin launchers: argument parsing, the OPS-1 check, and a
`python -m` call. **`matplotlib` + `seaborn`** for the two kept figures — **B1**, a paired
bar of the cross-release join count before vs after (1622 and 1484 → 0), and **B2**, a
grouped bar of privacy / utility / composite score per release, proving the mosaic fix did
not buy privacy by destroying utility. Both read every number from `mosaic_check.json` or
`scorecard.json`; none is typed by hand, and neither reads `truth/*` or `rowmap_*.csv`. The
reason for matplotlib over plotly is the output shape, not taste: these are static images
written by a non-interactive script, which matplotlib's `Agg` backend does with no display
and no browser, whereas plotly would need `kaleido` plus a headless-browser round-trip to
produce a PNG nobody will click on. **OPS-1:** both scripts verify a committed SHA-256
manifest of the original `data/` tree immediately before and immediately after every run,
and any difference in content, file set or path is a hard non-zero-exit failure, never a
warning — because every number this plan claims is a comparison against that data.

---

## 8. Residual risk

What the MVP does **not** close, stated plainly, because a green mosaic check is a narrow
claim and "which attacks still work, at what rate" is a jury item.

| ID | Residual risk |
|---|---|
| **R-1** | **Cross-release quasi-identifier mosaic.** Keyed tokens break *identifier* joins but leave probabilistic matching on birth date / age band / postcode / city / sex / employer — and the catalog says so itself: `employer` is flagged "small employers + city + age often unique". The k-anonymity targets are *within-release*; the cross-release equivalence class can be smaller than either. Measured and reported, not closed. |
| **R-5** | **Key compromise.** The entire defence rests on the attacker not knowing our keys. A leaked `keys/master.key` restores global linkability across both releases *retroactively*, because the tokens are deterministic. The MVP uses a local gitignored keyfile, not a KMS, and does not rotate. |
| **R-6** | **The pack's blind spot persists and our check is unofficial.** `pets-eval` will still score a mosaic-vulnerable release as low-risk, and the organisers hold a stronger private attacker set including a data-broker profile. A green `mosaic_check.json` means "our two releases do not join on the keys we tested" — not "no cross-domain attack works". |
| **R-9** | **Minimisation is not audited.** FIN-S2 needs no stable person key, so its identifiers should be *dropped*; HEALTH-S1 mandates one, so its HETU must be *tokenised*. Nothing automatically flags the case where an identifier was tokenised when it could have been dropped. A tokenised key is join surface that survives only as long as the key stays secret (see R-5); a dropped key is join surface that is gone. |

**On the risk that is deliberately absent.** **R-2, free-text residual leakage**, was in the
draft top four and **does not apply to this scope** — so it is not listed. Measured, not
assumed: `data/finance/customers.csv` has no free-text column at all, and
`data/health/ed_visits.csv` has exactly one, `chief_complaint`, whose 503 gold-annotated
records in `metadata/pii_spans/health__ed_visits__chief_complaint.jsonl` carry only
`LOCATION` (313) and `ORG` (190) spans — **zero `NATIONAL_ID`, `PHONE`, `IBAN` or `EMAIL`**.
R-2 is about *glue* surviving redaction, and there is no glue in the only in-scope free
text. All the glue-bearing free text sits in tables this MVP excludes (§4.3), so R-2 is
relocated there as a scope-widening caveat rather than dropped. **R-9** takes its place
because it is unmitigated, specific to the exact asymmetry between these two scenarios,
and compounds R-5, which is already in the list. (Next in line, not listed: **R-3**
key-propagation gaps — health's `patient_hetu` vs finance's `hetu`, a real trap whose
blast radius here is partly covered by PASS-1 and `pets-eval check` — and **R-7** recipient
collusion, which lost its sharpest form when energy left scope.) Risks **R-2, R-3, R-4,
R-7, R-8** are all in `MVP_Plan_original.md` §7 in full.

### The MVP's honest claim

> Against an attacker with our two protected releases, no public adversary file, and no
> access to our keys, the measured cross-release join count on HETU, phone and IBAN is
> **0**, down from a baseline of **1622** on the unprotected data — while each release
> still passes `pets-eval scorecard` for its own scenario.

Everything in the table above sits outside that sentence. That is the point of stating it
so narrowly.

---

## 9. Enhancements worth making next

- **Put a one-paragraph "what you can skip" note under the title**, telling a reader which
  two sections to read if they have two minutes (§1 and §5 Part 2) and which if they are
  implementing (§3, §5 Part 1, §6).
- **Promote §4.2's before/after table into the document's header block**, so 1622 → 0 is
  visible without scrolling. The number is the whole argument and currently sits four
  sections down.
- **Add a visual rule or a page break between §5 Part 1 and Part 2**, and label Part 2
  "safe to read with no technical background" in its heading, so the one jargon-free
  section is findable rather than discoverable.
- **Mark every residual risk in §8 with the phase that would close it**, so the table reads
  as a backlog rather than a disclaimer list.
- **Keep a short changelog at the bottom** — one line per revision, naming what moved to
  `MVP_Plan_original.md` — so the next compression pass does not have to re-derive this
  one's reasoning.

---

## 10. References

**`findings/IDEA.md`** — the attack narrative. Source for §1 (core idea), §2 (the attack
summary: the three keys, the 1622 overlap and the other six numbers, the `P013174` worked
example, why the pack's scorer misses it), §4.2's before/after numbers, and step [6] of §5
Part 2's data flow.

**`findings/MVP_Plan_original.md`** — **the complete, unabridged prior version of this
document (646 lines), kept on disk specifically so that any detail compressed or cut here
can be recovered.** Source for everything else. What happened to each of its nine sections:

| Original section | Disposition | Lands in |
|---|---|---|
| §1 Attacker view (93 lines) | Cut to a ~15-line summary that cites `IDEA.md` instead of re-deriving it | §2 |
| §2 Requirements R1-R11 | One line per row; the five load-bearing ones (R3, R4, R2, R8, R9) keep a half-line of justification | §3 |
| §3 Scope (4 datasets, 9 non-goals) | Narrowed to 2 datasets; ENERGY-S3 + CS-S1 relocated, not cut; non-goals to 4 clauses | §4.1, §4.2, §4.3 |
| §4 Architecture (8 components + diagram + reuse table) | Merged into one unified diagram showing the modules **and** the agent together | §5 Part 1 |
| §4.2a "In plain English" panel | Superseded by the arrow-by-arrow plain-language data flow — same spirit, different shape | §5 Part 2 |
| §5 Novel-attack process (~65 lines) | Compressed to five bullets | §4.3 |
| §6 Milestones M0-M6 | Replaced entirely by an hour-budget phase table | §6 |
| §7 Residual risk R-1..R-9 + honest claim | Top four risks only — **R-2 replaced by R-9**, reasoning stated in §8 — with the honest-claim blockquote carried near-verbatim | §8 |
| §8 Agentic layer (6 LangGraph nodes, A0-A4, AR-1..AR-6) | Collapsed to **one** agent inside the architecture diagram; the staged rollout reduced to one line | §5 Part 1 |
| §9 Tech stack (figures B1-B5, 4-step workflow, OPS-1) | B1 and B2 kept, B3-B5 deferred; workflow to one line each; OPS-1 to one line | §7, §6 |

Nothing was deleted without a trace.
