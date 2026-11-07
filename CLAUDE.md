# SinceAI

## Project
<!-- One paragraph: what this project is, input -> output. Point at the doc
     that holds the full technical plan (if one exists) instead of
     duplicating it here. -->
SinceAI builds a cross-release mosaic defence for the TrustED PETs proving
ground: unprotected pack releases in -> protected releases out that no longer
join across controllers. The first check re-measures Attack A's health ∩
finance baseline and locks it at 1622 (HETU) / 1484 (normalised phone). Full
technical plan: `findings/MVP_Plan.md`.

## Commands
<!-- Every command an agent might need to run: dev setup, build, lint,
     test, any pipeline/CLI scripts. Fill these in before running
     /code-task — the agents below are told to never invent commands. -->
- Dev environment setup: project requires **Python >=3.10** everywhere
  (`app/python_version.py`'s `require_python()` enforces this at import
  time in every entry point except `run_scorecard.py`, which still
  degrades gracefully). `.python-version` pins `3.13.15` via pyenv — with
  pyenv initialised in your shell, `pyenv install 3.13.15` once and `cd`
  into the repo is enough; otherwise point `python3` at any >=3.10
  interpreter yourself.
- Test: `bash scripts/final/measure_baseline.sh`  (exit 0 iff HETU=1622 and phone=1484)
- Gate (P3): `bash scripts/final/mosaic_check.sh`  (PASS-1 zeros + PASS-2 1622/1484)
- Protect (P1): `bash scripts/final/run_protect.sh --init-key`
- Attack-sim (P2 shadow): `bash scripts/final/run_attack_sim.sh --mode shadow`
- Scorecard (P3, needs the toolkit installed: `pip install -e resources/.../toolkit`): `bash scripts/final/run_scorecard.sh` (exits 4, not an error, if the toolkit isn't installed yet)
- Release pipeline (P6): `bash scripts/final/run_release.sh` (OPS-1 verify → attack raw → protect → re-attack → mosaic gate → analyze HTML under `analyze/no_AI/` → OPS-1 verify)
- Demo (P7): `bash scripts/final/run_demo.sh`
- Agents (P8, A2 — advisory, off by default): `bash scripts/final/run_agents.sh --agents auto --mode shadow` (reduces to deterministic `attack_sim` when `GROQ_API_KEY` is unset); offline graph run: `--agents on --llm-stub`
- Agent AR-4 contract self-test (no key, no network): `bash scripts/final/run_agents.sh --selftest`
- Groq env vars: `findings/agent_groq.md`
- Analyze HTML (raw vs protected + joins + scorecards): `bash scripts/final/run_analyze.sh` → `analyze/index.html`
- Benchmarks (P4): `pip install -r requirements-benchmark.txt` then `bash scripts/final/make_benchmark.sh`
- OPS-1 manifest (P5): `bash scripts/final/ops1_manifest.sh build|verify|selftest` (committed `manifests/pack_data_sha256.json`)
- Usage doc: `INSTRUCTION.md`
- Lint / type-check: `<fill in>`
- Build: `<fill in>`

## Conventions
<!-- Folder layout, commit style, naming — whatever a new contributor
     (human or agent) would otherwise have to guess. -->
- Folder structure:
  - `app/` — all Python (PET pipeline, gate, demo, OPS-1, …)
  - `scripts/material/` — shared bash helpers, sourced not run (`common.sh`: `ROOT` resolution + OPS-1 guard)
  - `scripts/final/` — user-facing shell entry points only (no `.py` here), plus `STEPS.md`
  - `clean_data/` — gitignored protected release output (`<dataset>__<SID>/`)
  - `keys/` — gitignored HMAC master secret (`master.key`)
  - `resources/…` — read-only OPS-1 pack (never write here)
- Commit style: Conventional Commits — see `CONTRIBUTING.md`.
- Things Claude must never do:
  - edit `resources/…` in place or write outputs under `resources/`
  - commit `keys/` or `clean_data/`
  - drop FIN-S2 glue keys (`hetu`/`phone`/`iban`/`email`) instead of tokenising them
  - add `phone` to HEALTH-S1 `TOKENISE_IDENTIFIERS` (phone must not be tokenised on health)
  - tokenise FIN-S2 direct name/address columns (`full_name`/`street_address`) — drop those instead
  - commit `findings/agent_proposals/` or `findings/agent_checkpoints/` (raw-pack attack evidence)
  - let the agent write `clean_data/` or set a release PASS
  - invent a second phone-norm recipe or retune 1622/1484 to pass checks
  - treat PASS-1 alone as release-safe without PASS-2 (or use `--skip-pass2` in production)
  - write `samples` / `proposals` into `mosaic_check.json` (gate uses `sample_limit=0`)
  - lower `app/python_version.py`'s floor back below 3.10 to work around a stale interpreter
  - send raw `hetu`/`patient_hetu`/`phone`/`iban`/`email`, attack-sim `samples`, `rowmap_*.csv`, `truth/*` or `keys/master.key` to Groq (AR-4 — `app/agent_contracts.py` is the chokepoint; never catch `ContractViolation`)
  - commit a `GROQ_API_KEY` or any API key, or put one in `findings/agent_groq.md`
  - wire `run_agents.sh` into `run_release.sh` / `run_demo.sh`, or let an agent node change a gate exit code or write `clean_data/`
  - implement free-text egress in `redact_assist`/`discover_assist` — they are A3-scope stubs (AR-1)

---

## Multi-agent workflow
<!-- This section and "Model policy" below are the reusable part of this
     template — copy them as-is into every project's CLAUDE.md. They
     describe the coordinator in .claude/commands/code-task.md and the two
     subagents in .claude/agents/. -->

This workflow uses **two agents only** — planner and coder. The planner
investigates (it measures and verifies before it plans), and the coder
implements and runs the project's own test/lint/build commands itself,
reporting the real output.

- Write a task in `Artifacts/TASK.md` and run `/code-task`.
- Only the coordinator (the `/code-task` command, run in the main session —
  not a subagent) writes `Artifacts/state.json`.
- Agent definitions live in `.claude/agents/` (`planner`, `coder`); the
  coordinator lives in `.claude/commands/code-task.md`.
- Route: **planner → coder → done** (retried on failure, see below).
- The planner runs first: it investigates (reads the relevant code and
  data, measures rather than assumes, researches externally when the task
  needs it, verifies the claims `TASK.md` itself makes) and then writes a
  plan concrete enough for a cheaper model to implement literally. It
  produces facts *and* a plan — the coder gets both in one handoff.
- The coder implements the plan, then runs the verification commands from
  `CLAUDE.md` itself and reports the real result — pass or fail — to the
  coordinator.
- After 2 failed attempts in a row, the coordinator stops and asks you
  instead of retrying again.
- If an agent dies because the **session/usage limit was hit**, that is a
  pause, not a failure: the coordinator records `status: "paused_rate_limit"`
  in `Artifacts/state.json`, leaves `consecutive_failures` untouched, reports
  what already landed on disk, and stops. Say "continue" once the limit
  resets — it picks up from the interrupted step rather than restarting, and
  never downgrades the model to get around the limit.

### Model policy (a constraint, not a default)
Opus is for **thinking**, never for typing. The reasoning budget is spent
upstream so the plan is detailed enough for a cheaper model to implement.

| agent | model |
|---|---|
| planner | **`opus`** — always; it's the only thinking step |
| coder | `sonnet` — always, never escalated |

- **The planner always runs on Opus.** It does both the investigation and
  the planning, so it carries the full reasoning budget for this workflow.
- **Never run the coder on Opus** — not on a retry, not when a task looks
  hard. If the coder struggles, the plan wasn't detailed enough: go back to
  the planner, don't upgrade the coder's model. The two-consecutive-failure
  stop above is the backstop, not a model upgrade.
- Because the coder runs on a smaller model, the planner **must** produce
  explicit step-by-step instructions — exact files, line numbers, values and
  call shapes — so the coder can implement literally without re-deriving
  anything.

- All agents and the coordinator treat this file as the source of truth for
  commands and conventions — they do not duplicate them elsewhere.
