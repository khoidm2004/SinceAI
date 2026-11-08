"""Shared Python-version guard for every CLI entry point in app/.

The vendored pets-eval toolkit (resources/.../toolkit) declares
`requires-python = ">=3.10"` itself. This module raises that same floor
across every app/*.py entry point, so running one on an older interpreter
fails fast with one clear message instead of a confusing downstream
ImportError the first time something needs pets-eval.
"""
from __future__ import annotations

import sys

_MIN = (3, 10)


def require_python() -> None:
    if sys.version_info[:2] < _MIN:
        have = ".".join(str(part) for part in sys.version_info[:3])
        need = ".".join(str(part) for part in _MIN)
        print(
            f"Mosaic requires Python >={need} (this interpreter is {have}). "
            "See scripts/final/STEPS.md for how to switch.",
            file=sys.stderr,
        )
        sys.exit(1)
