#!/usr/bin/env bash
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
cd "$ROOT"

usage() {
  cat <<'EOF'
Usage: bash scripts/testdata/run_testdata.sh <command> [options]

commands:
  release    full pipeline: generate (if needed) -> verify -> measure raw -> protect -> attack -> gate -> scorecard -> report -> verify
  demo       same pipeline + narrated summary
  generate   create a new synthetic run
  verify     validate the run against official metadata
  measure    attack the raw pack (run_attack_sim --raw-pack)
  protect    protect all scenario tables (both policies)
  attack     canonical raw + protected attack evidence
  gate       validation + raw baseline + protected HETU-0 gate
  scorecard  pets-eval scorecards
  report     build reports/index.html + report.json + methodology.md
  compare    compare against resources/ (comparison_official.html)
  latest     print the newest run directory

Global option for phase commands: --run-dir DIR (default: newest run).
release/demo options: --run-dir DIR, --profile demo, --people 2500, --seed 20261107, --run-id ID,
  --skip-protect, --policy both, --no-scorecard, --no-report, --tests.
EOF
}

resolve_run() {
  td_split_run_arg "$@"
  if [ -n "${TD_RUN:-}" ]; then
    td_require_run "$TD_RUN"
  else
    local latest
    latest="$(td_latest_run)" || return $?
    td_require_run "$latest"
  fi
}

# Empty-safe array expansion helper
rest_args() {
  if [ "${#TD_REST[@]}" -gt 0 ]; then
    printf '%s\n' "${TD_REST[@]}"
  fi
}

if [ $# -eq 0 ]; then
  usage >&2
  exit 2
fi

cmd="$1"
shift

case "$cmd" in
  -h|--help|help)
    usage
    exit 0
    ;;
esac

case "$cmd" in
  release|demo|generate|verify|measure|protect|attack|gate|scorecard|report|compare|latest) ;;
  *)
    usage >&2
    exit 2
    ;;
esac

case "$cmd" in
  generate)
    exec "$PYTHON_BIN" app/generate_test_data.py --out-root test_data/generated "$@"
    ;;
  latest)
    td_latest_run
    exit $?
    ;;
esac

# Phase commands
case "$cmd" in
  verify|measure|protect|attack|gate|scorecard|report|compare)
    RUN="$(resolve_run "$@")" || exit $?
    case "$cmd" in
      verify)
        exec "$PYTHON_BIN" app/validate_test_pack.py --run-dir "$RUN" "${TD_REST[@]+"${TD_REST[@]}"}"
        ;;
      measure)
        thread_id="td-raw-$(date -u +%Y%m%dT%H%M%SZ)"
        exec "$PYTHON_BIN" app/run_attack_sim.py --mode shadow --raw-pack --pack-root "$RUN/pack" --out-dir "$RUN/evidence/attack_sim" --checkpoint-dir "$RUN/evidence/attack_sim_checkpoints" --thread-id "$thread_id" "${TD_REST[@]+"${TD_REST[@]}"}"
        ;;
      protect)
        if [ -d "$RUN/protected" ] && [ -n "$(ls -A "$RUN/protected" 2>/dev/null)" ]; then
          echo "error: $RUN/protected already exists (never overwritten)" >&2
          exit 2
        fi
        exec "$PYTHON_BIN" app/run_test_pack.py --run-dir "$RUN" --init-key --policy both "${TD_REST[@]+"${TD_REST[@]}"}"
        ;;
      attack)
        exec "$PYTHON_BIN" app/run_test_attack.py --run-dir "$RUN" --policy both "${TD_REST[@]+"${TD_REST[@]}"}"
        ;;
      gate)
        exec "$PYTHON_BIN" scripts/testdata/gate.py --run-dir "$RUN" "${TD_REST[@]+"${TD_REST[@]}"}"
        ;;
      scorecard)
        exec "$PYTHON_BIN" app/run_test_scorecards.py --run-dir "$RUN" --policy both "${TD_REST[@]+"${TD_REST[@]}"}"
        ;;
      report)
        exec "$PYTHON_BIN" app/report_test_pack.py --run-dir "$RUN" "${TD_REST[@]+"${TD_REST[@]}"}"
        ;;
      compare)
        exec "$PYTHON_BIN" app/compare_test_pack.py --run-dir "$RUN" "${TD_REST[@]+"${TD_REST[@]}"}"
        ;;
    esac
    ;;
esac

# release / demo
is_demo=0
if [ "$cmd" = "demo" ]; then
  is_demo=1
fi

run_dir_opt=""
profile="demo"
people=2500
seed=20261107
run_id=""
skip_protect=0
policy="both"
no_scorecard=0
no_report=0
tests=0

while [ $# -gt 0 ]; do
  case "$1" in
    --run-dir)
      run_dir_opt="$2"; shift 2 ;;
    --run-dir=*)
      run_dir_opt="${1#--run-dir=}"; shift ;;
    --profile)
      profile="$2"; shift 2 ;;
    --profile=*)
      profile="${1#--profile=}"; shift ;;
    --people)
      people="$2"; shift 2 ;;
    --people=*)
      people="${1#--people=}"; shift ;;
    --seed)
      seed="$2"; shift 2 ;;
    --seed=*)
      seed="${1#--seed=}"; shift ;;
    --run-id)
      run_id="$2"; shift 2 ;;
    --run-id=*)
      run_id="${1#--run-id=}"; shift ;;
    --skip-protect)
      skip_protect=1; shift ;;
    --policy)
      policy="$2"; shift 2 ;;
    --policy=*)
      policy="${1#--policy=}"; shift ;;
    --no-scorecard)
      no_scorecard=1; shift ;;
    --no-report)
      no_report=1; shift ;;
    --tests)
      tests=1; shift ;;
    *)
      echo "error: unknown option $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$run_dir_opt" ]; then
  if [ -z "$run_id" ]; then
    run_id="$profile-n$people-s$seed-$(date -u +%Y%m%d-%H%M%S)"
  fi
  "$PYTHON_BIN" app/generate_test_data.py --profile "$profile" --people "$people" --seed "$seed" --out-root test_data/generated --run-id "$run_id" || exit $?
  run_dir_opt="test_data/generated/$run_id"
fi

RUN="$(td_require_run "$run_dir_opt")" || exit $?

echo "=== STEP 1/9 — VERIFY (validate_test_pack) ==="
"$PYTHON_BIN" app/validate_test_pack.py --run-dir "$RUN" || exit $?

echo "=== STEP 2/9 — MEASURE RAW (run_attack_sim --raw-pack) ==="
thread_id="td-raw-$(date -u +%Y%m%dT%H%M%SZ)"
"$PYTHON_BIN" app/run_attack_sim.py --mode shadow --raw-pack --pack-root "$RUN/pack" --out-dir "$RUN/evidence/attack_sim" --checkpoint-dir "$RUN/evidence/attack_sim_checkpoints" --thread-id "$thread_id" || exit $?

echo "=== STEP 3/9 — PROTECT ==="
if [ "$skip_protect" -eq 1 ]; then
  if [ ! -d "$RUN/protected" ] || [ -z "$(ls -A "$RUN/protected" 2>/dev/null)" ]; then
    echo "error: --skip-protect requires existing non-empty protected/ directory" >&2
    exit 2
  fi
else
  if [ -d "$RUN/protected" ] && [ -n "$(ls -A "$RUN/protected" 2>/dev/null)" ]; then
    echo "error: $RUN/protected already exists (never overwritten)" >&2
    exit 2
  fi
  "$PYTHON_BIN" app/run_test_pack.py --run-dir "$RUN" --init-key --policy "$policy" || exit $?
fi

echo "=== STEP 4/9 — ATTACK (run_test_attack) ==="
"$PYTHON_BIN" app/run_test_attack.py --run-dir "$RUN" --policy "$policy" || exit $?

echo "=== STEP 5/9 — GATE (gate.py) ==="
"$PYTHON_BIN" scripts/testdata/gate.py --run-dir "$RUN" || exit $?

if [ "$no_scorecard" -eq 0 ]; then
  echo "=== STEP 6/9 — SCORECARD (run_test_scorecards) ==="
  "$PYTHON_BIN" app/run_test_scorecards.py --run-dir "$RUN" --policy "$policy" || exit $?
else
  echo "=== STEP 6/9 — SCORECARD (skipped) ==="
fi

if [ "$no_report" -eq 0 ]; then
  echo "=== STEP 7/9 — REPORT (report_test_pack) ==="
  "$PYTHON_BIN" app/report_test_pack.py --run-dir "$RUN" || exit $?
else
  echo "=== STEP 7/9 — REPORT (skipped) ==="
fi

if [ "$tests" -eq 1 ]; then
  echo "=== STEP 8/9 — TESTS (pytest) ==="
  "$PYTHON_BIN" -m pytest -q -p no:cacheprovider tests || exit $?
else
  echo "=== STEP 8/9 — TESTS (skipped) ==="
fi

echo "=== STEP 9/9 — POST-VERIFY (validate_test_pack) ==="
"$PYTHON_BIN" app/validate_test_pack.py --run-dir "$RUN" || exit $?

if [ "$is_demo" -eq 1 ]; then
  echo "=== NARRATE (run_synthetic_demo --narrate-only) ==="
  "$PYTHON_BIN" app/run_synthetic_demo.py --run-dir "$RUN" --narrate-only || exit $?
fi

echo "run directory: $RUN"
echo "report: $RUN/reports/index.html"
