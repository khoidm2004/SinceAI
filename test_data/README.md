# test_data/

Generated synthetic Health + Finance test packs live in `test_data/generated/<run_id>/` (git-ignored):

```
<run_id>/
  pack/        custom pack root for pets-eval --root (data/, metadata/, adversary/, truth/, holdout/)
  private/     population ground truth, temporary master key, row maps (scoring only - never publish)
  protected/   <policy>/<dataset>__<scenario>/ protected release tables
  evidence/    manifest, validation, protection, attacks, scorecards, benchmark, tests (JSON)
  reports/     index.html (offline, aggregates only), report.json, methodology.md
```

Methodology and commands: `docs/SYNTHETIC_HEALTH_FINANCE.md`. Generator: `app/generate_test_data.py`.
