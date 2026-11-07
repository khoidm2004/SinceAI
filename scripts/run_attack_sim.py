#!/usr/bin/env python3
"""P2 attack-sim agent CLI (shadow default; advisory demonstrates interrupt)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_graph import build_graph  # noqa: E402
from agent_runtime import Command, FileCheckpointer, Interrupt  # noqa: E402

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

DEFAULT_OUT_DIR = REPO_ROOT / "findings" / "agent_proposals"
DEFAULT_CHECKPOINT_DIR = REPO_ROOT / "findings" / "agent_checkpoints"

EXIT_OK = 0
EXIT_DELAY = 1
EXIT_ERROR = 2
EXIT_PAUSED = 3

PROTECTED_COLUMN_MAP = {
    "health_hetu_col": "patient_hetu",
    "finance_hetu_col": "hetu",
    "health_phone_col": "phone",
    "finance_phone_col": "phone",
}

RAW_COLUMN_MAP = {
    "health_hetu_col": "patient_hetu",
    "finance_hetu_col": "hetu",
    "health_phone_col": "phone",
    "finance_phone_col": "phone",
}


def _refuse_resources(path: Path) -> None:
    resolved = path.resolve()
    resources = RESOURCES_ROOT.resolve()
    try:
        if resolved.is_relative_to(resources):
            raise ValueError(f"refusing to write under resources/: {resolved}")
    except AttributeError:
        if str(resolved).startswith(str(resources)):
            raise ValueError(f"refusing to write under resources/: {resolved}") from None


def _resolve_csvs(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.raw_pack:
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


def _write_report(payload: dict[str, Any], out_path: Path) -> None:
    _refuse_resources(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _print_summary(payload: dict[str, Any]) -> None:
    report = payload["report"]
    print("SinceAI P2 — attack_sim agent")
    print(f"  mode:      {payload['mode']}")
    print(f"  decision:  {payload['decision']}")
    print(f"  thread_id: {payload['thread_id']}")
    print(f"  health:    {payload['paths']['health_csv']}")
    print(f"  finance:   {payload['paths']['finance_csv']}")
    print(f"  hetu_join:  {report['hetu_join']}")
    print(f"  phone_join: {report['phone_join']}")
    n_prop = len(report.get("proposals") or [])
    print(f"  proposals: {n_prop}")


def _exit_code(mode: str, decision: str, report: dict[str, Any]) -> int:
    if mode == "advisory" and decision == "rejected":
        if report.get("hetu_join", 0) > 0 or report.get("phone_join", 0) > 0:
            return EXIT_DELAY
    return EXIT_OK


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P2 attack simulation agent")
    parser.add_argument("--mode", choices=("shadow", "advisory"), default="shadow")
    parser.add_argument("--clean-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    parser.add_argument("--health-rel", type=Path, default=DEFAULT_HEALTH_REL)
    parser.add_argument("--finance-rel", type=Path, default=DEFAULT_FINANCE_REL)
    parser.add_argument("--raw-pack", action="store_true", help="Use unprotected pack data/")
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--thread-id", default=None)
    parser.add_argument("--resume", choices=("accept", "reject"), default=None)
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    thread_id = args.thread_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    try:
        health_csv, finance_csv = _resolve_csvs(args)
    except (FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    column_map = dict(RAW_COLUMN_MAP if args.raw_pack else PROTECTED_COLUMN_MAP)
    checkpointer = FileCheckpointer(args.checkpoint_dir)
    graph = build_graph(checkpointer)
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "mode": args.mode,
        "health_csv": str(health_csv),
        "finance_csv": str(finance_csv),
        "column_map": column_map,
        "report": {},
        "review_payload": {},
        "decision": "pending",
        "thread_id": thread_id,
    }

    try:
        if args.mode == "advisory" and args.resume:
            final = graph.invoke(Command(resume=args.resume), config=config)
        else:
            final = graph.invoke(initial_state, config=config)
    except Interrupt:
        out_path = args.out_dir / f"{thread_id}.json"
        try:
            ckpt = checkpointer.load(thread_id) or {}
            ckpt_state = ckpt.get("state") or {}
            payload = {
                "thread_id": thread_id,
                "mode": args.mode,
                "decision": "pending",
                "paths": {
                    "health_csv": str(health_csv.resolve()),
                    "finance_csv": str(finance_csv.resolve()),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "report": ckpt_state.get("report") or {},
            }
            _write_report(payload, out_path)
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR
        print("PAUSED — re-run with --resume accept|reject")
        _print_summary(payload)
        return EXIT_PAUSED
    except (ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    payload = {
        "thread_id": thread_id,
        "mode": args.mode,
        "decision": final.get("decision", "pending"),
        "paths": {
            "health_csv": str(health_csv.resolve()),
            "finance_csv": str(finance_csv.resolve()),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "report": final.get("report") or {},
    }

    out_path = args.out_dir / f"{thread_id}.json"
    try:
        _write_report(payload, out_path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    _print_summary(payload)
    print(f"  wrote: {out_path}")
    return _exit_code(args.mode, payload["decision"], payload["report"])


if __name__ == "__main__":
    sys.exit(main())
