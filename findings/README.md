# findings/

Durable, human-readable write-ups of things the project learned —
investigations, measured evidence, "why we chose X over Y", methods that
took real effort to work out. Unlike `Artifacts/analysis.md` (which belongs
to the *current* task and gets overwritten every run), files here are
permanent and cumulative: one file per topic, kept up to date as
understanding changes.

Conventions seen in practice:
- Name files for the topic, not the task (`SYNC_METHOD.md`, not
  `task-12-notes.md`).
- If a later finding supersedes or corrects an earlier one, say so at the
  top of the new file rather than silently leaving the old one stale.
- Cite evidence (`file:line`, measured numbers, `Artifacts/analysis.md §n`)
  the same way `Artifacts/analysis.md` does — a finding without evidence is
  just an opinion.
- Reference these files by path from code comments and from
  `Artifacts/analysis.md` when a decision depends on one, instead of
  re-explaining the reasoning inline.

This directory is not written to automatically by any agent — it's where
*you* (or an analyzer, told to) park knowledge that should outlive a single
task.
