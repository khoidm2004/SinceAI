"""Field catalog loader and glue-column index for the PET pipeline."""
from __future__ import annotations

import csv
from pathlib import Path

GLUE_SUBTYPES = frozenset({"NATIONAL_ID", "PHONE", "IBAN", "EMAIL"})


def classify(pack_root: str | Path, dataset: str, table: str) -> dict[str, dict[str, str]]:
    path = Path(pack_root) / "metadata" / "field_catalog.csv"
    out: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["dataset"] == dataset and row["table"] == table:
                out[row["column"]] = {
                    "role": row["privacy_role"],
                    "subtype": row["subtype"],
                }
    return out


def glue_columns(pack_root: str | Path, dataset: str, table: str) -> list[str]:
    clf = classify(pack_root, dataset, table)
    return sorted(
        col
        for col, meta in clf.items()
        if meta["role"] == "direct_identifier" and meta["subtype"] in GLUE_SUBTYPES
    )
