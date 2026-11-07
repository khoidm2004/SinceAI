from __future__ import annotations

from python_version import require_python

require_python()
import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_contracts import ContractViolation, PROMPT_VERSION, selftest as contract_selftest  # noqa: E402
from agent_graph import build_graph  # noqa: E402
from agent_runtime import Command, FileCheckpointer, Interrupt  # noqa: E402
from groq_client import GroqClient, GroqConfig  # noqa: E402
from run_attack_sim import (  # noqa: E402
    DEFAULT_CHECKPOINT_DIR,
    DEFAULT_CLEAN_ROOT,
    DEFAULT_FINANCE_REL,
    DEFAULT_HEALTH_REL,
    DEFAULT_OUT_DIR,
    DEFAULT_PACK_ROOT,
    EXIT_DELAY,
    EXIT_ERROR,
    EXIT_OK,
    EXIT_PAUSED,
    PROTECTED_COLUMN_MAP,
    RAW_COLUMN_MAP,
    _exit_code,
    _refuse_resources,
    _resolve_csvs,
    _write_report,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_ROOT = REPO_ROOT / "resources"


def _refuse_clean_data(path: Path) -> None:
    resolved = path.resolve()
    clean = (REPO_ROOT / "clean_data").resolve()
    try:
        if resolved.is_relative_to(clean):
            raise ValueError(f"refusing to write under clean_data/: {resolved}")
    except AttributeError:
        if str(resolved).startswith(str(clean)):
            raise ValueError(f"refusing to write under clean_data/: {resolved}") from None


def _strip_runtime(state: dict) -> dict:
    return {k: v for k, v in state.items() if not str(k).startswith("_")}


def _resolve_agents(args: argparse.Namespace) -> tuple[bool, str]:
    if args.agents == "off":
        return False, "off (--agents off)"
    if args.llm_stub:
        return True, "on (stub — no network)"
    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if args.agents == "on":
        if not key:
            return False, "ERROR"
        return True, "on (groq)"
    if key:
        return True, "on (groq)"
    return False, "off (no GROQ_API_KEY)"


class _StrippingCheckpointer:
    """Drop runtime-only `_…` keys before JSON checkpoint writes."""

    def __init__(self, inner: FileCheckpointer) -> None:
        self._inner = inner

    def save(self, thread_id: str, data: dict) -> None:
        payload = dict(data)
        state = payload.get("state")
        if isinstance(state, dict):
            payload["state"] = _strip_runtime(state)
        self._inner.save(thread_id, payload)

    def load(self, thread_id: str) -> dict | None:
        return self._inner.load(thread_id)


def _candidate_hash(health_csv: Path, finance_csv: Path) -> str:
    h = hashlib.sha256()
    for p in (health_csv, finance_csv):
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()


def _run_selftest() -> int:
    all_ok = True
    for name, ok, detail in contract_selftest():
        mark = "PASS" if ok else "FAIL"
        print(f"{mark} {name} — {detail}")
        all_ok = all_ok and ok

    ckpt_dir = Path(tempfile.mkdtemp(prefix="sinceai-agent-selftest-"))
    checkpointer = FileCheckpointer(ckpt_dir)
    compiled = build_graph(checkpointer, agents_enabled=True)
    inner = compiled._graph
    expected = {
        "attack_sim",
        "supervisor",
        "classify_assist",
        "minim_assist",
        "brief_writer",
        "human_review",
    }
    if set(inner.nodes.keys()) != expected:
        print(f"SELFTEST: FAIL — unexpected nodes {set(inner.nodes.keys())}")
        return EXIT_ERROR
    successors: dict[str, list[str]] = {}
    for a, b in inner.edges:
        successors.setdefault(a, []).append(b)
    for name in expected:
        if name == "human_review":
            continue
        succ = successors.get(name, [])
        if len(succ) != 1:
            print(f"SELFTEST: FAIL — node {name!r} has {len(succ)} successors")
            all_ok = False
    if all_ok:
        print("SELFTEST: PASS")
        return EXIT_OK
    print("SELFTEST: FAIL")
    return EXIT_ERROR


def _print_summary(payload: dict[str, Any], agent_log: dict[str, Any]) -> None:
    report = payload["report"]
    print("SinceAI P8 — multi-agent layer")
    print(f"  agents:    {payload.get('agents', '')}")
    print(f"  mode:      {payload['mode']}")
    print(f"  decision:  {payload['decision']}")
    print(f"  thread_id: {payload['thread_id']}")
    print(f"  hetu_join:  {report.get('hetu_join')}")
    print(f"  phone_join: {report.get('phone_join')}")
    for name, entry in sorted(agent_log.items()):
        line = f"  {name}: {entry.get('status')}"
        dropped = entry.get("dropped") or 0
        if dropped:
            line += f" dropped={dropped}"
        print(line)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P8 multi-agent advisory layer")
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
    parser.add_argument("--agents", choices=("on", "off", "auto"), default="auto")
    parser.add_argument(
        "--llm-stub",
        action="store_true",
        help="Deterministic canned responses; no network, no key",
    )
    parser.add_argument(
        "--enable-a3",
        action="store_true",
        help="Wire the redact/discover stubs (A3 readiness; no free text is sent)",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Run the AR-4 contract self-test and exit; no network, no key",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.selftest:
        return _run_selftest()

    enabled, label = _resolve_agents(args)
    if label == "ERROR":
        print(
            "error: --agents on requires GROQ_API_KEY "
            "(use --llm-stub for an offline run, or --agents off)",
            file=sys.stderr,
        )
        return EXIT_ERROR

    thread_id = args.thread_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    try:
        health_csv, finance_csv = _resolve_csvs(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if not args.raw_pack:
            print("hint: run bash scripts/final/run_protect.sh --init-key first", file=sys.stderr)
        return EXIT_ERROR
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    column_map = dict(RAW_COLUMN_MAP if args.raw_pack else PROTECTED_COLUMN_MAP)
    checkpointer = _StrippingCheckpointer(FileCheckpointer(args.checkpoint_dir))
    graph = build_graph(
        checkpointer, agents_enabled=enabled, enable_a3=bool(args.enable_a3)
    )
    config = {"configurable": {"thread_id": thread_id}}

    groq_config = GroqConfig.from_env(stub=args.llm_stub) if enabled else None
    if enabled and groq_config:
        provider_line = json.dumps(groq_config.redacted(), ensure_ascii=False)
    else:
        provider_line = "(disabled)"

    print("SinceAI P8 — multi-agent layer")
    print(f"  agents:   {label}")
    print(f"  provider: {provider_line}")

    initial_state: dict[str, Any] = {
        "mode": args.mode,
        "health_csv": str(health_csv),
        "finance_csv": str(finance_csv),
        "column_map": column_map,
        "report": {},
        "review_payload": {},
        "decision": "pending",
        "thread_id": thread_id,
        "agents_enabled": enabled,
        "enable_a3": bool(args.enable_a3),
        "raw_pack": bool(args.raw_pack),
        "pack_root": str(args.pack_root.resolve()),
        "clean_root": str(args.clean_root.resolve()),
        "selected_specialists": [],
        "agent_log": {},
        "brief": None,
    }
    if enabled and groq_config:
        initial_state["_client"] = GroqClient(groq_config)

    try:
        if args.mode == "advisory" and args.resume:
            final = graph.invoke(Command(resume=args.resume), config=config)
        else:
            final = graph.invoke(initial_state, config=config)
    except Interrupt:
        out_path = args.out_dir / f"{thread_id}.agents.json"
        try:
            ckpt = checkpointer.load(thread_id) or {}
            ckpt_state = _strip_runtime(ckpt.get("state") or {})
            payload = {
                "thread_id": thread_id,
                "mode": args.mode,
                "agents": label,
                "agents_enabled": enabled,
                "decision": "pending",
                "paths": {
                    "health_csv": str(health_csv.resolve()),
                    "finance_csv": str(finance_csv.resolve()),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "report": ckpt_state.get("report") or {},
                "agent_log": ckpt_state.get("agent_log") or {},
            }
            _refuse_resources(out_path)
            _refuse_clean_data(out_path)
            _write_report(payload, out_path)
        except (OSError, ValueError, ContractViolation) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR
        print("PAUSED — re-run with --resume accept|reject")
        _print_summary(payload, payload.get("agent_log") or {})
        return EXIT_PAUSED
    except ContractViolation as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except (ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    final_clean = _strip_runtime(final)
    agent_log = final_clean.get("agent_log") or {}
    cand_hash = _candidate_hash(health_csv, finance_csv)
    payload = {
        "thread_id": thread_id,
        "mode": args.mode,
        "agents": label,
        "agents_enabled": enabled,
        "provider": groq_config.redacted() if groq_config else None,
        "prompt_version": PROMPT_VERSION,
        "candidate_hash": cand_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paths": {
            "health_csv": str(health_csv.resolve()),
            "finance_csv": str(finance_csv.resolve()),
        },
        "decision": final_clean.get("decision", "pending"),
        "report": final_clean.get("report") or {},
        "agent_log": agent_log,
        "brief": final_clean.get("brief"),
        "selected_specialists": final_clean.get("selected_specialists") or [],
    }

    out_path = args.out_dir / f"{thread_id}.agents.json"
    try:
        _refuse_resources(out_path)
        _refuse_clean_data(out_path)
        _write_report(payload, out_path)
    except (OSError, ValueError, ContractViolation) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    _print_summary(payload, agent_log)
    print(f"  wrote: {out_path}")
    return _exit_code(args.mode, payload["decision"], payload["report"])


if __name__ == "__main__":
    sys.exit(main())
