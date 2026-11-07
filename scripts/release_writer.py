"""Write protected release CSVs and row maps (never under resources/)."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_ROOT = REPO_ROOT / "resources"


def _refuse_resources(path: Path) -> None:
    resolved = path.resolve()
    resources = RESOURCES_ROOT.resolve()
    try:
        if resolved.is_relative_to(resources):
            raise ValueError(f"refusing to write under resources/: {resolved}")
    except AttributeError:
        if str(resolved).startswith(str(resources)):
            raise ValueError(f"refusing to write under resources/: {resolved}") from None


def write_release(
    out_dir: str | Path,
    table: str,
    rows: list[dict[str, Any]],
    fieldnames: Sequence[str],
    record_ids: Sequence[str],
) -> None:
    out_dir = Path(out_dir)
    _refuse_resources(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    table_path = out_dir / f"{table}.csv"
    _refuse_resources(table_path)
    with open(table_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    rowmap_path = out_dir / f"rowmap_{table}.csv"
    _refuse_resources(rowmap_path)
    with open(rowmap_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["protected_row", "original_record_id"])
        writer.writeheader()
        for i, rid in enumerate(record_ids):
            writer.writerow({"protected_row": i, "original_record_id": rid})
