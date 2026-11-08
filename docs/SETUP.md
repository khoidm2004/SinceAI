# SinceAI — project environment setup (uv)

This guide sets up the Python environment for the SinceAI application under
`app/` and its shell entry points under `scripts/final/`. (The root `SETUP.md`
documents the separate OpenCode agent pack and is unrelated to this guide.)

**Summary**

| What | Command |
|---|---|
| Create / update `.venv` (core app + pytest) | `uv sync` |
| Add benchmark charts (matplotlib) | `uv sync --extra benchmark` |
| Add the pets-eval scorecard (opt-in) | `bash scripts/final/install_pets_eval.sh` |
| Run the project tests | `uv run pytest` |
| Run any existing script | `uv run bash scripts/final/<name>.sh` |

---

## 1. Requirements

- **Python newer than 3.10.** `pyproject.toml` sets `requires-python = ">=3.11"`
  and `.python-version` pins **3.13.15**, which uv picks up automatically.
- **uv** (Astral's Python package and project manager).
- **Bash**, because every entry point in `scripts/final/` is a Bash script. See §8
  for Windows.
- **Git.**

The core application uses **only the Python standard library**. Everything
else is optional:

| Group | Contents | Why |
|---|---|---|
| core (`[project] dependencies`) | *(none)* | `app/*.py` uses stdlib only, including the LLM adapter (`urllib`) |
| `dev` dependency group | `pytest` | `tests/` |
| `benchmark` extra | `matplotlib>=3.7` | `app/make_benchmark.py`. Mirrors `requirements-benchmark.txt` |
| `scorecard` extra | `numpy`, `pandas`, `scipy`, `scikit-learn` | Runtime dependencies of the vendored `pets-eval` toolkit, copied from its `toolkit/pyproject.toml` so they are locked in `uv.lock` |

## 2. Install uv

Use the official installers (see <https://docs.astral.sh/uv/getting-started/installation/>):

```bash
# macOS / Linux / WSL
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows (PowerShell), either of:
winget install --id=astral-sh.uv -e
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

uv installs to `~/.local/bin`. Make sure that directory is on your `PATH`, then
check with `uv --version`.

## 3. Install Python

You do not need a system Python. uv downloads the pinned interpreter on demand:

```bash
uv python install 3.13.15   # optional; `uv sync` does this automatically
```

`pyenv` users can keep using it. `.python-version` is the same pin both tools read.

## 4. Create the environment

From the **repo root**:

```bash
uv sync                    # creates .venv/ with Python 3.13.15 + pytest, from uv.lock
uv run python --version    # -> Python 3.13.15
```

`.venv/` is git-ignored. `uv.lock` is committed, so `uv sync` reproduces
exactly the same versions on every machine. Use `uv sync --locked` in CI to
fail if the lock is out of date.

Optional extras:

```bash
uv sync --extra benchmark            # matplotlib for make_benchmark.sh
uv sync --extra scorecard            # pets-eval runtime deps (see §5)
```

## 5. Optional: the pets-eval toolkit (scorecards)

`pets-eval` ships inside the vendored challenge pack at
`resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/toolkit/`.
That tree is **strictly read-only**. Installing it the usual way
(`pip install -e …` or a uv path dependency) builds it in place. That writes
`pets_eval.egg-info/` and `build/` inside `resources/`, so we don't do it.

Instead, run:

```bash
bash scripts/final/install_pets_eval.sh
```

The script:

1. copies the toolkit to a fresh temporary directory **outside the repository**;
2. verifies that the copy is byte-identical (sha256 of every file);
3. runs `uv sync --extra scorecard --inexact`, which installs the locked
   numpy/pandas/scipy/scikit-learn;
4. builds a wheel from the copy (`uv build --wheel`);
5. installs it with `uv pip install --no-deps`. Every dependency is already locked;
6. re-checks that the vendored toolkit is unchanged, then deletes the temporary directory.

Then:

```bash
uv run pets-eval --help
bash scripts/final/run_scorecard.sh
```

Caveat: `pets-eval` itself is not in `uv.lock`. It is a local wheel. A plain
**exact** `uv sync` removes it. Either re-run the install script afterwards, or
sync with `uv sync --extra scorecard --inexact`. A plain `uv run …` does not
remove it.

## 6. Secrets: `.env`

The optional LLM specialists read the provider key from `.env` at the repo root.

```bash
cp .env.example .env     # only if .env does not exist yet. Never overwrite an existing .env.
# then edit .env and set API_KEY=<your GroqCloud key>
```

| Variable | Required | Default |
|---|---|---|
| `API_KEY` | for LLM calls | *(none: the specialists fall back to deterministic results)* |
| `LLM_BASE_URL` | no | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | no | `openai/gpt-oss-120b`. `openai/gpt-oss-20b` and `qwen/qwen3.8-27b` also support strict JSON schema |
| `LLM_TIMEOUT` | no | `20` (seconds, clamped to 1–120) |

- `.env` and `.env.*` are git-ignored. Only `.env.example`, with empty values, is tracked.
- Environment variables override `.env`.
- The key is never printed, logged, written to checkpoints, or put into graph state.

## 7. Tests

```bash
uv run pytest                 # project tests in tests/ (provider mocked; no network)
```

| File | Covers |
|---|---|
| `tests/test_no_drop.py` | No-drop invariant: columns, order and rows preserved; identifiers transformed; release guard; non-destructive proposals |
| `tests/test_llm_client.py` | Adapter: request shape, missing key, invalid JSON, unexpected fields, HTTP error, timeout, network error, privacy-policy rejection |
| `tests/test_agents.py` | Specialists in the existing graph: default graph unchanged, deterministic fallback, output filtering, checkpoint and resume, fail-closed |
| `tests/test_llm_live.py` | **Opt-in** live smoke test, using synthetic row-free metadata only |

Live provider check (sends one tiny synthetic payload; needs `API_KEY`):

```bash
SINCEAI_LIVE_LLM=1 uv run pytest -s tests/test_llm_live.py
```

**Vendored pack tests.** Don't run them in place: `tests/test_toolkit.py` starts a
subprocess that writes `__pycache__/` into `resources/…/toolkit`. Run them from a
temporary copy instead. This needs the scorecard extra (§5).

```bash
PACK=resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026
T="$(mktemp -d)" && cp -R "$PACK/tests" "$PACK/toolkit" "$T/" \
  && uv run python -m pytest -q -p no:cacheprovider --rootdir="$T" "$T/tests/test_toolkit.py"; rm -rf "$T"
```

## 8. Running the existing scripts

Always run from the repo root. Prefix commands with `uv run` so `.venv` is on
`PATH`:

```bash
uv run bash scripts/final/ops1_manifest.sh verify     # pack integrity (see the CRLF note below)
uv run bash scripts/final/measure_baseline.sh         # P0 baseline 1622 / 1484
uv run bash scripts/final/run_protect.sh --init-key   # P1. Writes clean_data/ and keys/: see warning
uv run bash scripts/final/run_attack_sim.sh --mode shadow
uv run bash scripts/final/run_attack_sim.sh --mode shadow --agents   # + advisory §8 specialists
uv run bash scripts/final/mosaic_check.sh
uv run bash scripts/final/run_scorecard.sh            # needs §5
uv run --extra benchmark bash scripts/final/make_benchmark.sh
```

**Warning.** `run_protect.sh`, `run_release.sh`, `run_demo.sh` (without
`--skip-protect`), `measure_baseline.sh` and `mosaic_check.sh` write to
`clean_data/` and `findings/` by default. To experiment without touching
existing outputs, pass a temporary location:

```bash
T="$(mktemp -d)"
uv run python app/run_protect.py --key-file "$T/master.key" --init-key --out-root "$T/out"
uv run python app/mosaic_check.py --clean-root "$T/out" --out "$T/out/mosaic_check.json"
uv run python app/measure_baseline.py --out "$T/baseline.json"
```

### What changed in the protected releases (no-drop)

`run_protect` now keeps **every original column, in the original order, for
every row**. Values are transformed instead of columns being dropped:

- direct identifiers that the scenario needs for linkage become keyed HMAC
  pseudonyms (HEALTH-S1 `patient_hetu`);
- other direct identifiers become typed placeholders such as `[PHONE]`;
- free-text and uncatalogued columns keep their text, with only the identifier
  spans redacted.

The run prints the tokenised, redacted, generalised, suppressed and unchanged
fields with a trade-off line for each. The release guard fails the run if:
- a column is missing or reordered;
- a row is lost;
- any raw direct-identifier value survives anywhere in the output.

### `--agents` (advisory LLM specialists)

- Off by default. The release, demo and gate paths behave exactly as before.
- With `--agents`, `supervisor → classify_assist → redact_assist → discover_assist →
  minim_assist → human_review → brief_writer` run inside the existing shim graph.
- Only `classify_assist`, `minim_assist` and `brief_writer` may call the provider.
  They receive row-free metadata only, and that is enforced in code by
  `app/llm_privacy.py` before any network I/O.
- `redact_assist` and `discover_assist` run locally and deterministically.
- All output is advisory and recorded in the JSON report with its provenance
  (model, prompt version, candidate hash). Nothing is applied automatically.

## 9. Windows notes

The shell wrappers need Bash. Use **Git Bash** or **WSL**.

**Git Bash: `python3`.** `scripts/material/common.sh` looks for `python3`, but
uv's Windows virtualenvs only contain `python.exe`. Windows' `python3` is often
the Microsoft Store alias, which fails. After `uv sync`, add a one-line shim
inside the virtualenv once:

```bash
printf '#!/usr/bin/env bash\nexec "$(dirname "$0")/python.exe" "$@"\n' > .venv/Scripts/python3
uv run bash -c 'python3 --version'    # -> Python 3.13.15
```

The shim lives in git-ignored `.venv/`. Re-create it if you delete `.venv`.
Disabling the Store alias (Settings → Apps → Advanced app settings → App
execution aliases) also avoids the confusing "Python was not found" message.

**Line endings and OPS-1.** `ops1_manifest.sh verify` hashes raw bytes, and
`manifests/pack_data_sha256.json` was built from LF files. With Git for Windows'
default `core.autocrlf=true`, the pack's text files are checked out with CRLF,
and verify reports every file as `changed` even though the content is identical.
The `test_manifest_checksums` and `test_spans_match_text` pack tests fail the
same way. To get a byte-exact checkout, clone with LF endings:

```bash
git -c core.autocrlf=false clone https://github.com/khoidm2004/SinceAI.git
```

Or use WSL, where `autocrlf` is normally off. Don't "fix" an existing checkout by
rebuilding the manifest (`ops1_manifest.sh build`), and don't edit files under
`resources/`.

**Paths.** Some console output contains non-ASCII paths. Set
`PYTHONIOENCODING=utf-8` if Python reports `UnicodeEncodeError` while printing.

## 10. Rules of the road

- Never modify `resources/`, `clean_data/`, `keys/` or an existing `.env`.
- Never commit `.env`, `keys/`, `clean_data/` or `rowmap_*.csv`.
- Python code goes in `app/`. `scripts/` stays shell-only (see `USAGE.md`).
