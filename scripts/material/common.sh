#!/usr/bin/env bash
# scripts/material/common.sh — shared helpers for every script in
# scripts/final/. Sourced, never executed directly.
#
# This file lives TWO directories below the repo root:
#   scripts/material/common.sh -> scripts/material -> scripts -> <repo root>
# so ROOT is resolved with "/../.." from this file's own location. Resolving
# it here, once, is what keeps scripts/final/*.sh working at their new depth.
# Do NOT copy a `dirname "$0"/..` one-level line back into any final/ script.
#
# This file must never `cd`: the six plain wrappers in final/ deliberately run
# from the caller's cwd, and only the three guarded ones cd to $ROOT.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export ROOT

# _pick_python — find a Python >=3.10 without assuming the caller's shell
# has pyenv's shims on PATH (e.g. non-interactive shells, CI, some agent
# sandboxes: pyenv itself may be reachable while its shims are not).
#
#   1. If ambient `python3` already satisfies the floor, use it as-is —
#      this is the common case in a normal, pyenv-initialised terminal.
#   2. Else, if the `pyenv` command is reachable, resolve this repo's
#      pinned version directly (honours ../../.python-version) and call
#      that interpreter by its real path under ~/.pyenv/versions/.
#   3. Else, fall back to ambient `python3` anyway — app/python_version.py's
#      require_python() will then explain exactly what's wrong, rather
#      than this script failing with a confusing "command not found".
#
# Every app/*.py guard still runs regardless of which path was used, so an
# interpreter this function picked wrong is still caught, just later.
_pick_python() {
  if command -v python3 >/dev/null 2>&1 \
      && python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)' 2>/dev/null; then
    echo "python3"
    return
  fi

  if command -v pyenv >/dev/null 2>&1; then
    local pyenv_root pinned candidate
    pyenv_root="$(pyenv root 2>/dev/null)"
    pinned="$(cd "$ROOT" && pyenv version-name 2>/dev/null)"
    if [ -n "$pyenv_root" ] && [ -n "$pinned" ]; then
      candidate="$pyenv_root/versions/$pinned/bin/python3"
      if [ -x "$candidate" ]; then
        echo "$candidate"
        return
      fi
    fi
  fi

  echo "python3"
}

PYTHON_BIN="$(_pick_python)"
export PYTHON_BIN

# If we resolved a specific interpreter rather than ambient `python3`, also
# put its own bin/ directory on PATH. pip installs any console script tied
# to that interpreter there too (e.g. `pets-eval`), and run_scorecard.py
# shells out to that command by name — without this, the right Python
# gets picked but `pets-eval` still isn't found.
case "$PYTHON_BIN" in
  /*)
    PATH="$(dirname "$PYTHON_BIN"):$PATH"
    export PATH
    ;;
esac

# ops1_verify — OPS-1 pack integrity check. Returns app/ops1_manifest.py's
# exit code; never exits the caller itself.
ops1_verify() {
  "$PYTHON_BIN" "$ROOT/app/ops1_manifest.py" verify
}

# run_with_ops1_guard CMD [ARGS...]
#
# OPS-1 verify -> payload -> OPS-1 verify, reproducing run_release.sh's
# `ops_after_rc` exit-code precedence exactly:
#   * before-verify fails -> return its code; the payload never runs
#   * after-verify fails  -> its code WINS over the payload's code
#   * otherwise           -> return the payload's own exit code
#
# CMD may be an external command or a shell function (run_release.sh passes a
# function so its three python calls still short-circuit on the first failure).
run_with_ops1_guard() {
  ops1_verify || return $?

  local payload_rc=0
  "$@" || payload_rc=$?

  local ops_after_rc=0
  ops1_verify || ops_after_rc=$?

  if [ "$ops_after_rc" -ne 0 ]; then
    return "$ops_after_rc"
  fi
  return "$payload_rc"
}
