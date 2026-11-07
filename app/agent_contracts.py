"""AR-4 input contract: nothing identifying leaves this process."""
from __future__ import annotations

import re
from typing import Any

PROMPT_VERSION = "p8-a2-1"

HETU_RE = re.compile(r"\d{6}[-+ABCDEFYXWVU]\d{3}[0-9A-Z]")
PHONE_RE = re.compile(r"(?:\+358|00358)\d{6,10}|\b0\d{8,10}\b")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

FORBIDDEN_SUBSTRINGS = (
    "master.key",
    "rowmap_",
    "truth/",
    "BEGIN PRIVATE KEY",
    "GROQ_API_KEY",
)
FORBIDDEN_KEYS = frozenset(
    {
        "samples",
        "hetu",
        "patient_hetu",
        "phone",
        "iban",
        "email",
        "full_name",
        "street_address",
        "patient_name",
        "home_address",
        "truth",
        "rowmap",
        "api_key",
        "master_key",
        "subkey",
    }
)


class ContractViolation(Exception):
    """Raised when AR-4 payload scanning finds forbidden content."""


def scan_value(text: str) -> list[str]:
    labels: list[str] = []
    if HETU_RE.search(text):
        labels.append("hetu")
    if PHONE_RE.search(text):
        labels.append("phone")
    if IBAN_RE.search(text):
        labels.append("iban")
    elif IBAN_RE.search(re.sub(r"\s+", "", text)):
        labels.append("iban")
    if EMAIL_RE.search(text):
        labels.append("email")
    low = text.lower()
    for s in FORBIDDEN_SUBSTRINGS:
        if s.lower() in low:
            labels.append(f"forbidden_substring:{s}")
    return labels


def scan(payload: Any, *, path: str = "$") -> list[str]:
    out: list[str] = []
    if isinstance(payload, dict):
        for key, val in payload.items():
            key_s = str(key)
            if key_s.lower() in FORBIDDEN_KEYS:
                out.append(f"forbidden_key:{key}@{path}")
                continue
            child = f"{path}.{key_s}" if path != "$" else f"$.{key_s}"
            out.extend(scan(val, path=child))
        return out
    if isinstance(payload, (list, tuple)):
        for i, item in enumerate(payload):
            out.extend(scan(item, path=f"{path}[{i}]"))
        return out
    if isinstance(payload, str):
        for label in scan_value(payload):
            out.append(f"{label}@{path}")
    return out


def assert_clean(payload: Any, *, where: str) -> None:
    violations = scan(payload)
    if violations:
        raise ContractViolation(f"{where}: AR-4 contract violation: {violations[:5]}")


def selftest() -> list[tuple[str, bool, str]]:
    cases: list[tuple[str, Any, bool, str | None]] = [
        (
            "clean_counts",
            {"hetu_join": 1622, "phone_join": 1484, "verdict": "PASS"},
            True,
            None,
        ),
        ("clean_thread_id", {"thread_id": "20261107T121800Z-protected"}, True, None),
        (
            "clean_provider",
            {"model": "openai/gpt-oss-120b", "temperature": 0.1, "max_tokens": 800},
            True,
            None,
        ),
        ("reject_samples_key", {"samples": []}, False, "forbidden_key:samples"),
        ("reject_hetu", {"note": "021280-9730"}, False, "hetu"),
        ("reject_phone", {"note": "+358443547786"}, False, "phone"),
        ("reject_iban", {"note": "FI21 1234 5600 0007 85"}, False, "iban"),
        ("reject_email", {"note": "a.virtanen@example.fi"}, False, "email"),
        (
            "reject_rowmap_path",
            {"p": "clean_data/health__HEALTH-S1/rowmap_ed_visits.csv"},
            False,
            "forbidden_substring",
        ),
    ]
    results: list[tuple[str, bool, str]] = []
    for name, payload, must_pass, needle in cases:
        try:
            assert_clean(payload, where=f"selftest:{name}")
            ok = must_pass
            detail = "passed" if must_pass else "expected violation"
        except ContractViolation as exc:
            ok = not must_pass
            msg = str(exc)
            if must_pass:
                detail = msg
            elif needle and needle not in msg:
                ok = False
                detail = f"wrong violation: {msg}"
            else:
                detail = "raised as expected"
        results.append((name, ok, detail))
    return results
