#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/../material/common.sh"
cd "$ROOT"

# P6 payload: attack raw → protect → re-attack protected → mosaic gate. The
# explicit `|| return $?` on each line preserves the pre-refactor short-circuit:
# a failure in an early step stops the pipeline immediately. Do not remove them
# — errexit is NOT active inside a function called in a `||` context, so
# without them later steps would run after an earlier step had failed.
release_payload() {
  local stamp
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"

  echo "=== STEP 1/4 — ATTACK unprotected data (raw pack) ==="
  "$PYTHON_BIN" "$ROOT/app/run_attack_sim.py" --mode shadow --raw-pack --thread-id "${stamp}-raw" || return $?

  echo "=== STEP 2/4 — DEFEND (protect releases) ==="
  "$PYTHON_BIN" "$ROOT/app/run_protect.py" --init-key || return $?

  echo "=== STEP 3/4 — RE-ATTACK protected data (clean_data) ==="
  "$PYTHON_BIN" "$ROOT/app/run_attack_sim.py" --mode shadow --thread-id "${stamp}-protected" || return $?

  echo "=== STEP 4/4 — MOSAIC GATE ==="
  "$PYTHON_BIN" "$ROOT/app/mosaic_check.py" || return $?
}

# OPS-1 verify -> payload -> OPS-1 verify, after-verify wins (unchanged).
rc=0
run_with_ops1_guard release_payload || rc=$?
exit "$rc"
