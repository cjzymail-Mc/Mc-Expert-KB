#!/usr/bin/env python3
"""Create and verify immutable skill-source manifests."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Iterable


SCHEMA_VERSION = 1
EXCLUDED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache"}
EXCLUDED_FILES = {".doctor-pass.json", ".skill-ready.json", ".DS_Store", "Thumbs.db"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


class ManifestError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_excluded_file(path: Path) -> bool:
    name = path.name
    return (
        name in EXCLUDED_FILES
        or path.suffix.casefold() in EXCLUDED_SUFFIXES
        or name.endswith(".bak")
        or ".bak-" in name
        or ".bak." in name
    )


def iter_source_files(root: Path) -> Iterable[Path]:
    for directory, names, files in os.walk(root, topdown=True, followlinks=False):
        names[:] = sorted(name for name in names if name not in EXCLUDED_DIRS)
        base = Path(directory)
        for name in sorted(files):
            path = base / name
            if is_excluded_file(path):
                continue
            if path.is_symlink():
                raise ManifestError(f"symbolic link is not allowed in release source: {path}")
            yield path


def file_records(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for path in iter_source_files(root):
        relative = path.relative_to(root).as_posix()
        identity = relative.casefold()
        if identity in seen:
            raise ManifestError(f"case-insensitive duplicate path: {relative}")
        seen.add(identity)
        records.append(
            {"path": relative, "size": path.stat().st_size, "sha256": sha256_file(path)}
        )
    records.sort(key=lambda record: str(record["path"]).casefold())
    return records


def tree_sha256(records: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        line = f"{record['path']}\0{record['size']}\0{record['sha256']}\n"
        digest.update(line.encode("utf-8"))
    return digest.hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def create_manifest(source: Path, output: Path) -> dict[str, object]:
    source = source.resolve()
    output = output.resolve()
    if not source.is_dir():
        raise ManifestError(f"source directory does not exist: {source}")
    if is_within(output, source):
        raise ManifestError("manifest output must be outside source_skill_root")
    records = file_records(source)
    if not records:
        raise ManifestError("release source contains no files")
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_root": str(source),
        "excluded_runtime": {
            "directories": sorted(EXCLUDED_DIRS),
            "files": sorted(EXCLUDED_FILES),
            "suffixes": sorted(EXCLUDED_SUFFIXES),
            "backup_name_patterns": ["*.bak", "*.bak-*", "*.bak.*"],
        },
        "file_count": len(records),
        "tree_sha256": tree_sha256(records),
        "files": records,
    }
    write_json(output, manifest)
    return manifest


def load_manifest(path: Path) -> dict[str, object]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ManifestError(f"manifest cannot be parsed: {exc}") from exc
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError("unsupported manifest schema_version")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ManifestError("manifest has no file records")
    if manifest.get("tree_sha256") != tree_sha256(files):
        raise ManifestError("manifest tree_sha256 does not match its file records")
    return manifest


def verify_manifest(manifest_path: Path, destination: Path) -> dict[str, object]:
    manifest = load_manifest(manifest_path.resolve())
    destination = destination.resolve()
    if not destination.is_dir():
        raise ManifestError(f"destination directory does not exist: {destination}")

    actual_records = file_records(destination)
    actual_by_path = {str(record["path"]).casefold(): record for record in actual_records}
    expected_records = manifest["files"]
    expected_by_path = {
        str(record["path"]).casefold(): record for record in expected_records
    }

    missing: list[str] = []
    changed: list[dict[str, str]] = []
    for identity, expected in expected_by_path.items():
        actual = actual_by_path.get(identity)
        if actual is None:
            missing.append(str(expected["path"]))
        elif actual["size"] != expected["size"] or actual["sha256"] != expected["sha256"]:
            changed.append(
                {
                    "path": str(expected["path"]),
                    "expected_sha256": str(expected["sha256"]),
                    "actual_sha256": str(actual["sha256"]),
                }
            )
    extra = [
        str(record["path"])
        for identity, record in actual_by_path.items()
        if identity not in expected_by_path
    ]
    passed = not missing and not changed and not extra
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if passed else "FAIL",
        "manifest": str(manifest_path.resolve()),
        "destination": str(destination),
        "expected_file_count": len(expected_records),
        "actual_file_count": len(actual_records),
        "expected_tree_sha256": manifest["tree_sha256"],
        "actual_tree_sha256": tree_sha256(actual_records),
        "missing": sorted(missing, key=str.casefold),
        "changed": sorted(changed, key=lambda item: item["path"].casefold()),
        "extra": sorted(extra, key=str.casefold),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="create a source manifest")
    create.add_argument("--source", required=True, type=Path)
    create.add_argument("--out", required=True, type=Path)

    verify = commands.add_parser("verify", help="strictly verify a deployed copy")
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--destination", required=True, type=Path)
    verify.add_argument("--report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "create":
            result = create_manifest(args.source, args.out)
            print(
                "RELEASE MANIFEST: PASS — "
                f"files={result['file_count']} tree_sha256={result['tree_sha256']}"
            )
            return 0

        result = verify_manifest(args.manifest, args.destination)
        if args.report:
            write_json(args.report.resolve(), result)
        print(
            f"DEPLOYMENT PARITY: {result['status']} — "
            f"missing={len(result['missing'])} changed={len(result['changed'])} "
            f"extra={len(result['extra'])}"
        )
        return 0 if result["status"] == "PASS" else 2
    except (ManifestError, OSError) as exc:
        print(f"RELEASE MANIFEST: FAIL — {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
