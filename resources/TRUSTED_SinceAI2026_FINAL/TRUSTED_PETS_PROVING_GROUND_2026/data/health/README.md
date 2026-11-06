# Health — Aurajoki Regional Hospital emergency department, 2025 (synthetic)

Aurajoki Regional Hospital is fictional. Every patient, visit, note and measurement is synthetic; postcodes and
municipality names are real geography of Southwest Finland.

## Tables

| Table | Rows | What it is |
|---|---|---|
| `ed_visits.csv` | 46,398 | One row per ED visit: patient identity, arrival, triage, diagnoses, vitals, physician, disposition |
| `lab_results.csv` | 130,341 | Lab results in long format, joined by `visit_id` |
| `clinical_notes.csv` | 30,103 | Physician and triage-nurse notes in Finnish, Swedish or English |
| `published_weekly_stats.csv` | 30,169 | An "official" weekly table: municipality × age band × sex × diagnosis group. Unsuppressed on purpose |

Triage is the Finnish ABCDE scale: A immediate, B within 10 min, C within 1 h, D within 2 h, E non-urgent.
Seasonality is built in: influenza peak in February, RSV in December–January, norovirus in winter, icy-pavement
fractures in January–February, Midsummer (20–21 June) and New Year injuries, weekend-night intoxication.

## Sharing scenarios

- **HEALTH-S1 — Secondary-use research in a controlled environment.** Analyse length of stay, revisits and diagnosis patterns. Utility tasks: H-U2, H-U4, H-U6, H-U7, H-U8.
- **HEALTH-S2 — Public weekly dashboard.** Weekly ED load, influenza-like illness and injury trends by age band and municipality. Utility tasks: H-U1, H-U8, H-DP.
- **HEALTH-S3 — AI vendor training a triage-support model.** Train a model predicting admission from triage-time information. Utility tasks: H-U3, H-U5, H-U2.

## Utility tasks (pets_eval.utility.health)

H-U1 weekly ILI counts by age band · H-U2 median length of stay by triage · H-U3 admission model trained on protected,
tested on original · H-U4 diagnosis mix by municipality · H-U5 vital-sign distributions · H-U6 30-day revisit rate by
age band · H-U7 CRP–temperature relationship (needs the lab join) · H-U8 hour-of-day arrival curve.
`metadata/dp_query_workload_health.json` holds 254 queries for differential-privacy experiments (H-DP).

## Things to watch

Identifiers hide in more places than the obvious columns: codes that encode attributes, free text, timestamps,
call signs, rare diagnoses, staff names and the published statistics. Spans for every identifying item in
`chief_complaint` and `note_text` are in `metadata/pii_spans/`. Attacker files: `adversary/news_clips_health.csv`,
`adversary/social_posts_health.csv`, plus `adversary/public_directory.csv`.
