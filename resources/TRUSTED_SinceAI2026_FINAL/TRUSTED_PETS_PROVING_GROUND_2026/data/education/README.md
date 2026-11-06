# Education — student records (synthetic)

Upper-secondary (general, IB) and vocational students in Southwest Finland, academic years 2022-23 to 2024-25. Schools are fictional; students are synthetic residents born 2004-2008. Course codes follow the style of the 2021 Finnish upper-secondary curriculum but are approximate, not an official code list.

## Tables

| table | rows | content |
|---|---|---|
| students | 5,161 | one row per student: identity, address, guardians, school, programme, support, status |
| course_grades | 152,026 | module / unit / IB subject grades (scales 4-10, S/H, 1-5, IB 1-7) |
| absences | 19,561 | excused and unexcused hours per term |
| matriculation_results | 12,649 | matriculation exam results (general upper secondary) |
| counsellor_notes | 3,820 | free-text guidance and student-welfare notes (fi/sv/en) |

Join key: `student_id`. Ground truth: `metadata/field_catalog.csv`, `metadata/pii_spans/education__counsellor_notes__note_text.jsonl`, `truth/education__*.csv`.

## Sharing scenarios

- **EDU-S1 Statistics publication for the education authority** — Publish grade, completion and drop-out statistics by school, programme, sex and language group. Utility tasks: EDU-U1, EDU-U5, EDU-U6, EDU-U3.
- **EDU-S2 Ed-tech vendor training a drop-out early-warning model** — Train a model that predicts drop-out risk from grades and absences. Utility tasks: EDU-U2, EDU-U4.
- **EDU-S3 Researcher studying grade gaps** — Analyse gender and language-group gaps in maths and matriculation results. Utility tasks: EDU-U3, EDU-U5, EDU-U1.

## Utility tasks (pets_eval.utility.education)

- EDU-U1 mean grade by school × subject (4-10 scale)
- EDU-U2 drop-out model AUC: train on protected, test on original
- EDU-U3 gender gap in maths grades
- EDU-U4 correlation of unexcused absences with mean grade (needs student_id join)
- EDU-U5 matriculation grade distribution by subject
- EDU-U6 drop-out rate by programme

## Attacker knowledge

- `adversary/graduation_lists.csv` (2,327 rows): newspaper lists of new graduates.
- `adversary/sports_club_rosters.csv` (809 rows): junior team rosters with birth years.
- A stronger classmate-knowledge attacker is held by the organisers.

## Things to watch

- Several columns that look harmless reveal special-category data. Check course codes carefully.
- Small schools and programmes. Twins.
- Grades come on four different scales.
- The notes contain more than names.
