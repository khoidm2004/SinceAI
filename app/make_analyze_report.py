#!/usr/bin/env python3
"""Gather raw vs protected evidence and write a self-contained HTML report.

Reusable entry: ``bash scripts/final/run_analyze.sh`` → ``analyze/index.html``.
"""
from __future__ import annotations

from python_version import require_python

require_python()

import argparse
import csv
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from attack_sim import simulate_attack  # noqa: E402
from measure_baseline import DEMO_HETU  # noqa: E402
from normalize import normalize_hetu  # noqa: E402
from pet_pipeline import TOKENISE_IDENTIFIERS  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACK_ROOT = (
    REPO_ROOT
    / "resources"
    / "TRUSTED_SinceAI2026_FINAL"
    / "TRUSTED_PETS_PROVING_GROUND_2026"
)
DEFAULT_CLEAN_ROOT = REPO_ROOT / "clean_data"
DEFAULT_OUT_DIR = REPO_ROOT / "analyze"

HEALTH_REL = Path("data/health/ed_visits.csv")
FINANCE_REL = Path("data/finance/customers.csv")
HEALTH_CLEAN = Path("health__HEALTH-S1/ed_visits.csv")
FINANCE_CLEAN = Path("finance__FIN-S2/customers.csv")
HEALTH_ROWMAP = Path("health__HEALTH-S1/rowmap_ed_visits.csv")
FINANCE_ROWMAP = Path("finance__FIN-S2/rowmap_customers.csv")
HEALTH_SCORECARD = Path("health__HEALTH-S1/scorecard.json")
FINANCE_SCORECARD = Path("finance__FIN-S2/scorecard.json")

# EVALUATION.md risk-component glossary (shown next to scorecard numbers).
RISK_GLOSSARY = {
    "direct identifiers retained": (
        "Share of catalogued direct-identifier values that still appear verbatim."
    ),
    "hashed ids reversible": (
        "Share of hashed values recovered by unsalted MD5 / SHA-1 / SHA-256 "
        "dictionary attack."
    ),
    "records with k<5": (
        "Share of rows in equivalence classes smaller than 5 on kept quasi-identifiers."
    ),
    "linkage re-identification": (
        "Worst re-identification or attribute-inference rate over "
        "metadata/attack_specs.json attacks."
    ),
    "free-text identifier leakage": (
        "Share of gold PII spans whose value survives in released free text."
    ),
    "trajectory unicity": (
        "Share of subjects singled out by a few known (place, hour) points."
    ),
    "synthetic": (
        "Distance to closest record / membership-inference advantage vs holdout."
    ),
}


def _e(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _load_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else None


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return cols, rows


def _find_row_by_hetu(
    path: Path, hetu_col: str, target: str
) -> tuple[Optional[int], Optional[dict[str, str]]]:
    want = normalize_hetu(target)
    with open(path, encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if normalize_hetu(row.get(hetu_col)) == want:
                return i, dict(row)
    return None, None


def _load_rowmap(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    if not path.is_file():
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            oid = (row.get("original_record_id") or "").strip()
            try:
                idx = int(row.get("protected_row") or "")
            except ValueError:
                continue
            if oid:
                out[oid] = idx
    return out


def _row_at(path: Path, index: int) -> Optional[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if i == index:
                return dict(row)
    return None


def _classify_field(
    col: str,
    raw_val: Optional[str],
    prot_val: Optional[str],
    *,
    in_protected: bool,
    tokenise_cols: set[str],
) -> str:
    if not in_protected:
        return "dropped"
    if col in tokenise_cols:
        return "tokenised"
    rv = "" if raw_val is None else str(raw_val)
    pv = "" if prot_val is None else str(prot_val)
    if rv != pv:
        return "generalised"
    return "unchanged"


def _pair_release(
    *,
    label: str,
    scenario_id: str,
    dataset: str,
    raw_path: Path,
    clean_path: Path,
    rowmap_path: Path,
    hetu_col: str,
    record_id_col: str,
    demo_hetu: str,
) -> dict[str, Any]:
    raw_idx, raw_row = _find_row_by_hetu(raw_path, hetu_col, demo_hetu)
    raw_cols, _ = _read_csv_rows(raw_path) if raw_path.is_file() else ([], [])
    prot_cols, _ = _read_csv_rows(clean_path) if clean_path.is_file() else ([], [])
    tokenise_cols = TOKENISE_IDENTIFIERS.get((dataset, scenario_id), set())

    prot_row: Optional[dict[str, str]] = None
    prot_idx: Optional[int] = None
    if raw_row is not None and clean_path.is_file():
        oid = str(raw_row.get(record_id_col) or "")
        rowmap = _load_rowmap(rowmap_path)
        if oid in rowmap:
            prot_idx = rowmap[oid]
            prot_row = _row_at(clean_path, prot_idx)

    fields: list[dict[str, Any]] = []
    for col in raw_cols:
        in_prot = col in prot_cols
        rv = None if raw_row is None else raw_row.get(col)
        pv = None if (prot_row is None or not in_prot) else prot_row.get(col)
        fields.append(
            {
                "column": col,
                "raw": rv,
                "protected": pv if in_prot else None,
                "action": _classify_field(
                    col,
                    rv,
                    pv,
                    in_protected=in_prot,
                    tokenise_cols=tokenise_cols,
                ),
            }
        )

    return {
        "label": label,
        "scenario_id": scenario_id,
        "dataset": dataset,
        "raw_path": str(raw_path),
        "clean_path": str(clean_path),
        "raw_columns": raw_cols,
        "protected_columns": prot_cols,
        "raw_column_count": len(raw_cols),
        "protected_column_count": len(prot_cols),
        "dropped_columns": [c for c in raw_cols if c not in prot_cols],
        "tokenise_columns": sorted(tokenise_cols),
        "demo_hetu": demo_hetu,
        "raw_row_index": raw_idx,
        "protected_row_index": prot_idx,
        "record_id": None if raw_row is None else raw_row.get(record_id_col),
        "fields": fields,
        "found": raw_row is not None and prot_row is not None,
    }


def _scorecard_view(path: Path, scenario_id: str) -> dict[str, Any]:
    data = _load_json(path)
    if data is None:
        return {
            "scenario_id": scenario_id,
            "path": str(path),
            "available": False,
            "summary": None,
            "risk_components": [],
            "utility_tasks": [],
        }

    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    risks_raw = data.get("risk_components") or {}
    risks: list[dict[str, Any]] = []
    if isinstance(risks_raw, dict):
        for name, value in risks_raw.items():
            gloss_key = name.split(": ", 1)[-1] if ": " in name else name
            gloss = next(
                (v for k, v in RISK_GLOSSARY.items() if k in gloss_key.lower() or gloss_key.lower() in k),
                RISK_GLOSSARY.get(gloss_key, "See pack docs/EVALUATION.md."),
            )
            risks.append({"name": name, "value": value, "glossary": gloss})

    tasks: list[dict[str, Any]] = []
    util = data.get("utility")
    if isinstance(util, list):
        for t in util:
            if not isinstance(t, dict):
                continue
            score = t.get("score")
            tasks.append(
                {
                    "id": t.get("id"),
                    "description": t.get("description"),
                    "required": bool(t.get("required")),
                    "score": score,
                    "metric": t.get("metric"),
                    "answerable": score is not None,
                }
            )

    return {
        "scenario_id": scenario_id,
        "path": str(path),
        "available": True,
        "dataset": data.get("dataset"),
        "tool": data.get("tool"),
        "summary": {
            "privacy": summary.get("privacy"),
            "utility": summary.get("utility"),
            "composite": summary.get("composite"),
            "label": summary.get("label"),
            "method": summary.get("method"),
        },
        "risk_components": risks,
        "utility_tasks": tasks,
    }


def gather(
    *,
    pack_root: Path,
    clean_root: Path,
    demo_hetu: str,
) -> dict[str, Any]:
    pack_root = pack_root.resolve()
    clean_root = clean_root.resolve()

    health = _pair_release(
        label="HEALTH-S1 · ed_visits",
        scenario_id="HEALTH-S1",
        dataset="health",
        raw_path=pack_root / HEALTH_REL,
        clean_path=clean_root / HEALTH_CLEAN,
        rowmap_path=clean_root / HEALTH_ROWMAP,
        hetu_col="patient_hetu",
        record_id_col="visit_id",
        demo_hetu=demo_hetu,
    )
    finance = _pair_release(
        label="FIN-S2 · customers",
        scenario_id="FIN-S2",
        dataset="finance",
        raw_path=pack_root / FINANCE_REL,
        clean_path=clean_root / FINANCE_CLEAN,
        rowmap_path=clean_root / FINANCE_ROWMAP,
        hetu_col="hetu",
        record_id_col="customer_id",
        demo_hetu=demo_hetu,
    )

    before = simulate_attack(
        pack_root / HEALTH_REL,
        pack_root / FINANCE_REL,
        health_hetu_col="patient_hetu",
        finance_hetu_col="hetu",
        health_phone_col="phone",
        finance_phone_col="phone",
        sample_limit=0,
    )
    after = simulate_attack(
        clean_root / HEALTH_CLEAN,
        clean_root / FINANCE_CLEAN,
        health_hetu_col="patient_hetu",
        finance_hetu_col="hetu",
        health_phone_col="phone",
        finance_phone_col="phone",
        sample_limit=0,
    )
    mosaic = _load_json(clean_root / "mosaic_check.json")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "demo_person": "P013174",
        "demo_hetu": demo_hetu,
        "pack_root": str(pack_root),
        "clean_root": str(clean_root),
        "evaluation_ref": (
            "resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026/"
            "docs/EVALUATION.md"
        ),
        "releases": [health, finance],
        "joins": {
            "before_protect": {
                "hetu_join": before["hetu_join"],
                "phone_join": before["phone_join"],
                "label": "Unprotected pack data/",
            },
            "after_protect": {
                "hetu_join": after["hetu_join"],
                "phone_join": after["phone_join"],
                "label": "Protected clean_data/",
            },
            "baseline_lock": {"hetu": 1622, "phone": 1484},
            "mosaic_check": mosaic,
        },
        "scorecards": [
            _scorecard_view(clean_root / HEALTH_SCORECARD, "HEALTH-S1"),
            _scorecard_view(clean_root / FINANCE_SCORECARD, "FIN-S2"),
        ],
        "evaluation_notes": {
            "privacy_formula": (
                "privacy = 1 − (0.5 × worst risk + 0.5 × mean risk)"
            ),
            "utility_formula": (
                "utility = mean of scenario task scores "
                "(required but unanswerable → 0)"
            ),
            "composite_formula": (
                "composite = weighted harmonic mean "
                "(privacy weight 30, utility weight 25)"
            ),
            "disclaimer": (
                "pets-eval scorecard is a self-assessment tool; official judging "
                "follows the Since AI evaluation process (EVALUATION.md)."
            ),
        },
    }


def _pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return _e(value)


def _bar(value: int, maximum: int, *, css: str) -> str:
    width = 0 if maximum <= 0 else min(100, round(100 * value / maximum))
    return (
        f'<div class="bar"><div class="bar-fill {css}" style="width:{width}%"></div>'
        f'<span class="bar-label">{_e(value)}</span></div>'
    )


def _action_badge(action: str) -> str:
    return f'<span class="badge badge-{_e(action)}">{_e(action)}</span>'


def _render_release(rel: dict[str, Any]) -> str:
    parts = [
        f'<section class="card release">',
        f'<h3>{_e(rel["label"])}</h3>',
        f'<p class="meta">Columns <strong>{rel["raw_column_count"]}</strong> → '
        f'<strong>{rel["protected_column_count"]}</strong>',
    ]
    if rel["dropped_columns"]:
        parts.append(
            f' · dropped: {", ".join(_e(c) for c in rel["dropped_columns"])}'
        )
    if rel["tokenise_columns"]:
        parts.append(
            f' · tokenised: {", ".join(_e(c) for c in rel["tokenise_columns"])}'
        )
    parts.append("</p>")

    if not rel["found"]:
        parts.append(
            '<p class="warn">Could not align the demo HETU via rowmap — '
            "run <code>run_protect.sh --init-key</code> first.</p></section>"
        )
        return "".join(parts)

    parts.append(
        f'<p class="meta">Demo row · raw index {rel["raw_row_index"]} · '
        f'protected index {rel["protected_row_index"]} · '
        f'id {_e(rel["record_id"])}</p>'
    )
    parts.append(
        '<table class="cmp"><thead><tr>'
        "<th>Column</th><th>Original</th><th>Protected</th><th>Action</th>"
        "</tr></thead><tbody>"
    )
    for field in rel["fields"]:
        action = field["action"]
        row_cls = f"row-{action}"
        prot_display = "—" if action == "dropped" else field["protected"]
        parts.append(
            f'<tr class="{row_cls}">'
            f'<td><code>{_e(field["column"])}</code></td>'
            f'<td class="mono">{_e(field["raw"])}</td>'
            f'<td class="mono">{_e(prot_display)}</td>'
            f"<td>{_action_badge(action)}</td>"
            f"</tr>"
        )
    parts.append("</tbody></table></section>")
    return "".join(parts)


def _render_scorecard(sc: dict[str, Any]) -> str:
    if not sc["available"]:
        return (
            f'<section class="card scorecard">'
            f'<h3>{_e(sc["scenario_id"])} scorecard</h3>'
            f'<p class="warn">Missing {_e(sc["path"])}. '
            f"Run <code>bash scripts/final/run_scorecard.sh</code>.</p>"
            f"</section>"
        )
    s = sc["summary"] or {}
    parts = [
        f'<section class="card scorecard">',
        f'<h3>{_e(sc["scenario_id"])} · {_e(sc.get("dataset"))}</h3>',
        f'<p class="meta">{_e(sc.get("tool"))} — {_e(s.get("label"))}</p>',
        '<div class="score-grid">',
        f'<div class="score"><span class="score-n">{_pct(s.get("privacy"))}</span>'
        f"<span>Privacy</span></div>",
        f'<div class="score"><span class="score-n">{_pct(s.get("utility"))}</span>'
        f"<span>Utility</span></div>",
        f'<div class="score"><span class="score-n">{_pct(s.get("composite"))}</span>'
        f"<span>Composite</span></div>",
        "</div>",
        f'<p class="method">{_e(s.get("method"))}</p>',
        "<h4>Privacy risk components "
        "<span class=\"hint\">0 = no risk, 1 = maximal</span></h4>",
        '<table class="cmp"><thead><tr><th>Component</th><th>Risk</th>'
        "<th>EVALUATION.md</th></tr></thead><tbody>",
    ]
    for risk in sc["risk_components"]:
        parts.append(
            "<tr>"
            f"<td>{_e(risk['name'])}</td>"
            f'<td class="mono">{_e(risk["value"])}</td>'
            f'<td class="gloss">{_e(risk["glossary"])}</td>'
            "</tr>"
        )
    parts.append("</tbody></table>")
    parts.append("<h4>Utility tasks</h4>")
    parts.append(
        '<table class="cmp"><thead><tr><th>ID</th><th>Task</th>'
        "<th>Score</th><th>Metric</th></tr></thead><tbody>"
    )
    for task in sc["utility_tasks"]:
        score = "n/a" if task["score"] is None else f"{float(task['score']):.3f}"
        cls = "row-unchanged" if task["answerable"] else "row-dropped"
        parts.append(
            f'<tr class="{cls}">'
            f'<td><code>{_e(task["id"])}</code></td>'
            f'<td>{_e(task["description"])}</td>'
            f'<td class="mono">{_e(score)}</td>'
            f'<td class="gloss">{_e(task["metric"])}</td>'
            "</tr>"
        )
    parts.append("</tbody></table></section>")
    return "".join(parts)


def render_html(payload: dict[str, Any]) -> str:
    joins = payload["joins"]
    before = joins["before_protect"]
    after = joins["after_protect"]
    lock = joins["baseline_lock"]
    mosaic = joins.get("mosaic_check") or {}
    verdict = mosaic.get("verdict", "—")
    notes = payload["evaluation_notes"]
    max_join = max(lock["hetu"], lock["phone"], before["hetu_join"], before["phone_join"], 1)

    release_html = "".join(_render_release(r) for r in payload["releases"])
    score_html = "".join(_render_scorecard(s) for s in payload["scorecards"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SinceAI · protect analysis</title>
<style>
  :root {{
    --bg: #f3efe6;
    --ink: #1c1914;
    --muted: #5c564c;
    --card: #fffdf8;
    --line: #d7d0c2;
    --accent: #0f6a5a;
    --accent-2: #b44a1f;
    --drop: #8b2e2e;
    --token: #1f4d8c;
    --gen: #6b4f1d;
    --ok: #0f6a5a;
    --warn: #8a5a00;
    --mono: "IBM Plex Mono", "SF Mono", ui-monospace, monospace;
    --sans: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
    --display: "Fraunces", "Iowan Old Style", Georgia, serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    color: var(--ink);
    background:
      radial-gradient(1200px 500px at 10% -10%, #e7f2ee 0%, transparent 55%),
      radial-gradient(900px 400px at 100% 0%, #f7e6dc 0%, transparent 50%),
      var(--bg);
    font-family: var(--sans);
    line-height: 1.45;
  }}
  header {{
    padding: 2.5rem 1.5rem 1.5rem;
    max-width: 1100px;
    margin: 0 auto;
  }}
  header h1 {{
    font-family: var(--display);
    font-weight: 560;
    font-size: clamp(1.8rem, 3vw, 2.6rem);
    margin: 0 0 0.4rem;
    letter-spacing: -0.02em;
  }}
  header p {{ margin: 0.25rem 0; color: var(--muted); max-width: 48rem; }}
  .verdict {{
    display: inline-block;
    margin-top: 0.9rem;
    padding: 0.35rem 0.75rem;
    border: 1px solid var(--accent);
    color: var(--accent);
    border-radius: 999px;
    font-size: 0.85rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }}
  main {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 1.5rem 3rem;
    display: grid;
    gap: 1.25rem;
  }}
  .card {{
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 1.1rem 1.2rem 1.3rem;
    box-shadow: 0 1px 0 rgba(28,25,20,0.04);
  }}
  h2, h3, h4 {{ font-family: var(--display); font-weight: 560; margin: 0 0 0.6rem; }}
  h2 {{ font-size: 1.35rem; }}
  h3 {{ font-size: 1.15rem; }}
  h4 {{ font-size: 1rem; margin-top: 1rem; }}
  .meta {{ color: var(--muted); font-size: 0.92rem; margin: 0 0 0.8rem; }}
  .method, .gloss, .hint {{ color: var(--muted); font-size: 0.86rem; }}
  .hint {{ font-weight: 400; }}
  .warn {{ color: var(--warn); }}
  .mono, code {{ font-family: var(--mono); font-size: 0.86em; }}
  .cmp {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.92rem;
  }}
  .cmp th, .cmp td {{
    text-align: left;
    vertical-align: top;
    padding: 0.45rem 0.5rem;
    border-bottom: 1px solid var(--line);
  }}
  .cmp th {{ font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }}
  .row-dropped td {{ background: #f8ecea; }}
  .row-tokenised td {{ background: #eaf1f8; }}
  .row-generalised td {{ background: #f7f1e3; }}
  .badge {{
    display: inline-block;
    padding: 0.12rem 0.45rem;
    border-radius: 999px;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }}
  .badge-dropped {{ background: #f0d4d1; color: var(--drop); }}
  .badge-tokenised {{ background: #d7e5f5; color: var(--token); }}
  .badge-generalised {{ background: #efe2c4; color: var(--gen); }}
  .badge-unchanged {{ background: #e4eee9; color: var(--ok); }}
  .join-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }}
  @media (max-width: 800px) {{ .join-grid {{ grid-template-columns: 1fr; }} }}
  .bar {{
    position: relative;
    height: 1.6rem;
    background: #ebe5da;
    border-radius: 6px;
    overflow: hidden;
    margin: 0.35rem 0 0.7rem;
  }}
  .bar-fill {{ height: 100%; }}
  .bar-fill.before {{ background: var(--accent-2); }}
  .bar-fill.after {{ background: var(--accent); }}
  .bar-label {{
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    padding-left: 0.55rem;
    font-family: var(--mono);
    font-size: 0.85rem;
    color: var(--ink);
  }}
  .score-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
    margin: 0.6rem 0 0.8rem;
  }}
  .score {{
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.7rem;
    text-align: center;
  }}
  .score-n {{
    display: block;
    font-family: var(--display);
    font-size: 1.55rem;
    color: var(--accent);
  }}
  footer {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 1.5rem 2.5rem;
    color: var(--muted);
    font-size: 0.85rem;
  }}
  a {{ color: var(--accent); }}
</style>
</head>
<body>
<header>
  <h1>SinceAI protect analysis</h1>
  <p>
    Side-by-side original vs protected releases for worked-example person
    <strong>{_e(payload["demo_person"])}</strong>
    (HETU <code>{_e(payload["demo_hetu"])}</code>), mosaic joins before/after
    protect, and pets-eval scorecards framed by
    <code>docs/EVALUATION.md</code>.
  </p>
  <p class="meta">Generated {_e(payload["generated_at"])}</p>
  <div class="verdict">Mosaic gate · {_e(verdict)}</div>
</header>
<main>
  <section class="card">
    <h2>1 · Example row transform</h2>
    <p class="meta">
      One aligned record from each release (via <code>rowmap_*.csv</code>).
      Highlighted rows show what protect changed.
    </p>
    {release_html}
  </section>

  <section class="card">
    <h2>2 · Cross-release joins (Attack A)</h2>
    <p class="meta">
      Same instrument as the mosaic gate. Baseline lock on raw data:
      HETU <strong>{lock["hetu"]}</strong> / phone <strong>{lock["phone"]}</strong>.
      After protect both joins must be <strong>0</strong>.
    </p>
    <div class="join-grid">
      <div>
        <h3>Before protect</h3>
        <p class="meta">{_e(before["label"])}</p>
        <div>HETU ∩</div>
        {_bar(before["hetu_join"], max_join, css="before")}
        <div>Phone ∩</div>
        {_bar(before["phone_join"], max_join, css="before")}
      </div>
      <div>
        <h3>After protect</h3>
        <p class="meta">{_e(after["label"])}</p>
        <div>HETU ∩</div>
        {_bar(after["hetu_join"], max_join, css="after")}
        <div>Phone ∩</div>
        {_bar(after["phone_join"], max_join, css="after")}
      </div>
    </div>
  </section>

  <section class="card">
    <h2>3 · pets-eval scorecards</h2>
    <p class="meta">{_e(notes["disclaimer"])}</p>
    <ul class="meta">
      <li>{_e(notes["privacy_formula"])}</li>
      <li>{_e(notes["utility_formula"])}</li>
      <li>{_e(notes["composite_formula"])}</li>
    </ul>
    {score_html}
  </section>
</main>
<footer>
  Source pack {_e(payload["pack_root"])}<br/>
  Protected {_e(payload["clean_root"])}<br/>
  Reference {_e(payload["evaluation_ref"])}<br/>
  Re-run with <code>bash scripts/final/run_analyze.sh</code>
</footer>
</body>
</html>
"""


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build analyze/ HTML comparing raw vs protected releases"
    )
    p.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    p.add_argument("--clean-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--hetu", default=DEMO_HETU, help=f"Demo HETU (default {DEMO_HETU})")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not (args.pack_root / HEALTH_REL).is_file():
        print(f"error: missing raw pack under {args.pack_root}", file=sys.stderr)
        return 2
    if not (args.clean_root / FINANCE_CLEAN).is_file():
        print(
            f"error: missing protected releases under {args.clean_root} "
            "(run bash scripts/final/run_protect.sh --init-key)",
            file=sys.stderr,
        )
        return 2

    payload = gather(
        pack_root=args.pack_root,
        clean_root=args.clean_root,
        demo_hetu=args.hetu,
    )
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "index.html"
    json_path = out_dir / "snapshot.json"
    html_path.write_text(render_html(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    joins = payload["joins"]
    print("SinceAI analyze report")
    print(f"  demo:     {payload['demo_person']} / {payload['demo_hetu']}")
    print(
        f"  joins:    before HETU={joins['before_protect']['hetu_join']} "
        f"phone={joins['before_protect']['phone_join']} → "
        f"after HETU={joins['after_protect']['hetu_join']} "
        f"phone={joins['after_protect']['phone_join']}"
    )
    for sc in payload["scorecards"]:
        if sc["available"]:
            s = sc["summary"] or {}
            print(
                f"  scorecard {sc['scenario_id']}: "
                f"privacy={s.get('privacy')} utility={s.get('utility')} "
                f"composite={s.get('composite')}"
            )
        else:
            print(f"  scorecard {sc['scenario_id']}: missing")
    print(f"  wrote:    {html_path}")
    print(f"  snapshot: {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
