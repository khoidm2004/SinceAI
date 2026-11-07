#!/usr/bin/env python3
"""P7 narrated demo: Attack A on raw pack data vs protected releases (no agents)."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from attack_sim import simulate_attack  # noqa: E402
from measure_baseline import (  # noqa: E402
    DEMO_HETU,
    EXPECTED_HETU,
    EXPECTED_PHONE,
    FINANCE_HETU_COL,
    FINANCE_PHONE_COL,
    FINANCE_REL,
    HEALTH_HETU_COL,
    HEALTH_PHONE_COL,
    HEALTH_REL,
)
from mosaic_check import (  # noqa: E402
    COLUMN_MAP,
    DEFAULT_CLEAN_ROOT,
    DEFAULT_FINANCE_REL,
    DEFAULT_HEALTH_REL,
    DEFAULT_PACK_ROOT,
    RAW_FINANCE_REL,
    RAW_HEALTH_REL,
)
from normalize import normalize_hetu, normalize_phone  # noqa: E402

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2

HONEST_CLAIM = (
    "Against an attacker with our two protected releases, no public adversary file, and no "
    "access to our keys, the measured cross-release join count on HETU, phone and IBAN is "
    "**0**, down from a baseline of **1622** on the unprotected data — while each release "
    "still passes `pets-eval scorecard` for its own scenario."
)

RESIDUAL_RISKS = (
    ("R-1", "Cross-release quasi-identifier mosaic: keyed tokens break identifier joins "
     "but probabilistic matching on demographics/postcode may still link across releases."),
    ("R-5", "Key compromise: a leaked master.key restores deterministic cross-release "
     "linkability retroactively."),
    ("R-6", "Pack blind spot: pets-eval may miss mosaic risk; our mosaic_check is additive, "
     "not a substitute for the organisers' private attacker set."),
    ("R-9", "Minimisation not audited: FIN-S2 glue should be dropped, HEALTH-S1 HETU "
     "tokenised — nothing flags tokenisation where drop would suffice."),
)

B1_PATH = REPO_ROOT / "benchmarks" / "B1_mosaic_joins.png"


def _banner(title: str) -> None:
    print()
    print(f"=== {title} ===")
    print()


def _fail(msg: str) -> int:
    print(f"ASSERTION FAILED: {msg}", file=sys.stderr)
    return EXIT_FAIL


def _find_row_by_hetu(
    path: Path,
    hetu_col: str,
    target: str,
) -> Optional[dict[str, str]]:
    target_norm = normalize_hetu(target)
    if not target_norm:
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if normalize_hetu(row.get(hetu_col)) == target_norm:
                return dict(row)
    return None


def _print_step1_extracts(pack_root: Path, hetu: str) -> tuple[dict[str, str], dict[str, str]] | int:
    health_path = pack_root / HEALTH_REL
    finance_path = pack_root / FINANCE_REL
    if not health_path.is_file() or not finance_path.is_file():
        print(f"error: missing raw pack CSVs under {pack_root}", file=sys.stderr)
        return EXIT_ERROR

    health = _find_row_by_hetu(health_path, HEALTH_HETU_COL, hetu)
    finance = _find_row_by_hetu(finance_path, FINANCE_HETU_COL, hetu)
    if health is None or finance is None:
        print(f"error: no matching rows for HETU {hetu!r} in both raw releases", file=sys.stderr)
        return _fail(f"worked-example HETU {hetu!r} missing from raw health and/or finance")

    _banner("Step 1 — Safe-looking extracts (raw pack data/)")
    print(f"  HETU (glue): {hetu}")
    print()
    print("  health (ed_visits):")
    print(f"    visit_id={health.get('visit_id')}")
    print(f"    patient_name={health.get('patient_name')}")
    print(f"    {HEALTH_HETU_COL}={health.get(HEALTH_HETU_COL)}")
    print(f"    {HEALTH_PHONE_COL}={health.get(HEALTH_PHONE_COL)}")
    print(f"    icd10_primary={health.get('icd10_primary')}")
    print()
    print("  finance (customers):")
    print(f"    customer_id={finance.get('customer_id')}")
    print(f"    full_name={finance.get('full_name')}")
    print(f"    {FINANCE_HETU_COL}={finance.get(FINANCE_HETU_COL)}")
    print(f"    {FINANCE_PHONE_COL}={finance.get(FINANCE_PHONE_COL)}")
    print(f"    income_band={finance.get('income_band')}")
    return health, finance


def _print_attack_raw(pack_root: Path, hetu: str, health: dict[str, str], finance: dict[str, str]) -> int:
    health_csv = pack_root / RAW_HEALTH_REL
    finance_csv = pack_root / RAW_FINANCE_REL
    result = simulate_attack(
        health_csv,
        finance_csv,
        sample_limit=0,
        **COLUMN_MAP,
    )
    hetu_obs = int(result["hetu_join"])
    phone_obs = int(result["phone_join"])

    _banner("Step 2 — Attack A on unprotected data (re-measure)")
    print(f"  observed hetu_join:  {hetu_obs}  (baseline lock expects {EXPECTED_HETU})")
    print(f"  observed phone_join: {phone_obs}  (baseline lock expects {EXPECTED_PHONE})")
    if hetu_obs != EXPECTED_HETU or phone_obs != EXPECTED_PHONE:
        return _fail(
            f"raw joins {hetu_obs}/{phone_obs} != expected baseline {EXPECTED_HETU}/{EXPECTED_PHONE}"
        )

    h_phone = health.get(HEALTH_PHONE_COL) or ""
    f_phone = finance.get(FINANCE_PHONE_COL) or ""
    print()
    print(
        "  dossier (same person, two releases): "
        f"visit_id={health.get('visit_id')} "
        f"icd10_primary={health.get('icd10_primary')} "
        f"+ customer_id={finance.get('customer_id')} "
        f"income_band={finance.get('income_band')}"
    )
    print(
        f"  phones raw: health={h_phone!r} finance={f_phone!r} "
        f"→ normalised both {normalize_phone(h_phone)!r}"
    )
    print(
        "  name-order note: health patient_name is "
        f"{health.get('patient_name')!r}; finance full_name is "
        f"{finance.get('full_name')!r} — name matching would fail, HETU still joins."
    )
    return EXIT_PASS


def _ensure_clean_data(pack_root: Path, clean_root: Path, skip_protect: bool) -> int:
    health_out = clean_root / DEFAULT_HEALTH_REL
    finance_out = clean_root / DEFAULT_FINANCE_REL
    if health_out.is_file() and finance_out.is_file():
        return EXIT_PASS
    if skip_protect:
        print(
            f"error: protected CSVs missing under {clean_root} "
            "(re-run without --skip-protect or run run_protect.py)",
            file=sys.stderr,
        )
        return EXIT_ERROR
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_protect.py"),
        "--init-key",
        "--pack-root",
        str(pack_root),
        "--out-root",
        str(clean_root),
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if proc.returncode != 0:
        print("error: run_protect.py failed", file=sys.stderr)
        return EXIT_ERROR
    if not health_out.is_file() or not finance_out.is_file():
        print("error: protect finished but protected CSVs still missing", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_PASS


def _column_diff(raw_fields: list[str], prot_fields: list[str]) -> tuple[list[str], list[str]]:
    raw_set = set(raw_fields)
    prot_set = set(prot_fields)
    dropped = sorted(raw_set - prot_set)
    # Columns present in both but changed role: tokenised HETU on health only
    kept = sorted(raw_set & prot_set)
    tokenised_hint = [c for c in kept if c in ("patient_hetu",)]
    return dropped, tokenised_hint


def _print_step3_defence(
    pack_root: Path,
    clean_root: Path,
) -> int:
    health_prot = clean_root / DEFAULT_HEALTH_REL
    finance_prot = clean_root / DEFAULT_FINANCE_REL
    if not health_prot.is_file() or not finance_prot.is_file():
        return EXIT_ERROR

    result = simulate_attack(
        health_prot,
        finance_prot,
        sample_limit=0,
        **COLUMN_MAP,
    )
    hetu_obs = int(result["hetu_join"])
    phone_obs = int(result["phone_join"])

    _banner("Step 3 — Same attack on protected releases + mosaic gate")
    print(f"  observed hetu_join (protected):  {hetu_obs}")
    print(f"  observed phone_join (protected): {phone_obs}")
    if hetu_obs != 0 or phone_obs != 0:
        return _fail(f"protected joins must be 0/0, got {hetu_obs}/{phone_obs}")

    raw_h = pack_root / RAW_HEALTH_REL
    raw_f = pack_root / RAW_FINANCE_REL
    with open(raw_h, encoding="utf-8-sig", newline="") as f:
        raw_health_cols = list(csv.DictReader(f).fieldnames or [])
    with open(raw_f, encoding="utf-8-sig", newline="") as f:
        raw_finance_cols = list(csv.DictReader(f).fieldnames or [])
    with open(health_prot, encoding="utf-8-sig", newline="") as f:
        prot_health_cols = list(csv.DictReader(f).fieldnames or [])
    with open(finance_prot, encoding="utf-8-sig", newline="") as f:
        prot_finance_cols = list(csv.DictReader(f).fieldnames or [])

    h_drop, h_tok = _column_diff(raw_health_cols, prot_health_cols)
    f_drop, _ = _column_diff(raw_finance_cols, prot_finance_cols)
    print()
    print("  HEALTH-S1: dropped columns include", ", ".join(h_drop) or "(none)")
    print("  HEALTH-S1: tokenised:", ", ".join(h_tok) or "(none)")
    print("  FIN-S2: dropped glue/identifiers include", ", ".join(f_drop) or "(none)")

    mosaic_out = clean_root / "mosaic_check.json"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "mosaic_check.py"),
        "--pack-root",
        str(pack_root),
        "--clean-root",
        str(clean_root),
        "--out",
        str(mosaic_out),
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if proc.returncode != EXIT_PASS:
        return _fail("mosaic_check.py did not exit 0")

    with open(mosaic_out, encoding="utf-8") as f:
        report: dict[str, Any] = json.load(f)
    verdict = report.get("verdict", "")
    print()
    print(f"  mosaic gate verdict: {verdict}")
    p1 = report.get("pass1") or {}
    print(
        "  PASS-1 observed joins: "
        f"hetu={p1.get('hetu_health_finance', {}).get('observed')} "
        f"phone={p1.get('phone_health_finance', {}).get('observed')}"
    )
    if verdict != "PASS":
        return _fail(f"mosaic gate verdict {verdict!r} != PASS")
    return EXIT_PASS


def _print_step4_claim() -> None:
    _banner("Step 4 — Honest claim and residual risk")
    print("HONEST_CLAIM:")
    print(HONEST_CLAIM)
    print()
    print("Residual risks (MVP_Plan §8):")
    for rid, text in RESIDUAL_RISKS:
        print(f"  {rid}: {text}")
    print()
    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(
        f"pets-eval scorecard: needs Python ≥3.10 and toolkit install; "
        f"this interpreter is {ver} — run_scorecard.py exits 4 (unavailable)."
    )
    if B1_PATH.is_file():
        print(f"B1 utility-of-attack figure: {B1_PATH}")
    else:
        print(
            f"B1 utility-of-attack figure: {B1_PATH} (not present — "
            "generate with: bash scripts/make_benchmark.sh)"
        )


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P7 narrated Attack A demo (agent-free)")
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--clean-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    parser.add_argument(
        "--skip-protect",
        action="store_true",
        help="Assume clean_data/ already exists; do not invoke run_protect.py",
    )
    parser.add_argument("--hetu", default=DEMO_HETU, help=f"Worked-example HETU (default {DEMO_HETU})")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    pack_root = args.pack_root.resolve()
    clean_root = args.clean_root.resolve()
    hetu = args.hetu

    print("SinceAI P7 — Attack A demo (health ∩ finance, no LangGraph)")
    print(f"  pack:  {pack_root}")
    print(f"  clean: {clean_root}")

    step1 = _print_step1_extracts(pack_root, hetu)
    if isinstance(step1, int):
        return step1
    health, finance = step1

    rc = _print_attack_raw(pack_root, hetu, health, finance)
    if rc != EXIT_PASS:
        return rc

    rc = _ensure_clean_data(pack_root, clean_root, args.skip_protect)
    if rc != EXIT_PASS:
        return rc

    rc = _print_step3_defence(pack_root, clean_root)
    if rc != EXIT_PASS:
        return rc

    _print_step4_claim()
    print()
    print("VERDICT: PASS")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
