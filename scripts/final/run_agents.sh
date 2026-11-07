#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/../material/common.sh"
exec "$PYTHON_BIN" "$ROOT/app/run_agents.py" "$@"
