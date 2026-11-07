from __future__ import annotations

from python_version import require_python

require_python()
import argparse
import csv
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from field_classifier import classify, glue_columns  # noqa: E402
from pet_pipeline import TOKENISE_IDENTIFIERS, protect_table  # noqa: E402
from pseudonym import create_master_key, derive_subkey, load_master_key  # noqa: E402
from release_writer import write_release  # noqa: E402
from scenario_loader import get_scenario  # noqa: E402

DEFAULT_PACK_ROOT = (
    REPO_ROOT
    / "resources"
    / "TRUSTED_SinceAI2026_FINAL"
    / "TRUSTED_PETS_PROVING_GROUND_2026"
)

RELEASES: dict[str, tuple[str, str, str]] = {
    "HEALTH-S1": ("health", "ed_visits", "visit_id"),
    "FIN-S2": ("finance", "customers", "customer_id"),
}

EXIT_OK = 0
EXIT_ERROR = 2


def read_table_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"no header in {path}")
        rows = list(reader)
        return rows, list(reader.fieldnames)


def glue_survival_guard(
    dataset: str,
    scenario_id: str,
    pack_root: Path,
    table: str,
    out_fieldnames: list[str],
) -> None:
    allowed = TOKENISE_IDENTIFIERS.get((dataset, scenario_id), set())
    glue = set(glue_columns(pack_root, dataset, table))
    survivors = glue & set(out_fieldnames) - allowed
    if survivors:
        raise SystemExit(
            f"glue-survival guard failed for {scenario_id}: "
            f"glue column(s) still present but not tokenised: {sorted(survivors)}"
        )


def protect_one(
    pack_root: Path,
    out_root: Path,
    master: bytes,
    scenario_id: str,
) -> int:
    if scenario_id not in RELEASES:
        print(f"error: unsupported scenario {scenario_id!r}", file=sys.stderr)
        return EXIT_ERROR

    scenario = get_scenario(pack_root, scenario_id)
    dataset, table, record_key = RELEASES[scenario_id]
    if scenario["dataset"] != dataset:
        print(
            f"error: scenario {scenario_id} dataset mismatch "
            f"(catalog {scenario['dataset']!r}, expected {dataset!r})",
            file=sys.stderr,
        )
        return EXIT_ERROR

    csv_path = pack_root / "data" / dataset / f"{table}.csv"
    if not csv_path.is_file():
        print(f"error: missing pack CSV {csv_path}", file=sys.stderr)
        return EXIT_ERROR

    rows, fieldnames = read_table_csv(csv_path)
    classifier = classify(pack_root, dataset, table)
    subkey = derive_subkey(master, dataset, scenario_id)

    out_rows, out_fieldnames, actions = protect_table(
        rows,
        fieldnames,
        dataset=dataset,
        table=table,
        scenario_id=scenario_id,
        classifier=classifier,
        subkey=subkey,
    )

    glue_survival_guard(dataset, scenario_id, pack_root, table, out_fieldnames)

    record_ids = [str(r.get(record_key, "")) for r in rows]
    out_dir = out_root / f"{dataset}__{scenario_id}"
    write_release(out_dir, table, out_rows, out_fieldnames, record_ids)

    print(f"=== {scenario_id} ({dataset}/{table}) ===")
    print(f"  output: {out_dir}")
    print(f"  rows: {len(rows)} in → {len(out_rows)} out")
    print(f"  columns: {len(fieldnames)} in → {len(out_fieldnames)} out")
    print(f"  dropped:     {', '.join(actions['dropped']) or '(none)'}")
    print(f"  tokenised:   {', '.join(actions['tokenised']) or '(none)'}")
    print(f"  generalised: {', '.join(actions['generalised']) or '(none)'}")
    print()
    return EXIT_OK


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P1 protect HEALTH-S1 + FIN-S2")
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--key-file", type=Path, default=REPO_ROOT / "keys" / "master.key")
    parser.add_argument("--out-root", type=Path, default=REPO_ROOT / "clean_data")
    parser.add_argument(
        "--init-key",
        action="store_true",
        help="Create key file with 32 random bytes if missing (never overwrite)",
    )
    parser.add_argument(
        "--only",
        choices=["HEALTH-S1", "FIN-S2"],
        help="Protect a single scenario (default: both)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    pack_root = args.pack_root.resolve()
    if not pack_root.is_dir():
        print(f"error: pack root not found: {pack_root}", file=sys.stderr)
        return EXIT_ERROR

    key_path = args.key_file if args.key_file.is_absolute() else REPO_ROOT / args.key_file
    if key_path.is_file():
        master = load_master_key(key_path)
    elif args.init_key:
        master = create_master_key(key_path)
        print(f"created master key: {key_path}")
    else:
        print(
            f"error: key file missing ({key_path}); pass --init-key to create one",
            file=sys.stderr,
        )
        return EXIT_ERROR

    scenarios = ["HEALTH-S1", "FIN-S2"] if args.only is None else [args.only]
    out_root = args.out_root if args.out_root.is_absolute() else REPO_ROOT / args.out_root

    for sid in scenarios:
        code = protect_one(pack_root, out_root, master, sid)
        if code != EXIT_OK:
            return code
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
