#!/usr/bin/env python3
"""Build the run report for a synthetic test pack: reports/index.html (self-contained, offline),
reports/report.json and reports/methodology.md - aggregates only.

Every number comes from the run's evidence files (manifest, validation, protection, attacks, pets-eval
scorecards, benchmark). Before the files are kept they are scanned for raw identifiers of the pack (HETU,
phones, IBANs, e-mails, card numbers, names, addresses), pseudonym tokens of the protected releases and the
run's key; any hit aborts and nothing is written.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalize_phone  # noqa: E402
from synth_common import RELEASE_TABLES, read_csv, read_json, run_dirs, sha256_file, utf8_stdout, write_json  # noqa: E402

E = lambda s: html.escape("" if s is None else str(s), quote=True)  # noqa: E731
POL_COLOR = {"raw": "var(--ref)", "current": "var(--s2)", "relational": "var(--s3)"}
POL_LABEL = {"raw": "Raw synthetic data", "current": "Protected: current policy", "relational": "Protected: relational policy"}

TASK_TEXT = {
    "H-U2": ("Median length of stay by triage level", "ed_visits: triage, los_minutes", "1 - mean relative error of the median per triage level / 0.3"),
    "H-U4": ("Diagnosis-group mix in the 8 largest municipalities", "ed_visits: municipality, icd10_primary", "1 - mean total-variation distance / 0.15"),
    "H-U6": ("30-day revisit rate by age band", "ed_visits: readmit_30d (or a consistent patient pseudonym), date_of_birth + arrival_ts",
             "1 - (mean |rate difference| by age band / overall rate) / 0.5"),
    "H-U7": ("CRP vs temperature, and CRP by diagnosis group", "lab_results (P-CRP) joined to ed_visits on visit_id; temp_c",
             "0.5 x (1 - |Spearman difference| / 0.3) + 0.5 x (1 - mean log-median gap over groups with >= 30 rows)"),
    "H-U8": ("Hour-of-day arrival curve", "ed_visits: arrival_ts with a time of day", "1 - total-variation distance of the hour histogram / 0.3"),
    "FIN-U1": ("Fraud model: train Jul-Oct, test on original Nov-Dec", "card_transactions: ts, amount_eur, mcc, channel, merchant_country, card_pan, is_fraud",
               "min(1, PR-AUC of model trained on protected / PR-AUC of model trained on original)"),
    "FIN-U4": ("Card spending-profile segmentation (k = 6)", "card_transactions grouped by a consistent card_pan pseudonym; amount, mcc, channel",
               "0.5 x centroid agreement + 0.5 x (1 - TVD of cluster sizes)"),
    "FIN-U6": ("Mean monthly spend by income band x age band", "customers (income_band, birth_date) -> cards (customer_id, card_pan) -> card_transactions",
               "1 - MAPE / 0.5 over cells with >= 10 customers"),
}
RISK_TEXT = {
    "direct identifiers retained": "Share of values of catalogued direct-identifier columns that still appear verbatim (normalised) in the release. Lower is better.",
    "hashed ids reversible": "Share of hash-looking values (32/40/64 hex) recovered by hashing candidate identifiers with unsalted MD5/SHA-1/SHA-256. Keyed HMAC tokens are not reversible this way. Lower is better.",
    "records with k<5": "Share of rows whose combination of kept quasi-identifiers is shared by fewer than 5 rows (equivalence class size k < 5). Lower is better.",
    "linkage re-identification": "Worst, over the scenario's adversaries, of the re-identification rate (unique correct claims / adversary targets present) or the attribute-inference advantage over the base rate. Lower is better.",
    "free-text identifier leakage": "Share of gold identifying PII spans (PERSON, NATIONAL_ID, PHONE, ADDRESS, ...) whose text still appears in the released free text. Lower is better.",
}


def table(headers: Sequence[str], rows: Sequence[Sequence[Any]], raw: bool = False) -> str:
    th = "".join(f"<th>{E(h)}</th>" for h in headers)
    tb = "".join("<tr>" + "".join(f"<td>{c if raw else E(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>'


def pct(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{v * 100:.1f}%"


def bars(cats: Sequence[str], series: Sequence[Dict[str, Any]], vmax: float, fmt, aria: str, width: int = 680, height: int = 230) -> str:
    """Grouped column chart (inline SVG): bars <= 24px, 2px gaps, 4px rounded tops, value labels, n/a markers, <title> tooltips."""
    ml, mr, mt, mb = 52, 8, 34, 40  # top margin leaves room for staggered labels
    pw, ph = width - ml - mr, height - mt - mb
    n, g = len(series), max(1, len(cats))
    gw = pw / g
    bw = max(6.0, min(24.0, (gw * 0.72 - 2 * (n - 1)) / n))
    tot = n * bw + 2 * (n - 1)
    vmax = vmax or 1.0
    o = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{E(aria)}">']
    for i in range(5):
        v = vmax * i / 4
        y = mt + ph - ph * v / vmax
        o.append(f'<line class="grid" x1="{ml}" x2="{width - mr}" y1="{y:.1f}" y2="{y:.1f}"/><text x="{ml - 6}" y="{y + 4:.1f}" text-anchor="end">{E(fmt(v))}</text>')
    for gi, cat in enumerate(cats):
        x0 = ml + gi * gw + (gw - tot) / 2
        for si, s in enumerate(series):
            v = s["values"][gi]
            x = x0 + si * (bw + 2)
            if v is None:
                o.append(f'<text class="mut" x="{x + bw / 2:.1f}" y="{mt + ph - 5}" text-anchor="middle">n/a</text>')
                continue
            h = ph * max(0.0, v) / vmax
            y = mt + ph - h
            r = min(4, h, bw / 2)
            path = (f"M{x:.1f},{y + h:.1f} L{x:.1f},{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} L{x + bw - r:.1f},{y:.1f} "
                    f"Q{x + bw:.1f},{y:.1f} {x + bw:.1f},{y + r:.1f} L{x + bw:.1f},{y + h:.1f} Z") if h >= 1 else ""
            mark = f'<path d="{path}" fill="{s["color"]}"/>' if path else f'<rect x="{x:.1f}" y="{mt + ph - 2}" width="{bw:.1f}" height="2" fill="{s["color"]}"/>'
            o.append(f'<g class="mark"><title>{E(s["name"])} - {E(cat)}: {E(fmt(v))}</title>{mark}</g>')
            txt = fmt(v)
            lift = 11 * (si % 2) if len(txt) * 6.2 + 2 > bw + 2 else 0
            o.append(f'<text class="lab" x="{x + bw / 2:.1f}" y="{y - 4 - lift:.1f}" text-anchor="middle">{E(txt)}</text>')
        o.append(f'<text x="{ml + gi * gw + gw / 2:.1f}" y="{mt + ph + 16}" text-anchor="middle">{E(cat)}</text>')
    o.append(f'<line class="axis" x1="{ml}" x2="{width - mr}" y1="{mt + ph}" y2="{mt + ph}"/></svg>')
    return "".join(o)


def legend(keys: Sequence[str]) -> str:
    return '<div class="legend">' + "".join(f'<span><i style="background:{POL_COLOR[k]}"></i>{E(POL_LABEL[k])}</span>' for k in keys) + "</div>"


def relationship_svg(prot: Dict[str, Any]) -> str:
    """Tables, release-internal keys and the cross-domain person link, with per-policy join status."""
    st = {}
    for pol, ev in prot.items():
        for sid, r in ev["releases"].items():
            for j in r["relationships"]:
                st[(pol, j["child"])] = j["status"]
    def lab(child):
        return " / ".join(f"{p[:3]}: {'OK' if st.get((p, child)) == 'PRESERVED' else 'BROKEN'}" for p in ("current", "relational"))
    boxes = [("ed_visits", 40, 40), ("lab_results", 40, 150), ("clinical_notes", 230, 150), ("customers", 470, 40), ("cards", 470, 150), ("card_transactions", 470, 260)]
    o = ['<svg class="chart" viewBox="0 0 700 330" role="img" aria-label="table relationships">']
    edges = [((40, 150), (40, 40), "lab_results.visit_id", 60, 112), ((230, 150), (40, 40), "clinical_notes.visit_id", 205, 112),
             ((470, 150), (470, 40), "cards.customer_id", 490, 112), ((470, 260), (470, 150), "card_transactions.card_pan", 490, 222)]
    for (x1, y1), (x2, y2), child, lx, ly in edges:
        o.append(f'<line x1="{x1 + 75}" y1="{y1}" x2="{x2 + 75}" y2="{y2 + 34}" class="edge"/><text x="{lx}" y="{ly}" class="lab">{E(child)}</text>'
                 f'<text x="{lx}" y="{ly + 13}">{E(lab(child))}</text>')
    o.append('<line x1="190" y1="57" x2="470" y2="57" class="edge dash"/><text x="245" y="50" class="lab">person link (raw): HETU, phone</text>'
             '<text x="245" y="75">cut by per-release key domains</text>')
    for name, x, y in boxes:
        o.append(f'<rect x="{x}" y="{y}" width="150" height="34" rx="6" class="box"/><text x="{x + 75}" y="{y + 21}" text-anchor="middle" class="lab">{E(name)}</text>')
    o.append("</svg>")
    return "".join(o)


CSS = """:root{color-scheme:light;--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--ref:#898781;--good:#006300;--warn:#8a5a00;--bad:#b02a2a;--chipgood:#e3f4e3;--chipwarn:#fdf0d2;--chipbad:#fbe3e3;--border:rgba(11,11,11,.1)}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--good:#0ca30c;--warn:#fab219;--bad:#ec6a6a;--chipgood:#16301a;--chipwarn:#3a2f10;--chipbad:#3a1a1a;--border:rgba(255,255,255,.1)}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--s1:#3987e5;--s2:#d95926;--s3:#199e70;
--good:#0ca30c;--warn:#fab219;--bad:#ec6a6a;--chipgood:#16301a;--chipwarn:#3a2f10;--chipbad:#3a1a1a;--border:rgba(255,255,255,.1)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
header,main{max-width:1100px;margin:0 auto;padding:0 16px}header{padding-top:22px}h1{font-size:25px;margin:0 0 4px}
h2{font-size:20px;margin:34px 0 8px;padding-top:10px;border-top:1px solid var(--grid)}h3{font-size:16px;margin:18px 0 6px}
.sub,.note{color:var(--ink2)}.note{font-size:13px}nav{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:13px;margin:10px 0}nav a{color:var(--ink2)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 16px;margin:10px 0}
.chip{display:inline-block;border-radius:999px;padding:1px 10px;font-weight:600;font-size:13px;border:1px solid var(--border)}
.PASS,.OK,.PRESERVED,.MEASURED{background:var(--chipgood);color:var(--good)}.REVIEW,.CAPPED,.NOT_MEASURED,.NOT_ANSWERABLE,.PARTIAL{background:var(--chipwarn);color:var(--warn)}
.FAIL,.BROKEN,.LEAK,.DEGENERATE{background:var(--chipbad);color:var(--bad)}
.tw{overflow-x:auto;margin:8px 0}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:5px 8px;border-bottom:1px solid var(--grid);text-align:left;vertical-align:top}
th{color:var(--ink2);font-weight:600;background:var(--surface)}svg.chart{width:100%;max-width:700px;height:auto;display:block}
svg text{fill:var(--ink2);font:11px system-ui,sans-serif}svg .lab{fill:var(--ink);font-weight:600}svg .mut{fill:var(--muted)}svg .grid{stroke:var(--grid)}svg .axis{stroke:var(--axis)}
svg .mark:hover{opacity:.78}svg .box{fill:var(--surface);stroke:var(--axis)}svg .edge{stroke:var(--ink2);stroke-width:1.5}svg .dash{stroke-dasharray:5 4}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:13px;color:var(--ink2);margin:4px 0}.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
details{margin:6px 0}summary{cursor:pointer;color:var(--ink2)}pre{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px;overflow-x:auto;font-size:12px}
button.theme{float:right;background:var(--surface);color:var(--ink);border:1px solid var(--border);border-radius:6px;padding:4px 10px;cursor:pointer}"""


def chip(s: str) -> str:
    return f'<span class="chip {E(s.split()[0].split("_")[0] if s.startswith(("BROKEN", "PROTECTED")) else s.split()[0])}">{E(s)}</span>'


def build(run: Path) -> Dict[str, Any]:
    d = run_dirs(run)
    ev = d["evidence"]
    man = read_json(ev / "manifest.json")
    val = read_json(ev / "validation.json") if (ev / "validation.json").is_file() else None
    prot = {p: read_json(ev / f"protection_{p}.json") for p in ("current", "relational") if (ev / f"protection_{p}.json").is_file()}
    araw = read_json(ev / "attack_raw.json")
    aprot = read_json(ev / "attack_protected.json")
    sc = read_json(ev / "scorecards.json") if (ev / "scorecards.json").is_file() else {}
    bench = read_json(ev / "benchmark.json") if (ev / "benchmark.json").is_file() else None
    tests = read_json(ev / "tests.json") if (ev / "tests.json").is_file() else None
    rep: Dict[str, Any] = {"run_id": run.name, "generator": man["generator_version"], "seed": man["seed"], "profile": man["profile"],
                           "population": man["population"], "overlaps": man["overlaps"], "missing_identifiers": man["missing_identifiers"],
                           "relationships_raw": man["relationships"], "tables": {k: {"rows": v["rows"], "columns": len(v["columns"]),
                           "matches_official_header": v["matches_official_header"], "schema_sha256": v["schema_sha256"]} for k, v in man["tables"].items()},
                           "validation": {"passed": val["passed"], "total": len(val["checks"]), "failed": val["failed"],
                                          "integrity_passed": val.get("integrity_passed"), "scorecard_ready": val.get("scorecard_ready"),
                                          "official_attack_a": val.get("official_attack_a")} if val else None,
                           "protection": {p: {"seconds": e["seconds"], "rows": e["rows_processed"], "peak_memory_bytes": e.get("peak_memory_bytes"),
                                              "releases": {sid: {"relationships": r["relationships"], "tables": {t: {k: tr[k] for k in ("rows_in", "rows_out", "columns_in", "columns_out", "dropped", "column_order_preserved")}
                                                                                                                  | {"rowmap_aligned": tr["rowmap"]["aligned"], "raw_identifier_survivors": tr["raw_identifier_survival"]["total"],
                                                                                                                     "glue_guard_passed": tr["glue_survival_guard"]["passed"], "csv_sha256": tr["csv_sha256"],
                                                                                                                     "column_actions": tr["column_actions"]} for t, tr in r["tables"].items()}}
                                                           for sid, r in e["releases"].items()}} for p, e in prot.items()},
                           "attack_raw": {k: {x: v.get(x) for x in ("status", "join", "true_person_links", "false_links", "columns_present")} for k, v in araw["keys"].items()}
                           | {"consistency": araw["consistency"], "official_attack_a_constants": araw["official_attack_a_constants_unchanged"]},
                           "attack_protected": {p: {k: {x: v.get(x) for x in ("status", "join", "verdict", "columns_present")} for k, v in r["keys"].items()} for p, r in aprot.items()},
                           "scorecards": {k: {x: v.get(x) for x in ("scorecard_returncode", "scorecard_seconds", "check_seconds", "summary", "risk_components",
                                                                    "binding_ok", "binding_problems", "check", "scorecard_sha256", "protected_csv_sha256")}
                                          | {"utility": [{x: u.get(x) for x in ("id", "description", "required", "score", "metric", "answerable", "missing", "sanity")} for u in v.get("utility", [])],
                                             "tables": {t: {x: i.get(x) for x in ("status", "rows_original", "rows_protected", "columns_dropped", "risks", "k_anonymity", "free_text")}
                                                        | {"linkage": {a: ({y: l.get(y) for y in ("evaluated", "reidentification_rate", "n_targets_in_data", "note", "reason")} if isinstance(l, dict) else l)
                                                                     for a, l in (i.get("linkage") or {}).items()}}
                                                        for t, i in (v.get("tables") or {}).items()}} for k, v in sc.items()},
                           "benchmark": bench, "tests": tests}
    return rep


def render(rep: Dict[str, Any]) -> str:
    pols = [p for p in ("current", "relational") if p in rep["protection"]]
    pop, ov, rel = rep["population"], rep["overlaps"], rep["relationships_raw"]
    out: List[str] = []
    # 1 summary
    sc = rep["scorecards"]
    summ_rows = []
    for k, v in sc.items():
        s = v.get("summary") or {}
        unans = [u["id"] for u in v["utility"] if not u["answerable"]]
        capped = [u["id"] for u in v["utility"] if (u.get("sanity") or {}).get("flag") in ("CAPPED", "DEGENERATE")]
        summ_rows.append((k, pct(s.get("privacy")), pct(s.get("utility")), pct(s.get("composite")), ", ".join(unans) or "none", ", ".join(capped) or "none",
                          "yes" if v.get("binding_ok") else "NO"))
    ap = rep["attack_protected"]
    out.append('<section id="summary"><h2>1. Executive summary</h2><div class="card"><ul>'
               f"<li>One synthetic population of <b>{pop['size']:,}</b> people: {pop['health_subjects']:,} ED patients, {pop['finance_customers']:,} bank customers, "
               f"<b>{pop['shared_subjects']:,}</b> in both domains (ground truth).</li>"
               f"<li>Raw cross-domain attack (repo join code): HETU join <b>{rep['attack_raw']['hetu']['join']}</b>, normalised-phone join <b>{rep['attack_raw']['phone']['join']}</b> "
               f"&mdash; all true person links ({rep['attack_raw']['hetu']['false_links']} / {rep['attack_raw']['phone']['false_links']} false), equal to the generator manifest.</li>"
               + "".join(f"<li>Protected ({E(p)}): HETU {E(ap[p]['hetu']['status'])} join={E('n/a' if ap[p]['hetu']['join'] is None else ap[p]['hetu']['join'])}; "
                         f"phone {E(ap[p]['phone']['status'])} join={E('n/a' if ap[p]['phone']['join'] is None else ap[p]['phone']['join'])} &mdash; {E(ap[p]['phone']['verdict'])}.</li>" for p in pols)
               + "<li>The <b>current</b> pipeline breaks every release-internal join (record key passes through, foreign key is tokenised; card_pan is dropped), so H-U7, FIN-U4 and FIN-U6 are not answerable. "
               "The <b>relational</b> policy (same PET code, join keys tokenised with one release key) preserves all joins.</li>"
               "<li>H-U8 is not answerable under both policies: the pipeline generalises arrival_ts to ISO week, removing the time of day.</li>"
               "<li>Free text (clinical_notes.note_text) passes through unredacted in both policies; see the free-text leakage risk.</li></ul></div>"
               + table(["Scorecard", "Privacy", "Utility", "Composite", "Not answerable", "Capped / degenerate", "Bound to files"], summ_rows) + "</section>")
    # 2 population
    trs = [(k, f"{v['rows']:,}", v["columns"], "yes" if v["matches_official_header"] else "NO", v["schema_sha256"][:16] + "…") for k, v in rep["tables"].items()]
    out.append('<section id="population"><h2>2. Synthetic population and tables</h2>'
               + table(["Measure", "Value", "How it is computed"], [
                   ("Population size", f"{pop['size']:,}", "people generated (seeded); membership drawn from configured shares"),
                   ("Health subjects", f"{pop['health_subjects']:,}", "distinct person_id in truth/health__ed_visits.csv"),
                   ("Finance customers", f"{pop['finance_customers']:,}", "rows in customers.csv"),
                   ("Shared subjects", f"{pop['shared_subjects']:,}", "person_id present in both truth files"),
                   ("HETU overlap", f"{ov['hetu_overlap']:,}", "|normalize_hetu(ed_visits.patient_hetu) ∩ normalize_hetu(customers.hetu)|"),
                   ("Phone overlap (normalised)", f"{ov['phone_overlap_normalised']:,}", "|normalize_phone(ed_visits.phone) ∩ normalize_phone(customers.phone)|"),
                   ("Accidental collisions", f"{ov['hetu_collisions_between_different_people']} / {ov['phone_collisions_between_different_people']}", "shared value but different person (HETU / phone)"),
                   ("ED rows without HETU / phone", f"{rep['missing_identifiers']['ed_visits_rows_without_hetu']:,} / {rep['missing_identifiers']['ed_visits_rows_without_phone']:,}", "blank cells"),
                   ("Customers without phone", f"{rep['missing_identifiers']['customers_without_phone']:,}", "blank cells"),
                   ("Visits per patient (mean)", rel["visits_per_patient_mean"], "identified visits / health subjects"),
                   ("Labs / notes resolving to a visit", f"{rel['lab_results_resolving_to_ed_visits']:,}/{rel['lab_results']:,} · {rel['clinical_notes_resolving_to_ed_visits']:,}/{rel['clinical_notes']:,}", "foreign key check"),
                   ("Cards / transactions resolving", f"{rel['cards_resolving_to_customers']:,}/{rel['cards']:,} · {rel['transactions_resolving_to_cards']:,}/{rel['transactions']:,}", "foreign key check"),
                   ("Fraud before / from 2025-11-01", f"{rel['fraud_before_2025_11_01']} / {rel['fraud_from_2025_11_01']}", "FIN-U1 needs >= 10 labelled frauds before the cut"),
                   ("P-CRP results", f"{rel['crp_results']:,}", "H-U7 input")])
               + "<h3>Tables (schemas compared with the official headers)</h3>" + table(["Table", "Rows", "Columns", "Official header", "Schema sha256"], trs)
               + (f"<p>Validation against official metadata and conventions: integrity <b>{E(rep['validation'].get('integrity_passed'))}</b>, "
                  f"scorecard task minimums met: <b>{E(rep['validation'].get('scorecard_ready'))}</b>; {rep['validation']['passed']}/{rep['validation']['total']} checks passed in total"
                  + (f"; failed: {E(rep['validation']['failed'])}" if rep['validation']['failed'] else "") + ". Official Attack A on the official pack: "
                  + E((rep["validation"].get("official_attack_a") or {}).get("verdict")) + " " + E((rep["validation"].get("official_attack_a") or {}).get("observed")) + " (expected 1622 / 1484, unchanged).</p>" if rep["validation"] else "")
               + "</section>")
    # 3 relationships
    out.append('<section id="relationships"><h2>3. Relationship graph and join preservation</h2>' + relationship_svg({p: {"releases": rep["protection"][p]["releases"]} for p in pols})
               + table(["Policy", "Release", "Child -> parent", "Status", "Resolving share"],
                       [(p, sid, f"{j['child']} -> {j['parent']}", chip(j["status"]), j["resolving_share"]) for p in pols for sid, r in rep["protection"][p]["releases"].items() for j in r["relationships"]], raw=True)
               + "</section>")
    # 4 attacks
    raw, cats = rep["attack_raw"], ["HETU join", "Phone join"]
    vals = {"raw": [raw["hetu"]["join"], raw["phone"]["join"]]}
    for p in pols:
        vals[p] = [ap[p]["hetu"]["join"], ap[p]["phone"]["join"]]
    vmax = float(max(v for vs in vals.values() for v in vs if v is not None) or 1)
    series = [{"name": POL_LABEL[k], "color": POL_COLOR[k], "values": vals[k]} for k in ["raw"] + pols]
    out.append('<section id="attacks"><h2>4. Cross-domain attack: raw vs protected</h2>' + legend(["raw"] + pols)
               + bars(cats, series, vmax, lambda v: f"{v:,.0f}", "joins") + table(["Data", "Key", "Status", "Join", "Columns present", "Verdict / ground truth"],
                   [("raw", k.upper(), chip(raw[k]["status"]), raw[k]["join"], E(raw[k]["columns_present"]), f"true links {raw[k]['true_person_links']}, false {raw[k]['false_links']}") for k in ("hetu", "phone")]
                   + [(p, k.upper(), chip(ap[p][k]["status"]), E(ap[p][k]["join"]), E(ap[p][k]["columns_present"]), E(ap[p][k]["verdict"])) for p in pols for k in ("hetu", "phone")], raw=True)
               + "<p class='note'>Normalisation is the repository's own recipe (app/normalize.py): HETU <code>strip</code>; phone <code>strip non-[0-9+]; ^+358 -> 0; ^00358 -> 0</code>. "
                 "The expected raw overlap is computed from this pack (not the official 1622 / 1484, which stay unchanged in measure_baseline.py). "
                 "<b>NOT_MEASURED</b> means a column was dropped: the attack could not run on that key and the zero is not counted as protection.</p></section>")
    # 5 transformations
    rows = []
    for p in pols:
        for sid, r in rep["protection"][p]["releases"].items():
            for t, tr in r["tables"].items():
                acts: Dict[str, List[str]] = {}
                for c in tr["column_actions"]:
                    acts.setdefault(c["action"], []).append(c["column"] + (" (override)" if c["override"] else ""))
                rows.append((p, f"{sid} {t}", f"{tr['rows_in']:,} -> {tr['rows_out']:,}", f"{tr['columns_in']} -> {tr['columns_out']}",
                             "; ".join(f"{k}: {', '.join(v)}" for k, v in sorted(acts.items())), "yes" if tr["rowmap_aligned"] else "NO",
                             tr["raw_identifier_survivors"], "pass" if tr["glue_guard_passed"] else "FAIL"))
    out.append('<section id="transforms"><h2>5. Per-column PET actions (actual pipeline output)</h2>'
               + table(["Policy", "Table", "Rows", "Columns", "Actions by column (from app/pet_pipeline.protect_table)", "Row map aligned", "Raw identifiers surviving", "Glue guard"], rows)
               + "<p class='note'>Raw identifiers surviving = values of any catalogued direct identifier of the release found in the protected table (whole cell or inside text), counts only. "
                 "The current pipeline passes free text through, so names, HETUs and phones typed into clinical notes survive.</p></section>")
    # 6 scorecards
    sec = ['<section id="scorecards"><h2>6. pets-eval scorecards (HEALTH-S1, FIN-S2)</h2><p class="note">Official toolkit, unchanged, run with <code>--root</code> = this synthetic pack and private row maps. '
           'Protected-release comparison (row maps present) &mdash; not a DCR / membership-inference evaluation of a synthetic-data generator.</p>']
    for sid in RELEASE_TABLES:
        keys = [f"{p}/{sid}" for p in pols if f"{p}/{sid}" in sc]
        series = [{"name": POL_LABEL[k.split('/')[0]], "color": POL_COLOR[k.split('/')[0]], "values": [(sc[k].get("summary") or {}).get(m) for m in ("privacy", "utility", "composite")]} for k in keys]
        sec.append(f"<h3>{E(sid)}: scores</h3>" + legend(pols) + bars(["Privacy", "Utility", "Composite"], series, 1.0, lambda v: f"{v * 100:.1f}%", f"{sid} scores"))
        tasks = sorted({u["id"] for k in keys for u in sc[k]["utility"]})
        tseries = [{"name": POL_LABEL[k.split('/')[0]], "color": POL_COLOR[k.split('/')[0]], "values": [next((u["score"] for u in sc[k]["utility"] if u["id"] == t), None) for t in tasks]} for k in keys]
        sec.append(f"<h4>{E(sid)}: utility tasks (n/a = not answerable, never shown as 0)</h4>" + legend(pols) + bars(tasks, tseries, 1.0, lambda v: f"{v * 100:.0f}%", f"{sid} tasks"))
        trows = []
        for t in tasks:
            q, src, metric = TASK_TEXT.get(t, ("", "", ""))
            cells = []
            for k in keys:
                u = next(u for u in sc[k]["utility"] if u["id"] == t)
                flag = (u.get("sanity") or {}).get("flag", "")
                cells.append(("NOT ANSWERABLE: " + "; ".join(u.get("missing") or []) if not u["answerable"] else f"{u['score']:.3f}") + f" [{flag}]")
            trows.append((t, q, src, metric, *cells))
        sec.append(table(["Task", "Question", "Source fields", "Metric (0..1, higher is better)", *[k.split('/')[0] for k in keys]], trows))
        for k in keys:
            for u in sc[k]["utility"]:
                s = u.get("sanity") or {}
                if s.get("flag") in ("CAPPED", "DEGENERATE"):
                    sec.append(f"<p class='note'><b>{E(k)} {E(u['id'])} [{E(s['flag'])}]</b>: {E(s.get('why'))}</p>")
        rkeys = sorted({rk for k in keys for rk in (sc[k].get("risk_components") or {})})
        sec.append(f"<h4>{E(sid)}: risk components (0 = no risk, 1 = maximal)</h4>"
                   + table(["Risk component", *[k.split('/')[0] for k in keys], "Meaning"],
                           [(rk, *[pct((sc[k].get("risk_components") or {}).get(rk)) for k in keys], RISK_TEXT.get(rk.split(": ", 1)[-1], "")) for rk in rkeys]))
        for k in keys:
            for t, info in (sc[k].get("tables") or {}).items():
                ka = info.get("k_anonymity") or {}
                if ka:
                    sec.append(f"<p class='note'>{E(k)} {E(t)}: k-anonymity on {len(ka.get('qis') or [])} kept quasi-identifiers &mdash; {E(ka.get('n_classes'))} equivalence classes, "
                               f"min k {E(ka.get('min_k'))}, median k {E(ka.get('median_k'))}, share k&lt;2 / k&lt;5 / k&lt;10 = {E(ka.get('share_below'))}.</p>")
                ft = info.get("free_text") or {}
                for col, f in ft.items():
                    if isinstance(f, dict) and f.get("evaluated"):
                        sec.append(f"<p class='note'>{E(k)} {E(t)}.{E(col)} free text: identifying leakage {pct(f.get('identifying_leakage_rate'))}, all-label leakage {pct(f.get('leakage_rate'))} "
                                   f"over {E(f.get('n_values'))} gold span values; per label {E({l: v.get('rate') for l, v in (f.get('per_label') or {}).items()})}.</p>")
        for k in keys:
            ck = sc[k].get("check") or {}
            sec.append(f"<p class='note'>{E(k)}: pets-eval check scanned {E(ck.get('files_scanned'))} files, residual pattern totals {E(ck.get('totals'))}. "
                       f"Scorecard bound to the scored files: {E(sc[k].get('binding_ok'))}.</p>")
    sec.append("</section>")
    out.append("".join(sec))
    # 7 composite
    out.append('<section id="composite"><h2>7. How the scores are computed (docs/EVALUATION.md, toolkit scorecard.py)</h2><div class="card">'
               "<p><b>Privacy</b> = 1 - (0.5 x worst risk + 0.5 x mean risk) over all risk components of all released tables. The worst risk counts on purpose: one open door is enough.</p>"
               "<p><b>Utility</b> = mean over the scenario's required tasks; a required task that cannot be answered counts as 0 in this mean (it is shown here as 'not answerable', not as a measured 0).</p>"
               "<p><b>Composite</b> = weighted harmonic mean (30 + 25) / (30 / privacy + 25 / utility). It is high only when both are high: releasing everything gives "
               "privacy near 0, releasing nothing gives utility 0 - both make the composite small.</p></div></section>")
    # 8 performance
    b = rep.get("benchmark")
    if b:
        sizes = [str(s["people"]) for s in b["sizes"]]
        def med(stage):
            return [s["stages"][stage]["median"] for s in b["sizes"]]
        series = [{"name": f"{st}", "color": c, "values": med(st)} for st, c in (("generate", "var(--s1)"), ("protect", "var(--s2)"), ("scorecards", "var(--s3)"))]
        vmax = max(v for sr in series for v in sr["values"] if v) * 1.15
        out.append('<section id="performance"><h2>8. Performance benchmark</h2><p class="note">'
                   f"{E(b['machine'])}; {b['repetitions']} repetitions per size, same seed and configuration; wall-clock per stage (subprocess, includes interpreter start-up). "
                   "Peak memory = peak working set of the stage's own Python process (pets-eval child processes not profiled). Speed says nothing about privacy.</p>"
                   '<div class="legend"><span><i style="background:var(--s1)"></i>generate</span><span><i style="background:var(--s2)"></i>protect (both policies)</span>'
                   '<span><i style="background:var(--s3)"></i>pets-eval scorecards + check (both policies)</span></div>'
                   + bars(sizes, series, vmax, lambda v: f"{v:.1f}s", "median stage time by population size")
                   + table(["People", "Rows protected", "Generate s (min/med/max)", "Protect s", "Attack s", "Scorecards s", "Total s", "Protect rows/s (median)", "Protected bytes", "Peak MB (gen / protect)"],
                           [(s["people"], f"{s['rows_protected']:,}", *[f"{s['stages'][st]['min']}/{s['stages'][st]['median']}/{s['stages'][st]['max']}" for st in ("generate", "protect", "attack", "scorecards", "total")],
                             f"{s['protect_rows_per_s']['median']:,.0f}", f"{s['protected_bytes']:,}",
                             f"{s['peak_mb']['generate']['median']} / {s['peak_mb']['protect']['median']}") for s in b["sizes"]]) + "</section>")
    # 9 tests / validation
    t = rep.get("tests")
    out.append('<section id="tests"><h2>9. Validation and tests</h2>' + (f"<p>Test suite: <b>{E(t.get('summary'))}</b> (exit {E(t.get('returncode'))}).</p>" if t else "<p>Test results not attached to this run.</p>")
               + (f"<p>Pack validation: {rep['validation']['passed']}/{rep['validation']['total']} checks.</p>" if rep["validation"] else "") + "</section>")
    # 10 limitations
    out.append('<section id="limitations"><h2>10. Known limitations</h2><ul>' + "".join(f"<li>{E(x)}</li>" for x in [
        "FIN-U4 (k-means card segmentation) is not stable between runs: with byte-identical data, a different temporary key changes token values and "
        "therefore card ordering, and the score moved between 0.75 and 0.93 in the benchmark repetitions. Treat it as a range, not a point value.",
        "Synthetic data follows the official schemas and roughly their distributions, but it is simpler: e.g. synthetic fraud is easier to separate than real fraud (FIN-U1 is capped at 1.0 when the protected-trained model scores higher).",
        "Utility scores of 1.0 where values pass through unchanged (H-U2, H-U4, FIN-U6) measure only the analytical fields the task reads; they do not mean the release is safe.",
        "H-U8 is unanswerable because the current pipeline generalises timestamps to ISO week; keeping the hour would trade k-anonymity for this task.",
        "The 'relational' policy is a test-runner override documented in run_test_pack.py, not a change to the official pipeline; it shows what the current per-table design costs.",
        "Free text is not redacted by the current pipeline; leakage in clinical_notes.note_text is measured, not fixed.",
        "Linkage attacks use synthetic adversary files generated for this population; they are not the organisers' hidden attackers.",
        "Peak memory covers the generator/protection/attack processes only; pets-eval runtime is measured, its memory is not.",
        "The smoke profile is for schema/determinism checks only; its privacy and utility numbers are not meaningful."]) + "</ul></section>")
    out.append('<section id="repro"><h2>11. Reproduction</h2><pre>' + E(REPRO.format(seed=rep["seed"], people=rep["population"]["size"])) + "</pre></section>")
    nav = "".join(f'<a href="#{i}">{E(n)}</a>' for i, n in (("summary", "Summary"), ("population", "Population"), ("relationships", "Relationships"), ("attacks", "Attacks"),
                   ("transforms", "PET actions"), ("scorecards", "Scorecards"), ("composite", "Score formulas"), ("performance", "Performance"), ("tests", "Tests"),
                   ("limitations", "Limitations"), ("repro", "Reproduce")))
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synthetic H+F test pack</title>'
            f"<style>{CSS}</style></head><body><header><button class='theme' id='theme' type='button'>Light / dark</button><h1>Mosaic synthetic Health + Finance test pack</h1>"
            f"<div class='sub'>Run {E(rep['run_id'])} &middot; {E(rep['generator'])} &middot; seed {rep['seed']} &middot; fully synthetic, aggregates only</div><nav>{nav}</nav></header>"
            f"<main>{''.join(out)}</main><script>document.getElementById('theme').onclick=function(){{var r=document.documentElement,d=r.getAttribute('data-theme')==='dark'||"
            "(!r.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);r.setAttribute('data-theme',d?'light':'dark')}</script></body></html>")


REPRO = """# from the repo root, existing uv environment (no sync)
uv run --no-sync python app/run_synthetic_demo.py --profile demo --people {people} --seed {seed}
# or step by step (RUN = the printed run directory):
uv run --no-sync python app/generate_test_data.py --profile demo --people {people} --seed {seed}
uv run --no-sync python app/validate_test_pack.py   --run-dir RUN
uv run --no-sync python app/run_test_pack.py        --run-dir RUN --init-key
uv run --no-sync python app/run_test_attack.py      --run-dir RUN
uv run --no-sync python app/run_test_scorecards.py  --run-dir RUN
uv run --no-sync python app/report_test_pack.py     --run-dir RUN"""


def leak_scan(text: str, run: Path) -> Dict[str, Any]:
    d = run_dirs(run)
    vals: set = set()
    for ds, tbl, cols in (("health", "ed_visits", ("patient_hetu", "patient_name", "phone", "home_address", "attending_physician_name")),
                          ("finance", "customers", ("hetu", "full_name", "email", "phone", "iban", "street_address")), ("finance", "cards", ("card_pan",))):
        rows, _ = read_csv(d["pack"] / "data" / ds / f"{tbl}.csv")
        for r in rows:
            for c in cols:
                v = (r.get(c) or "").strip()
                if len(v) >= 6:
                    vals.add(v.casefold())
                    if c == "phone":
                        vals.add(normalize_phone(v))
    low = text.casefold()
    words = re.findall(r"[0-9a-zåäöü+@._-]{6,}", low)
    hits = sum(1 for w in set(words) if w in vals)
    multi = sum(1 for v in vals if " " in v and v in low)
    tokens = set()
    for p in ("current", "relational"):
        f = d["protected"] / p / "health__HEALTH-S1" / "ed_visits.csv"
        if f.is_file():
            tokens |= {r["patient_hetu"] for r in read_csv(f)[0] if r.get("patient_hetu")}
    tok = sum(1 for t in re.findall(r"(?<![0-9a-f])[0-9a-f]{16}(?![0-9a-f])", text) if t in tokens)
    key = d["private"] / "master.key"
    key_hit = key.is_file() and key.read_bytes().hex() in text
    return {"identifier_value_hits": hits + multi, "pseudonym_token_hits": tok, "key_hit": bool(key_hit), "clean": not (hits or multi or tok or key_hit)}


def methodology_md(rep: Dict[str, Any]) -> str:
    pols = list(rep["protection"])
    lines = [f"# Methodology - run {rep['run_id']}", "", f"Generator {rep['generator']}, seed {rep['seed']}, profile {rep['profile']}.", "",
             "Full methodology: `docs/SYNTHETIC_HEALTH_FINANCE.md`. This file summarises what this run did.", "",
             "## Steps", "1. Generate one synthetic population and derive Health (ed_visits, lab_results, clinical_notes) and Finance (customers, cards, card_transactions) tables, "
             "official headers, synthetic identifiers (NOTICE.md conventions), adversary files, truth, holdout and PII spans.",
             "2. Validate against the official metadata and conventions; re-run the official Attack A baseline on the official pack (1622 / 1484).",
             f"3. Protect every scenario table with the existing PET pipeline under policies: {', '.join(pols)}.",
             "4. Attack: raw and protected HETU / normalised-phone joins with app/attack_sim.simulate_attack; missing columns -> NOT_MEASURED.",
             "5. Score with the unchanged pets-eval CLI (`--root` = this pack, private row maps) and run `pets-eval check`.", "",
             "## Key results"]
    lines.append(f"- Raw joins: HETU {rep['attack_raw']['hetu']['join']}, phone {rep['attack_raw']['phone']['join']} (all true links).")
    for p, r in rep["attack_protected"].items():
        lines.append(f"- Protected ({p}): HETU {r['hetu']['status']} {r['hetu']['join']}; phone {r['phone']['status']} {r['phone']['join']}.")
    for k, v in rep["scorecards"].items():
        s = v.get("summary") or {}
        lines.append(f"- {k}: privacy {pct(s.get('privacy'))}, utility {pct(s.get('utility'))}, composite {pct(s.get('composite'))}; not answerable: "
                     + (", ".join(u["id"] for u in v["utility"] if not u["answerable"]) or "none"))
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    utf8_stdout()
    p = argparse.ArgumentParser(description="Build the HTML/JSON/Markdown report for a synthetic test-pack run")
    p.add_argument("--run-dir", type=Path, required=True)
    a = p.parse_args(argv)
    run = a.run_dir.resolve()
    d = run_dirs(run)
    rep = build(run)
    page = render(rep)
    js = json.dumps(rep, indent=2, ensure_ascii=False, default=str)
    md = methodology_md(rep)
    scans = {n: leak_scan(t, run) for n, t in (("index.html", page), ("report.json", js), ("methodology.md", md))}
    if not all(s["clean"] for s in scans.values()):
        print(f"error: leak scan failed {scans}; nothing written", file=sys.stderr)
        return 3
    rep["leak_scan"] = scans
    d["reports"].mkdir(parents=True, exist_ok=True)
    (d["reports"] / "index.html").write_text(page, encoding="utf-8")
    write_json(d["reports"] / "report.json", rep)
    (d["reports"] / "methodology.md").write_text(md, encoding="utf-8")
    print(f"report: {d['reports'] / 'index.html'} (leak scan clean: {all(s['clean'] for s in scans.values())}, html sha256 {sha256_file(d['reports'] / 'index.html')[:16]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
