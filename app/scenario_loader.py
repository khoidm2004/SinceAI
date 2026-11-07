"""Load scenario definitions from the pack metadata."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_scenarios(pack_root: str | Path) -> dict[str, dict[str, Any]]:
    path = Path(pack_root) / "metadata" / "scenarios.json"
    with open(path, encoding="utf-8") as f:
        entries: list[dict[str, Any]] = json.load(f)
    return {entry["id"]: entry for entry in entries}


def get_scenario(pack_root: str | Path, scenario_id: str) -> dict[str, Any]:
    scenarios = load_scenarios(pack_root)
    if scenario_id not in scenarios:
        raise KeyError(f"unknown scenario id: {scenario_id!r}")
    return scenarios[scenario_id]
