"""HMAC pseudonym service: per-(dataset, scenario_id) subkeys and tokenisation."""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalize_hetu, normalize_iban, normalize_phone  # noqa: E402


def load_master_key(path: str | Path) -> bytes:
    data = Path(path).read_bytes()
    if len(data) < 16:
        raise ValueError(f"master key too short: {path}")
    return data


def create_master_key(path: str | Path) -> bytes:
    p = Path(path)
    if p.exists():
        raise FileExistsError(f"refusing to overwrite existing key: {p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
    p.write_bytes(key)
    os.chmod(p, 0o600)
    return key


def derive_subkey(master: bytes, dataset: str, scenario_id: str) -> bytes:
    msg = f"{dataset}|{scenario_id}".encode("utf-8")
    return hmac.new(master, msg, hashlib.sha256).digest()


def tokenise(value: str | None, subkey: bytes, *, kind: str = "hetu") -> str:
    if kind == "hetu":
        norm = normalize_hetu(value)
    elif kind == "phone":
        norm = normalize_phone(value)
    elif kind == "iban":
        norm = normalize_iban(value)
    elif kind == "raw":
        norm = "" if value is None else str(value).strip()
    else:
        raise ValueError(f"unknown tokenise kind: {kind!r}")
    if not norm:
        return ""
    return hmac.new(subkey, norm.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
