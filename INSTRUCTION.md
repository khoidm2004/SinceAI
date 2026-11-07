# SinceAI — attack, defend, measure

SinceAI is a cross-release mosaic defence for the TrustED PETs proving ground:
unprotected pack releases in, protected releases out that no longer join on HETU or
normalised phone across health and finance. **Always run commands from the repo
root.**

Shell entry points live in `scripts/final/` (shared helpers in `scripts/material/`);
Python implementation is under `app/`. Requires **Python ≥3.10** (`.python-version`
pins `3.13.15` via pyenv). Technical plan: [`findings/MVP_Plan.md`](findings/MVP_Plan.md).

## Before you start

| Path | Role |
|---|---|
| `app/` | Protect, attack-sim, mosaic gate, demo, OPS-1 |
| `scripts/final/` | User-facing shell entry points |
| `resources/` | Read-only TrustED pack (**never edit**) |
| `clean_data/` | Protected releases (gitignored; created by protect) |
| `keys/` | HMAC master key (gitignored; `--init-key` creates it) |

`scripts/material/common.sh` picks a qualifying Python interpreter automatically.

## 0. Verify the pack is intact (OPS-1)

```bash
bash scripts/final/ops1_manifest.sh verify
```

Expect: `verify OK` (exit 0). Do **not** run `ops1_manifest.sh build` just to silence
a failure — that overwrites committed evidence.

## 1. Attack the UNPROTECTED data

Measure Attack A on raw pack `data/` and show the join succeeds:

```bash
bash scripts/final/measure_baseline.sh
bash scripts/final/run_attack_sim.sh --mode shadow --raw-pack
```

Expect: HETU join **1622**, phone join **1484** (baseline lock). Raw-pack attack-sim
may write evidence under `findings/agent_proposals/` and `findings/agent_checkpoints/`
(gitignored — never commit).

The narrated demo (step 2) replays the same join code on the worked-example HETU
`021280-9730` before any defence runs.

## 2. Defend

Build protected releases under `clean_data/` — keyed tokens and drops driven by the
pack classifier, not blanket blanking of glue columns:

```bash
bash scripts/final/run_protect.sh --init-key
```

**FIN-S2 (`customers.csv`) expected shape:**

- Columns: **17 → 15** (utility fields retained where safe)
- **Dropped:** `full_name`, `street_address` (direct identifiers)
- **Tokenised (per-release keys):** `email`, `hetu`, `iban`, `phone` — columns stay
  present but do not join across releases

**HEALTH-S1:** `patient_hetu` tokenised; `phone` left raw within the release (do not
tokenise phone on health — token normalisation can re-introduce cross-release joins).

Re-run protect whenever you change `app/pet_pipeline.py` or delete `clean_data/`.

## 3. Re-attack and gate

Re-run the **same** Attack A on `clean_data/` and run the mosaic gate (PASS-1 zeros +
PASS-2 baseline reproduction on raw `data/`):

```bash
bash scripts/final/run_attack_sim.sh --mode shadow
bash scripts/final/mosaic_check.sh
```

Expect: protected joins **0 / 0**; gate `VERDICT: PASS` (exit 0). PASS-1 alone is
not release-safe without PASS-2.

## 4. Metrics

Compare before and after:

| Metric | Raw `data/` | `clean_data/` |
|---|---|---|
| HETU join | 1622 | 0 |
| Phone join | 1484 | 0 |

Artifacts:

- `clean_data/mosaic_check.json` — full gate report
- `bash scripts/final/run_scorecard.sh` — pets-eval per-scenario scorecard (needs
  toolkit: `pip install -e resources/.../toolkit`; exits **4** if unavailable)
- `bash scripts/final/make_benchmark.sh` — B1 mosaic-join chart (`benchmarks/B1_mosaic_joins.png`)
  and B2 once scorecards exist

## 5. Multi-agent layer (P8 — optional, advisory)

The Groq layer is **advisory only** — it cannot pass a release or change gate
artefacts. With no API key it reduces to the deterministic `attack_sim` path.

```bash
# Kill switch — same as attack_sim on clean_data/
bash scripts/final/run_agents.sh --agents off --mode shadow

# Offline full graph (canned LLM responses)
bash scripts/final/run_agents.sh --agents on --llm-stub --mode shadow

# Auto: specialists run only when GROQ_API_KEY is set
bash scripts/final/run_agents.sh --agents auto --mode shadow
```

Environment variables and AR-4 rules: [`findings/agent_groq.md`](findings/agent_groq.md).
Proposals land under gitignored `findings/agent_proposals/` (`*.agents.json`).

Contract self-test (no key, no network):

```bash
bash scripts/final/run_agents.sh --selftest
```

## One command for all of it

**Full release pipeline** (attack raw → protect → re-attack → gate, wrapped in OPS-1):

```bash
bash scripts/final/run_release.sh
```

**Narrated jury demo** (raw attack story → defend → zeros → metrics):

```bash
bash scripts/final/run_demo.sh --skip-protect   # after protect once
# or without --skip-protect to build clean_data/ inside the demo
```

Step-by-step script reference: [`scripts/final/STEPS.md`](scripts/final/STEPS.md).

## What we do not claim

- **Anonymous** or “safe to publish together” — only that measured identifier joins on
  HETU and phone are **zero** between these two releases under stated assumptions.
- **Closed residual risk** — quasi-identifier mosaic, key compromise, pack blind spots,
  and free-text gaps remain documented.
- **Utility numbers we did not measure** — no invented scorecard metrics when pets-eval
  is not installed.
- **truth/ person_ids** — the public walkthrough uses pack `data/` rows only.

## Known gap — free text is not redacted

Deterministic transforms cover catalogued columns (drop / tokenise / generalise). **Free
text** such as HEALTH-S1 `chief_complaint` is **not** safely rewritten by this
pipeline. The Groq multi-agent layer ships at **A2** (`supervisor`, `classify_assist`,
`minim_assist`, `brief_writer` in shadow/advisory mode). `redact_assist` and
`discover_assist` are **A3 stubs that send no free text** — narrative fields are still
not redacted here; do not expect this repo to fake LLM redaction.

## Troubleshooting

- **`ops1_manifest.sh verify` fails** — `resources/` drifted from
  `manifests/pack_data_sha256.json`; investigate, do not blindly rebuild the manifest.
- **Missing `keys/master.key`** — `bash scripts/final/run_protect.sh --init-key`.
- **`mosaic_check.sh` missing CSV** — run protect first; if you changed FIN-S2 tokenise
  policy, re-run protect so `clean_data/` is not stale.
- **Stale `clean_data/` after pipeline changes** — delete `clean_data/` and re-run
  `run_protect.sh --init-key` before trusting mosaic output.
- **`run_scorecard.sh` exits 4** — install Python ≥3.10 and the vendored toolkit for
  the interpreter `common.sh` selected.
- **Join counts not 1622 / 1484 on raw data** — do not retune thresholds; fix the
  join code or pack paths instead.
