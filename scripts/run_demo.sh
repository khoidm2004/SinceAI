#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/ops1_manifest.py verify
python3 scripts/run_demo.py "$@"
python3 scripts/ops1_manifest.py verify
