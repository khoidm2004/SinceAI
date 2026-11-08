"""Shared helpers for the synthetic Health + Finance test pack (stdlib only).

Directory rules (enforced here, used by every test-pack CLI):
  * nothing is ever written under resources/, clean_data/ or keys/ (or to .env);
  * every generated run lives in its own new directory under test_data/generated/<run_id>/;
  * row maps and keys live under <run>/private/ and are never part of a public export.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_PACK = REPO_ROOT / "resources" / "TRUSTED_SinceAI2026_FINAL" / "TRUSTED_PETS_PROVING_GROUND_2026"
DEFAULT_GENERATED_ROOT = REPO_ROOT / "test_data" / "generated"
FORBIDDEN_ROOTS = (REPO_ROOT / "resources", REPO_ROOT / "clean_data", REPO_ROOT / "keys")

# Scenario -> (dataset, [(table, record_key)]) in release order. Tables needed by the scenario's
# utility tasks (pets-eval utility/health.py, utility/finance.py), not just the official P1 table.
RELEASE_TABLES: Dict[str, tuple] = {
    "HEALTH-S1": ("health", [("ed_visits", "visit_id"), ("lab_results", "lab_id"), ("clinical_notes", "note_id")]),
    "FIN-S2": ("finance", [("customers", "customer_id"), ("cards", "card_ref_id"), ("card_transactions", "tx_id")]),
}


def is_inside(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def refuse_forbidden(path: Path, what: str = "output") -> None:
    """Raise if `path` is (inside) resources/, clean_data/, keys/ or is the .env file."""
    p = Path(path).resolve()
    for root in FORBIDDEN_ROOTS:
        if is_inside(p, root):
            raise ValueError(f"refusing to write {what} under {root.name}/: {p}")
    if p.name == ".env" or p == (REPO_ROOT / ".env").resolve():
        raise ValueError(f"refusing to write {what} to .env")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tree_hashes(root: Path, exclude: Sequence[str] = ()) -> Dict[str, str]:
    root = Path(root)
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not any(x in p.parts for x in exclude):
            out[str(p.relative_to(root)).replace("\\", "/")] = sha256_file(p)
    return out


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return list(r), list(r.fieldnames or [])


def read_header(path: Path) -> list[str]:
    with open(path, encoding="utf-8", newline="") as f:
        return next(csv.reader(f), [])


def write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[Any]]) -> int:
    """Official convention: UTF-8 without BOM, CRLF row endings, minimal quoting."""
    refuse_forbidden(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(header)
        for row in rows:
            w.writerow(row)
            n += 1
    return n


def write_json(path: Path, obj: Any) -> None:
    refuse_forbidden(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def peak_memory_bytes() -> Optional[int]:
    """Peak working set / max RSS of the current process; None if no reliable method."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes as w

            class PMC(ctypes.Structure):
                _fields_ = [("cb", w.DWORD), ("PageFaultCount", w.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t),
                            ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("e", ctypes.c_size_t), ("f", ctypes.c_size_t)]

            k32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
            k32.GetCurrentProcess.restype = w.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(PMC), w.DWORD]
            c = PMC()
            c.cb = ctypes.sizeof(PMC)
            return int(c.PeakWorkingSetSize) if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb) else None
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(rss if sys.platform == "darwin" else rss * 1024)
    except Exception:  # noqa: BLE001
        return None


def run_dirs(run_dir: Path) -> Dict[str, Path]:
    run_dir = Path(run_dir)
    return {
        "run": run_dir,
        "pack": run_dir / "pack",
        "private": run_dir / "private",
        "protected": run_dir / "protected",
        "evidence": run_dir / "evidence",
        "reports": run_dir / "reports",
    }


def utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass


def stats(xs: Sequence[float]) -> Dict[str, Optional[float]]:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return {"min": None, "median": None, "max": None, "n": 0}
    mid = len(xs) // 2
    med = xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2
    return {"min": round(xs[0], 4), "median": round(med, 4), "max": round(xs[-1], 4), "n": len(xs)}


def list_files(root: Path) -> List[Path]:
    return sorted(p for p in Path(root).rglob("*") if p.is_file())
