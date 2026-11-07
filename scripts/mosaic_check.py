#!/usr/bin/env python3
"""P3 mosaic gate: PASS-1 (protected joins == 0) + PASS-2 (raw == 1622/1484)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from attack_sim import simulate_attack  # noqa: E402
from measure_baseline import EXPECTED_HETU, EXPECTED_PHONE  # noqa: E402
from normalize import HETU_RECIPE, PHONE_RECIPE  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_ROOT = REPO_ROOT / "resources"

DEFAULT_PACK_ROOT = (
    REPO_ROOT / "resources" / "TRUSTED_SinceAI2026_FINAL" / "TRUSTED_PETS_PROVING_GROUND_2026"
)
DEFAULT_CLEAN_ROOT = REPO_ROOT / "clean_data"
DEFAULT_HEALTH_REL = Path("health__HEALTH-S1/ed_visits.csv")
DEFAULT_FINANCE_REL = Path("finance__FIN-S2/customers.csv")
RAW_HEALTH_REL = Path("data/health/ed_visits.csv")
RAW_FINANCE_REL = Path("data/finance/customers.csv")

DEFAULT_OUT = DEFAULT_CLEAN_ROOT / "mosaic_check.json"
DEFAULT_OUT_NEG = Path("/tmp/mosaic_neg.json")

EXPECTED_PASS1_HETU = 0
EXPECTED_PASS1_PHONE = 0

COLUMN_MAP = {
    "health_hetu_col": "patient_hetu",
    "finance_hetu_col": "hetu",
    "health_phone_col": "phone",
    "finance_phone_col": "phone",
}

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2

# Future energy/customer_service PASS-2 rows are out of MVP scope (MVP_Plan §4).


def _refuse_resources_write(path: Path) -> None:
    resolved = path.resolve()
    resources = RESOURCES_ROOT.resolve()
    try:
        if resolved.is_relative_to(resources):
            raise ValueError(f"refusing to write under resources/: {resolved}")
    except AttributeError:
        if str(resolved).startswith(str(resources)):
            raise ValueError(f"refusing to write under resources/: {resolved}") from None


def _join_block(observed: int, expected: int) -> dict[str, Any]:
    return {
        "observed": observed,
        "expected": expected,
        "pass": observed == expected,
    }


def _run_pass(
    health_csv: Path,
    finance_csv: Path,
    expected_hetu: int,
    expected_phone: int,
) -> dict[str, Any]:
    result = simulate_attack(
        health_csv,
        finance_csv,
        sample_limit=0,
        **COLUMN_MAP,
    )
    hetu_obs = int(result["hetu_join"])
    phone_obs = int(result["phone_join"])
    return {
        "hetu_health_finance": _join_block(hetu_obs, expected_hetu),
        "phone_health_finance": _join_block(phone_obs, expected_phone),
    }


def _pass_ok(block: dict[str, Any]) -> bool:
    return bool(
        block["hetu_health_finance"]["pass"] and block["phone_health_finance"]["pass"]
    )


def _resolve_pass1_csvs(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.pass1_as_raw:
        root = args.pack_root.resolve()
        health = root / RAW_HEALTH_REL
        finance = root / RAW_FINANCE_REL
    else:
        root = args.clean_root.resolve()
        health = root / args.health_rel
        finance = root / args.finance_rel
    if not health.is_file():
        raise FileNotFoundError(f"missing health CSV: {health}")
    if not finance.is_file():
        raise FileNotFoundError(f"missing finance CSV: {finance}")
    return health, finance


def _resolve_pass2_csvs(pack_root: Path) -> tuple[Path, Path]:
    root = pack_root.resolve()
    health = root / RAW_HEALTH_REL
    finance = root / RAW_FINANCE_REL
    if not health.is_file():
        raise FileNotFoundError(f"missing raw health CSV: {health}")
    if not finance.is_file():
        raise FileNotFoundError(f"missing raw finance CSV: {finance}")
    return health, finance


def build_report(
    pack_root: Path,
    clean_root: Path,
    pass1: dict[str, Any],
    pass2: Optional[dict[str, Any]],
    *,
    skip_pass2: bool,
) -> dict[str, Any]:
    if skip_pass2 or pass2 is None:
        positive_control: dict[str, Any] = {
            "skipped": True,
            "reason": "PASS-2 not run (--skip-pass2)",
        }
        pass1_ok = _pass_ok(pass1)
        if pass1_ok:
            verdict = "PASS_UNVERIFIED"
        else:
            verdict = "FAIL"
    else:
        positive_control = {
            "skipped": False,
            "hetu_health_finance": dict(pass2["hetu_health_finance"]),
            "phone_health_finance": dict(pass2["phone_health_finance"]),
            "pass": _pass_ok(pass2),
        }
        if _pass_ok(pass1) and _pass_ok(pass2):
            verdict = "PASS"
        else:
            verdict = "FAIL"

    return {
        "pack_root": str(pack_root.resolve()),
        "clean_root": str(clean_root.resolve()),
        "normalisation": {
            "phone": PHONE_RECIPE,
            "hetu": HETU_RECIPE,
        },
        "pass1": pass1,
        "pass2": pass2,
        "positive_control": positive_control,
        "verdict": verdict,
    }


def print_summary(report: dict[str, Any], *, skip_pass2: bool) -> None:
    print("SinceAI P3 — mosaic gate (health ∩ finance)")
    print(f"  pack:  {report['pack_root']}")
    print(f"  clean: {report['clean_root']}")
    print()
    print("  join                        observed   expected   result")
    for label, block in (
        ("PASS-1 hetu  health ∩ finance", report["pass1"]["hetu_health_finance"]),
        ("PASS-1 phone health ∩ finance", report["pass1"]["phone_health_finance"]),
    ):
        print(
            f"  {label:<28} {block['observed']:>10}   "
            f"{block['expected']:>10}   {'PASS' if block['pass'] else 'FAIL'}"
        )
    if not skip_pass2 and report.get("pass2"):
        pass2 = report["pass2"]
        for label, block in (
            ("PASS-2 hetu  health ∩ finance", pass2["hetu_health_finance"]),
            ("PASS-2 phone health ∩ finance", pass2["phone_health_finance"]),
        ):
            print(
                f"  {label:<28} {block['observed']:>10}   "
                f"{block['expected']:>10}   {'PASS' if block['pass'] else 'FAIL'}"
            )
    elif skip_pass2:
        print("  PASS-2                      (skipped — unverified)")
    print()
    verdict = report["verdict"]
    if verdict == "PASS":
        print(f"VERDICT: PASS")
    elif verdict == "PASS_UNVERIFIED":
        print("VERDICT: PASS (unverified — PASS-2 skipped)")
    else:
        print(f"VERDICT: FAIL")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P3 mosaic cross-release gate")
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--clean-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    parser.add_argument("--health-rel", type=Path, default=DEFAULT_HEALTH_REL)
    parser.add_argument("--finance-rel", type=Path, default=DEFAULT_FINANCE_REL)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"JSON report (default: {DEFAULT_OUT} or {DEFAULT_OUT_NEG} with --pass1-as-raw)",
    )
    parser.add_argument(
        "--pass1-as-raw",
        action="store_true",
        help="Run PASS-1 on unprotected pack data/ (negative control); PASS-2 unchanged",
    )
    parser.add_argument(
        "--skip-pass2",
        action="store_true",
        help="DEBUG: skip PASS-2 positive control (loud warning)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    if args.skip_pass2:
        print(
            "WARNING: --skip-pass2 set — PASS-1 alone is NOT sufficient for a verified release.",
            file=sys.stderr,
        )

    out_path = args.out
    if out_path is None:
        out_path = DEFAULT_OUT_NEG if args.pass1_as_raw else DEFAULT_OUT

    try:
        pass1_health, pass1_finance = _resolve_pass1_csvs(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if not args.pass1_as_raw:
            print(
                "hint: run `python3 scripts/run_protect.py --init-key` first",
                file=sys.stderr,
            )
        return EXIT_ERROR

    pass1 = _run_pass(
        pass1_health,
        pass1_finance,
        EXPECTED_PASS1_HETU,
        EXPECTED_PASS1_PHONE,
    )

    pass2: Optional[dict[str, Any]] = None
    if not args.skip_pass2:
        try:
            p2_health, p2_finance = _resolve_pass2_csvs(args.pack_root)
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR
        pass2 = _run_pass(p2_health, p2_finance, EXPECTED_HETU, EXPECTED_PHONE)

    report = build_report(
        args.pack_root,
        args.clean_root,
        pass1,
        pass2,
        skip_pass2=args.skip_pass2,
    )

    print_summary(report, skip_pass2=args.skip_pass2)

    try:
        _refuse_resources_write(out_path)
        out_path = out_path.resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    verdict = report["verdict"]
    if verdict in ("PASS", "PASS_UNVERIFIED"):
        return EXIT_PASS
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
