from __future__ import annotations

from python_version import require_python

require_python()
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_ROOT = REPO_ROOT / "resources"

DEFAULT_PACK_ROOT = (
    REPO_ROOT
    / "resources"
    / "TRUSTED_SinceAI2026_FINAL"
    / "TRUSTED_PETS_PROVING_GROUND_2026"
)
DEFAULT_MANIFEST = REPO_ROOT / "manifests" / "pack_data_sha256.json"

EXCLUDED_NAMES = frozenset({".DS_Store"})
EXCLUDED_DIR_NAMES = frozenset({"__pycache__"})
ALGORITHM = "sha256"
CHUNK = 1 << 20

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_SETUP = 2


def _refuse_resources_write(path: Path) -> None:
    resolved = path.resolve()
    resources = RESOURCES_ROOT.resolve()
    try:
        if resolved.is_relative_to(resources):
            raise ValueError(f"refusing to write under resources/: {resolved}")
    except AttributeError:
        if str(resolved).startswith(str(resources)):
            raise ValueError(f"refusing to write under resources/: {resolved}") from None


def pack_data_dir(pack_root: Path) -> Path:
    return pack_root.resolve() / "data"


def pack_data_root_relative(pack_root: Path) -> str:
    data = pack_data_dir(pack_root)
    rel = data.relative_to(REPO_ROOT.resolve())
    return rel.as_posix()


def _should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDED_DIR_NAMES:
            return True
    if path.name in EXCLUDED_NAMES:
        return True
    return False


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def hash_pack_data(pack_root: Path) -> dict[str, str]:
    data_root = pack_data_dir(pack_root)
    if not data_root.is_dir():
        raise FileNotFoundError(f"missing pack data directory: {data_root}")
    files: dict[str, str] = {}
    for path in sorted(data_root.rglob("*")):
        if not path.is_file():
            continue
        if _should_skip(path):
            continue
        rel = path.relative_to(data_root).as_posix()
        files[rel] = sha256_file(path)
    return files


def build_manifest_dict(pack_root: Path, files: dict[str, str]) -> dict[str, Any]:
    return {
        "pack_data_root": pack_data_root_relative(pack_root),
        "algorithm": ALGORITHM,
        "excluded_names": sorted(EXCLUDED_NAMES),
        "file_count": len(files),
        "files": dict(sorted(files.items())),
    }


def compare_manifests(
    expected: dict[str, str],
    observed: dict[str, str],
) -> tuple[bool, list[str]]:
    issues: list[str] = []
    exp_keys = set(expected)
    obs_keys = set(observed)
    for key in sorted(exp_keys - obs_keys):
        issues.append(f"removed: {key}")
    for key in sorted(obs_keys - exp_keys):
        issues.append(f"added: {key}")
    for key in sorted(exp_keys & obs_keys):
        if expected[key] != observed[key]:
            issues.append(f"changed: {key}")
    return (len(issues) == 0, issues)


def cmd_build(pack_root: Path, out: Path) -> int:
    try:
        _refuse_resources_write(out)
        files = hash_pack_data(pack_root)
        manifest = build_manifest_dict(pack_root, files)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
            f.write("\n")
        print(f"wrote {out} ({manifest['file_count']} files)")
        return EXIT_OK
    except (ValueError, FileNotFoundError, OSError) as e:
        print(f"build error: {e}", file=sys.stderr)
        return EXIT_SETUP


def load_manifest(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_verify(pack_root: Path, manifest_path: Path) -> int:
    try:
        if not manifest_path.is_file():
            print(f"missing manifest: {manifest_path}", file=sys.stderr)
            return EXIT_SETUP
        manifest = load_manifest(manifest_path)
        expected_files = manifest.get("files")
        if not isinstance(expected_files, dict):
            print("manifest missing or invalid 'files' object", file=sys.stderr)
            return EXIT_SETUP
        expected = {str(k): str(v) for k, v in expected_files.items()}
        observed = hash_pack_data(pack_root)
        ok, issues = compare_manifests(expected, observed)
        if ok:
            print(f"verify OK ({len(observed)} files)")
            return EXIT_OK
        for line in issues:
            print(line, file=sys.stderr)
        return EXIT_MISMATCH
    except FileNotFoundError as e:
        print(f"verify setup error: {e}", file=sys.stderr)
        return EXIT_SETUP
    except (json.JSONDecodeError, OSError) as e:
        print(f"verify error: {e}", file=sys.stderr)
        return EXIT_SETUP


def _selftest_in_memory() -> bool:
    base = {"a.txt": "aa", "b.txt": "bb"}
    ok, issues = compare_manifests(base, dict(base))
    if not ok or issues:
        print("selftest fail: identical case", file=sys.stderr)
        return False
    changed = dict(base)
    changed["a.txt"] = "xx"
    ok, issues = compare_manifests(base, changed)
    if ok or not any("changed:" in i for i in issues):
        print("selftest fail: changed case", file=sys.stderr)
        return False
    removed = {"a.txt": base["a.txt"]}
    ok, issues = compare_manifests(base, removed)
    if ok or not any("removed:" in i for i in issues):
        print("selftest fail: removed case", file=sys.stderr)
        return False
    added = dict(base)
    added["c.txt"] = "cc"
    ok, issues = compare_manifests(base, added)
    if ok or not any("added:" in i for i in issues):
        print("selftest fail: added case", file=sys.stderr)
        return False
    return True


def cmd_selftest(pack_root: Path, manifest_path: Path) -> int:
    if not _selftest_in_memory():
        return EXIT_MISMATCH
    if manifest_path.is_file():
        try:
            manifest = load_manifest(manifest_path)
            expected_files = manifest.get("files")
            if isinstance(expected_files, dict) and expected_files:
                tampered = copy.deepcopy(expected_files)
                first_key = next(iter(sorted(tampered)))
                tampered[first_key] = "0" * 64
                expected = {str(k): str(v) for k, v in expected_files.items()}
                tampered_s = {str(k): str(v) for k, v in tampered.items()}
                ok, _ = compare_manifests(expected, tampered_s)
                if ok:
                    print("selftest fail: tampered digest not detected", file=sys.stderr)
                    return EXIT_MISMATCH
        except (json.JSONDecodeError, OSError) as e:
            print(f"selftest manifest read error: {e}", file=sys.stderr)
            return EXIT_SETUP
    observed = hash_pack_data(pack_root)
    ok, _ = compare_manifests(observed, observed)
    if not ok:
        print("selftest fail: live hash inconsistency", file=sys.stderr)
        return EXIT_MISMATCH
    print("selftest OK")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OPS-1 pack data SHA-256 manifest")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("build", "verify", "selftest"):
        p = sub.add_parser(name)
        p.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
        if name == "build":
            p.add_argument("--out", type=Path, default=DEFAULT_MANIFEST)
        else:
            p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)

    args = parser.parse_args(argv)
    pack_root: Path = args.pack_root

    if args.command == "build":
        return cmd_build(pack_root, args.out)
    if args.command == "verify":
        return cmd_verify(pack_root, args.manifest)
    return cmd_selftest(pack_root, args.manifest)


if __name__ == "__main__":
    sys.exit(main())
