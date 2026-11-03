# MAS — multi-agent coding workflow template

A reusable **analyze → plan → code → test** loop for Claude Code, extracted
from `Hack4Hum`. One coordinator command drives four subagents, routes by
task difficulty, and tracks run state on disk so it survives interruptions
(including rate limits).

```
analyzer (facts)  ->  planner (steps)  ->  coder (implementation)  ->  tester (PASS/FAIL)
   opus                 sonnet/opus            sonnet                    sonnet
```

## What's in here

```
.claude/
  agents/
    analyzer.md    # investigates, writes Artifacts/analysis.md — never plans or edits code
    planner.md     # turns analysis into an exact step-by-step plan — never edits code
    coder.md       # implements the plan literally — never escalates to opus
    tester.md      # runs real commands, reports PASS/FAIL — never fixes code
  commands/
    code-task.md   # the coordinator: /code-task — routes by difficulty, owns state.json
  statusline.sh    # optional: shows "difficulty | agent | attempt N | failures N/2"
CLAUDE.md.template  # drop-in CLAUDE.md with the generic workflow + model-policy
                    # sections, and placeholders for this project's own commands/conventions
Artifacts/
  TASK.md.template  # skeleton for the task you hand to /code-task
  .gitkeep
findings/
  README.md         # convention for durable write-ups (not auto-written by any agent)
  .gitkeep
gitignore.snippet    # optional block if you want this kept out of the project's git history
```

These agent/command files are already project-agnostic (no Hack4Hum-specific
content) — copy them verbatim. The only thing to fill in per-project is
`CLAUDE.md`.

## Setting up a new project

1. Copy `.claude/` (whole directory) into the new project's root.
2. Copy `CLAUDE.md.template` to the project root as `CLAUDE.md`, and fill in
   `## Project`, `## Commands`, `## Conventions` at the top. Leave
   `## Multi-agent workflow` and `### Model policy` untouched — they're the
   reusable contract the agents/coordinator are written against. If the
   project already has a `CLAUDE.md`, append those two sections to it
   instead of overwriting.
3. Create `Artifacts/` and `findings/` at the project root (copy the
   `.gitkeep`s, or just `mkdir`).
4. Decide whether this tooling is local-only or shared with collaborators:
   - Local-only (matches how Hack4Hum runs it): append `gitignore.snippet`
     to the project's `.gitignore`.
   - Shared: commit `.claude/`, `CLAUDE.md`, and `Artifacts/` as-is.
5. If using the statusline, point Claude Code's settings at
   `.claude/statusline.sh` (it degrades to an empty line if `jq` is missing
   or no run has started yet).

## Running it

1. Copy `Artifacts/TASK.md.template` to `Artifacts/TASK.md`, fill in `#
   Task`, `# Difficulty` (`easy`/`medium`/`hard`), `# Notes`.
2. Run `/code-task`.
3. The coordinator reads `Artifacts/TASK.md`, routes to the right subagents,
   and reports back what changed, the test result, and where the durable
   record (`Artifacts/state.json`, `Artifacts/dev-diary.md`) landed.

## Design notes worth keeping in mind

- **Opus is reserved for thinking, never typing.** The analyzer (on
  medium/hard) and planner (on hard only) may use Opus; coder and tester
  never do, even on retries. If a cheap-model step struggles, the fix is a
  better plan, not a bigger model.
- **Files, not context, carry state between agents.** The coordinator
  points the planner at `Artifacts/analysis.md` rather than relaying its
  contents — keeps each subagent's prompt small and the record durable on
  disk.
- **`Artifacts/` vs `findings/`**: `Artifacts/` is per-run and disposable
  (gitignored in the source project) — `analysis.md` and `state.json` get
  overwritten every task. `findings/` is cumulative and durable — write-ups
  that should survive long after the task that produced them is forgotten.
- **Two consecutive test failures stop the loop** rather than retrying
  forever — the coordinator reports and asks, it doesn't grind.
