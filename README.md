# SinceAI

SinceAI builds a cross-release mosaic defence for the TrustED PETs proving ground: unprotected pack releases go in, protected releases come out that no longer join across health and finance on HETU or normalised phone. Attack A is measured on raw `data/` first (baseline lock), then defence closes the join on `clean_data/` before the mosaic gate ships a release.

**Python lives in `app/`. Terminal entry points are shell scripts under `scripts/final/` (shared helpers in `scripts/material/`).**

**Start here:** [`INSTRUCTION.md`](INSTRUCTION.md) — attack, defend, measure, and expected outcomes.

```bash
bash scripts/final/ops1_manifest.sh verify
bash scripts/final/measure_baseline.sh
bash scripts/final/run_release.sh    # or run_demo.sh for the narrated path
```

Technical plan: [`findings/MVP_Plan.md`](findings/MVP_Plan.md).  
Script phases: [`scripts/final/STEPS.md`](scripts/final/STEPS.md).

**Pipelines**

- `bash scripts/final/run_release.sh` — verify → attack raw → protect → re-attack → mosaic gate → verify
- `bash scripts/final/run_demo.sh` — OPS-1 verify → narrated attack/defend story → OPS-1 verify
