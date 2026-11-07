#!/usr/bin/env bash
# Build analyze HTML (default: analyze/). Release pipeline writes analyze/no_AI/.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/../material/common.sh"
cd "$ROOT"
exec "$PYTHON_BIN" "$ROOT/app/make_analyze_report.py" "$@"
