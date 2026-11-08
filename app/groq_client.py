"""Groq OpenAI-compatible chat client (stdlib urllib)."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_contracts import PROMPT_VERSION, assert_clean

DEFAULT_API_BASE = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 800
DEFAULT_TIMEOUT = 20.0

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOTENV_LOADED = False


def _load_dotenv_file() -> None:
    """Load repo-root `.env` into os.environ without overriding existing keys.

    Only KEY=VALUE lines; `#` comments and blank lines ignored. `.env` is
    gitignored — API base is optional (DEFAULT_API_BASE applies).
    """
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    path = _REPO_ROOT / ".env"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        if key not in os.environ or not (os.environ.get(key) or "").strip():
            os.environ[key] = val

_STUBS = {
    "supervisor": (
        '{"specialists": ["classify_assist", "minim_assist", "brief_writer"], "why": "stub"}'
    ),
    "classify_assist": '{"rows": []}',
    "minim_assist": '{"candidates": []}',
    "brief_writer": (
        '{"brief": "Stub brief: cross-release identifier joins are 0 on the protected '
        "releases; the positive control still reproduces the baseline on raw data. "
        'The JSON report remains the record."}'
    ),
}


class GroqUnavailable(Exception):
    """Transport, HTTP, or parse failure — message must never include the API key."""


def stub_response(node: str) -> str:
    return _STUBS.get(node, "{}")


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


@dataclass
class GroqConfig:
    api_key: str | None
    api_base: str
    model: str
    temperature: float
    max_tokens: int
    timeout: float
    stub: bool

    @classmethod
    def from_env(cls, *, stub: bool = False) -> GroqConfig:
        _load_dotenv_file()
        key = (os.environ.get("GROQ_API_KEY") or "").strip() or None
        # API base is optional — built-in Groq OpenAI-compatible default.
        base = (os.environ.get("GROQ_API_BASE") or DEFAULT_API_BASE).strip()
        model = (os.environ.get("GROQ_MODEL") or DEFAULT_MODEL).strip()
        return cls(
            api_key=key,
            api_base=base or DEFAULT_API_BASE,
            model=model or DEFAULT_MODEL,
            temperature=_float_env("GROQ_TEMPERATURE", DEFAULT_TEMPERATURE),
            max_tokens=_int_env("GROQ_MAX_TOKENS", DEFAULT_MAX_TOKENS),
            timeout=_float_env("GROQ_TIMEOUT", DEFAULT_TIMEOUT),
            stub=stub,
        )

    def key_present(self) -> bool:
        return bool(self.api_key)

    def redacted(self) -> dict[str, Any]:
        return {
            "provider": "groq",
            "api_base": self.api_base,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "key_present": self.key_present(),
            "stub": self.stub,
            "prompt_version": PROMPT_VERSION,
        }


class GroqClient:
    def __init__(self, config: GroqConfig) -> None:
        self.config = config
        self.calls = 0
        self.last_latency_ms: int | None = None

    def chat(self, messages: list[dict[str, Any]], *, node: str) -> str:
        assert_clean(messages, where=f"groq.chat[{node}]")
        if self.config.stub:
            self.calls += 1
            self.last_latency_ms = 0
            return stub_response(node)
        if not self.config.key_present():
            raise GroqUnavailable("no GROQ_API_KEY")
        body = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        url = self.config.api_base.rstrip("/") + "/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
                "User-Agent": "Mosaic-P8/1",
            },
            method="POST",
        )
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise GroqUnavailable(f"HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GroqUnavailable(f"transport: {type(exc).__name__}") from None
        self.last_latency_ms = int((time.monotonic() - t0) * 1000)
        self.calls += 1
        try:
            data = json.loads(raw)
            return str(data["choices"][0]["message"]["content"])
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            raise GroqUnavailable("malformed response") from None
