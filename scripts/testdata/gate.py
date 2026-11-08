#!/usr/bin/env python3
"""Test-pack gate (analogous to app/mosaic_check.py) for a synthetic run directory.

Stdlib only. Reads the run's evidence files and writes evidence/mosaic_check.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FORBIDDEN_ROOTS = (REPO_ROOT / "resources", REPO_ROOT / "clean_data", REPO_ROOT / "keys")


def is_inside(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def refuse_forbidden(path: Path, what: str = "path") -> None:
    p = Path(path).resolve()
    for root in FORBIDDEN_ROOTS:
        if is_inside(p, root):
            raise ValueError(f"refusing to use {what} under {root.name}/: {p}")
    if p.name == ".env":
        raise ValueError(f"refusing to use {what} as .env")


def parse_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if "/" in value:
            part = value.split("/", 1)[0].strip()
            try:
                return int(part)
            except ValueError:
                pass
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def die(msg: str, code: int = 2) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return code


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Test-pack gate for a synthetic run directory")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    try:
        refuse_forbidden(run_dir, "run directory")
    except ValueError as exc:
        return die(str(exc))

    out_path = args.out
    if out_path is None:
        out_path = run_dir / "evidence" / "mosaic_check.json"
    out_path = Path(out_path).resolve()
    try:
        refuse_forbidden(out_path, "output path")
    except ValueError as exc:
        return die(str(exc))

    ev = run_dir / "evidence"
    required = [ev / "validation.json", ev / "manifest.json", ev / "attack_raw.json", ev / "attack_protected.json"]
    for rp in required:
        if not rp.is_file():
            return die(f"missing required file: {rp}")

    try:
        validation = load_json(ev / "validation.json")
        manifest = load_json(ev / "manifest.json")
        attack_raw = load_json(ev / "attack_raw.json")
        attack_protected = load_json(ev / "attack_protected.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return die(f"invalid JSON input: {exc}")

    protection_relational = None
    pr_path = ev / "protection_relational.json"
    if pr_path.is_file():
        try:
            protection_relational = load_json(pr_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return die(f"invalid JSON input: {exc}")

    pack_root = (run_dir / "pack").resolve()
    protected_root = (run_dir / "protected").resolve()

    # validation block
    checks_list = validation.get("checks", [])
    if not isinstance(checks_list, list):
        checks_list = []
    validation_block = {
        "all_ok": validation.get("all_ok"),
        "scorecard_ready": validation.get("scorecard_ready"),
        "checks": len(checks_list) if checks_list else validation.get("checks", 0),
        "ok": validation.get("passed", sum(1 for c in checks_list if c.get("ok"))),
        "integrity_passed": parse_int(validation.get("integrity_passed")),
    }

    # pass2 raw
    overlaps = manifest.get("overlaps", {})
    raw_keys = attack_raw.get("keys", {})
    pass2_raw: Dict[str, Any] = {}
    for key in ("hetu", "phone"):
        e = raw_keys.get(key, {})
        status = e.get("status", "UNKNOWN")
        observed = e.get("join", None)
        if key == "hetu":
            expected = overlaps.get("hetu_overlap")
        else:
            expected = overlaps.get("phone_overlap_normalised")
        if status == "MEASURED":
            passed = (observed == expected)
        else:
            passed = None
        pass2_raw[key] = {
            "status": status,
            "observed": observed,
            "expected": expected,
            "pass": passed,
        }

    # pass1 protected
    pass1_protected: Dict[str, Any] = {}
    for policy, res in attack_protected.items():
        if not isinstance(res, dict):
            continue
        keys = res.get("keys", {})
        hetu_e = keys.get("hetu", {})
        phone_e = keys.get("phone", {})
        hetu_status = hetu_e.get("status", "UNKNOWN")
        hetu_join = hetu_e.get("join", None)
        hetu_block = {
            "status": hetu_status,
            "observed": hetu_join,
            "expected": 0,
            "pass": (hetu_status == "MEASURED" and hetu_join == 0),
        }
        phone_status = phone_e.get("status", "UNKNOWN")
        phone_join = phone_e.get("join", None)
        if phone_status == "MEASURED":
            phone_block = {
                "status": "MEASURED",
                "observed": phone_join,
                "expected": 0,
                "pass": (phone_join == 0),
            }
        elif phone_status == "NOT_MEASURED":
            phone_block = {
                "status": "NOT_MEASURED",
                "observed": None,
                "expected": 0,
                "pass": None,
                "caveat": "phone join NOT MEASURED (column dropped); not counted as protection",
            }
        else:
            phone_block = {
                "status": phone_status,
                "observed": phone_join,
                "expected": 0,
                "pass": False,
            }
        pass1_protected[policy] = {
            "hetu": hetu_block,
            "phone": phone_block,
        }

    # relationships (informational)
    relationships: Dict[str, Any] = {}
    if isinstance(protection_relational, dict):
        statuses: List[str] = []
        for sid, rr in (protection_relational.get("releases") or {}).items():
            if not isinstance(rr, dict):
                continue
            for j in (rr.get("relationships") or []):
                if isinstance(j, dict):
                    statuses.append(j.get("status"))
        preserved = sum(1 for s in statuses if s == "PRESERVED")
        total = len(statuses)
        relationships["relational"] = {
            "all_preserved": (preserved == total),
            "preserved": preserved,
            "total": total,
        }

    # caveats
    caveats: List[str] = []
    for policy, block in pass1_protected.items():
        phone = block.get("phone", {})
        if phone.get("status") == "NOT_MEASURED":
            c = phone.get("caveat", "phone join NOT MEASURED (column dropped); not counted as protection")
            if c not in caveats:
                caveats.append(c)

    # verdict
    validation_ok = (validation_block["all_ok"] is True and validation_block["scorecard_ready"] is True)
    raw_ok = (pass2_raw.get("hetu", {}).get("pass") is True and pass2_raw.get("phone", {}).get("pass") is True)
    policies_present = len(pass1_protected) >= 1
    every_hetu_pass = all(pass1_protected[p].get("hetu", {}).get("pass") is True for p in pass1_protected)
    no_measured_phone_gt0 = all(
        not (pass1_protected[p].get("phone", {}).get("status") == "MEASURED"
             and (pass1_protected[p].get("phone", {}).get("observed") or 0) > 0)
        for p in pass1_protected
    )
    verdict = "PASS" if (validation_ok and raw_ok and policies_present and every_hetu_pass and no_measured_phone_gt0) else "FAIL"

    report = {
        "schema": "sinceai.testdata_gate.v1",
        "run": run_dir.name,
        "pack_root": str(pack_root),
        "protected_root": str(protected_root),
        "validation": validation_block,
        "pass2_raw": pass2_raw,
        "pass1_protected": pass1_protected,
        "relationships": relationships,
        "caveats": caveats,
        "verdict": verdict,
    }

    # print mosaic_check-style table
    print("SinceAI test-pack gate — health ∩ finance")
    print(f"  run:        {run_dir.name}")
    print(f"  pack:       {pack_root}")
    print(f"  protected:  {protected_root}")
    print()
    print("  join                        observed   expected   result")
    for key in ("hetu", "phone"):
        b = pass2_raw[key]
        obs = "n/a" if b["observed"] is None else str(b["observed"])
        res_str = "PASS" if b["pass"] is True else ("FAIL" if b["pass"] is False else "n/a")
        print(f"  raw {key:<5} health ∩ finance   {obs:>8}   {b['expected']:>8}   {res_str}")
    for policy in pass1_protected:
        for key in ("hetu", "phone"):
            b = pass1_protected[policy][key]
            obs = "n/a" if b["observed"] is None else str(b["observed"])
            if b["pass"] is True:
                res_str = "PASS"
            elif b["pass"] is False:
                res_str = "FAIL"
            else:
                res_str = "n/a"
            print(f"  {policy:<8} {key:<5}              {obs:>8}   {b['expected']:>8}   {res_str}")
    print()
    print(f"VERDICT: {verdict}")
    for c in caveats:
        print(f"caveat: {c}")

    # write JSON
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if verdict == "PASS":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
