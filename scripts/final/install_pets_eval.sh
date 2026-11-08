#!/usr/bin/env bash
# Opt-in: install the vendored pets-eval toolkit into the uv-managed .venv.
#
# The toolkit under resources/ is READ-ONLY. Building it in place would make
# setuptools write pets_eval.egg-info/ and build/ next to its sources, so this
# script copies the toolkit to a fresh temporary directory OUTSIDE the
# repository, verifies the copy is byte-identical, builds a wheel there, and
# installs that wheel into .venv. Nothing is written under resources/.
#
# Usage (from the repo root):  bash scripts/final/install_pets_eval.sh
# Requires: uv on PATH. Re-run after any plain `uv sync`, which removes
# packages that are not in uv.lock (or use `uv sync --extra scorecard --inexact`).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../.." && pwd)"
TOOLKIT="$ROOT/resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/toolkit"

command -v uv >/dev/null 2>&1 || { echo "error: uv not found on PATH (see docs/SETUP.md)" >&2; exit 2; }
[ -f "$TOOLKIT/pyproject.toml" ] || { echo "error: toolkit not found: $TOOLKIT" >&2; exit 2; }

# Fingerprint every toolkit file (sorted path + sha256) so we can prove both
# that the copy is exact and that the source tree was left untouched.
fingerprint() {
  (cd "$1" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum)
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

before="$(fingerprint "$TOOLKIT")"
mkdir -p "$TMP/toolkit"
cp -R "$TOOLKIT/." "$TMP/toolkit/"
[ "$before" = "$(fingerprint "$TMP/toolkit")" ] \
  || { echo "error: temporary copy differs from the vendored toolkit" >&2; exit 2; }

# Make sure the runtime dependencies (locked in uv.lock) are present first.
(cd "$ROOT" && uv sync --extra scorecard --inexact)

uv build --wheel --out-dir "$TMP/dist" "$TMP/toolkit"
wheel="$(ls "$TMP"/dist/pets_eval-*.whl)"
# --no-deps: every runtime dependency is already locked via the `scorecard` extra.
(cd "$ROOT" && uv pip install --no-deps --reinstall "$wheel")

[ "$before" = "$(fingerprint "$TOOLKIT")" ] \
  || { echo "error: vendored toolkit changed during the build" >&2; exit 2; }

(cd "$ROOT" && uv run --no-sync pets-eval --help >/dev/null) \
  && echo "pets-eval installed into $ROOT/.venv (built from a temporary copy; resources/ untouched)"
