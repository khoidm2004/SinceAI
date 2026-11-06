# Unseen dataset: HR / payroll export (detection challenge)

`export_2025_q4.csv` (2,818 rows, 26 columns) is an export from the HR and payroll system of **Kaarna Care Oy**,
a fictional care-services company in the Turku region. All people and values are synthetic.

Column names are deliberately uninformative (`c01` … `c26`) and formats are mixed, as in real exports that arrive
without documentation. **No labels are provided.** Use it to test whether your tool can detect what each column contains
(identifiers, quasi-identifiers, sensitive attributes, free text) from the values alone, and to show your tool working on
data it has never seen.

Organisers hold the field labels and the PII spans of the free-text column and can score detection results.
Submission format for scoring: a CSV with columns `column,privacy_role,subtype` (vocabularies in
`metadata/taxonomy.md`), and optionally a JSONL of detected text spans
(`record_id`, `spans` with `start`, `end`, `label`) for the free-text column.
