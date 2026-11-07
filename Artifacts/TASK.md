# Task

Implement **P8** from `findings/MVP_Plan.md` §5.3 / §6: the **multi-agent
layer on Groq**, without moving the deterministic gate and without breaking
offline P0–P7 demos when no API key is present.

## Goals

1. **Groq provider adapter** in `app/` — single chat interface; config from
   env (`GROQ_API_KEY`, `GROQ_MODEL`, optional `GROQ_API_BASE`). Model/API
   may stay defaulted placeholders; never commit secrets.
2. **Multi-agent graph** extending today’s `attack_sim` → `human_review`:
   - Keep `attack_sim` **deterministic** (no LLM).
   - Add specialist nodes: `supervisor`, `classify_assist`, `minim_assist`,
     `brief_writer` at minimum (A2 scope). Optionally stub
     `redact_assist` / `discover_assist` behind the same adapter for A3
     readiness, but they may no-op or run only when explicitly enabled.
   - `human_review` stays fail-closed; shadow mode logs only.
3. **Kill switch**: if `GROQ_API_KEY` missing or `--agents off`, graph
   reduces to deterministic `attack_sim` (+ human_review as today). Release
   path and mosaic gate must still PASS with agents disabled.
4. **Input contracts (AR-4)**: never send raw `hetu`/`phone`/`iban`/`email`,
   keys, `truth/`, or `rowmap_*.csv` to Groq. Specialist prompts get schema
   names, aggregates, mosaic/scorecard JSON numbers, or free text only via
   `redact_assist` when enabled (treat as untrusted data).
5. **CLI / shell**: wire a usable entry (extend `run_attack_sim.py` and/or
   add `app/run_agents.py` + `scripts/final/run_agents.sh`) with
   `--mode shadow|advisory`, `--agents on|off|auto`.
6. **Docs**: update `INSTRUCTION.md`, `CLAUDE.md` Commands, and a short
   `findings/agent_groq.md` pin for env vars. Do not modify `resources/`.

## Non-goals

- Do not replace `mosaic_check` / protect / scorecard with LLM logic.
- Do not write under `clean_data/` from agents.
- Do not require a live Groq key for verification to pass — offline path is
  mandatory for CI/demo.
- Do not invent join counts in `discover_assist`.

## Verification

```bash
bash scripts/final/ops1_manifest.sh verify
bash scripts/final/measure_baseline.sh
# agents off / no key — still works:
bash scripts/final/run_attack_sim.sh --mode shadow
# if run_agents exists:
bash scripts/final/run_agents.sh --agents off --mode shadow || true
bash scripts/final/mosaic_check.sh
# nothing under resources/ dirty
```

With a key (optional, not required for PASS): shadow run logs a proposal
JSON under `findings/agent_proposals/` without changing gate results.

# Notes

- Trunk `main`. Work on `task/p8-multi-agent-groq`.
- Prefer stdlib + `urllib` for the Groq OpenAI-compatible HTTP client so we
  do not force a heavy SDK; optional dependency ok if documented.
- Keep `app/agent_runtime.py` as the orchestrator shim unless swapping to
  real LangGraph is trivial and pinned — do not break existing attack_sim.
- Conventional Commits. Never commit `keys/`, `clean_data/`, or API keys.
