#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/../material/common.sh"
cd "$ROOT"

# P4 — OPS-1 verify -> make_benchmark.py -> OPS-1 verify, after-verify wins.
rc=0
run_with_ops1_guard "$PYTHON_BIN" "$ROOT/app/make_benchmark.py" "$@" || rc=$?
exit "$rc"
