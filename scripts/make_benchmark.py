#!/usr/bin/env python3
"""P4 benchmark figures: B1 mosaic joins from mosaic_check.json; optional B2 scorecards."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MOSAIC = REPO_ROOT / "clean_data" / "mosaic_check.json"
DEFAULT_OUT_DIR = REPO_ROOT / "benchmarks"
DEFAULT_SC_HEALTH = REPO_ROOT / "clean_data" / "health__HEALTH-S1" / "scorecard.json"
DEFAULT_SC_FINANCE = REPO_ROOT / "clean_data" / "finance__FIN-S2" / "scorecard.json"

EXIT_OK = 0
EXIT_ERROR = 2

JOIN_KEYS = ("hetu_health_finance", "phone_health_finance")
JOIN_LABELS = {"hetu_health_finance": "HETU", "phone_health_finance": "Phone"}


def _load_mosaic(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing mosaic JSON: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for block in ("pass1", "pass2"):
        if block not in data or not isinstance(data[block], dict):
            raise ValueError(f"mosaic JSON missing block: {block}")
        for key in JOIN_KEYS:
            if key not in data[block]:
                raise ValueError(f"mosaic JSON missing {block}.{key}")
            obs = data[block][key].get("observed")
            if obs is None:
                raise ValueError(f"mosaic JSON missing observed for {block}.{key}")
    return data


def _observed(block: dict[str, Any], key: str) -> int:
    return int(block[key]["observed"])


def _import_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: WPS433

        return plt
    except ImportError as e:
        raise ImportError("matplotlib is required for benchmarks") from e


def plot_b1(
    mosaic: dict[str, Any],
    out_path: Path,
) -> None:
    plt = _import_matplotlib()
    before_hetu = _observed(mosaic["pass2"], "hetu_health_finance")
    before_phone = _observed(mosaic["pass2"], "phone_health_finance")
    after_hetu = _observed(mosaic["pass1"], "hetu_health_finance")
    after_phone = _observed(mosaic["pass1"], "phone_health_finance")

    groups = [JOIN_LABELS["hetu_health_finance"], JOIN_LABELS["phone_health_finance"]]
    before_vals = [before_hetu, before_phone]
    after_vals = [after_hetu, after_phone]

    x = list(range(len(groups)))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    bars1 = ax.bar([i - width / 2 for i in x], before_vals, width, label="Before (PASS-2)")
    bars2 = ax.bar([i + width / 2 for i in x], after_vals, width, label="After (PASS-1)")
    ax.bar_label(bars1)
    ax.bar_label(bars2)
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_ylabel("Cross-release join count")
    ax.set_title("Attack A join yield — before vs after protection")
    ax.legend()
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _scorecard_metrics(path: Path) -> Optional[dict[str, float]]:
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    summary = data.get("summary")
    if isinstance(summary, dict):
        keys = ("privacy", "utility", "composite")
        if all(k in summary and summary[k] is not None for k in keys):
            return {k: float(summary[k]) for k in keys}
    for k in ("privacy", "utility", "composite"):
        if k not in data or data[k] is None:
            return None
    return {k: float(data[k]) for k in ("privacy", "utility", "composite")}


def plot_b2(
    health_path: Path,
    finance_path: Path,
    out_path: Path,
) -> bool:
    h = _scorecard_metrics(health_path)
    f = _scorecard_metrics(finance_path)
    if h is None or f is None:
        return False
    plt = _import_matplotlib()
    metrics = ("privacy", "utility", "composite")
    releases = ("health", "finance")
    values = [[h[m] for m in metrics], [f[m] for m in metrics]]

    x = list(range(len(metrics)))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    bars1 = ax.bar([i - width / 2 for i in x], values[0], width, label=releases[0])
    bars2 = ax.bar([i + width / 2 for i in x], values[1], width, label=releases[1])
    ax.bar_label(bars1, fmt="%.2f")
    ax.bar_label(bars2, fmt="%.2f")
    ax.set_xticks(x)
    ax.set_xticklabels([m.capitalize() for m in metrics])
    ax.set_ylabel("Score")
    ax.set_title("PET scorecards — privacy / utility / composite")
    ax.set_ylim(0, 1.05)
    ax.legend()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


def write_b2_unavailable(out_dir: Path, health_path: Path, finance_path: Path) -> None:
    lines = [
        "B2 scorecard benchmark unavailable.",
        "",
        "Scorecard JSON files were not found or did not contain summary.privacy,",
        "summary.utility, and summary.composite (pets-eval needs Python >= 3.10).",
        "",
        f"  health scorecard:  {health_path}",
        f"  finance scorecard: {finance_path}",
    ]
    path = out_dir / "B2_UNAVAILABLE.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate P4 benchmark figures")
    parser.add_argument("--mosaic-json", type=Path, default=DEFAULT_MOSAIC)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--scorecard-health", type=Path, default=DEFAULT_SC_HEALTH)
    parser.add_argument("--scorecard-finance", type=Path, default=DEFAULT_SC_FINANCE)
    args = parser.parse_args(argv)

    try:
        mosaic = _load_mosaic(args.mosaic_json)
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError) as e:
        print(f"mosaic JSON error: {e}", file=sys.stderr)
        return EXIT_ERROR

    try:
        b1_path = args.out_dir / "B1_mosaic_joins.png"
        plot_b1(mosaic, b1_path)
        print(f"wrote {b1_path}")
    except ImportError as e:
        print(f"{e}", file=sys.stderr)
        return EXIT_ERROR

    if plot_b2(args.scorecard_health, args.scorecard_finance, args.out_dir / "B2_scores.png"):
        print(f"wrote {args.out_dir / 'B2_scores.png'}")
    else:
        write_b2_unavailable(args.out_dir, args.scorecard_health, args.scorecard_finance)
        print(f"wrote {args.out_dir / 'B2_UNAVAILABLE.txt'}")

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
