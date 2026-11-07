# Task

Fix the **demo / instruction narrative** so it matches real defence practice
(**attack first → defend from the attack → show metrics**), and stop teaching
users that FIN-S2 “protection” means blank dropping of glue columns when the
goal is to **transform data into a safe form while retaining usable fields**.

## Problem (coordinator notes)

1. `bash scripts/final/run_release.sh` currently does protect → shadow
   attack-sim on `clean_data/` → mosaic gate. Shadow on already-protected
   releases correctly reports **0 joins**, which feels like “no attack found”
   rather than “attack succeeded on raw, then defence closed it”.
2. `DEMO.md` / `USAGE.md` still lead with protect-first and split the story
   across two files. Gather them into one **`INSTRUCTION.md`** that walks:
   attacker trigger on raw → defence → metrics / scorecard comparing
   original vs `clean_data/`.
3. FIN-S2 currently **drops** `hetu` / `phone` / `iban` / `email`. That is
   the wrong product story for “retain safe information”. Prefer transforms
   (keyed tokenise / generalise / redact) that keep columns present in a
   non-joinable form — **without inventing LLM calls**.
4. **Do not modify `resources/`.** Read pack docs (PET playbook, FIN-S2
   scenario, threat model) for evidence only.
5. **Groq / LLM agent integration is incoming from a teammate.** Do **not**
   touch LLM-provider wiring or agent files that exist only to host that
   integration. Keep `app/agent_graph.py`, `app/agent_runtime.py`, and any
   Groq-related stubs untouched unless a one-line import path break forces
   a mechanical fix. If a proposed FIN-S2 change **requires** an LLM to
   rewrite free text / decide drops, **document it in INSTRUCTION.md /
   findings and leave the code for the teammate** — do not invent a fake
   LLM path.

## Deliverables

1. **`INSTRUCTION.md`** at repo root — single runbook replacing the user-
   facing role of `DEMO.md` + `USAGE.md` (update those two to short
   pointers to `INSTRUCTION.md`, or delete content duplication). Flow must
   be explicit:
   - OPS-1 verify
   - **Attack on raw** (baseline / attack-sim `--raw-pack` or equivalent)
     showing 1622 / 1484 and the worked-example dossier
   - **Defend** (`run_protect`) driven by that attack (keyed tokens / safe
     transforms — not “drop everything”)
   - **Re-attack / gate** on `clean_data/` (0 / 0) + mosaic PASS
   - **Metrics** — mosaic before/after + pets-eval scorecard pointers /
     B1–B2 charts for easy compare
2. **Demo / release UX** — reorder or re-narrate so the first attack the
   user sees is on **unprotected** data. Prefer changing
   `app/run_demo.py` and/or `scripts/final/run_release.sh` +
   `scripts/final/STEPS.md` so P2 shadow is not the only story and is
   clearly “after defence”. Keep exit codes and OPS-1 guards intact.
3. **FIN-S2 protection without blank drop** — investigate pack FIN-S2
   requirements. If non-LLM transforms suffice (HMAC tokenise of glue
   instead of drop, keep utility columns, generalise QIDs), implement in
   `app/pet_pipeline.py` / `app/run_protect.py` and update CLAUDE.md’s
   “never tokenise FIN-S2” rule to match the new policy. If only an LLM
   can safely “retain meaning”, **do not fake it** — document the gap and
   leave pipeline drop behaviour with an honest TODO pointing at the
   teammate Groq agent.
4. **Docs sync** — `README.md`, `CLAUDE.md` Commands, `scripts/final/STEPS.md`
   point at `INSTRUCTION.md` and the attack→defend→measure order.
5. Verification commands (coder + coordinator):
   - `bash scripts/final/ops1_manifest.sh verify`
   - `bash scripts/final/measure_baseline.sh` → 1622 / 1484
   - Demo path that shows raw attack **before** protected zeros
   - `bash scripts/final/mosaic_check.sh` still PASS (0/0 + 1622/1484)
   - If FIN-S2 now tokenises: confirm columns still present but joins are 0;
     re-run protect if needed (new key behaviour)
   - Nothing under `resources/` modified

# Notes

- Trunk is `main`. Work on `task/<slug>`, then coordinator merges.
- Conventional Commits.
- Never commit `keys/` or `clean_data/`.
- Do not retune 1622 / 1484.
- Pass-1 alone is not release-safe without Pass-2.
