from __future__ import annotations

from python_version import require_python

require_python()
import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import (  # noqa: E402
    HETU_RECIPE,
    PHONE_RECIPE,
    normalize_hetu,
    normalize_phone,
    unique_nonempty,
)

EXPECTED_HETU = 1622
EXPECTED_PHONE = 1484  # NEVER retune these

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACK_ROOT = (
    REPO_ROOT / "resources" / "TRUSTED_SinceAI2026_FINAL" / "TRUSTED_PETS_PROVING_GROUND_2026"
)
DEFAULT_OUT = REPO_ROOT / "findings" / "baseline_overlap.json"

RESOURCES_ROOT = REPO_ROOT / "resources"

HEALTH_REL = Path("data") / "health" / "ed_visits.csv"
FINANCE_REL = Path("data") / "finance" / "customers.csv"

HEALTH_HETU_COL = "patient_hetu"
HEALTH_PHONE_COL = "phone"
FINANCE_HETU_COL = "hetu"
FINANCE_PHONE_COL = "phone"

REFERENCE_HEALTH_ROWS = 46398
REFERENCE_FINANCE_ROWS = 6315

DEMO_HETU = "021280-9730"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2

# Future PASS-2 joins (energy/customer_service, etc.) are out of MVP scope;
# mosaic_check.py will add them later. P0 requires only health ∩ finance.


def read_csv_columns(path: Path, columns: Sequence[str]) -> dict[str, list[str | None]]:
    with open(path, encoding="utf-8-sig", newline="", mode="r") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"no header in {path}")
        fieldnames = set(reader.fieldnames)
        missing = [c for c in columns if c not in fieldnames]
        if missing:
            raise ValueError(f"missing column(s) {missing!r} in {path}")
        out: dict[str, list[str | None]] = {col: [] for col in columns}
        for row in reader:
            for column in columns:
                out[column].append(row.get(column))
        return out


def load_pack(pack_root: Path) -> tuple[dict[str, list[str | None]], dict[str, list[str | None]]]:
    pack_root = pack_root.resolve()
    if not pack_root.is_dir():
        raise FileNotFoundError(f"pack root not found: {pack_root}")
    health_path = pack_root / HEALTH_REL
    finance_path = pack_root / FINANCE_REL
    if not health_path.is_file():
        raise FileNotFoundError(f"missing {health_path}")
    if not finance_path.is_file():
        raise FileNotFoundError(f"missing {finance_path}")
    health = read_csv_columns(health_path, [HEALTH_HETU_COL, HEALTH_PHONE_COL])
    finance = read_csv_columns(finance_path, [FINANCE_HETU_COL, FINANCE_PHONE_COL])
    return health, finance


def build_report(
    pack_root: Path,
    health: dict[str, list[str | None]],
    finance: dict[str, list[str | None]],
) -> dict[str, Any]:
    health_hetus = unique_nonempty(health[HEALTH_HETU_COL], normalize_hetu)
    health_phones = unique_nonempty(health[HEALTH_PHONE_COL], normalize_phone)
    finance_hetus = unique_nonempty(finance[FINANCE_HETU_COL], normalize_hetu)
    finance_phones = unique_nonempty(finance[FINANCE_PHONE_COL], normalize_phone)

    hetu_overlap = len(health_hetus & finance_hetus)
    phone_overlap = len(health_phones & finance_phones)

    hetu_pass = hetu_overlap == EXPECTED_HETU
    phone_pass = phone_overlap == EXPECTED_PHONE
    verdict = "PASS" if hetu_pass and phone_pass else "FAIL"

    health_rows = len(health[HEALTH_HETU_COL])
    finance_rows = len(finance[FINANCE_HETU_COL])

    return {
        "pack_root": str(pack_root.resolve()),
        "joins": {
            "hetu_health_finance": {
                "observed": hetu_overlap,
                "expected": EXPECTED_HETU,
                "pass": hetu_pass,
            },
            "phone_health_finance": {
                "observed": phone_overlap,
                "expected": EXPECTED_PHONE,
                "pass": phone_pass,
            },
        },
        "normalisation": {
            "phone": PHONE_RECIPE,
            "hetu": HETU_RECIPE,
        },
        "counts": {
            "health": {
                "rows": health_rows,
                "distinct_hetu": len(health_hetus),
                "distinct_phone_norm": len(health_phones),
            },
            "finance": {
                "rows": finance_rows,
                "distinct_hetu": len(finance_hetus),
                "distinct_phone_norm": len(finance_phones),
            },
        },
        "verdict": verdict,
    }


def print_summary(report: dict[str, Any]) -> None:
    counts = report["counts"]
    joins = report["joins"]
    print("Mosaic P0 — Attack A baseline (health ∩ finance), unprotected data")
    print(f"pack root: {report['pack_root']}")
    print()
    print(
        f"  health  {HEALTH_REL}      {counts['health']['rows']:>6} rows   "
        f"{counts['health']['distinct_hetu']:>6} distinct HETU   "
        f"{counts['health']['distinct_phone_norm']:>6} distinct phone(norm)"
    )
    print(
        f"  finance {FINANCE_REL}     {counts['finance']['rows']:>6} rows   "
        f"{counts['finance']['distinct_hetu']:>6} distinct HETU   "
        f"{counts['finance']['distinct_phone_norm']:>6} distinct phone(norm)"
    )
    print(
        f"  (reference row counts: health {REFERENCE_HEALTH_ROWS}, "
        f"finance {REFERENCE_FINANCE_ROWS})"
    )
    print()
    print(f"  normalisation  phone: {PHONE_RECIPE}")
    print(f"                 hetu:  {HETU_RECIPE}")
    print()
    print("  join                        observed   expected   result")
    hetu = joins["hetu_health_finance"]
    phone = joins["phone_health_finance"]
    print(
        f"  hetu  health ∩ finance      {hetu['observed']:>10}   "
        f"{hetu['expected']:>10}   {'PASS' if hetu['pass'] else 'FAIL'}"
    )
    print(
        f"  phone health ∩ finance      {phone['observed']:>10}   "
        f"{phone['expected']:>10}   {'PASS' if phone['pass'] else 'FAIL'}"
    )
    print()
    verdict = report["verdict"]
    if verdict == "PASS":
        print(f"VERDICT: {verdict}  (baseline locked at {EXPECTED_HETU} / {EXPECTED_PHONE})")
    else:
        print(f"VERDICT: {verdict}")


def _phone_for_hetu(
    pack_root: Path,
    hetu: str,
) -> tuple[str | None, str | None]:
    """Return (health_phone_raw, finance_phone_raw) for hetu in data/ CSVs."""
    health_phone: str | None = None
    finance_phone: str | None = None
    health_path = pack_root / HEALTH_REL
    with open(health_path, encoding="utf-8-sig", newline="", mode="r") as f:
        for row in csv.DictReader(f):
            if normalize_hetu(row.get(HEALTH_HETU_COL)) == hetu:
                health_phone = row.get(HEALTH_PHONE_COL)
                break
    finance_path = pack_root / FINANCE_REL
    with open(finance_path, encoding="utf-8-sig", newline="", mode="r") as f:
        for row in csv.DictReader(f):
            if normalize_hetu(row.get(FINANCE_HETU_COL)) == hetu:
                finance_phone = row.get(FINANCE_PHONE_COL)
                break
    return health_phone, finance_phone


def print_demo_row(pack_root: Path) -> None:
    print()
    print(f"  demo-row (P013174) — HETU {DEMO_HETU}")
    health_path = pack_root / HEALTH_REL
    finance_path = pack_root / FINANCE_REL
    with open(health_path, encoding="utf-8-sig", newline="", mode="r") as f:
        for row in csv.DictReader(f):
            if normalize_hetu(row.get(HEALTH_HETU_COL)) == DEMO_HETU:
                print(
                    f"    health  visit_id={row.get('visit_id')} "
                    f"name={row.get('patient_name')} phone={row.get(HEALTH_PHONE_COL)}"
                )
                break
        else:
            print(f"    health  (no row with HETU {DEMO_HETU})")
    with open(finance_path, encoding="utf-8-sig", newline="", mode="r") as f:
        for row in csv.DictReader(f):
            if normalize_hetu(row.get(FINANCE_HETU_COL)) == DEMO_HETU:
                print(
                    f"    finance customer_id={row.get('customer_id')} "
                    f"name={row.get('full_name')} phone={row.get(FINANCE_PHONE_COL)}"
                )
                break
        else:
            print(f"    finance (no row with HETU {DEMO_HETU})")
    h_raw, f_raw = _phone_for_hetu(pack_root, DEMO_HETU)
    if h_raw is not None and f_raw is not None:
        print(
            f"    normalised phone: health={normalize_phone(h_raw)!r} "
            f"finance={normalize_phone(f_raw)!r}"
        )


def write_report(report: dict[str, Any], out_path: Path) -> None:
    out_path = out_path.resolve()
    if out_path.is_relative_to(RESOURCES_ROOT.resolve()):
        raise ValueError(f"refusing to write under resources/: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as out_f:
        json.dump(report, out_f, indent=2, ensure_ascii=False)
        out_f.write("\n")


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P0 Attack A baseline lock (health ∩ finance)"
    )
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--no-out", "--no-json", dest="no_out", action="store_true", help="Skip JSON report"
    )
    parser.add_argument("--demo-row", action="store_true", help="Print P013174 demo row")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    pack_root = args.pack_root

    try:
        health, finance = load_pack(pack_root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    report = build_report(pack_root, health, finance)
    print_summary(report)

    if args.demo_row:
        print_demo_row(pack_root.resolve())

    if not args.no_out:
        try:
            write_report(report, args.out)
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR

    if report["verdict"] == "PASS":
        return EXIT_PASS
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
