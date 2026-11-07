"""R2 identifier normalisation for SinceAI.

Pure functions, no I/O, no side effects. Shared by:
  - app/measure_baseline.py  (P0 baseline positive control)
  - app/mosaic_check.py      (P3 cross-release gate) -- import, do not copy

The recipe is locked by findings/MVP_Plan.md section 3 (R2): it must reproduce
HETU 1622 / phone 1484 on the unprotected pack data/. Changing it is a
behaviour change, not a cleanup.
"""
from __future__ import annotations

import re
from typing import Callable, Iterable

PHONE_RECIPE = "strip non-[0-9+]; ^\\+358→0; ^00358→0"
HETU_RECIPE = "strip; string as-is"

_PHONE_STRIP_RE = re.compile(r"[^0-9+]")

def normalize_phone(value: str | None) -> str:
    if value is None:
        return ""
    digits = _PHONE_STRIP_RE.sub("", value)
    if digits.startswith("+358"):
        return "0" + digits[4:]
    if digits.startswith("00358"):
        return "0" + digits[5:]
    return digits

def normalize_hetu(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()

IBAN_RECIPE = "strip whitespace; uppercase"
_IBAN_STRIP_RE = re.compile(r"\s+")


def normalize_iban(value: str | None) -> str:
    if value is None:
        return ""
    return _IBAN_STRIP_RE.sub("", value).upper()

def unique_nonempty(values: Iterable[str | None], normalizer: Callable[[str | None], str]) -> set[str]:
    out: set[str] = set()
    for value in values:
        normalized = normalizer(value)
        if normalized:
            out.add(normalized)
    return out
