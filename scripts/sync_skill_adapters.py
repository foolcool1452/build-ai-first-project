#!/usr/bin/env python3
"""Check or generate managed Claude Code mirrors for portable repository skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


MARKER = ".ai-source.json"
MARKER_MAX_BYTES = 65536
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build",
    "target", ".venv", "venv", "__pycache__", ".next", ".turbo",
}
NON_LIVE_PARTS = {
    "example", "examples", "fixture", "fixtures", "sample", "samples",
    "template", "templates", "project-template", "testdata",
}


def is_link_like(path: Path) -> bool:
    """Treat symlinks and Windows junctions as indirections."""
    try:
        return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())
    except OSError:
        return True


def is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def destination_issue(root: Path, destination: Path) -> str | None:
    """Reject managed destinations whose parents can redirect writes outside root."""
    root = root.resolve()
    parent = destination.parent
    while parent != root:
        try:
            parent.relative_to(root)
        except ValueError:
            return "destination is not under the repository root"
        if is_link_like(parent):
            return f"ancestor is a symlink or junction: {parent.relative_to(root).as_posix()}"
        parent = parent.parent
    if not is_inside(destination, root):
        return "destination resolves outside the repository root"
    return None


def is_live(path: Path, root: Path) -> bool:
    parts = list(path.relative_to(root).parts)
    lowered = [part.lower() for part in parts]
    scope_parts = parts[:lowered.index(".agents")] if ".agents" in lowered else parts
    return not any(part.lower() in NON_LIVE_PARTS for part in scope_parts)


def all_skill_dirs(root: Path):
    for current, dirs, files in os.walk(root):
        directory = Path(current)
        if directory.name == "skills" and directory.parent.name == ".agents":
            for name in sorted(dirs):
                candidate = directory / name
                if is_link_like(candidate) and is_live(candidate, root):
                    yield candidate
        dirs[:] = sorted(
            name for name in dirs
            if name not in SKIP_DIRS
            and name != ".claude"
            and not is_link_like(directory / name)
            and is_inside(directory / name, root)
        )
        if (
            "SKILL.md" in files
            and directory.parent.name == "skills"
            and directory.parent.parent.name == ".agents"
            and is_live(directory, root)
        ):
            yield directory


def nearest_git_root(path: Path) -> Path | None:
    for candidate in (path.resolve(), *path.resolve().parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def is_portable_skill(source: Path, root: Path) -> bool:
    scope = source.parent.parent.parent.resolve()
    return scope == (nearest_git_root(scope) or root.resolve())


def portable_skills(root: Path):
    yield from (source for source in all_skill_dirs(root) if is_portable_skill(source, root))


def nested_skills(root: Path):
    yield from (source for source in all_skill_dirs(root) if not is_portable_skill(source, root))


def tree_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in tree_files(directory):
        relative = path.relative_to(directory).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(digest_bytes(path))
        digest.update(b"\0")
    return digest.hexdigest()


def digest_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def tree_files(directory: Path) -> list[Path]:
    if is_link_like(directory):
        raise ValueError(f"skill source must not be a symlink or junction: {directory}")
    files: list[Path] = []
    for current, dirs, names in os.walk(directory, followlinks=False):
        base = Path(current)
        for name in [*dirs, *names]:
            candidate = base / name
            if is_link_like(candidate):
                raise ValueError(
                    f"skill tree contains a symlink or junction: {candidate.relative_to(directory).as_posix()}"
                )
        files.extend(base / name for name in names if name != MARKER)
    return sorted(files, key=lambda path: path.relative_to(directory).as_posix())


def destination_for(source: Path) -> Path:
    scope = source.parent.parent.parent
    return scope / ".claude" / "skills" / source.name


def marker_value(source: Path, digest: str) -> dict[str, str | int]:
    scope = source.parent.parent.parent
    return {
        "schemaVersion": 1,
        "source": source.relative_to(scope).as_posix(),
        "digest": digest,
    }


def read_marker(path: Path) -> dict:
    try:
        if path.stat().st_size > MARKER_MAX_BYTES:
            return {}
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, ValueError, RecursionError):
        return {}


def write_managed_copy(root: Path, source: Path, destination: Path, source_digest: str) -> None:
    issue = destination_issue(root, destination)
    if issue:
        raise ValueError(issue)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    marker = marker_value(source, source_digest)
    (destination / MARKER).write_text(
        json.dumps(marker, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def check_or_apply(root: Path, source: Path, apply: bool) -> tuple[bool, str]:
    destination = destination_for(source)
    relative = destination.relative_to(root).as_posix()
    issue = destination_issue(root, destination)
    if issue:
        return False, f"error   {relative}: {issue}"
    try:
        source_digest = tree_digest(source)
    except (OSError, ValueError) as exc:
        return False, f"error   {source.relative_to(root).as_posix()}: {exc}"

    if destination.is_symlink():
        if destination.resolve() == source.resolve():
            return True, f"ok      {relative} (symlink)"
        return False, f"error   {relative}: symlink does not target {source.relative_to(root).as_posix()}"

    if not destination.exists():
        if not apply:
            return False, f"missing {relative}"
        try:
            write_managed_copy(root, source, destination, source_digest)
        except (OSError, ValueError) as exc:
            return False, f"error   {relative}: {exc}"
        return True, f"created {relative}"

    if not destination.is_dir():
        return False, f"error   {relative}: expected a directory"

    marker_path = destination / MARKER
    marker = read_marker(marker_path)
    expected_source = source.relative_to(source.parent.parent.parent).as_posix()
    recorded_source = marker.get("source")
    owned_source = isinstance(recorded_source, str) and recorded_source == expected_source
    if not owned_source or not isinstance(marker.get("digest"), str):
        return False, f"error   {relative}: unmanaged directory; preserve it and resolve manually"

    try:
        destination_digest = tree_digest(destination)
    except (OSError, ValueError) as exc:
        return False, f"error   {relative}: {exc}"
    recorded_digest = marker["digest"]
    if destination_digest != recorded_digest:
        return False, f"error   {relative}: managed mirror was edited; copy intended edits to the canonical source or move the mirror aside, then rerun --apply"

    if source_digest == recorded_digest and recorded_source == expected_source:
        return True, f"ok      {relative}"

    if not apply:
        return False, f"stale   {relative}"

    # The marker and digest prove this is an unchanged generated mirror owned by this script.
    issue = destination_issue(root, destination)
    if issue:
        return False, f"error   {relative}: {issue}"
    try:
        shutil.rmtree(destination)
        write_managed_copy(root, source, destination, source_digest)
    except (OSError, ValueError) as exc:
        return False, f"error   {relative}: {exc}"
    return True, f"updated {relative}"


def managed_mirrors(root: Path):
    for current, dirs, files in os.walk(root):
        directory = Path(current)
        dirs[:] = sorted(
            name for name in dirs
            if name not in SKIP_DIRS
            and not is_link_like(directory / name)
            and is_inside(directory / name, root)
        )
        destination = Path(current)
        if (
            MARKER in files
            and destination.parent.name == "skills"
            and destination.parent.parent.name == ".claude"
        ):
            yield destination


def prune_orphan(root: Path, destination: Path, apply: bool) -> tuple[bool, str]:
    relative = destination.relative_to(root).as_posix()
    issue = destination_issue(root, destination)
    if issue:
        return False, f"error   {relative}: {issue}"
    marker = read_marker(destination / MARKER)
    recorded = marker.get("digest")
    expected_source = f".agents/skills/{destination.name}"
    source = marker.get("source")
    owned_source = isinstance(source, str) and source == expected_source
    if marker.get("schemaVersion") != 1 or not owned_source:
        return False, f"error   {relative}: orphaned directory is unmanaged; preserve and resolve manually"
    try:
        current = tree_digest(destination)
    except (OSError, ValueError) as exc:
        return False, f"error   {relative}: {exc}"
    if not isinstance(recorded, str) or current != recorded:
        return False, f"error   {relative}: orphaned mirror is modified or unmanaged; preserve and resolve manually"
    if not apply:
        return False, f"orphan  {relative} (use --prune to remove the unchanged managed mirror)"
    issue = destination_issue(root, destination)
    if issue:
        return False, f"error   {relative}: {issue}"
    try:
        shutil.rmtree(destination)
    except OSError as exc:
        return False, f"error   {relative}: {exc}"
    return True, f"pruned  {relative}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="Repository or component root")
    parser.add_argument("--apply", action="store_true", help="Create or safely refresh managed mirrors")
    parser.add_argument("--prune", action="store_true", help="Remove unchanged managed mirrors whose canonical source is gone")
    args = parser.parse_args()

    root = Path(args.repo).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    sources = list(portable_skills(root))
    nested = list(nested_skills(root))
    expected = {destination_for(source).resolve() for source in sources}
    failures = len(nested)
    for source in nested:
        print(
            f"error   {source.relative_to(root).as_posix()}: nested .agents/skills are not "
            "cross-tool portable; move the workflow to the nearest Git root"
        )
    for source in sources:
        valid, message = check_or_apply(root, source, args.apply)
        print(message)
        failures += not valid
    for destination in managed_mirrors(root):
        if destination.resolve() in expected:
            continue
        valid, message = prune_orphan(root, destination, args.prune)
        print(message)
        failures += not valid
    if not sources:
        print("No portable repository skills found.")
    return 1 if failures else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
