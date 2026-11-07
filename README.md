# SinceAI

SinceAI builds a cross-release mosaic defence for the TrustED PETs proving ground: unprotected pack releases go in, protected releases come out that no longer join across health and finance on HETU or normalised phone. Attack A is measured on raw `data/` first (baseline lock), then re-run on `clean_data/` and blocked by a deterministic mosaic gate before anything ships.

**Python lives in `app/`. Terminal entry points are shell scripts under `scripts/final/` (shared helpers in `scripts/material/`).**

**Start here**

```bash
bash scripts/final/ops1_manifest.sh verify
bash scripts/final/run_protect.sh --init-key   # once, if clean_data/ is empty
bash scripts/final/run_demo.sh --skip-protect  # narrated before/after walkthrough
```

How to use every command: [`USAGE.md`](USAGE.md).  
Jury five-minute path: [`DEMO.md`](DEMO.md).  
Full technical plan: [`findings/MVP_Plan.md`](findings/MVP_Plan.md).

**Pipelines**

- `bash scripts/final/run_demo.sh` — OPS-1 verify → demo → OPS-1 verify
- `bash scripts/final/run_release.sh` — verify → protect → shadow attack-sim → mosaic gate → verify
