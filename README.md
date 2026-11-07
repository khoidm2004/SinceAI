# SinceAI

SinceAI builds a cross-release mosaic defence for the TrustED PETs proving ground: unprotected pack releases go in, protected releases come out that no longer join across health and finance on HETU or normalised phone. Attack A is measured on raw `data/` first (baseline lock), then defence closes the join on `clean_data/` before the mosaic gate ships a release.

**Python lives in `app/`. Terminal entry points are shell scripts under `scripts/final/` (shared helpers in `scripts/material/`).**

**Start here:** [`INSTRUCTION.md`](INSTRUCTION.md) — attack, defend, measure, and expected outcomes.

```bash
bash scripts/final/ops1_manifest.sh verify
bash scripts/final/measure_baseline.sh
bash scripts/final/run_release.sh    # or run_demo.sh for the narrated path
```

Technical plan: [`findings/MVP_Plan.md`](findings/MVP_Plan.md).  
Script phases: [`scripts/final/STEPS.md`](scripts/final/STEPS.md).  
Analyze HTML (raw↔protected + joins + scorecards): `bash scripts/final/run_analyze.sh` → `analyze/index.html`.

## How the app behaves

Pipeline order:

1. **Attack raw** — measure Attack A on pack `data/` (baseline lock: HETU **1622** / phone **1484**).
2. **Protect** — `run_protect.sh` / `pet_pipeline.py` drop, keyed-tokenise, and generalise → write `clean_data/` (e.g. FIN-S2 **17 → 15**: drop `full_name` / `street_address`; tokenise glue `hetu` / `phone` / `iban` / `email`).
3. **Re-attack** — same join instrument on `clean_data/` (expect **0 / 0**).
4. **Optional Groq agents** — advisory pass on already-built releases (`run_agents.sh`).
5. **Mosaic gate** — `mosaic_check` still decides PASS/FAIL (`clean_data/mosaic_check.json`).

Release / demo wrappers:

- `bash scripts/final/run_release.sh` — verify → attack raw → protect → re-attack → mosaic gate → verify
- `bash scripts/final/run_demo.sh` — OPS-1 verify → narrated attack/defend story → OPS-1 verify

Agents are **not** wired into `run_release.sh` / `run_demo.sh`. Run them beside the gate when you want proposals:

```bash
bash scripts/final/run_protect.sh --init-key
bash scripts/final/run_agents.sh --agents on --mode shadow   # needs GROQ_API_KEY / .env
bash scripts/final/mosaic_check.sh
```

## Where the AI agent takes place

Agents run **after** protect, on already-built releases. They do **not** choose which columns leave the file.

| Piece | Role in protection |
|---|---|
| `run_protect.sh` / `pet_pipeline.py` | **Real defence** — drop / tokenise / generalise → writes `clean_data/` |
| `attack_sim` | Deterministic join check (instrument, **not** an LLM) |
| Groq `supervisor` / `classify_assist` / `minim_assist` / `brief_writer` | **Advisory only** — proposals + brief under `findings/agent_proposals/` |
| `mosaic_check` | Still the PASS/FAIL gate |

`minim_assist` can *suggest* dropping tokenised columns that look unused for utility. Those suggestions are **logged, not applied**. Stub / empty runs often return `"candidates": []`. Agents cannot write `clean_data/`, flip mosaic / scorecard exit codes, or invent a PASS. Env and AR-4 rules: [`findings/agent_groq.md`](findings/agent_groq.md).

## Why tokenise + optional agents is better

Compared with blank-dropping every direct identifier (older “drop all glue” shape → fewer usable columns):

- **Utility** — Fraud / KYC-style fields and within-release linkage stay usable; deleting glue nukes that.
- **Same mosaic stop** — Per-release HMAC means health ∩ finance joins still go to **0**; you do not need to delete the columns to break Attack A.
- **Minimisation as review** — Agents can flag “this tokenised column might be droppable,” but a human / the gate still owns the decision.
- **Clearer evidence** — Gate numbers stay in JSON; the brief explains beside the record, it does not replace it.
