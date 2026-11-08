#!/usr/bin/env python3
"""Generate findings/Future_and_Pilot_Plan.pdf — future + pilot plan for Mosaic."""

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).with_suffix("").with_name("Future_and_Pilot_Plan.pdf")

INK = HexColor("#1a1f2e")
MUTED = HexColor("#4a5568")
ACCENT = HexColor("#0d5c63")
RULE = HexColor("#c5d0d3")
SOFT = HexColor("#eef5f6")
WARN = HexColor("#8a4b08")


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=INK,
            spaceAfter=4,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=ACCENT,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=INK,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.5,
            textColor=INK,
            leftIndent=2,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=INK,
        ),
        "cell_h": ParagraphStyle(
            "cell_h",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=white,
        ),
        "foot": ParagraphStyle(
            "foot",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceBefore=16,
        ),
        "callout": ParagraphStyle(
            "callout",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=13,
            textColor=ACCENT,
            alignment=TA_LEFT,
            spaceBefore=2,
            spaceAfter=2,
        ),
    }


def bullets(items, st):
    return ListFlowable(
        [ListItem(Paragraph(i, st["bullet"]), leftIndent=8, bulletColor=ACCENT) for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=12,
        bulletFontSize=9,
        spaceBefore=2,
        spaceAfter=6,
    )


def section_table(headers, rows, col_widths, st):
    data = [[Paragraph(h, st["cell_h"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(c, st["cell"]) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("BACKGROUND", (0, 1), (-1, -1), SOFT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [SOFT, white]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("BOX", (0, 0), (-1, -1), 0.8, ACCENT),
            ]
        )
    )
    return t


def build():
    st = styles()
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Mosaic — Future Plan & Pilot Plan",
        author="Mosaic",
    )
    story = []

    story.append(Paragraph("Mosaic", st["title"]))
    story.append(
        Paragraph(
            "Future Plan &amp; Pilot Plan<br/>Cross-release mosaic defence for the TrustED PETs proving ground",
            st["subtitle"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceAfter=10))

    story.append(
        Paragraph(
            "<b>Approach.</b> We attack first. Measure the linkage join on unprotected "
            "releases, lock the baseline, protect with per-release HMAC tokens, then "
            "re-attack until the same join is 0/0 under a hard mosaic gate.",
            st["callout"],
        )
    )
    story.append(Spacer(1, 4))

    # --- Where we are ---
    story.append(Paragraph("1. Where we are today", st["h1"]))
    story.append(
        Paragraph(
            "The MVP path (P0–P7) is built: OPS-1 pack integrity, Attack A baseline "
            "(HETU <b>1622</b> / phone <b>1484</b>), protect for HEALTH-S1 and FIN-S2, "
            "re-attack, mosaic gate (PASS-1 zeros + PASS-2 baseline lock), scorecards, "
            "analyze HTML, and a narrated demo. Optional Groq agents (P8 A2) advise in "
            "shadow mode only — they never write <font face='Courier'>clean_data/</font> "
            "or flip a release PASS.",
            st["body"],
        )
    )

    # --- Future plan ---
    story.append(Paragraph("2. Future plan", st["h1"]))
    story.append(
        Paragraph(
            "The roadmap keeps the same loop — measure → derive requirement → protect → "
            "re-attack → gate — and widens scope without forking the architecture.",
            st["body"],
        )
    )

    story.append(Paragraph("2.1 Near term (product)", st["h2"]))
    story.append(
        bullets(
            [
                "<b>Widen scenarios.</b> Next pair: ENERGY-S3 × CS-S1 (widest phone glue; "
                "medical_device_priority payload). Always measure the raw baseline before protecting.",
                "<b>Restore FIN utility.</b> Include withheld <font face='Courier'>cards</font> / "
                "<font face='Courier'>card_transactions</font> under FIN-S2 so pets-eval utility "
                "and composite are meaningful (today they can be 0 while mosaic still PASSes).",
                "<b>Agent graduation (P8 A3→A4).</b> Shadow free-text helpers "
                "(<font face='Courier'>redact_assist</font> / "
                "<font face='Courier'>discover_assist</font>), then advisory pre-test that can "
                "delay a release but never auto-PASS. Start on HEALTH "
                "<font face='Courier'>chief_complaint</font>.",
                "<b>Gated apply path.</b> Human accept/reject of agent proposals recorded; "
                "deterministic gate remains the only PASS authority.",
            ],
            st,
        )
    )

    story.append(Paragraph("2.2 Medium term (platform)", st["h2"]))
    story.append(
        bullets(
            [
                "Multi-release mosaic matrix: any two outward scenarios that share glue types, "
                "with per-pair baselines and PASS-2 locks.",
                "Key rotation / recipient revocation runbook without rewriting historical "
                "releases incorrectly.",
                "Hardening free-text glue (notes, turns) once CS/energy enter scope — residual "
                "risk R-text outside the two-file MVP.",
                "CI packaging: one-command release evidence pack (gate JSON, scorecards, "
                "analyze HTML, OPS-1 verify) for auditors.",
            ],
            st,
        )
    )

    story.append(Paragraph("2.3 Longer term (adoption)", st["h2"]))
    story.append(
        bullets(
            [
                "Controller playbook: how a real data controller runs attack-first protect "
                "before shipping extracts to research / processor recipients.",
                "Policy alignment: document HMAC domains vs GDPR Art. 9 / processor contracts "
                "when live LLMs touch free text.",
                "Beyond proving-ground CSVs: connector adapters that preserve string dtypes "
                "and the same phone/HETU/IBAN normalisation recipe (R2).",
            ],
            st,
        )
    )

    # --- Pilot ---
    story.append(Paragraph("3. Pilot plan", st["h1"]))
    story.append(
        Paragraph(
            "A short, gated pilot with one data owner (or TrustED lab host) to prove "
            "attack-first defence on real release workflow — not a rewrite of Mosaic.",
            st["body"],
        )
    )

    story.append(Paragraph("3.1 Goals &amp; non-goals", st["h2"]))
    story.append(
        bullets(
            [
                "<b>Goals:</b> reproduce Attack A on agreed extracts; protect two recipient "
                "releases; show 0/0 re-join; deliver gate + scorecard + analyze evidence; "
                "optional agent brief for reviewers.",
                "<b>Non-goals:</b> editing vendored pack inputs; auto-applying LLM proposals; "
                "claiming official pets-eval judging; shipping keys or raw glue off-site.",
            ],
            st,
        )
    )

    story.append(Paragraph("3.2 Phases (6–8 weeks)", st["h2"]))
    story.append(
        section_table(
            ["Phase", "Weeks", "Activities", "Exit criteria"],
            [
                [
                    "0 — Align",
                    "1",
                    "Pick release pair &amp; recipients; threat story; success metrics; "
                    "data-handling rules (AR-4).",
                    "Signed scope note; OPS-1 / input integrity agreed.",
                ],
                [
                    "1 — Attack",
                    "1–2",
                    "Ingest extracts; run Attack A; lock baseline join counts; "
                    "positive control on known overlap.",
                    "Baseline numbers recorded; PASS-2 recipe fixed.",
                ],
                [
                    "2 — Defend",
                    "2–3",
                    "Protect with per-release HMAC; drop vs tokenise decisions; "
                    "re-attack; mosaic_check + scorecards.",
                    "PASS-1 = 0/0; PASS-2 matches Phase 1; verdict PASS.",
                ],
                [
                    "3 — Review",
                    "1",
                    "Analyze HTML + optional Groq advisory brief; human accept/reject log; "
                    "demo to stakeholders.",
                    "Evidence pack archived; go / no-go for wider rollout.",
                ],
                [
                    "4 — Next",
                    "1",
                    "Pilot retrospective; backlog (new pair / FIN tables / A3 text); "
                    "draft controller playbook.",
                    "Written next-phase plan with owners.",
                ],
            ],
            [22 * mm, 16 * mm, 72 * mm, 55 * mm],
            st,
        )
    )

    story.append(Paragraph("3.3 Roles &amp; success metrics", st["h2"]))
    story.append(
        bullets(
            [
                "<b>Roles:</b> Pilot lead (scope), Mosaic engineer (pipeline/gate), "
                "data steward (keys + extracts), reviewer (accept/reject proposals).",
                "<b>Must-pass:</b> raw join measurable; protected join 0 on agreed keys; "
                "OPS-1 / integrity verify; no raw HETU/phone/IBAN/email in agent egress.",
                "<b>Target:</b> stakeholder can explain attack-first in one slide; "
                "evidence pack reusable without retuning baselines.",
            ],
            st,
        )
    )

    story.append(Paragraph("3.4 Risks &amp; mitigations", st["h2"]))
    story.append(
        section_table(
            ["Risk", "Mitigation"],
            [
                [
                    "Scope creep into many datasets",
                    "One pair only; measure-first rule before any new table.",
                ],
                [
                    "Utility looks ‘broken’ (FIN composite 0)",
                    "Separate mosaic PASS from pets-eval utility; document withheld tables.",
                ],
                [
                    "LLM leaks identifiers",
                    "AR-4 contracts; agents advisory; kill-switch to deterministic path.",
                ],
                [
                    "Baseline drift / tampered inputs",
                    "OPS-1 SHA-256 verify before and after runs.",
                ],
            ],
            [55 * mm, 110 * mm],
            st,
        )
    )

    story.append(Paragraph("4. Immediate next actions", st["h1"]))
    story.append(
        bullets(
            [
                "Confirm pilot host, release pair, and calendar (Phase 0).",
                "Freeze demo evidence from current HEALTH-S1 × FIN-S2 PASS as the reference pack.",
                "Open backlog tickets: ENERGY×CS measure-first; FIN cards inclusion; "
                "P8 A3 shadow on <font face='Courier'>chief_complaint</font>.",
            ],
            st,
        )
    )

    story.append(
        Paragraph(
            "Mosaic · Future &amp; Pilot Plan · grounded in README.md and findings/MVP_Plan.md",
            st["foot"],
        )
    )

    doc.build(story)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
