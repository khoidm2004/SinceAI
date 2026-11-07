#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/ops1_manifest.py verify
python3 scripts/run_protect.py --init-key
python3 scripts/run_attack_sim.py --mode shadow

gate_rc=0
python3 scripts/mosaic_check.py || gate_rc=$?

ops_after_rc=0
python3 scripts/ops1_manifest.py verify || ops_after_rc=$?

if [ "$ops_after_rc" -ne 0 ]; then
  exit "$ops_after_rc"
fi
exit "$gate_rc"
