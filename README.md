# SinceAI

Cross-release **mosaic defence** for the TrustED PETs proving ground: unprotected pack releases in → protected releases out that no longer join across controllers on HETU or normalised phone.

**Code:** `app/` · **Commands:** `scripts/final/` · **Runbook:** [`INSTRUCTION.md`](INSTRUCTION.md)

```bash
bash scripts/final/ops1_manifest.sh verify
bash scripts/final/measure_baseline.sh
bash scripts/final/run_release.sh    # or run_demo.sh for the narrated path
```

## Scenario (MVP)

**Threat story.** Pack scenarios (HEALTH-S1, FIN-S2 in `metadata/scenarios.json`) define two *separate* outward releases for different recipients. A **linkage attacker** who obtains *both* extracts — e.g. via leak, resale, or a black-market dump — can join on shared identifiers (HETU / phone) to rebuild a richer profile (health + finance) and abuse it (phishing, fraud, scams). They need not hack either controller live: the harm is in **combining** releases that still share joinable glue.

**SinceAI** role-plays that attacker on unprotected pack `data/` (baseline joins), then protects so the same join fails on `clean_data/`.

```text
Controller(s)
   │
   ├── HEALTH-S1 extract ──► University research group
   │                              │
   └── FIN-S2 extract ─────► AI vendor (processor)
                                  │
                                  ▼
                    Linkage attacker (holds both extracts)
                                  │
                                  ▼
                    HETU / phone join  →  mosaic profile
                    (raw data/: 1622 / 1484 people)
                                  │
                    SinceAI protect (per-release HMAC)
                                  │
                                  ▼
                    same join on clean_data/  →  0 / 0
```

Exactly **two** pack scenarios / tables — the pair Attack A joins on:

| Scenario | Table | Trust | Recipient (pack intent) | Protect choice |
|---|---|---|---|---|
| **HEALTH-S1** | `data/health/ed_visits.csv` | `controlled_research` | University research: LOS, revisits, diagnosis mix | Tokenise `patient_hetu` (stable pseudonym required); do **not** tokenise health `phone` |
| **FIN-S2** | `data/finance/customers.csv` | `contractual` | AI vendor (processor): fraud / spending model | Drop `full_name` / `street_address`; keyed-tokenise `hetu` / `phone` / `iban` / `email` (**17 → 15** cols) |

Scenarios answer *who may receive each release and why*. The attacker story answers *what goes wrong if both extracts still share joinable glue*. Same person must get a **different** HMAC token in each release so health ∩ finance cannot re-link. Other pack datasets / scenarios are out of MVP scope. Plan detail: [`findings/MVP_Plan.md`](findings/MVP_Plan.md) §4; attack account: [`findings/IDEA.md`](findings/IDEA.md).

## Metrics outputs (short)

| Signal | Where | What “good” looks like |
|---|---|---|
| **Attack A joins** | `measure_baseline` / `attack_sim` / mosaic PASS-2 | Raw: HETU (Finnish personal identity code) **1622**, phone **1484** (baseline still works) |
| **Mosaic gate** | `clean_data/mosaic_check.json` | PASS-1: joins on `clean_data/` are **0 / 0**; PASS-2: baseline reproduced; `verdict: PASS` |
| **pets-eval scorecard** | `clean_data/<dataset>__<SID>/scorecard.json` | **Privacy** / **utility** / **composite** per [`docs/EVALUATION.md`](resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/docs/EVALUATION.md) — self-assessment, not official judging |
| **Analyze HTML** | `analyze/index.html` via `run_analyze.sh` | One demo row raw↔protected, joins before/after, scorecards side by side |

**Scorecard reading tip:** privacy = `1 − (0.5×worst + 0.5×mean risk)`; utility = mean of the scenario’s tasks (required but unanswerable → 0); composite = weighted harmonic mean (privacy 30, utility 25). FIN-S2 utility/composite can be **0** in this MVP because required tasks (FIN-U1/U4/U6) need `cards` / `card_transactions`, which are **withheld** — only `customers.csv` is released. That does not mean the mosaic join defence failed.

## How the app behaves

1. **Attack raw** — measure Attack A on pack `data/` (baseline lock).
2. **Protect** — `run_protect.sh` / `pet_pipeline.py` drop / tokenise / generalise → `clean_data/`.
3. **Re-attack** — same join instrument on `clean_data/` (expect **0 / 0**).
4. **Optional Groq agents** — advisory only (`run_agents.sh`); not inside protect.
5. **Mosaic gate** — `mosaic_check` decides PASS/FAIL.

Wrappers:

- `run_release.sh` — OPS-1 verify → attack raw → protect → re-attack → gate → analyze (`analyze/no_AI/`) → verify
- `run_demo.sh` — narrated attack → defend → measure (OPS-1 wrapped)

Agents are **not** wired into those wrappers. Beside the gate when needed:

```bash
bash scripts/final/run_protect.sh --init-key
bash scripts/final/run_agents.sh --agents on --mode shadow   # GROQ_API_KEY / .env
bash scripts/final/mosaic_check.sh
```

## Where the AI agent takes place

Agents run **after** protect on already-built releases. They do **not** choose which columns leave the file.

| Piece | Role |
|---|---|
| `run_protect.sh` / `pet_pipeline.py` | **Real defence** — writes `clean_data/` |
| `attack_sim` | Deterministic join check (**not** LLM) |
| Groq `supervisor` / `classify_assist` / `minim_assist` / `brief_writer` | **Advisory** — proposals + brief → `findings/agent_proposals/` |
| `mosaic_check` | PASS/FAIL gate |

`minim_assist` may *suggest* dropping tokenised columns; suggestions are **logged, not applied**. Agents cannot write `clean_data/`, flip gate exit codes, or invent a PASS. Env / AR-4: [`findings/agent_groq.md`](findings/agent_groq.md).

## Why tokenise + optional agents

- **Utility** — within-release linkage and profile fields stay usable; blank-dropping all glue does not.
- **Same mosaic stop** — per-release HMAC still drives health ∩ finance joins to **0**.
- **Minimisation as review** — agents flag candidates; human / gate own the decision.
- **Evidence** — JSON numbers remain the record; the brief explains beside them.

## Further reading

| Doc | Role |
|---|---|
| [`INSTRUCTION.md`](INSTRUCTION.md) | Full attack → defend → measure runbook |
| [`scripts/final/STEPS.md`](scripts/final/STEPS.md) | Script phase index |
| [`findings/MVP_Plan.md`](findings/MVP_Plan.md) | Technical plan |
| Pack `docs/EVALUATION.md` / `docs/SCENARIOS.md` | pets-eval metrics and scenario text |
|Slides|https://canva.link/1dutfazmfhmyrgb|
|[Demo Video](https://youtu.be/upakRzSFs90)||

