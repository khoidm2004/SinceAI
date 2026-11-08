#!/usr/bin/env python3
"""Compare a generated synthetic test pack with the official TrustED data for the same scenarios.

Scenario tables: HEALTH-S1 (health/ed_visits, lab_results, clinical_notes) and FIN-S2 (finance/customers, cards,
card_transactions). Output: <run>/reports/comparison_official.html (+ .json), aggregates only.

What is compared per table: row count, header/column order, catalog role; per column: empty share, distinct ratio,
and - by kind - categorical distribution (total-variation distance, TVD), numeric quantiles + Kolmogorov-Smirnov
statistic, temporal range + month/hour distributions, identifier/free-text format shapes (digits -> 9, letters ->
A/a; values themselves are never shown) and lengths. Plus relationships (visits per patient, labs/notes per visit,
cards per customer, transactions per card), key rates (readmission, fraud, CRP share) and the cross-domain
HETU / phone overlap (absolute and relative to the finance customers).

Category values are shown only for low-cardinality columns that are not identifiers or free text.
The official pack is only read. Output is refused under resources/, clean_data/, keys/.
"""
from __future__ import annotations

from python_version import require_python

require_python()
import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalize_hetu, normalize_phone  # noqa: E402
from synth_common import OFFICIAL_PACK, RELEASE_TABLES, refuse_forbidden, run_dirs, sha256_file, utf8_stdout, write_json  # noqa: E402

E = lambda s: html.escape("" if s is None else str(s), quote=True)  # noqa: E731
HIDE_VALUES_ROLES = {"direct_identifier", "technical_identifier", "record_key", "free_text"}
HIDE_VALUE_COLUMNS = {"merchant_name", "employer", "attending_physician_id", "author_staff_id", "ambulance_unit"}
MAX_CATS = 40


def load(root: Path, ds: str, tb: str) -> pd.DataFrame:
    return pd.read_csv(root / "data" / ds / f"{tb}.csv", dtype=str, keep_default_na=False)


def catalog(root: Path) -> Dict[tuple, Dict[str, str]]:
    c = pd.read_csv(root / "metadata" / "field_catalog.csv", dtype=str, keep_default_na=False)
    return {(r.dataset, r.table, r.column): {"role": r.privacy_role, "kind": r.data_kind, "subtype": r.subtype} for r in c.itertuples()}


def shape(v: str) -> str:
    s = re.sub(r"[0-9]", "9", v)
    s = re.sub(r"[A-ZÅÄÖ]", "A", s)
    s = re.sub(r"[a-zåäöü]", "a", s)
    return re.sub(r"(a)\1{2,}", "a+", re.sub(r"(A)\1{2,}", "A+", re.sub(r"(9)\1{3,}", "9+", s)))


def tvd(p: pd.Series, q: pd.Series) -> float:
    idx = p.index.union(q.index)
    return float(0.5 * (p.reindex(idx, fill_value=0) - q.reindex(idx, fill_value=0)).abs().sum())


def ks(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    if len(a) == 0 or len(b) == 0:
        return None
    a, b = np.sort(a), np.sort(b)
    grid = np.concatenate([a, b])
    return float(np.max(np.abs(np.searchsorted(a, grid, side="right") / len(a) - np.searchsorted(b, grid, side="right") / len(b))))


def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.replace("<", "", regex=False), errors="coerce")


def to_dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.where(s != ""), errors="coerce", format="mixed")


def col_profile(o: pd.Series, s: pd.Series, meta: Dict[str, str], col: str) -> Dict[str, Any]:
    role, kind = meta.get("role", "unclassified"), meta.get("kind", "")
    res: Dict[str, Any] = {"column": col, "role": role, "subtype": meta.get("subtype", ""),
                           "empty": [round(float((o == "").mean()), 4), round(float((s == "").mean()), 4)],
                           "distinct_ratio": [round(o[o != ""].nunique() / max(1, (o != "").sum()), 4), round(s[s != ""].nunique() / max(1, (s != "").sum()), 4)]}
    on, sn = o[o != ""], s[s != ""]
    numeric_share = float(pd.to_numeric(on.head(5000).str.replace("<", "", regex=False), errors="coerce").notna().mean()) if len(on) else 0
    if role in ("direct_identifier", "technical_identifier", "record_key") or (role == "free_text"):
        so = on.map(shape).value_counts(normalize=True).head(4)
        ss = sn.map(shape).value_counts(normalize=True).head(4)
        res["kind"] = "identifier" if role != "free_text" else "free_text"
        res["shapes"] = [{k: round(float(v), 3) for k, v in so.items()}, {k: round(float(v), 3) for k, v in ss.items()}] if role != "free_text" else None
        res["length"] = [[int(on.str.len().quantile(q)) if len(on) else None for q in (0.05, 0.5, 0.95)], [int(sn.str.len().quantile(q)) if len(sn) else None for q in (0.05, 0.5, 0.95)]]
        if role != "free_text":
            res["shape_tvd"] = round(tvd(on.map(shape).value_counts(normalize=True), sn.map(shape).value_counts(normalize=True)), 3)
        return res
    if kind == "temporal" or meta.get("subtype") in ("TIMESTAMP", "DATE", "BIRTH_DATE"):
        do, dsn = to_dt(o), to_dt(s)
        res["kind"] = "temporal"
        res["range"] = [[str(do.min())[:19], str(do.max())[:19]], [str(dsn.min())[:19], str(dsn.max())[:19]]]
        mo, ms = do.dt.month.value_counts(normalize=True), dsn.dt.month.value_counts(normalize=True)
        res["month_tvd"] = round(tvd(mo, ms), 3)
        if meta.get("subtype") == "TIMESTAMP":
            ho, hs = do.dt.hour.value_counts(normalize=True).sort_index(), dsn.dt.hour.value_counts(normalize=True).sort_index()
            res["hour_tvd"] = round(tvd(ho, hs), 3)
            res["hour_dist"] = [[round(float(ho.get(h, 0)), 4) for h in range(24)], [round(float(hs.get(h, 0)), 4) for h in range(24)]]
        res["month_dist"] = [[round(float(mo.get(m, 0)), 4) for m in range(1, 13)], [round(float(ms.get(m, 0)), 4) for m in range(1, 13)]]
        return res
    if numeric_share > 0.95 and on.nunique() > 12:
        a, b = to_num(on).dropna().to_numpy(), to_num(sn).dropna().to_numpy()
        res["kind"] = "numeric"
        res["quantiles"] = [[round(float(np.quantile(x, q)), 2) if len(x) else None for q in (0.05, 0.25, 0.5, 0.75, 0.95)] for x in (a, b)]
        res["mean"] = [round(float(a.mean()), 2) if len(a) else None, round(float(b.mean()), 2) if len(b) else None]
        res["ks"] = None if ks(a, b) is None else round(ks(a, b), 3)
        return res
    po, ps = on.value_counts(normalize=True), sn.value_counts(normalize=True)
    res["kind"] = "categorical"
    res["n_categories"] = [int(po.size), int(ps.size)]
    res["tvd"] = round(tvd(po, ps), 3)
    res["only_official"] = int(len(set(po.index) - set(ps.index)))
    res["only_synthetic"] = int(len(set(ps.index) - set(po.index)))
    if po.size <= MAX_CATS and col not in HIDE_VALUE_COLUMNS and role not in HIDE_VALUES_ROLES:
        cats = list(po.index[:MAX_CATS])
        res["dist"] = {"categories": cats, "official": [round(float(po.get(c, 0)), 4) for c in cats], "synthetic": [round(float(ps.get(c, 0)), 4) for c in cats]}
    return res


def per_group(series: pd.Series) -> Dict[str, Any]:
    c = series.value_counts()
    return {"mean": round(float(c.mean()), 3), "median": float(c.median()), "p95": float(c.quantile(0.95)), "max": int(c.max()), "groups": int(c.size)}


def relationships(T: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    ed, lab, notes, cu, cards, tx = (T[k] for k in ("ed_visits", "lab_results", "clinical_notes", "customers", "cards", "card_transactions"))
    edh = ed[ed["patient_hetu"] != ""]
    r = {
        "visits per patient (by HETU)": per_group(edh["patient_hetu"]),
        "share of visits with labs": round(float(ed["visit_id"].isin(set(lab["visit_id"])).mean()), 4),
        "labs per visit (visits with labs)": per_group(lab["visit_id"]),
        "share of visits with notes": round(float(ed["visit_id"].isin(set(notes["visit_id"])).mean()), 4),
        "notes per visit (visits with notes)": per_group(notes["visit_id"]),
        "share of customers with a card": round(float(cu["customer_id"].isin(set(cards["customer_id"])).mean()), 4),
        "cards per customer (customers with cards)": per_group(cards["customer_id"]),
        "transactions per card": per_group(tx["card_pan"]),
        "lab FK resolves to ed_visits": round(float(lab["visit_id"].isin(set(ed["visit_id"])).mean()), 4),
        "card FK resolves to customers": round(float(cards["customer_id"].isin(set(cu["customer_id"])).mean()), 4),
        "transaction FK resolves to cards": round(float(tx["card_pan"].isin(set(cards["card_pan"])).mean()), 4),
    }
    rates = {
        "readmit_30d rate": round(float(pd.to_numeric(ed["readmit_30d"], errors="coerce").mean()), 4),
        "fraud rate (transactions)": round(float((tx["is_fraud"] == "1").mean()), 5),
        "fraud before 2025-11-01 (count)": int(((tx["is_fraud"] == "1") & (tx["ts"] < "2025-11-01")).sum()),
        "fraud from 2025-11-01 (count)": int(((tx["is_fraud"] == "1") & (tx["ts"] >= "2025-11-01")).sum()),
        "P-CRP share of lab results": round(float((lab["test_code"] == "P-CRP").mean()), 4),
        "closed_fraud share of cards": round(float((cards["status"] == "closed_fraud").mean()), 4),
        "non-resident share of visits": round(float((ed["municipality"] == "non-resident").mean()), 4),
    }
    hh, fh = set(ed["patient_hetu"].map(normalize_hetu)) - {""}, set(cu["hetu"].map(normalize_hetu)) - {""}
    hp, fp = set(ed["phone"].map(normalize_phone)) - {""}, set(cu["phone"].map(normalize_phone)) - {""}
    cross = {"HETU join": len(hh & fh), "phone join": len(hp & fp), "finance customers": len(cu), "distinct patients (HETU)": len(hh),
             "HETU join / finance customers": round(len(hh & fh) / max(1, len(cu)), 4), "phone join / finance customers": round(len(hp & fp) / max(1, len(cu)), 4),
             "phone join / HETU join": round(len(hp & fp) / max(1, len(hh & fh)), 4)}
    return {"relationships": r, "rates": rates, "cross_domain": cross}


def compare(run: Path, official: Path = OFFICIAL_PACK) -> Dict[str, Any]:
    pack = run_dirs(run)["pack"]
    cat = catalog(official)
    out: Dict[str, Any] = {"run": run.name, "official_pack": "resources/TRUSTED_SinceAI2026_FINAL/TRUSTED_PETS_PROVING_GROUND_2026", "tables": {}}
    TO: Dict[str, pd.DataFrame] = {}
    TS: Dict[str, pd.DataFrame] = {}
    for sid, (ds, tables) in RELEASE_TABLES.items():
        for tb, _ in tables:
            o, s = load(official, ds, tb), load(pack, ds, tb)
            TO[tb], TS[tb] = o, s
            cols = [c for c in o.columns if c in s.columns]
            out["tables"][f"{ds}/{tb}"] = {
                "scenario": sid, "rows": [len(o), len(s)], "row_ratio": round(len(s) / max(1, len(o)), 4),
                "header_identical": list(o.columns) == list(s.columns), "columns": [len(o.columns), len(s.columns)],
                "file_sha256": [sha256_file(official / "data" / ds / f"{tb}.csv")[:16], sha256_file(pack / "data" / ds / f"{tb}.csv")[:16]],
                "profiles": [col_profile(o[c], s[c], cat.get((ds, tb, c), {}), c) for c in cols],
            }
            print(f"  compared {ds}/{tb}: official {len(o):,} rows, synthetic {len(s):,} rows")
    out["official"] = relationships(TO)
    out["synthetic"] = relationships(TS)
    # overall similarity summary
    tvds = [(t, p["column"], p["tvd"]) for t, v in out["tables"].items() for p in v["profiles"] if p.get("kind") == "categorical"]
    kss = [(t, p["column"], p["ks"]) for t, v in out["tables"].items() for p in v["profiles"] if p.get("kind") == "numeric" and p.get("ks") is not None]
    out["summary"] = {"categorical_columns": len(tvds), "median_tvd": round(float(np.median([x[2] for x in tvds])), 3) if tvds else None,
                      "numeric_columns": len(kss), "median_ks": round(float(np.median([x[2] for x in kss])), 3) if kss else None,
                      "largest_tvd": sorted(tvds, key=lambda x: -x[2])[:8], "largest_ks": sorted(kss, key=lambda x: -x[2])[:8],
                      "headers_identical": all(v["header_identical"] for v in out["tables"].values())}
    return out


# ------------------------------------------------------------------ HTML
CSS = """:root{color-scheme:light;--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--s1:#2a78d6;--s2:#eb6834;
--good:#006300;--warn:#8a5a00;--bad:#b02a2a;--border:rgba(11,11,11,.1)}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--s1:#3987e5;--s2:#d95926;--good:#0ca30c;--warn:#fab219;--bad:#ec6a6a;--border:rgba(255,255,255,.1)}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--s1:#3987e5;--s2:#d95926;--good:#0ca30c;--warn:#fab219;--bad:#ec6a6a;--border:rgba(255,255,255,.1)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
header,main{max-width:1120px;margin:0 auto;padding:0 16px}header{padding-top:22px}h1{font-size:25px;margin:0 0 4px}h2{font-size:20px;margin:34px 0 8px;padding-top:10px;border-top:1px solid var(--grid)}
h3{font-size:16px;margin:18px 0 6px}.sub,.note{color:var(--ink2)}.note{font-size:13px}nav{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:13px;margin:10px 0}nav a{color:var(--ink2)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 16px;margin:10px 0}.tw{overflow-x:auto;margin:8px 0}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:5px 8px;border-bottom:1px solid var(--grid);text-align:left;vertical-align:top}th{color:var(--ink2);font-weight:600;background:var(--surface)}
.good{color:var(--good)}.warn{color:var(--warn)}.bad{color:var(--bad)}.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}
svg.chart{width:100%;max-width:720px;height:auto;display:block}svg text{fill:var(--ink2);font:11px system-ui,sans-serif}svg .grid{stroke:var(--grid)}svg .axis{stroke:var(--axis)}svg .mark:hover{opacity:.75}
.legend{display:flex;gap:16px;font-size:13px;color:var(--ink2);margin:4px 0}.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
details{margin:6px 0}summary{cursor:pointer;color:var(--ink2)}button.theme{float:right;background:var(--surface);color:var(--ink);border:1px solid var(--border);border-radius:6px;padding:4px 10px;cursor:pointer}"""
LEGEND = '<div class="legend"><span><i style="background:var(--s1)"></i>Official (resources/)</span><span><i style="background:var(--s2)"></i>Synthetic (test_data/)</span></div>'


def table(h: Sequence[str], rows: Sequence[Sequence[Any]], raw: bool = False) -> str:
    return ('<div class="tw"><table><thead><tr>' + "".join(f"<th>{E(x)}</th>" for x in h) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{c if raw else E(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>")


def pairs(cats: Sequence[str], a: Sequence[float], b: Sequence[float], aria: str, width: int = 720, height: int = 220) -> str:
    """Paired share bars (official vs synthetic), 0..max share, <title> tooltips."""
    ml, mr, mt, mb = 44, 8, 12, 58
    pw, ph = width - ml - mr, height - mt - mb
    n = max(1, len(cats))
    gw = pw / n
    bw = max(3.0, min(18.0, (gw * 0.8 - 2) / 2))
    vmax = max([*a, *b, 0.01]) * 1.1
    o = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{E(aria)}">']
    for i in range(5):
        v = vmax * i / 4
        y = mt + ph - ph * v / vmax
        o.append(f'<line class="grid" x1="{ml}" x2="{width - mr}" y1="{y:.1f}" y2="{y:.1f}"/><text x="{ml - 5}" y="{y + 4:.1f}" text-anchor="end">{v * 100:.0f}%</text>')
    for i, c in enumerate(cats):
        x0 = ml + i * gw + (gw - (2 * bw + 2)) / 2
        for j, (val, col, who) in enumerate(((a[i], "var(--s1)", "official"), (b[i], "var(--s2)", "synthetic"))):
            h = ph * val / vmax
            o.append(f'<g class="mark"><title>{E(c)} - {who}: {val * 100:.1f}%</title><rect x="{x0 + j * (bw + 2):.1f}" y="{mt + ph - h:.1f}" width="{bw:.1f}" height="{max(h, 0.8):.1f}" rx="2" fill="{col}"/></g>')
        lab = c if len(c) <= 14 else c[:13] + "…"
        o.append(f'<text transform="translate({ml + i * gw + gw / 2:.1f},{mt + ph + 10}) rotate(40)" text-anchor="start">{E(lab)}</text>')
    o.append(f'<line class="axis" x1="{ml}" x2="{width - mr}" y1="{mt + ph}" y2="{mt + ph}"/></svg>')
    return "".join(o)


def grade(v: Optional[float], good: float, warn: float) -> str:
    if v is None:
        return "n/a"
    cls = "good" if v <= good else "warn" if v <= warn else "bad"
    return f'<span class="{cls}">{v:.3f}</span>'


def render(c: Dict[str, Any]) -> str:
    sm = c["summary"]
    out: List[str] = []
    out.append('<section id="summary"><h2>1. Summary</h2><div class="card"><ul>'
               f"<li>Compared the synthetic run <b>{E(c['run'])}</b> with the official pack for the scenario tables of HEALTH-S1 and FIN-S2 (6 tables).</li>"
               f"<li>Headers identical to the official tables (names and order): <b>{'yes' if sm['headers_identical'] else 'NO'}</b>.</li>"
               f"<li>Categorical columns: median total-variation distance (TVD) <b>{sm['median_tvd']}</b> over {sm['categorical_columns']} columns "
               "(0 = identical distribution, 1 = disjoint).</li>"
               f"<li>Numeric columns: median Kolmogorov-Smirnov statistic <b>{sm['median_ks']}</b> over {sm['numeric_columns']} columns (0 = identical, 1 = disjoint).</li>"
               "<li>Scale differs by design: the official pack draws on 100,000 residents; the synthetic demo on 2,500 people. Compare shares and rates, not counts.</li></ul>"
               "<p class='note'>Colour grading for TVD / KS: green &le; 0.10, amber &le; 0.25, red above. These are reading aids, not pass/fail thresholds.</p></div>"
               + table(["Largest categorical differences (table, column)", "TVD"], [(f"{t} · {col}", grade(v, 0.1, 0.25)) for t, col, v in sm["largest_tvd"]], raw=True)
               + table(["Largest numeric differences (table, column)", "KS"], [(f"{t} · {col}", grade(v, 0.1, 0.25)) for t, col, v in sm["largest_ks"]], raw=True) + "</section>")
    # tables overview
    out.append('<section id="tables"><h2>2. Tables</h2>' + table(["Table", "Scenario", "Rows official", "Rows synthetic", "Ratio", "Columns", "Header identical", "File sha256 (official / synthetic)"],
               [(t, v["scenario"], f"{v['rows'][0]:,}", f"{v['rows'][1]:,}", v["row_ratio"], f"{v['columns'][0]} / {v['columns'][1]}", "yes" if v["header_identical"] else "NO",
                 f"{v['file_sha256'][0]} / {v['file_sha256'][1]}") for t, v in c["tables"].items()]) + "</section>")
    # relationships & rates
    o, s = c["official"], c["synthetic"]
    def fmt(v):
        return ", ".join(f"{k} {v2}" for k, v2 in v.items()) if isinstance(v, dict) else v
    out.append('<section id="relationships"><h2>3. Relationships, rates and cross-domain overlap</h2>'
               + table(["Relationship", "Official", "Synthetic"], [(k, fmt(o["relationships"][k]), fmt(s["relationships"][k])) for k in o["relationships"]])
               + table(["Rate", "Official", "Synthetic"], [(k, o["rates"][k], s["rates"][k]) for k in o["rates"]])
               + table(["Cross-domain (health ed_visits x finance customers)", "Official", "Synthetic"], [(k, o["cross_domain"][k], s["cross_domain"][k]) for k in o["cross_domain"]])
               + "<p class='note'>Joins use the repository's own normalisation (app/normalize.py). The official joins are the locked Attack A baseline (1622 / 1484); "
                 "the synthetic overlap comes from the generator's configured shared population (20 % of people in both domains) and is computed from its files.</p></section>")
    # per table column profiles
    sec = ['<section id="columns"><h2>4. Column-by-column comparison</h2><p class="note">Identifier and free-text columns are compared by format shape '
           "(digits &rarr; 9, letters &rarr; A/a) and length only; their values are never shown. Category values are listed only for low-cardinality, non-identifying columns.</p>"]
    for t, v in c["tables"].items():
        rows = []
        charts = []
        for p in v["profiles"]:
            k = p.get("kind")
            if k == "categorical":
                metric = f"TVD {grade(p['tvd'], 0.1, 0.25)} · categories {p['n_categories'][0]} / {p['n_categories'][1]} · only official {p['only_official']}, only synthetic {p['only_synthetic']}"
                if p.get("dist") and len(p["dist"]["categories"]) > 1:
                    charts.append(f"<h4>{E(t)} · {E(p['column'])} (share of non-empty values)</h4>" + LEGEND + pairs(p["dist"]["categories"], p["dist"]["official"], p["dist"]["synthetic"], p["column"]))
            elif k == "numeric":
                metric = f"KS {grade(p['ks'], 0.1, 0.25)} · p5/p25/p50/p75/p95 official {p['quantiles'][0]} vs synthetic {p['quantiles'][1]} · mean {p['mean'][0]} / {p['mean'][1]}"
            elif k == "temporal":
                metric = (f"range official {p['range'][0][0]}..{p['range'][0][1]} vs synthetic {p['range'][1][0]}..{p['range'][1][1]} · month TVD {grade(p['month_tvd'], 0.1, 0.25)}"
                          + (f" · hour TVD {grade(p['hour_tvd'], 0.1, 0.25)}" if "hour_tvd" in p else ""))
                if p.get("hour_dist"):
                    charts.append(f"<h4>{E(t)} · {E(p['column'])} by hour of day</h4>" + LEGEND + pairs([f"{h:02d}" for h in range(24)], p["hour_dist"][0], p["hour_dist"][1], p["column"]))
                elif p.get("month_dist") and p["column"] not in ("date_of_birth", "birth_date", "account_open_date", "issued_date", "expiry"):
                    charts.append(f"<h4>{E(t)} · {E(p['column'])} by month</h4>" + LEGEND + pairs(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], p["month_dist"][0], p["month_dist"][1], p["column"]))
            elif k == "identifier":
                metric = (f"shape TVD {grade(p['shape_tvd'], 0.1, 0.25)} · top shapes official <span class='mono'>{E(p['shapes'][0])}</span> vs synthetic <span class='mono'>{E(p['shapes'][1])}</span>"
                          f" · length p5/p50/p95 {p['length'][0]} / {p['length'][1]}")
            else:
                metric = f"free text length p5/p50/p95 official {p['length'][0]} vs synthetic {p['length'][1]} (content not shown)"
            rows.append((p["column"], p["role"], k, f"{p['empty'][0] * 100:.1f}% / {p['empty'][1] * 100:.1f}%", f"{p['distinct_ratio'][0]} / {p['distinct_ratio'][1]}", metric))
        sec.append(f"<h3>{E(t)}</h3>" + table(["Column", "Catalog role", "Compared as", "Empty (off / syn)", "Distinct ratio (off / syn)", "Comparison"], rows, raw=True)
                   + (f"<details><summary>Distribution charts ({len(charts)})</summary>{''.join(charts)}</details>" if charts else ""))
    sec.append("</section>")
    out.append("".join(sec))
    out.append('<section id="method"><h2>5. Method and reading guide</h2><div class="card"><ul>'
               "<li><b>TVD</b> (total-variation distance) = &frac12; &Sigma; |p<sub>official</sub>(c) &minus; p<sub>synthetic</sub>(c)| over categories c: the share of probability mass that would have to move to make the two distributions equal.</li>"
               "<li><b>KS</b> (Kolmogorov-Smirnov) = max |F<sub>official</sub>(x) &minus; F<sub>synthetic</sub>(x)|, the largest gap between the two cumulative distributions.</li>"
               "<li><b>Empty</b> = share of blank cells; <b>distinct ratio</b> = distinct non-empty values / non-empty values (1 = every value unique, e.g. identifiers).</li>"
               "<li>Synthetic categories that never occur in the official data (or vice versa) are counted, so a fictional value set (names, merchants, employers) shows up as large TVD without implying an error.</li>"
               "<li>Both datasets are fully synthetic; the official pack is only read. This report contains aggregates only.</li></ul></div></section>")
    nav = "".join(f'<a href="#{i}">{n}</a>' for i, n in (("summary", "Summary"), ("tables", "Tables"), ("relationships", "Relationships"), ("columns", "Columns"), ("method", "Method")))
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synthetic vs official comparison</title>'
            f"<style>{CSS}</style></head><body><header><button class='theme' id='theme' type='button'>Light / dark</button><h1>Synthetic vs official data: HEALTH-S1 + FIN-S2</h1>"
            f"<div class='sub'>Synthetic run {E(c['run'])} &middot; official pack {E(c['official_pack'])} &middot; aggregates only</div><nav>{nav}</nav></header><main>{''.join(out)}</main>"
            "<script>document.getElementById('theme').onclick=function(){var r=document.documentElement,d=r.getAttribute('data-theme')==='dark'||"
            "(!r.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);r.setAttribute('data-theme',d?'light':'dark')}</script></body></html>")


def leak_check(text: str, run: Path, official: Path = OFFICIAL_PACK) -> Dict[str, int]:
    """No identifier value from either dataset may appear in the report."""
    hits = 0
    low = text.casefold()
    words = set(re.findall(r"[0-9a-zåäöü+@._-]{6,}", low))
    for root in (official, run_dirs(run)["pack"]):
        for ds, tb, cols in (("health", "ed_visits", ("patient_hetu", "patient_name", "phone", "home_address")), ("finance", "customers", ("hetu", "full_name", "email", "phone", "iban", "street_address")),
                             ("finance", "cards", ("card_pan",))):
            df = pd.read_csv(root / "data" / ds / f"{tb}.csv", dtype=str, keep_default_na=False, usecols=list(cols))
            for c in cols:
                vals = {v.casefold() for v in df[c] if len(v) >= 6}
                hits += len(words & vals) + sum(1 for v in vals if " " in v and v in low)
    return {"identifier_value_hits": hits}


def main(argv: Optional[Sequence[str]] = None) -> int:
    utf8_stdout()
    p = argparse.ArgumentParser(description="Compare a synthetic test pack with the official data (same scenarios); writes a separate HTML report")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, default=None, help="default: <run>/reports/comparison_official.html")
    a = p.parse_args(argv)
    run = a.run_dir.resolve()
    out = (a.out or run_dirs(run)["reports"] / "comparison_official.html").resolve()
    refuse_forbidden(out, "comparison report")
    res = compare(run)
    page = render(res)
    lk = leak_check(page, run)
    if lk["identifier_value_hits"]:
        print(f"error: leak check failed {lk}; nothing written", file=sys.stderr)
        return 3
    res["leak_check"] = lk
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    write_json(out.with_suffix(".json"), res)
    print(f"report: {out}\nmedian TVD {res['summary']['median_tvd']} | median KS {res['summary']['median_ks']} | leak check clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
