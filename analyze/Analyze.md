# Analyze: no_AI vs AI

Side-by-side of the two HTML reports under this folder. Both use the same Attack A
instrument and HEALTH-S1 / FIN-S2 MVP; the AI path only applies **advisory**
`minim_assist` drop candidates, then re-protects.

| Report | Open |
|---|---|
| Default protect (no agent applied) | [`no_AI/index.html`](no_AI/index.html) |
| After applying Groq `minim_assist` | [`AI/index.html`](AI/index.html) |

## How each report was produced

**no_AI**

1. `run_release.sh` / `run_protect.sh` with default `TOKENISE_IDENTIFIERS`
2. `run_analyze.sh --out-dir analyze/no_AI`

**AI** (latest refresh)

1. `run_agents.sh --agents on --mode shadow`  
   → `findings/agent_proposals/20261107T144056Z.agents.json`
2. Apply `minim_assist` candidates: **drop** FIN-S2 `email`, `phone`  
   (temporary: remove them from `TOKENISE_IDENTIFIERS` so they drop as direct IDs)
3. `run_protect.sh` → `run_scorecard.sh` → `run_analyze.sh --out-dir analyze/AI`
4. Restore default TOKENISE and re-protect `clean_data/` (working tree back to default)

See also [`AI/NOTE.txt`](AI/NOTE.txt).

## Main differences

### FIN-S2 column plan (the real delta)

| | no_AI | AI |
|---|---|---|
| Columns | **17 → 15** | **17 → 13** |
| Dropped | `full_name`, `street_address` | those + **`email`**, **`phone`** |
| Tokenised | `hetu`, `phone`, `iban`, `email` | **`hetu`**, **`iban`** only |

HEALTH-S1 protect plan is the same in both reports (agent had no uncatalogued columns / no health drop candidates in that run).

### Mosaic joins (Attack A) — no difference

| | Raw `data/` | After protect |
|---|---|---|
| HETU ∩ | 1622 | **0** (both) |
| Phone ∩ | 1484 | **0** (both) |

Keyed tokens already break cross-release joins. Dropping extra finance glue does not change PASS-1 once joins are already zero.

### Scorecard metrics — little / no difference

| Scenario | Metric | no_AI | AI |
|---|---|---|---|
| HEALTH-S1 | privacy / utility / composite | 0.3791 / 0.5928 / 0.4534 | same |
| FIN-S2 | privacy / utility / composite | 0.3375 / **0.0** / **0.0** | same |

FIN-S2 utility/composite stay **0** because required tasks (FIN-U1 / U4 / U6) need
`cards` / `card_transactions`, which this MVP **withholds**. Dropping `email`/`phone`
does not make those tasks answerable.

## What the agent changed vs what it did not

| Changed | Did not change |
|---|---|
| FIN-S2 shape: two more columns dropped (`email`, `phone`) | Mosaic join counts (still 0 / 0) |
| Demo-row actions in the HTML (tokenised → dropped for those cols) | HEALTH-S1 column plan |
| | Headline pets-eval scores on this MVP |

**Bottom line:** On this project, AI advice is a **minimisation co-pilot** (drop unused tokenised contact fields). It is **not** what stops Attack A — default keyed tokenisation already does — and it does **not** fix FIN-S2 scorecard utility while card tables stay withheld.

## Quick open

```bash
open analyze/no_AI/index.html
open analyze/AI/index.html
```
