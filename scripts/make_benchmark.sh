#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/ops1_manifest.py verify

bench_rc=0
python3 scripts/make_benchmark.py "$@" || bench_rc=$?

ops_after_rc=0
python3 scripts/ops1_manifest.py verify || ops_after_rc=$?

if [ "$ops_after_rc" -ne 0 ]; then
  exit "$ops_after_rc"
fi
exit "$bench_rc"

