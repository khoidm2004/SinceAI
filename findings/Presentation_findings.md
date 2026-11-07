- Idea: A linkage attack is when attackers collect many pieces that seem harmless, combine them, then infer something sensitive that no single piece discloses.
- Why it is strong
    - Low-cost and passive
    - Hard to detect — attacker only puzzles with existing data
    - Cumulative: each new release helps the attacker ⇒ hurts the defender
    - Often bypasses per-release protection
    
- HETU = Finnish personal identity code (*henkilötunnus*), e.g. `021280-9730` — near-perfect person key across controllers
- **1622 (HETU join):** number of distinct people who appear in *both* health and finance with the **same HETU** — not a row count.
  How to calculate: unique non-empty HETUs in `ed_visits.patient_hetu` ∩ unique non-empty HETUs in `customers.hetu` → **|intersection| = 1622**.
- **1484 (phone join):** number of distinct people who appear in *both* releases with the **same normalised phone** — a second glue key; lower than 1622 because phones are often blank or oddly formatted.
  How to calculate: normalise phones (strip non-`[0-9+]`, `+358`/`00358` → `0`), then unique phones in health ∩ unique phones in finance → **|intersection| = 1484**.

- Scorecard metrics (pets-eval; self-assessment, not official judging — see pack `docs/EVALUATION.md`)
    - **Privacy** (0–1, higher = safer): how much re-ID / leakage risk remains.
      Built from risk components (0 = none, 1 = maximal): direct IDs retained, reversible hashes, share of rows with k&lt;5, linkage attacks, free-text leakage, …
      Formula: `privacy = 1 − (0.5 × worst risk + 0.5 × mean risk)` — worst counts on purpose (one open door is enough).
    - **Utility** (0–1, higher = more useful): can the recipient still answer the scenario’s tasks?
      Each required task scores original vs protected in [0, 1]; required but unanswerable → 0.
      Formula: mean of those task scores.
      Note: FIN-S2 utility can be **0** here because FIN-U1/U4/U6 need `cards` / `card_transactions` (withheld); only `customers.csv` is released — mosaic join defence can still be fine.
    - **Composite** (0–1): privacy and utility together — weighted harmonic mean (privacy ×30, utility ×25).
      If either side is 0, composite is **0** (cannot look good by releasing nothing or everything).

- **OPS-1** — pack integrity safeguard (not a privacy PET, not Attack A).
    - Committed SHA-256 manifest of vendored pack `data/` files: `manifests/pack_data_sha256.json`.
    - Before and after `run_release.sh` / demo / benchmark: verify hashes still match → pack was not silently edited.
    - Fails the run if someone tampers with proving-ground inputs (so baselines like 1622/1484 stay honest).
    - Command: `bash scripts/final/ops1_manifest.sh verify` (expect `verify OK`).
