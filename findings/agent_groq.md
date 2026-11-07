# Groq multi-agent layer (P8 A2)

## Environment variables

**You only need key + model.** Put them in a gitignored repo-root `.env`
(`cp .env.example .env`) or export them in your shell. `scripts/material/common.sh`
and `app/groq_client.py` load `.env` automatically. **Do not set `GROQ_API_BASE`
unless you are pointing at a non-default host** — the client already defaults to
`https://api.groq.com/openai/v1`.

| Variable | Role |
|---|---|
| `GROQ_API_KEY` | Required for live Groq calls; never commit; use `.env` |
| `GROQ_MODEL` | Default `openai/gpt-oss-120b` |
| `GROQ_API_BASE` | Optional; default `https://api.groq.com/openai/v1` |
| `GROQ_TEMPERATURE` | Default `0.1` |
| `GROQ_MAX_TOKENS` | Default `800` |
| `GROQ_TIMEOUT` | Default `20` (seconds) |

The retired model `llama-3.3-70b-versatile` (free/developer tier, 2026-08-16) must not
be used. List live model ids:

```bash
curl -s -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models
```

## Kill switch (`run_agents.sh`)

| Flag / env | Behaviour |
|---|---|
| `--agents off` | Deterministic `attack_sim` → `human_review` only |
| `--agents auto` (default) | Specialists on iff `GROQ_API_KEY` is set |
| `--agents on` | Error exit if key missing (unless `--llm-stub`) |
| `--llm-stub` | Full graph, canned JSON responses, no network |

## Never sent (AR-4)

Raw `hetu` / `patient_hetu` / `phone` / `iban` / `email`, direct name/address columns,
`attack_sim` `samples`, `rowmap_*.csv`, anything under `truth/`, `keys/master.key`.

Enforced in `app/agent_contracts.py` (`assert_clean`), called inside `GroqClient.chat`
before every request. Offline verification:

```bash
bash scripts/final/run_agents.sh --selftest
```

## Artefacts

Proposals: gitignored `findings/agent_proposals/<thread_id>.agents.json`. The gate
record remains `clean_data/mosaic_check.json` — agents do not write `clean_data/`.
