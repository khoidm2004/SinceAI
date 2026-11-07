"""R2 normalisation helpers for P0 baseline and P3 mosaic_check."""

from __future__ import annotations

import re
from typing import Callable, Iterable, Optional

_PHONE_STRIP_RE = re.compile(r"[^0-9+]")


def normalize_phone(raw: Optional[str]) -> str:
    if raw is None:
        return ""
    s = _PHONE_STRIP_RE.sub("", str(raw))
    if s.startswith("+358"):
        s = "0" + s[4:]
    elif s.startswith("00358"):
        s = "0" + s[5:]
    return s


def normalize_hetu(raw: Optional[str]) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


def unique_nonempty(
    values: Iterable[Optional[str]],
    normalizer: Callable[[Optional[str]], str],
) -> set[str]:
    return {n for n in (normalizer(v) for v in values) if n}
