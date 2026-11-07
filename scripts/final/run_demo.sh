#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/../material/common.sh"
cd "$ROOT"

# P7 — OPS-1 verify -> run_demo.py -> OPS-1 verify, after-verify wins.
rc=0
run_with_ops1_guard "$PYTHON_BIN" "$ROOT/app/run_demo.py" "$@" || rc=$?
exit "$rc"
