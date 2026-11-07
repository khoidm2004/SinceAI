"""P2 two-node agent graph: attack_sim → human_review."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_runtime import END, StateGraph, interrupt
from attack_sim import simulate_attack


def attack_sim_node(state: dict) -> dict:
    cm = state["column_map"]
    report = simulate_attack(
        Path(state["health_csv"]),
        Path(state["finance_csv"]),
        health_hetu_col=cm["health_hetu_col"],
        finance_hetu_col=cm["finance_hetu_col"],
        health_phone_col=cm.get("health_phone_col"),
        finance_phone_col=cm.get("finance_phone_col"),
    )
    state["report"] = report
    state["review_payload"] = {
        "hetu_join": report["hetu_join"],
        "phone_join": report["phone_join"],
        "samples": report["samples"],
        "proposals": report["proposals"],
        "mode": state["mode"],
    }
    state.setdefault("decision", "pending")
    return state


def human_review_node(state: dict) -> dict:
    if state.get("mode") == "shadow":
        state["decision"] = "shadow_logged"
        return state

    resume = state.get("_resume")
    if resume is None:
        interrupt(state["review_payload"])

    token = str(resume).strip().lower()
    if token in ("accept", "accept-all"):
        state["decision"] = "accepted"
    elif resume and token not in ("reject", "false", "0", "no"):
        state["decision"] = "accepted"
    else:
        state["decision"] = "rejected"
    return state


def build_graph(checkpointer: Any) -> Any:
    graph = StateGraph()
    graph.add_node("attack_sim", attack_sim_node)
    graph.add_node("human_review", human_review_node)
    graph.add_edge("attack_sim", "human_review")
    graph.add_edge("human_review", END)
    graph.set_entry_point("attack_sim")
    graph.set_finish_point("human_review")
    return graph.compile(checkpointer=checkpointer)
