# P8 Multi-agent Groq — IMPLEMENTATION PLAN (A2)

Full plan from planner. Coder: implement literally. Key facts:

- `agent_runtime` is **linear** (first successor only) → one chain, one edge per node.
- Do **NOT** edit `run_attack_sim.py` — P8 is parallel via `run_agents.py`.
- Do **NOT** touch resources/, mosaic_check, protect, normalize, pet_pipeline, attack_sim, agent_runtime.
- Default Groq model: `openai/gpt-oss-120b` (NOT retired llama-3.3-70b-versatile).
- Kill switch: no key / `--agents off` → deterministic only.
- AR-4: `agent_contracts.assert_clean` before every Groq call; never catch ContractViolation softly.
- Stub redact/discover: zero LLM, zero free text.

## New files
1. `app/agent_contracts.py` — PROMPT_VERSION, scan/assert_clean, selftest (9 cases)
2. `app/groq_client.py` — GroqConfig/GroqClient/stub via urllib
3. `app/agent_nodes.py` — supervisor, classify, minim, brief, redact/discover stubs
4. `app/run_agents.py` — CLI
5. `scripts/final/run_agents.sh` — thin wrapper
6. `findings/agent_groq.md` — env pin

## Edit
- `app/agent_graph.py` — `build_graph(..., agents_enabled=, enable_a3=)` linear chain
- `CLAUDE.md`, `INSTRUCTION.md`, `USAGE.md`, `scripts/final/STEPS.md`

## Verify (no GROQ_API_KEY)
```bash
unset GROQ_API_KEY
bash scripts/final/ops1_manifest.sh verify
bash scripts/final/measure_baseline.sh
bash scripts/final/run_agents.sh --selftest
bash scripts/final/run_protect.sh --init-key
cp clean_data/mosaic_check.json /tmp/m_before.json || bash scripts/final/mosaic_check.sh
bash scripts/final/mosaic_check.sh
cp clean_data/mosaic_check.json /tmp/m_before.json
bash scripts/final/run_agents.sh --agents off --mode shadow
bash scripts/final/run_agents.sh --agents auto --mode shadow
bash scripts/final/run_agents.sh --agents on --mode shadow ; echo expect_fail:$?
bash scripts/final/run_agents.sh --agents on --llm-stub --mode shadow
bash scripts/final/mosaic_check.sh
diff /tmp/m_before.json clean_data/mosaic_check.json
bash scripts/final/run_attack_sim.sh --mode shadow
bash scripts/final/ops1_manifest.sh verify
```

Note: mosaic_check may not have `--out`; use copy of `clean_data/mosaic_check.json` for byte-identical check.
