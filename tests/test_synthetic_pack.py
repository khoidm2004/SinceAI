"""Synthetic Health + Finance test pack: generator, pipeline integration and evaluation tests.

Uses the small 'smoke' profile in pytest's tmp_path (never test_data/, clean_data/, keys/ or resources/).
Smoke-sized numbers are for correctness checks only, not for privacy/utility conclusions.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import attack_sim
import generate_test_data as gen
import measure_baseline
import pet_pipeline
import report_test_pack
import run_test_attack
import run_test_pack
import run_test_scorecards
import validate_test_pack
from normalize import normalize_hetu, normalize_phone
from synth_common import RELEASE_TABLES, read_csv, read_header, read_json, refuse_forbidden, run_dirs, sha256_file, tree_hashes, REPO_ROOT

SEED = 424242


def _gen(root: Path, run_id: str, seed: int = SEED) -> Path:
    assert gen.main(["--profile", "smoke", "--seed", str(seed), "--out-root", str(root), "--run-id", run_id]) == 0
    return root / run_id


@pytest.fixture(scope="module")
def run(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("synth")
    r = _gen(root, "smoke-a")
    assert run_test_pack.main(["--run-dir", str(r), "--init-key"]) == 0
    assert run_test_attack.main(["--run-dir", str(r)]) == 0
    return r


# ---------------------------------------------------------------- generator
def test_same_seed_identical_and_different_seed_differs(tmp_path, run):
    a = tree_hashes(run_dirs(run)["pack"])
    b = tree_hashes(run_dirs(_gen(tmp_path, "smoke-b"))["pack"])
    assert a == b
    c = tree_hashes(run_dirs(_gen(tmp_path, "smoke-c", seed=SEED + 1))["pack"])
    assert a["data/health/ed_visits.csv"] != c["data/health/ed_visits.csv"]


def test_manifest_overlaps_match_independent_recount(run):
    d = run_dirs(run)
    m = read_json(d["evidence"] / "manifest.json")
    ed, _ = read_csv(d["pack"] / "data" / "health" / "ed_visits.csv")
    cu, _ = read_csv(d["pack"] / "data" / "finance" / "customers.csv")
    hetu = len(({normalize_hetu(r["patient_hetu"]) for r in ed} - {""}) & ({normalize_hetu(r["hetu"]) for r in cu} - {""}))
    phone = len(({normalize_phone(r["phone"]) for r in ed} - {""}) & ({normalize_phone(r["phone"]) for r in cu} - {""}))
    assert m["overlaps"]["hetu_overlap"] == hetu > 0
    assert m["overlaps"]["phone_overlap_normalised"] == phone > 0
    assert m["overlaps"]["hetu_collisions_between_different_people"] == 0
    assert m["overlaps"]["phone_collisions_between_different_people"] == 0


def test_shared_population_reflected_in_relationships(run):
    d = run_dirs(run)
    pop, _ = read_csv(d["private"] / "population.csv")
    both = {r["person_id"] for r in pop if r["membership"] == "both"}
    t_ed = {r["person_id"] for r in read_csv(d["pack"] / "truth" / "health__ed_visits.csv")[0] if r["person_id"]}
    t_cu = {r["person_id"] for r in read_csv(d["pack"] / "truth" / "finance__customers.csv")[0]}
    assert (t_ed & t_cu) == both
    assert read_json(d["evidence"] / "manifest.json")["population"]["shared_subjects"] == len(both)


def test_validation_against_official_metadata_and_conventions(run):
    res = validate_test_pack.validate(run_dirs(run)["pack"])
    assert res["all_ok"], res["failed"]  # integrity; smoke may legitimately be below the scorecard task minimums
    assert all(c["kind"] in ("integrity", "readiness") for c in res["checks"])
    names = " ".join(c["check"] for c in res["checks"])
    for must in ("header identical", "unique record ids", "FK card_transactions.card_pan", "HETU: individual number 900-999",
                 "IBAN: FI, mod-97", "public test BIN + Luhn", ".example", "finance period", "PII spans health__clinical_notes"):
        assert must in names


def test_row_counts_and_column_order(run):
    d = run_dirs(run)
    m = read_json(d["evidence"] / "manifest.json")
    for (ds, tb), cols in gen.SCHEMA.items():
        rows, hdr = read_csv(d["pack"] / "data" / ds / f"{tb}.csv")
        assert hdr == cols
        assert m["tables"][f"data/{ds}/{tb}"]["rows"] == len(rows)


def test_span_validator_rejects_bad_offsets():
    assert gen.validate_spans("abc def", [{"start": 4, "end": 7, "label": "PERSON", "text": "def"}]) == []
    assert gen.validate_spans("abc def", [{"start": 3, "end": 7, "label": "PERSON", "text": "def"}])
    assert gen.validate_spans("abc def", [{"start": 0, "end": 3, "label": "X", "text": "abc"}, {"start": 2, "end": 5, "label": "Y", "text": "c d"}])


def test_identifier_helpers():
    assert gen.hetu_ok(gen.make_hetu(gen.date(1990, 1, 1), "M", 901))
    assert gen.iban_ok(gen.make_iban("90012345678901"))
    body = "411111" + "123456789"
    assert gen.luhn_ok(body + gen.luhn_digit(body))
    assert all(normalize_phone(f) == "0401234567" for f in gen.phone_formats("0401234567"))


# ---------------------------------------------------------------- pipeline integration
def test_runner_reuses_existing_pet_implementation():
    assert run_test_pack.protect_table is pet_pipeline.protect_table


@pytest.mark.parametrize("policy", ["current", "relational"])
def test_every_table_protected_rows_kept_rowmaps_private(run, policy):
    d = run_dirs(run)
    ev = read_json(d["evidence"] / f"protection_{policy}.json")
    for sid, (ds, tables) in RELEASE_TABLES.items():
        rel = f"{ds}__{sid}"
        for t, _ in tables:
            assert (d["protected"] / policy / rel / f"{t}.csv").is_file()
            assert not (d["protected"] / policy / rel / f"rowmap_{t}.csv").exists()  # never next to the release
            assert (d["private"] / "rowmaps" / policy / rel / f"rowmap_{t}.csv").is_file()
            tr = ev["releases"][sid]["tables"][t]
            assert tr["rows_in"] == tr["rows_out"] and tr["rowmap"]["aligned"] and tr["column_order_preserved"]


def test_actions_recorded_match_protect_table(run):
    d = run_dirs(run)
    ev = read_json(d["evidence"] / "protection_current.json")
    rows, fields = read_csv(d["pack"] / "data" / "health" / "ed_visits.csv")
    clf = run_test_pack.classify(d["pack"], "health", "ed_visits")
    _, out_fields, actions = pet_pipeline.protect_table(rows, fields, dataset="health", table="ed_visits", scenario_id="HEALTH-S1", classifier=clf, subkey=b"x" * 32)
    tr = ev["releases"]["HEALTH-S1"]["tables"]["ed_visits"]
    assert tr["dropped"] == actions["dropped"] and tr["columns_out_list"] == out_fields


def test_relationships_current_vs_relational(run):
    d = run_dirs(run)
    cur = {j["child"]: j["status"] for r in read_json(d["evidence"] / "protection_current.json")["releases"].values() for j in r["relationships"]}
    rel = {j["child"]: j["status"] for r in read_json(d["evidence"] / "protection_relational.json")["releases"].values() for j in r["relationships"]}
    assert set(rel.values()) == {"PRESERVED"}
    assert cur["lab_results.visit_id"] == "BROKEN_INCONSISTENT_TRANSFORM"      # record key passthrough vs tokenised FK
    assert cur["card_transactions.card_pan"] == "BROKEN_COLUMN_DROPPED"        # card_pan is a non-tokenised direct identifier
    # joinable in the actual protected files (relational)
    lab, _ = read_csv(d["protected"] / "relational" / "health__HEALTH-S1" / "lab_results.csv")
    ed, _ = read_csv(d["protected"] / "relational" / "health__HEALTH-S1" / "ed_visits.csv")
    assert {r["visit_id"] for r in lab} <= {r["visit_id"] for r in ed}


def test_protected_output_readable_by_repository_modules(run):
    base = run_dirs(run)["protected"] / "relational"
    res = attack_sim.simulate_attack(base / "health__HEALTH-S1" / "ed_visits.csv", base / "finance__FIN-S2" / "customers.csv", sample_limit=0,
                                     **run_test_attack.COLUMNS)
    assert res["hetu_join"] == 0


def test_raw_identifier_survival_detects_free_text_leak(run):
    tr = read_json(run_dirs(run)["evidence"] / "protection_current.json")["releases"]["HEALTH-S1"]["tables"]
    assert tr["ed_visits"]["raw_identifier_survival"]["total"] == 0
    assert tr["clinical_notes"]["raw_identifier_survival"]["total"] > 0     # free text is passed through by the current pipeline
    assert all("note_text" in k for k in tr["clinical_notes"]["raw_identifier_survival"]["survivors"])


def test_refuses_forbidden_output_locations():
    for p in (REPO_ROOT / "clean_data" / "x", REPO_ROOT / "resources" / "x", REPO_ROOT / "keys" / "k", REPO_ROOT / ".env"):
        with pytest.raises(ValueError):
            refuse_forbidden(p)


# ---------------------------------------------------------------- evaluation
def test_custom_baseline_dynamic_and_official_constants_unchanged(run):
    d = run_dirs(run)
    raw = read_json(d["evidence"] / "attack_raw.json")
    m = read_json(d["evidence"] / "manifest.json")
    assert raw["keys"]["hetu"]["join"] == m["overlaps"]["hetu_overlap"]
    assert raw["keys"]["phone"]["join"] == m["overlaps"]["phone_overlap_normalised"]
    assert raw["keys"]["hetu"]["false_links"] == 0
    assert (measure_baseline.EXPECTED_HETU, measure_baseline.EXPECTED_PHONE) == (1622, 1484)
    assert raw["official_attack_a_constants_unchanged"]["used_for_this_pack"] is False


def test_missing_column_is_not_measured_not_a_zero(run):
    ap = read_json(run_dirs(run)["evidence"] / "attack_protected.json")
    assert ap["current"]["keys"]["phone"]["status"] == "NOT_MEASURED" and ap["current"]["keys"]["phone"]["join"] is None
    assert ap["current"]["keys"]["hetu"]["status"] == "MEASURED" and ap["current"]["keys"]["hetu"]["join"] == 0


def test_attack_on_synthetic_missing_column(tmp_path):
    h, f = tmp_path / "h.csv", tmp_path / "f.csv"
    h.write_text("visit_id,patient_hetu\nV1,x\n", encoding="utf-8")
    f.write_text("customer_id,hetu,phone\nC1,x,0401234567\n", encoding="utf-8")
    r = run_test_attack.attack(h, f)
    assert r["keys"]["hetu"]["status"] == "MEASURED" and r["keys"]["hetu"]["join"] == 1
    assert r["keys"]["phone"]["status"] == "NOT_MEASURED"


def test_scorecards_bound_to_exact_files_and_report_clean(run):
    import sys

    if run_test_scorecards._run([sys.executable, "-c", "import pets_eval"], run).returncode != 0:
        pytest.skip("pets-eval not installed in this interpreter")
    assert run_test_scorecards.main(["--run-dir", str(run), "--policy", "relational"]) in (0, 1)
    d = run_dirs(run)
    sc = read_json(d["evidence"] / "scorecards.json")
    for key, r in sc.items():
        assert r["scorecard_returncode"] == 0, r.get("error_tail")
        assert r["binding_ok"], r["binding_problems"]
        rel = key.split("/")[1]
        ds = RELEASE_TABLES[rel][0]
        sj = d["evidence"] / "scorecards" / "relational" / f"{ds}__{rel}" / "scorecard.json"
        assert sha256_file(sj) == r["scorecard_sha256"]
        assert Path(read_json(sj)["original"]).resolve() == (d["pack"] / "data" / ds).resolve()   # scored against the synthetic pack
        for t, h in r["protected_csv_sha256"].items():
            assert sha256_file(d["protected"] / "relational" / f"{ds}__{rel}" / t) == h
        assert {u["id"] for u in r["utility"]} == set(read_json(d["pack"] / "metadata" / "scenarios.json")[0 if rel == "HEALTH-S1" else 1]["utility_requirements"])
        for u in r["utility"]:
            assert (u["score"] is None) == (not u["answerable"])   # unavailable is never turned into 0
    validate_test_pack.main(["--run-dir", str(run), "--skip-official-baseline"])
    assert report_test_pack.main(["--run-dir", str(run)]) == 0
    rep = read_json(d["reports"] / "report.json")
    assert all(s["clean"] for s in rep["leak_scan"].values())
    html = (d["reports"] / "index.html").read_text(encoding="utf-8")
    assert "http://" not in html and "https://" not in html and "<script src" not in html


def test_official_attack_a_still_reproduces(tmp_path):
    res = validate_test_pack.official_baseline(tmp_path / "official_baseline.json")
    assert res["verdict"] == "PASS"
    assert res["observed"] == {"hetu_health_finance": 1622, "phone_health_finance": 1484}
