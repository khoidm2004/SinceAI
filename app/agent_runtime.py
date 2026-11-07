"""Stdlib LangGraph-shaped shim for Python 3.9.

Swap for real ``langgraph`` when on Python ≥3.10; do not grow this into a framework.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

END = "__end__"


class Interrupt(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value
        super().__init__(repr(value))


def interrupt(value: Any) -> Any:
    raise Interrupt(value)


class Command:
    def __init__(self, *, resume: Any) -> None:
        self.resume = resume


class InMemorySaver:
    def __init__(self) -> None:
        self._store: Dict[str, dict] = {}

    def save(self, thread_id: str, data: dict) -> None:
        self._store[thread_id] = data

    def load(self, thread_id: str) -> Optional[dict]:
        return self._store.get(thread_id)


class FileCheckpointer:
    """Persist checkpoints as JSON under a directory (one file per thread_id)."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, thread_id: str) -> Path:
        safe = thread_id.replace("/", "_").replace("\\", "_")
        return self.directory / f"{safe}.json"

    def save(self, thread_id: str, data: dict) -> None:
        with open(self._path(thread_id), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    def load(self, thread_id: str) -> Optional[dict]:
        p = self._path(thread_id)
        if not p.is_file():
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)


class CompiledGraph:
    def __init__(self, graph: "StateGraph", checkpointer: Any) -> None:
        self._graph = graph
        self._checkpointer = checkpointer

    def _thread_id(self, config: Optional[dict]) -> str:
        if config and "configurable" in config:
            return str(config["configurable"].get("thread_id", "default"))
        return "default"

    def _successors(self, node: str) -> List[str]:
        return [b for a, b in self._graph.edges if a == node]

    def _run_linear(self, state: dict, start: str) -> dict:
        cur = start
        while cur and cur != END:
            fn = self._graph.nodes[cur]
            try:
                state = fn(state)
            except Interrupt:
                self._graph._last_node = cur
                raise
            nxt = self._successors(cur)
            cur = nxt[0] if nxt else END
        return state

    def invoke(self, input: Any, config: Optional[dict] = None) -> dict:
        tid = self._thread_id(config)
        if isinstance(input, Command):
            ckpt = self._checkpointer.load(tid)
            if ckpt is None:
                raise ValueError(f"no checkpoint for thread_id={tid!r}")
            state = dict(ckpt["state"])
            state["_resume"] = input.resume
            pending = ckpt.get("pending_node", self._graph.finish)
            try:
                return self._run_linear(state, pending)
            finally:
                state.pop("_resume", None)

        state = dict(input)
        try:
            return self._run_linear(state, self._graph.entry)
        except Interrupt as exc:
            pending = getattr(self._graph, "_last_node", self._graph.finish)
            self._checkpointer.save(
                tid,
                {
                    "state": state,
                    "pending_node": pending,
                    "interrupt_value": exc.value,
                },
            )
            raise


class StateGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, Callable[[dict], dict]] = {}
        self.edges: List[tuple[str, str]] = []
        self.entry: str = ""
        self.finish: str = ""
        self._last_node: str = ""

    def add_node(self, name: str, fn: Callable[[dict], dict]) -> None:
        self.nodes[name] = fn

    def add_edge(self, a: str, b: str) -> None:
        self.edges.append((a, b))

    def set_entry_point(self, name: str) -> None:
        self.entry = name

    def set_finish_point(self, name: str) -> None:
        self.finish = name

    def compile(self, *, checkpointer: Any) -> CompiledGraph:
        return CompiledGraph(self, checkpointer)
