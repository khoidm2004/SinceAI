#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/../material/common.sh"
cd "$ROOT"

# P6 payload: protect -> shadow attack-sim -> mosaic gate. The explicit
# `|| return $?` on each line preserves the pre-refactor short-circuit: a
# failure in protect or attack-sim stops the pipeline immediately. Do not
# remove them -- errexit is NOT active inside a function called in a `||`
# context, so without them attack-sim would run after protect had failed.
release_payload() {
  "$PYTHON_BIN" "$ROOT/app/run_protect.py" --init-key || return $?
  "$PYTHON_BIN" "$ROOT/app/run_attack_sim.py" --mode shadow || return $?
  "$PYTHON_BIN" "$ROOT/app/mosaic_check.py" || return $?
}

# OPS-1 verify -> payload -> OPS-1 verify, after-verify wins (unchanged).
rc=0
run_with_ops1_guard release_payload || rc=$?
exit "$rc"
