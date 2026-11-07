# Dev diary

## 2026-11-07 — MVP plan for defending against the cross-domain mosaic attack (Attack A)

**Task:** Create `findings/MVP_Plan.md` — an MVP plan for a defensive tool/process
protecting the TrustED PETs Proving Ground datasets against the cross-domain
"mosaic" linkage attack documented in `findings/IDEA.md` (Attack A: phone/HETU/IBAN
glue across health, energy, finance, customer_service). Required: attacker view
first, derived defensive requirements, MVP scope, software architecture, a process
for handling the fact that this attack is novel vs. the pack's own metadata/tooling,
milestones, and residual risk — run via the planner → coder loop (`/code-task`).

**What was done:**
- Planner (opus) investigated `findings/IDEA.md`, `findings/CHA_SUMMARY.md`, and the
  vendored pack's `docs/`, `metadata/`, and `toolkit/pets_eval/`. Independently
  re-measured all 8 overlap numbers in IDEA.md directly from the raw CSVs and
  reproduced every one exactly (HETU health∩finance 1622, phone health∩finance 1484,
  phone health∩CS 2296, phone health∩energy 195, HETU health∩energy 194, IBAN
  energy∩finance 15, IBAN finance∩CS 150, truth triple-overlap 19).
- Confirmed structurally (not just by absence) that `metadata/attack_specs.json` and
  `metadata/scenarios.json` cannot express a cross-controller attack — every
  `"dataset"` field is a scalar string across all 16 attack specs and 27 scenarios —
  and that `scorecard.run_scorecard` fixes one domain per call
  (`toolkit/pets_eval/scorecard.py:286-290`), so a cross-release join check is
  impossible by signature, not merely unconfigured.
- Picked scenario IDs HEALTH-S1, FIN-S2, ENERGY-S3, CS-S1 for the MVP, each justified
  against the scenario's own recipient/trust/privacy-target fields; explicitly
  excluded FIN-S1 as the deliberate cross-controller shared-key anti-pattern.
- Designed the MVP architecture: per-recipient keyed HMAC pseudonymiser, a
  scenario-driven PET pipeline, a new `scripts/mosaic_check.py` cross-release join
  checker (with a positive control that must reproduce the 7 baseline counts), and
  continued use of `pets-eval scorecard` per release.
- Coder (sonnet) wrote `findings/MVP_Plan.md` (357 lines, all 7 required sections)
  verbatim per the plan, then copied it from the isolated worktree back to the main
  checkout (both `findings/` and `Artifacts/` are gitignored, so worktree and main
  checkout each have their own untracked copies).

**Files changed:**
- `findings/MVP_Plan.md` (new, 357 lines) — the MVP plan document.

**Test result:**
- `grep -n '^## [1-7]\.' findings/MVP_Plan.md` → exactly 7 lines, `## 1.` through
  `## 7.`, in ascending order. PASS.
- `wc -l findings/MVP_Plan.md` → 357. PASS.
- Citation spot-check: `docs/THREAT_MODEL.md:9` ("Mosaic effect..."),
  `docs/PET_PLAYBOOK.md:29` (joins/pseudonym-domains row),
  `toolkit/pets_eval/scorecard.py:286-290` (`domain = original_dir.name`) — all 3
  matched as cited. PASS.
- No other automated test/lint/build exists yet in this project (`CLAUDE.md`
  commands are unfilled placeholders).

## 2026-11-07 — Section 8: proposed LangGraph agent layer for MVP_Plan.md

**Task:** The user approved the plan's 7 sections and asked where AI agents
(a LangGraph multiagent system, rest of the stack TBD) could help across the
system, with the explicit requirement that agents **validate before tests
run**, since this handles sensitive Art. 9 personal data — run via the
planner → coder loop (`/code-task`) again.

**What was done:**
- Planner (opus) re-read the full, now-372-line `findings/MVP_Plan.md` (it
  had grown since the first pass — §4.2a was added in between) and grounded
  every proposed agent in an admitted gap already in the document: R-3
  (uncatalogued columns), R-2 (residual free-text leakage), R-6 + §5b step 1
  (the manual "Discover" step), and R-9 (unaudited minimisation). Explicitly
  named where agents must NOT go: `pseudonym_service`'s pure HMAC path and
  the mosaic checker's PASS-1/PASS-2 arithmetic — both must stay
  deterministic.
- Verified LangGraph's real human-in-the-loop mechanism against current
  docs (`StateGraph`, `interrupt()`, `Command(resume=...)`, mandatory
  checkpointer, `thread_id`) rather than inventing an API.
- Designed a redesigned data-flow diagram showing a 6-node LangGraph layer
  (supervisor + 5 specialists: `classify_assist`, `redact_assist`,
  `discover_assist`, `minim_assist`, `brief_writer`) sitting between the
  existing deterministic pipeline's staged output and the existing test
  gate (`mosaic_check.py` + `pets-eval scorecard`) — validate-before-test,
  never validate-instead-of-test — with two `interrupt()` checkpoints
  (`human_review` pre-test, `human_signoff` post-test, both fail-closed).
- Named 6 new risks the agent layer itself introduces (AR-1..AR-6),
  including prompt-injection risk from attacker-authorable free text
  (two of the five redacted columns are literally written by the party
  the threat model calls the attacker), and a governing invariant: no
  agent output may trigger an irreversible action without a deterministic
  re-run + the existing test gate + human sign-off.
- Staged a cautious rollout (A0-A4) starting only after the existing M4,
  beginning in pure shadow/advisory mode with zero gating power, with an
  explicit constraint that the M5 demo must remain demonstrable with the
  agent layer entirely switched off.
- Coder (sonnet) appended the content verbatim at 3 string-anchored edits.
- Coordinator mirrored the new section into `findings/MVP_Plan.html`
  (added a new violet `--agent` accent token to all three theme blocks,
  `badge--ar`/`badge--node` classes, 8 new subsections, and
  programmatically HTML-escaped the ASCII diagram via Python's
  `html.escape` to avoid manual transcription errors), then republished
  the artifact at the same URL.

**Files changed:**
- `findings/MVP_Plan.md` — Section 8 appended (580 lines total, +208).
- `findings/MVP_Plan.html` — Section 8 mirrored + new CSS tokens (1148
  lines total, +227).

**Test result:**
- `grep -n '^## [0-9]'` → `## 8.` is the highest-numbered heading. PASS.
- `grep -n '^### 8\.'` → exactly 7 subsections, 8.1-8.7. PASS.
- `grep -o 'AR-[0-9]' | sort -u` → AR-1 through AR-6 present, nothing
  beyond. PASS.
- Both forward-reference paragraphs (§4→§8, §7→§8) landed at their exact
  anchors. PASS.
- Pre-existing cross-references (R-3, §5b, §4.2a) still resolve — nothing
  was accidentally deleted. PASS.
- No stray HTML entities (`&lt;`/`&gt;`/`&amp;`) leaked into the markdown.
  PASS.
- `git status --short` empty (expected — `findings/` is gitignored).
- No `scripts/` or `custom_metadata/` directories created (design-only, as
  required). PASS.
- Diagram box-drawing characters confirmed aligned, byte-for-byte match
  against the staged source. PASS.
- HTML mirror: all `<section>`/`<div>`/`<table>`/`<ol>`/`<ul>`/`<li>`/
  `<blockquote>` tags balanced (32/34/15/9/7/70/5 each); no raw unescaped
  `<` outside a real tag; no double-escaped entities. PASS.

## 2026-11-07 — Section 9: workflow, tech stack, and the clean_data/ rename

**Task:** The user approved everything through Section 8, then gave concrete
implementation decisions — Python core, a benchmark-visualization library
recommendation (asked for, with reasoning, before implementing), a 4-step
shell-script workflow (config → clean → `clean_data/` → benchmark figures),
and a hard constraint that the original dataset under `resources/` must
never be modified, with an enforced safeguard in the scripts — and asked
to update the plan accordingly, via `/code-task` again.

**What was done:**
- Recommended `matplotlib` + `seaborn` over `plotly` for the benchmark
  figures (stated to the user directly before delegating): the output is
  a static, non-interactive, shell-script-produced artifact, so plotly's
  interactivity buys nothing and would add a `kaleido` dependency just to
  export a static image. Named 5 concrete figures (B1 mosaic join counts
  before/after, B2 privacy/utility/composite scores, B3 a QI distribution
  before/after, B4 redaction recall per glue type vs. target, B5
  k-anonymity group-size distribution).
- Planner (opus) re-read the full document, found **25** `pets_out`
  occurrences across 21 lines (TASK.md's "21" was a `grep -c` line count —
  4 lines actually carry 2 occurrences each), verified zero existing
  plotting dependency in `toolkit/` and that `scorecard.json` already
  contains before/after k-anonymity (no new computation needed for B5),
  and measured SHA-256 over the full 441 MB original dataset at **0.19 s**
  — the fact that justifies a full checksum-manifest re-verification as
  OPS-1's primary enforcement mechanism rather than "too slow to run
  every time."
- Renamed `pets_out/` → `clean_data/` throughout (3 ASCII-diagram lines
  needed hand-recalculated width adjustments since `clean_data` is 2
  characters longer; the other 22 occurrences were plain substitutions).
- Appended Section 9 (9.1 tech stack + the 5 named figures, 9.2 the
  4-step workflow mapped explicitly onto existing M1-M4/A0-A4 rather than
  a disconnected new scheme, 9.3 the OPS-1 safeguard: a committed
  SHA-256 manifest checked before and after every run, plus a
  path-resolution guard and read-only file access as complementary
  mechanisms) and a new milestone M6 for the benchmark script.
- A transient "Connection lost mid-response" server error interrupted the
  coder mid-verification (its last message was "Now let's run all 8
  verification commands"). Confirmed via direct inspection that all the
  edits had already landed correctly on disk, then independently re-ran
  all 8 of the planner's verification commands myself — all passed. This
  was not treated as a real implementation failure.
- Mirrored the rename and Section 9 into `findings/MVP_Plan.html` (fixed
  the same 3 diagram lines by hand, swept the rest with a safe `sed`
  after confirming the 3 tricky lines no longer contained the literal
  string, added the M6 row and full Section 9 content in the document's
  default teal theme), then republished the artifact.

**Files changed:**
- `findings/MVP_Plan.md` — rename + Section 9 appended (646 lines total).
- `findings/MVP_Plan.html` — rename + Section 9 mirrored (1218 lines
  total).

**Test result:**
- `pets_out` count: `0` (was 25). PASS.
- `clean_data` count: `35` in markdown, `15`+ in HTML (≥25 expected in MD
  given Section 9 itself adds more mentions). PASS.
- `pets-eval` count unaffected (43 in MD, 26 in HTML) — confirms the
  rename didn't collide with the similarly-spelled `pets-eval`/
  `pets_submission` strings. PASS.
- All 3 diagram lines: exact length and `|`-column positions verified by
  script against the planner's computed literals. PASS.
- `## 9.` present after `## 8.`, with `### 9.1`/`9.2`/`9.3` in order.
  PASS.
- `OPS-1` defined as a labelled, enforced rule (6 mentions in MD). PASS.
- Milestone table has M0 through M6, 7 rows, in sequence. PASS.
- `git status --short` empty (gitignored, as before); no `scripts/`,
  `benchmarks/`, or `custom_metadata/` directories created. PASS.
- HTML: all tag types balanced (section 36/36, div 36/36, table 17/17,
  ol 11/11, ul 8/8, li 82/82, blockquote 5/5); no double-escaped entities.
  PASS.

## 2026-11-07 — Compact refactor (v2): 9 sections -> 10 short ones, scope narrowed

**Task:** The user said `findings/MVP_Plan.md` (646 lines by this point) had
grown too detailed and too long, and asked for a compact refactor using
`findings/IDEA.md` as the reference source — short sections, the "defend by
simulating the attack first" core idea kept central, one unified system
design (not separate deterministic/agent sections) in two required parts
(a technical architecture graph, and a strictly jargon-free plain-language
data-flow chart), one fixed MVP scenario, scope cut to fit a 15-17 hour
build, an enhancements list, and full traceability (References section in
the new doc, a kept/cut/merged record in TASK.md, and the original
preserved on disk rather than only in git history — `findings/` is
gitignored, so git history was never an option here).

**What was done:**
- Backed up the original immediately, before writing any task spec, to
  `findings/MVP_Plan_original.md` — verified byte-identical (646 lines) —
  so the refactor was safe to do destructively from that point on.
- Made two consequential scoping calls myself and stated them to the user
  before delegating (not buried in a sub-agent): narrowed the MVP from 4
  datasets to 2 (health + finance — the simplest exact-identifier join,
  and literally `IDEA.md`'s own worked example, person P013174); collapsed
  the previous 6-node LangGraph agent layer to **one** agent, whose job is
  to re-simulate Attack A's join against the candidate release before the
  deterministic test runs — making "simulate the attack first" the literal
  pre-test mechanism instead of a separate idea.
- Wrote a full traceability table into `Artifacts/TASK.md` recording, for
  each of the original's 9 sections, what was kept/cut/merged and why.
- Planner (opus) re-measured 1622/1484 independently rather than trusting
  the prior numbers, and found that person P013174's name order is
  *reversed* between the two files while the HETU matches — a sharper
  "name-matching would fail here" anchor than the document previously used.
- **Key finding: R-2 (free-text leakage) does not apply to the narrowed
  health+finance scope.** Measured, not assumed: `finance/customers.csv`
  has no free-text column at all, and health's only one (`chief_complaint`)
  has zero glue-type gold spans in its 503 annotations (all `LOCATION`/
  `ORG`). R-2 was swapped for R-9 (minimisation is not audited) in the
  compact document's top-4 residual risks, with the measured reasoning
  stated inline rather than silently dropped.
- Produced the full compact document (3805 words vs. the original's
  14638 — roughly 3.8x compression by content density) with both required
  System Design parts: a technical ASCII architecture diagram with the one
  agent integrated directly into it, and a second, separate, strictly
  jargon-free plain-language arrow-flow — verified clean by grepping for
  15 technical terms across just that section and getting zero matches.
  Added the 15-17 hour phase table (P0-P7), an Enhancements section, and a
  References section naming both source files and what moved where.
- Rebuilt `findings/MVP_Plan.html` from scratch rather than editing the
  old 1218-line page — a sidebar-nav, four-accent-color design no longer
  fit a document meant to read in a few minutes. New design: no sidebar,
  a slim pill-row anchor nav, a header stat callout promoting 1622→0
  (one of the document's own "Enhancements" suggestions, implemented
  directly), and Part 1/Part 2 of the system design visually distinguished
  (another of its own suggestions) — then republished to the same
  artifact link.

**Files changed:**
- `findings/MVP_Plan_original.md` (new) — 646-line backup of the
  pre-refactor document.
- `findings/MVP_Plan.md` — overwritten, 646 → 371 lines.
- `findings/MVP_Plan.html` — rebuilt, 1218 → 514 lines.

**Test result:**
- Backup verified byte-identical before any edit (646 lines), and
  confirmed still untouched after (646 lines) — PASS.
- Both "### Part 1" and "### Part 2" headings present under §5 — PASS.
- Part 2 grepped for 15 technical terms (LangGraph, HMAC, PASS-1/2, HETU,
  IBAN, `interrupt(`, pets-eval, scorecard, clean_data, k-anonymity,
  pseudonym, quasi-identifier, dtype, SHA-256, csv, mosaic, PET) — zero
  matches. PASS.
- Both MVP table paths (`data/health/ed_visits.csv`,
  `data/finance/customers.csv`) present, each ≥1 occurrence — PASS.
- `1622` present (5 hits in the .md, 11 in the .html) — PASS.
- No HTML entities leaked into the markdown (count = 0) — PASS.
- `git status --short` empty (expected — `findings/` is gitignored, same
  as every prior pass on this document).
- HTML: all tag types balanced (section 10/10, div 19/19, table 6/6,
  ul 2/2, li 10/10, blockquote 1/1); no double-escaped entities; no
  unescaped raw `<` outside a real tag — PASS.

## 2026-11-07 — scripts/ reorganised into material/ + final/ (real code)

**Task:** Reorganise the real, working `scripts/` directory (9 shell
wrappers around a Python `app/` package, already built and tested outside
this session) into `scripts/material/` (shared internal helpers) and
`scripts/final/` (user-facing entry points), via `/code-task`.

**What was done:**
- Investigated the real codebase first (not just read — ran a pre-refactor
  baseline smoke test: `ops1_manifest.sh verify` and `measure_baseline.sh`
  both passed cleanly before anything changed). Found the critical risk:
  every script resolves its own repo root via `dirname "$0"/..`, which
  silently breaks the moment a script moves one directory deeper.
- Planner (opus) corrected two of the coordinator's own assumptions: the
  three "guarded" scripts (`run_release.sh`, `make_benchmark.sh`,
  `run_demo.sh`) did **not** share byte-identical exit-code logic —
  `run_demo.sh` had no rc capture at all — so unifying them onto one
  shared guard function changes behaviour only on a failure path, and
  that delta was deliberately chosen in favour of `run_release.sh`'s own
  existing precedence rule, not invented. Also: the six passthrough
  scripts never `cd`, the three composites do — `common.sh` preserves
  that split rather than normalising it away.
- Extracted `scripts/material/common.sh`: correct two-directories-deep
  `ROOT` resolution, plus one `run_with_ops1_guard()` function replacing
  three copies of the same 7-line verify/run/verify pattern.
- Updated all 41 counted stale-path references across `CLAUDE.md`,
  `README.md`, `USAGE.md`, `DEMO.md`, and two printed hint strings in
  `app/run_demo.py` / `app/mosaic_check.py`. Left `findings/MVP_Plan*`
  untouched (planning artifacts, separate concern) and never touched
  `app/`'s actual logic beyond those two strings.
- Ran the full pipeline for real, end to end, inside the isolated
  worktree sandbox — fresh `--init-key`, fresh `clean_data/`, never the
  main checkout's real secret — and independently re-verified the single
  most important test (`run_release.sh`) myself after the coder reported
  success, rather than only trusting its report.
- **Mid-task incident:** while syncing the verified result back to the
  main checkout, discovered the user had been concurrently editing
  `app/*.py` files in the main checkout during the coder's run (adding a
  `require_python()` version guard to 5 files). Flagged this to the user
  immediately rather than silently finishing, since the sync had already
  overwritten `app/mosaic_check.py` and `app/run_demo.py` — the two files
  that pattern conspicuously skipped — with no way to know from this
  session whether that was intentional sequencing or a clobbered edit.

**Files changed:** `scripts/material/common.sh` (new),
`scripts/final/*.sh` (9, relocated), `scripts/final/STEPS.md` (new),
`CLAUDE.md`, `README.md`, `USAGE.md`, `DEMO.md`, `app/run_demo.py`,
`app/mosaic_check.py`.

**Test result:** all 19 end-to-end steps passed — OPS-1 build/verify,
baseline PASS at 1622/1484, protect creating both releases, shadow
attack-sim, mosaic gate PASS-1 zeros + PASS-2 1622/1484,
`run_release.sh` exit 0 (proves the new two-level-deep path resolution
works), B1 chart produced, demo walkthrough exit 0, `run_scorecard.sh`
exit 4 with the expected "needs Python >=3.10" message (not a
regression — a documented pre-existing environment limit at the time).

## 2026-11-07 — migrate app/ to require Python >=3.10 for pets-eval

**Task:** Following on directly from the concurrent-edit incident above —
the user confirmed the intent: finish raising the project's Python floor
to >=3.10 so `pets-eval` (which itself requires 3.10) actually works,
instead of gracefully degrading on 3.9.

**What was done:**
- Investigated rather than assumed: found the user's in-progress pattern
  was `from python_version import require_python` + `require_python()`,
  identically placed in 5 files, but the module it imports
  (`app/python_version.py`) did not exist yet — meaning those 5 files
  were currently broken in the main checkout at the moment this task
  started, independent of anything this session did.
- Given the live concurrent-editing risk just discovered, implemented
  this directly rather than running a multi-minute planner/coder cycle
  that would widen the race window — the change set was small and fully
  understood after investigation. Re-pulled fresh copies of every file
  about to be touched immediately before editing, and re-checked their
  main-checkout mtimes right before syncing back, to catch any further
  concurrent edits before overwriting.
- Wrote `app/python_version.py` (one function, `require_python()`,
  checking `sys.version_info` against `(3, 10)`, printing a clear
  message and exiting 1 if unmet) matching the exact import/call
  convention already used by the 5 in-progress files.
- Added the same guard to the two files that hadn't gotten it yet —
  `app/mosaic_check.py`, `app/run_demo.py` — completing the rollout.
  Deliberately left `app/run_scorecard.py` alone: its own inline check
  already degrades gracefully (exit 4, not a hard crash) for a
  genuinely different condition — "toolkit not pip-installed" is
  independent of Python version, and `require_python()`'s hard-fail
  philosophy doesn't fit that case.
- Added `.python-version` (pyenv convention) pinning `3.13.15` — already
  installed via `pyenv` on this machine but not the active interpreter.
  Updated `requirements-benchmark.txt` to drop the `matplotlib<3.10`
  ceiling that existed only to accommodate the old 3.9 floor. Updated
  `CLAUDE.md` (filled in the previously-blank "Dev environment setup"
  line), `USAGE.md`, and `DEMO.md`'s now-outdated "unavailable on 3.9"
  framing.
- **Verified for real, not just by reading code:** confirmed the guard
  blocks execution on the system's actual Python 3.9.6 with the intended
  message and exit 1; confirmed it passes silently under the pyenv
  3.13.15 interpreter; `pip install -e` the vendored pets-eval toolkit
  under 3.13.15 and ran the real `pets-eval scorecard` + `check` —
  genuine privacy/utility/composite numbers came back for both releases
  (not a dry run), proving pets-eval actually works now, not just that
  the guard compiles.
- Noted but did not fix (out of scope for this task): the scorecard run
  surfaced one real `PHONE` pattern hit in the health release's residual
  scan, and FIN-S2's utility score came back 0.0 with several tasks
  "not answerable" — both are informative findings about the existing
  protection design, not bugs in this migration.

**Files changed:** `app/python_version.py` (new),
`app/mosaic_check.py`, `app/run_demo.py` (guard added),
`requirements-benchmark.txt`, `CLAUDE.md`, `USAGE.md`, `DEMO.md`,
`.python-version` (new).

**Test result:** guard correctly blocks system Python 3.9.6 (exit 1,
clear message) and passes under pyenv's 3.13.15 (confirmed directly, by
full interpreter path, since pyenv shims are not active in this
session's shell). `pip install -e .../toolkit` succeeded under 3.13.15.
Real `pets-eval scorecard` + `check` run produced genuine output
(`privacy 0.3791 utility 0.5928 composite 0.4534` for HEALTH-S1;
`privacy 0.3375 utility 0.0 composite 0.0` for FIN-S2) and exit 0 —
pets-eval is now genuinely usable, not just gracefully skipped.
Re-verified no further concurrent main-checkout edits occurred between
investigation and sync (mtime comparison) before overwriting anything.

## 2026-11-07 — make Python auto-detection robust (no manual activation)

**Task:** Follow-up after the user confirmed they'd installed Python
3.13.15: verifying `! cd ... && python3 --version` still showed 3.9.6
revealed the real issue — the `!` prefix runs in this same sandboxed
session (no pyenv shims on `PATH`), so the ambient `python3` could not be
relied on in general, regardless of what the user's own terminal shows.
Fixed this at the source instead of depending on shell configuration.

**What was done:**
- Added `_pick_python()` to `scripts/material/common.sh`: use ambient
  `python3` if it's already >=3.10; else, if the `pyenv` *command* is
  reachable (even without its shims on `PATH`), resolve this repo's
  pinned version directly via `pyenv root` + `pyenv version-name` and
  call that interpreter by its real path; else fall back to ambient
  `python3` and let `require_python()` explain what's wrong. Exported as
  `PYTHON_BIN`; all 9 `scripts/final/*.sh` now call `"$PYTHON_BIN"`
  instead of bare `python3` (11 call sites updated).
- Found and fixed a second, related gap while testing:
  `run_scorecard.py` shells out to the `pets-eval` console script by
  name, which needs its own `bin/` directory on `PATH` too — not just
  the right Python. `common.sh` now also prepends the resolved
  interpreter's directory to `PATH` when it picked a specific one.
- Verified for real, end to end, in this sandboxed session specifically
  *because* it has no pyenv shims on `PATH` — the hardest case:
  `source common.sh` resolves `PYTHON_BIN` to the pyenv 3.13.15 path with
  zero manual intervention; `run_release.sh`, `run_scorecard.sh` (now
  exits 0, not 4), and `make_benchmark.sh` (now writes a real
  `B2_scores.png`, not `B2_UNAVAILABLE.txt`) all pass end to end, both in
  the worktree sandbox and — re-run a second time — against the real
  main checkout.
- Installed `matplotlib` for the 3.13.15 interpreter specifically (the
  prior install had only reached the system Python 3.9 interpreter).
- Deleted the now-stale `benchmarks/B2_UNAVAILABLE.txt` in the main
  checkout — misleading now that `B2_scores.png` sits next to it.
- Updated `scripts/final/STEPS.md`'s Prerequisites, phase table, exit-code
  and troubleshooting sections to describe the auto-detection and drop
  the now-inaccurate "Python 3.9 → B2 unavailable" framing; added one
  pointer line in `USAGE.md`.

**Files changed:** `scripts/material/common.sh`, all 9
`scripts/final/*.sh` (python3 → `$PYTHON_BIN`), `scripts/final/STEPS.md`,
`USAGE.md`; `benchmarks/B2_UNAVAILABLE.txt` deleted (stale).

**Test result:** `source scripts/material/common.sh; echo $PYTHON_BIN`
correctly resolves to `~/.pyenv/versions/3.13.15/bin/python3` in this
shim-less session. `run_release.sh`, `run_scorecard.sh`, and
`make_benchmark.sh` all exit 0 against the real main checkout, with
`run_scorecard.sh` producing genuine scorecards (not exit 4) and
`make_benchmark.sh` writing a real `B2_scores.png`.

## 2026-11-07 — committed and opened a PR (did not push to main directly)

**Task:** User asked to commit everything and push to main. Two
constraints applied instead: this session's own rule never to push to
main/master directly from a background job, and this project's own
`CONTRIBUTING.md` ("Everyone contributes to `main` through a pull
request — no direct pushes").

**What was done:**
- Before touching git at all, re-synced the worktree's `app/`, `scripts/`,
  and doc files from the main checkout's current state — discovered the
  user had *also* updated `.gitignore` again in parallel (now properly
  excluding `clean_data/`, `benchmarks/*.png`, `__pycache__/`) and added a
  `.venv/` directory that wasn't yet gitignored. Added `.venv/` and the
  `pets_eval.egg-info/` editable-install side-effect to `.gitignore` as a
  safety measure before any `git add`.
- Hit a real bug while refreshing: `cp -R app ...` onto an
  already-existing destination nests instead of merging
  (`app/app/...`), which would have left stale top-level files in place
  silently. Caught it by listing the tree before staging, removed the
  worktree's `app/`/`scripts/` entirely, and re-copied cleanly — then
  verified byte-for-byte with `diff -rq` against the main checkout before
  proceeding.
- `git status` revealed `app/`, `scripts/`, `DEMO.md`, `USAGE.md` were
  never committed at all before this point — this whole implementation
  has existed only in the working directory since it was built. Staged
  35 files by explicit name (never `git add -A`/`.`), scanned the staged
  diff for secret-looking patterns (none found), then committed on the
  worktree's own branch.
- Did not push that commit to `main`. Instead: created a conventionally
  named branch (`feat/mosaic-defence-pipeline`, per `CONTRIBUTING.md`'s
  `<type>/<short-description>` convention) from the same commit, pushed
  *that* to `origin`, and opened PR #1 into `main` — leaving the actual
  merge decision to the user, since "never push to main/master, force-push,
  or merge" is an explicit rule for this session, not a judgement call.

**Files changed:** none beyond what the prior two entries already
describe — this entry is the commit/PR delivery step, not new code.

**Result:** commit `ed01449` on `feat/mosaic-defence-pipeline`, pushed to
`origin`, PR opened at `https://github.com/khoidm2004/SinceAI/pull/1`.
`main` itself was not touched.

## 2026-11-07 — resolved a real PR merge conflict in .gitignore

**Task:** User reported the PR had a `.gitignore` conflict and asked to
resolve it.

**What was done:**
- `git fetch origin` revealed `origin/main` had moved — 3 new commits
  the user pushed directly (bypassing the PR-only convention for their
  own commits, apparently), adding 8 Python files directly under
  `scripts/` (`measure_baseline.py`, `pet_pipeline.py`, etc.) — an
  earlier project layout from before the `app/` split.
- Diffed both sides against the real merge-base (`4ba6bf7`, verified via
  `git merge-base`, not assumed) rather than guessing: this branch's
  `.gitignore` change turned out to be a **strict superset** of main's
  (same `__pycache__/`/`keys/`/`clean_data/` entries, plus `.venv/`, the
  egg-info artifact, and `benchmarks/*.png`) — so the correct resolution
  was simply keeping this branch's version wholesale, not hand-merging.
- `git merge origin/main` confirmed only `.gitignore` conflicted — the 8
  old `scripts/*.py` files merged in cleanly since this branch never
  touched those paths. But that clean auto-merge would have left two
  copies of the same logic in the tree (the old files under `scripts/`,
  the superseding versions under `app/`), violating `CLAUDE.md`'s own
  "scripts/ is shell-only" convention.
- This was broader than what was asked (just the `.gitignore` conflict),
  so asked the user before deciding: verified all 8 old files really are
  superseded (every one has an `app/` counterpart; `diff` showed several
  byte-identical, others differing only by the `require_python()` guard
  app/ added) and presented the choice. User chose to remove them.
- Completed the merge commit, re-verified the working tree was clean and
  `scripts/` held only `final/`+`material/`, ran `ops1_manifest.sh
  verify` as a quick post-merge sanity check, then pushed.

**Result:** merge commit `5bc6381` on `feat/mosaic-defence-pipeline`,
pushed. PR #1 now reports `mergeStateStatus: CLEAN`,
`mergeable: MERGEABLE`. `main` still untouched — merging it remains the
user's call.

## 2026-11-07 — Attack-first runbook + FIN-S2 tokenise

**Task:** Attack-first demo/release narrative; consolidate DEMO+USAGE into
INSTRUCTION.md; FIN-S2 transform (HMAC tokenise) instead of blank-dropping
glue; leave Groq agent files alone.

**What was done:**
- FIN-S2 TOKENISE_IDENTIFIERS = hetu/phone/iban/email; names/addresses still dropped.
- run_release.sh: raw attack (1622/1484) → protect → re-attack (0/0) → gate.
- run_demo.py re-narrated; INSTRUCTION.md added; DEMO/USAGE stubs.
- Documented free-text chief_complaint gap for teammate Groq agent.

**Files changed:**
.gitignore, app/pet_pipeline.py, app/run_demo.py, scripts/final/run_release.sh,
scripts/final/STEPS.md, INSTRUCTION.md, DEMO.md, USAGE.md, README.md, CLAUDE.md,
Artifacts/{TASK,PLAN,state,dev-diary}.md

**Test result:**
ops1 0; baseline 1622/1484; protect FIN-S2 17→15 tokenise four glue;
mosaic PASS 0/0+1622/1484; release STEP1 1622/1484 STEP3 0/0; demo PASS.
