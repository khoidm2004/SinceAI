#!/usr/bin/env python3
"""Run pets-eval scorecard/check when available; honest skip on Python 3.9."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_PACK_ROOT = (
    REPO_ROOT / "resources" / "TRUSTED_SinceAI2026_FINAL" / "TRUSTED_PETS_PROVING_GROUND_2026"
)
DEFAULT_CLEAN_ROOT = REPO_ROOT / "clean_data"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_UNAVAILABLE = 4


def _pets_eval_importable() -> bool:
    if sys.version_info < (3, 10):
        return False
    try:
        import pets_eval  # noqa: F401
    except ImportError:
        return False
    return True


def _pets_eval_available() -> bool:
    if shutil.which("pets-eval"):
        return True
    return _pets_eval_importable()


def _build_commands(pack_root: Path, clean_root: Path) -> List[List[str]]:
    pack = pack_root.resolve()
    clean = clean_root.resolve()
    return [
        [
            "pets-eval",
            "scorecard",
            "--original",
            str(pack / "data/health"),
            "--protected",
            str(clean / "health__HEALTH-S1"),
            "--scenario",
            "HEALTH-S1",
        ],
        [
            "pets-eval",
            "scorecard",
            "--original",
            str(pack / "data/finance"),
            "--protected",
            str(clean / "finance__FIN-S2"),
            "--scenario",
            "FIN-S2",
        ],
        [
            "pets-eval",
            "check",
            str(clean / "health__HEALTH-S1"),
        ],
        [
            "pets-eval",
            "check",
            str(clean / "finance__FIN-S2"),
        ],
    ]


def _print_commands(commands: List[List[str]]) -> None:
    for cmd in commands:
        print(" ".join(cmd))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run pets-eval scorecard + check (optional on Python 3.9)"
    )
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--clean-root", type=Path, default=DEFAULT_CLEAN_ROOT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands only; always exit 0",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    commands = _build_commands(args.pack_root, args.clean_root)
    _print_commands(commands)

    if args.dry_run:
        return EXIT_OK

    if not _pets_eval_available():
        print(
            "pets-eval unavailable: need Python >=3.10 + toolkit install "
            "(pip install -e resources/.../toolkit)",
            file=sys.stderr,
        )
        return EXIT_UNAVAILABLE

    for cmd in commands:
        proc = subprocess.run(cmd)
        if proc.returncode != 0:
            return EXIT_FAIL
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
