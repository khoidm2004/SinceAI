#!/usr/bin/env bash
# scripts/testdata/common.sh — shared helpers for the synthetic test-pack entry points.
# Sourced, never executed directly.
#
# Resolves ROOT two levels up (scripts/testdata -> scripts -> repo root).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export ROOT

# Avoid bytecode caches in the repo (verification hygiene).
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=utf-8

# _load_dotenv — export KEY=VALUE from repo-root `.env` without overriding
# variables already set in the shell. Copied from scripts/material/common.sh.
_load_dotenv() {
  local env_file="$ROOT/.env" line key val
  [ -f "$env_file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    case "$line" in
      ""|\#*) continue ;;
    esac
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"
    val="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    key="${key#"${key%%[![:space:]]*}"}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ "$val" == \"*\" ]]; then
      val="${val:1:${#val}-2}"
    elif [[ "$val" == \'*\' ]]; then
      val="${val:1:${#val}-2}"
    fi
    if [ -z "${!key+x}" ] || [ -z "${!key}" ]; then
      export "$key=$val"
    fi
  done < "$env_file"
}
_load_dotenv

# _pick_python — venv wins on this machine, then ambient, then pyenv.
_pick_python() {
  if [ -x "$ROOT/.venv/Scripts/python.exe" ]; then
    echo "$ROOT/.venv/Scripts/python.exe"
    return 0
  fi
  if [ -x "$ROOT/.venv/bin/python" ]; then
    echo "$ROOT/.venv/bin/python"
    return 0
  fi
  if [ -x "$ROOT/.venv/bin/python3" ]; then
    echo "$ROOT/.venv/bin/python3"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1 \
      && python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)' 2>/dev/null; then
    echo "python3"
    return 0
  fi
  if command -v pyenv >/dev/null 2>&1; then
    local pyenv_root pinned candidate
    pyenv_root="$(pyenv root 2>/dev/null)"
    pinned="$(cd "$ROOT" && pyenv version-name 2>/dev/null)"
    if [ -n "$pyenv_root" ] && [ -n "$pinned" ]; then
      candidate="$pyenv_root/versions/$pinned/bin/python3"
      if [ -x "$candidate" ]; then
        echo "$candidate"
        return 0
      fi
    fi
  fi
  echo "python3"
}

PYTHON_BIN="$(_pick_python)"
export PYTHON_BIN

case "$PYTHON_BIN" in
  /*)
    PATH="$(dirname "$PYTHON_BIN"):$PATH"
    export PATH
    ;;
esac

# td_die MSG -> stderr + exit 2
td_die() {
  echo "error: $*" >&2
  exit 2
}

# td_latest_run -> newest directory under $ROOT/test_data/generated/*/
td_latest_run() {
  local d
  d="$(ls -1dt "$ROOT/test_data/generated"/*/ 2>/dev/null | head -n 1)" || true
  d="${d%/}"
  if [ -z "$d" ]; then
    echo "error: no run directories found under $ROOT/test_data/generated/" >&2
    return 2
  fi
  printf '%s\n' "$d"
}

# td_require_run RUN -> absolute path on stdout; validates location + required files
td_require_run() {
  local run="$1"
  if [ ! -d "$run" ]; then
    td_die "run directory not found: $run"
  fi
  run="$(cd "$run" && pwd)" || return $?
  case "$run" in
    "$ROOT/test_data/generated"/*) ;;
    *) td_die "run must be under $ROOT/test_data/generated/: $run" ;;
  esac
  if [ ! -f "$run/pack/metadata/field_catalog.csv" ]; then
    td_die "missing $run/pack/metadata/field_catalog.csv"
  fi
  if [ ! -f "$run/evidence/manifest.json" ]; then
    td_die "missing $run/evidence/manifest.json"
  fi
  printf '%s\n' "$run"
}

# td_split_run_arg "$@" -> sets TD_RUN and TD_REST
td_split_run_arg() {
  TD_RUN=""
  TD_REST=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --run-dir)
        if [ $# -lt 2 ]; then
          td_die "--run-dir requires an argument"
        fi
        TD_RUN="$2"
        shift 2
        ;;
      --run-dir=*)
        TD_RUN="${1#--run-dir=}"
        shift
        ;;
      *)
        TD_REST+=("$1")
        shift
        ;;
    esac
  done
}
