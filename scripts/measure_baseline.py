"""P0, Attack A health∩finance baseline lock."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalize_hetu, normalize_phone, unique_nonempty  # reused by mosaic_check.py (P3)

EXPECTED_HETU = 1622
EXPECTED_PHONE = 1484

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACK_ROOT = (
    REPO_ROOT / "resources" / "TRUSTED_SinceAI2026_FINAL" / "TRUSTED_PETS_PROVING_GROUND_2026"
)
DEFAULT_OUT = REPO_ROOT / "findings" / "baseline_overlap.json"

HEALTH_REL = Path("data") / "health" / "ed_visits.csv"
FINANCE_REL = Path("data") / "finance" / "customers.csv"

HEALTH_HETU_COL = "patient_hetu"
HEALTH_PHONE_COL = "phone"
FINANCE_HETU_COL = "hetu"
FINANCE_PHONE_COL = "phone"

NORMALISATION_PHONE = r"strip non-[0-9+]; ^\+358→0; ^00358→0"
NORMALISATION_HETU = "strip; string as-is"

DEMO_HETU = "021280-9730"


def load_table(
    csv_path: Path,
    hetu_col: str,
    phone_col: str,
) -> tuple[set[str], set[str], int]:
    with open(csv_path, encoding="utf-8-sig", newline="", mode="r") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print(f"error: no header in {csv_path}", file=sys.stderr)
            sys.exit(2)
        fieldnames = set(reader.fieldnames)
        for col in (hetu_col, phone_col):
            if col not in fieldnames:
                print(f"error: missing column {col!r} in {csv_path}", file=sys.stderr)
                sys.exit(2)
        hetu_values: list[Optional[str]] = []
        phone_values: list[Optional[str]] = []
        row_count = 0
        for row in reader:
            row_count += 1
            hetu_values.append(row.get(hetu_col))
            phone_values.append(row.get(phone_col))
        hetu_set = unique_nonempty(hetu_values, normalize_hetu)
        phone_set = unique_nonempty(phone_values, normalize_phone)
        return hetu_set, phone_set, row_count


def _find_demo_rows(pack_root: Path) -> None:
    health_path = pack_root / HEALTH_REL
    finance_path = pack_root / FINANCE_REL
    print()
    print(f"  demo-row (P013174) — HETU {DEMO_HETU}")
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="P0 Attack A baseline lock")
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-json", action="store_true")
    parser.add_argument("--demo-row", action="store_true")
    args = parser.parse_args(argv)

    pack_root = args.pack_root.resolve()
    health_path = pack_root / HEALTH_REL
    finance_path = pack_root / FINANCE_REL

    missing = False
    if not health_path.is_file():
        print(f"error: missing {health_path}", file=sys.stderr)
        missing = True
    if not finance_path.is_file():
        print(f"error: missing {finance_path}", file=sys.stderr)
        missing = True
    if missing:
        return 2

    health_hetus, health_phones, health_rows = load_table(
        health_path, HEALTH_HETU_COL, HEALTH_PHONE_COL
    )
    finance_hetus, finance_phones, finance_rows = load_table(
        finance_path, FINANCE_HETU_COL, FINANCE_PHONE_COL
    )

    hetu_overlap = len(health_hetus & finance_hetus)
    phone_overlap = len(health_phones & finance_phones)

    hetu_pass = hetu_overlap == EXPECTED_HETU
    phone_pass = phone_overlap == EXPECTED_PHONE
    verdict = "PASS" if (hetu_pass and phone_pass) else "FAIL"

    print("SinceAI P0 — Attack A baseline (health ∩ finance), unprotected data")
    print(f"pack root: {pack_root}")
    print()
    print(
        f"  health  {HEALTH_REL}      {health_rows:>6} rows   "
        f"{len(health_hetus):>6} distinct HETU   {len(health_phones):>6} distinct phone(norm)"
    )
    print(
        f"  finance {FINANCE_REL}     {finance_rows:>6} rows   "
        f"{len(finance_hetus):>6} distinct HETU   {len(finance_phones):>6} distinct phone(norm)"
    )
    print()
    print("  normalisation  phone: strip non-[0-9+]; ^+358→0; ^00358→0")
    print("                 hetu:  strip; string as-is")
    print()
    print("  join                        observed   expected   result")
    print(
        f"  hetu  health ∩ finance      {hetu_overlap:>10}   "
        f"{EXPECTED_HETU:>10}   {'PASS' if hetu_pass else 'FAIL'}"
    )
    print(
        f"  phone health ∩ finance      {phone_overlap:>10}   "
        f"{EXPECTED_PHONE:>10}   {'PASS' if phone_pass else 'FAIL'}"
    )
    print()
    if verdict == "PASS":
        print(f"VERDICT: {verdict}  (baseline locked at {EXPECTED_HETU} / {EXPECTED_PHONE})")
    else:
        print(f"VERDICT: {verdict}")

    if args.demo_row:
        _find_demo_rows(pack_root)

    if not args.no_json:
        report = {
            "pack_root": str(pack_root),
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
                "phone": NORMALISATION_PHONE,
                "hetu": NORMALISATION_HETU,
            },
            "verdict": verdict,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as out_f:
            json.dump(report, out_f, indent=2)
            out_f.write("\n")

    return 0 if (hetu_pass and phone_pass) else 1


if __name__ == "__main__":
    sys.exit(main())
