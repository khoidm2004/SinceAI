#!/usr/bin/env bash
# Build analyze/index.html — raw vs protected row, joins, pets-eval scorecards.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/../material/common.sh"
cd "$ROOT"
exec "$PYTHON_BIN" "$ROOT/app/make_analyze_report.py" "$@"
