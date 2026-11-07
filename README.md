# SinceAI

SinceAI builds a cross-release mosaic defence for the TrustED PETs proving ground: unprotected pack releases go in, protected releases come out that no longer join across health and finance on HETU or normalised phone. Attack A is measured on raw `data/` first (baseline lock), then re-run on `clean_data/` and blocked by a deterministic mosaic gate before anything ships.

**Start here**

```bash
python3 scripts/ops1_manifest.py verify
python3 scripts/run_protect.py --init-key   # once, if clean_data/ is empty
python3 scripts/run_demo.py --skip-protect  # narrated before/after walkthrough
```

Full technical plan: [`findings/MVP_Plan.md`](findings/MVP_Plan.md). Jury-facing five-minute path: [`DEMO.md`](DEMO.md).

**Shell entry points**

- `bash scripts/run_demo.sh` — OPS-1 verify → demo → OPS-1 verify
- `bash scripts/run_release.sh` — verify → protect → shadow attack-sim → mosaic gate → verify
