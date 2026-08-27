#!/usr/bin/env python3
"""Read-only AI-readiness audit for a software repository."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    raise SystemExit("audit_project.py and scaffold_project.py require Python 3.11 or newer") from None


SKIP_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", "node_modules", "vendor",
    "dist", "build", "target", ".venv", "venv", "__pycache__", ".next",
    ".turbo", "coverage", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}

NON_LIVE_PARTS = {
    "example", "examples", "fixture", "fixtures", "sample", "samples",
    "template", "templates", "project-template", "testdata",
}
TEST_DIRS = {"test", "tests", "spec", "specs", "__tests__"}

SOURCE_EXTENSIONS = {
    ".py": "Python", ".pyi": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
    ".cs": "C#", ".cpp": "C++", ".cc": "C++", ".c": "C",
    ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
    ".lua": "Lua", ".sh": "Shell", ".dart": "Dart", ".vue": "Vue",
    ".ex": "Elixir", ".exs": "Elixir", ".scala": "Scala",
}
TEST_SOURCE_EXTENSIONS = set(SOURCE_EXTENSIONS) | {".bash", ".ps1"}


def resolve_root(path: Path) -> Path:
    path = path.resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    raise ValueError(f"--scope repository requires a containing Git repository: {path}")


def iter_files(root: Path):
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        base = Path(current)
        for name in sorted(files):
            yield base / name


def relative_files(root: Path) -> list[str]:
    return [p.relative_to(root).as_posix() for p in iter_files(root)]


def is_live_path(value: str) -> bool:
    parts = list(Path(value).parts)
    lowered = [part.lower() for part in parts]
    adapter_indexes = [lowered.index(anchor) for anchor in (".agents", ".claude", ".kimi-code") if anchor in lowered]
    scope_parts = parts[:min(adapter_indexes)] if adapter_indexes else parts
    return not any(part.lower() in NON_LIVE_PARTS for part in scope_parts)


def is_source_path(value: str) -> bool:
    """Exclude examples and fixtures while retaining application template modules."""
    path = Path(value)
    lowered = [part.lower() for part in path.parts]
    if tuple(lowered[:2]) == ("tools", "ai") and path.name in {
        "validate_harness.py", "sync_skill_adapters.py",
    }:
        return False
    parts = lowered[:-1]
    for index, part in enumerate(parts):
        if part not in NON_LIVE_PARTS:
            continue
        if part in {"template", "templates"} and index > 0 and parts[index - 1] in {"src", "app", "lib"}:
            continue
        return False
    return True


def is_test_path(value: str) -> bool:
    if not is_live_path(value):
        return False
    path = Path(value)
    if path.suffix.lower() not in TEST_SOURCE_EXTENSIONS:
        return False
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    return (
        any(part in TEST_DIRS for part in parts[:-1])
        or name.startswith("test_")
        or name.endswith(("_test.py", "_test.go", ".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.tsx", ".spec.js"))
    )


def is_architecture_check_path(value: str) -> bool:
    path = Path(value)
    compact = re.sub(r"[^a-z0-9]", "", path.name.lower())
    tokens = ("archunit", "architecturetest", "checkarchitecture", "dependencycruiser", "importlinter")
    if not any(token in compact for token in tokens):
        return False
    suffix = path.suffix.lower()
    if suffix in TEST_SOURCE_EXTENSIONS:
        return is_test_path(value) or compact in {"checkarchitecture", "architecturecheck"} or path.stem.lower().endswith(("test", "tests")) or any(
            token in compact for token in ("archunit", "dependencycruiser", "importlinter")
        )
    return suffix in {".json", ".toml", ".yml", ".yaml"} and any(
        token in compact for token in ("dependencycruiser", "importlinter")
    )


def contains_parts(value: str, sequence: tuple[str, ...]) -> bool:
    parts = tuple(part.lower() for part in Path(value).parts)
    size = len(sequence)
    return any(parts[index:index + size] == sequence for index in range(len(parts) - size + 1))


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def command(argv: list[str], cwd: str = ".", required: bool = False, timeout: int = 900) -> dict[str, Any]:
    return {"argv": argv, "cwd": cwd, "timeoutSeconds": timeout, "required": required}


def discover_commands(root: Path) -> dict[str, list[dict[str, Any]]]:
    discovered: dict[str, list[dict[str, Any]]] = {
        "setup": [], "test": [], "lint": [], "typecheck": [], "build": [],
        "architecture": [], "docs": [],
    }

    package = root / "package.json"
    if package.exists():
        data = read_json(package)
        if data is None:
            data = {}
            package_valid = False
        else:
            package_valid = True
        scripts = data.get("scripts", {}) if isinstance(data.get("scripts"), dict) else {}
        declared_manager = data.get("packageManager", "").split("@", 1)[0] if isinstance(data.get("packageManager"), str) else ""
        if (root / "pnpm-lock.yaml").exists() or declared_manager == "pnpm":
            runner = ["pnpm"]
            install = ["pnpm", "install"] + (["--frozen-lockfile"] if (root / "pnpm-lock.yaml").exists() else [])
        elif (root / "yarn.lock").exists() or declared_manager == "yarn":
            runner = ["yarn"]
            frozen = ["--immutable"] if (root / ".yarnrc.yml").exists() else ["--frozen-lockfile"]
            install = ["yarn", "install"] + (frozen if (root / "yarn.lock").exists() else [])
        elif (root / "bun.lock").exists() or (root / "bun.lockb").exists() or declared_manager == "bun":
            runner = ["bun", "run"]
            has_lock = (root / "bun.lock").exists() or (root / "bun.lockb").exists()
            install = ["bun", "install"] + (["--frozen-lockfile"] if has_lock else [])
        else:
            runner = ["npm", "run"]
            install = ["npm", "ci"] if (root / "package-lock.json").exists() else ["npm", "install"]
        if package_valid:
            discovered["setup"].append(command(install, required=False, timeout=1200))
        aliases = {
            "test": ["test"], "lint": ["lint"],
            "typecheck": ["typecheck", "type-check", "check-types"],
            "build": ["build"], "architecture": ["check:architecture", "architecture"],
            "docs": ["docs:check", "check:docs"],
        }
        for group, names in aliases.items():
            for name in names:
                if name in scripts:
                    argv = runner + [name]
                    if runner == ["yarn"]:
                        argv = ["yarn", name]
                    discovered[group].append(command(argv, required=group in {"test", "lint", "typecheck"}))
                    break

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            py_data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            py_data = None
        dependencies: list[str] = []
        if isinstance(py_data, dict):
            project = py_data.get("project", {})
            if isinstance(project, dict):
                dependencies.extend(item for item in project.get("dependencies", []) if isinstance(item, str))
                optional = project.get("optional-dependencies", {})
                if isinstance(optional, dict):
                    dependencies.extend(item for values in optional.values() if isinstance(values, list) for item in values if isinstance(item, str))
            groups = py_data.get("dependency-groups", {})
            if isinstance(groups, dict):
                dependencies.extend(item for values in groups.values() if isinstance(values, list) for item in values if isinstance(item, str))
        dependency_names = {re.split(r"[<>=!~\[\s]", value.lower(), maxsplit=1)[0] for value in dependencies}
        tool = py_data.get("tool", {}) if isinstance(py_data, dict) and isinstance(py_data.get("tool"), dict) else {}
        if py_data is not None and (root / "uv.lock").exists():
            discovered["setup"].append(command(["uv", "sync", "--frozen"], timeout=1200))
        if py_data is not None and ("pytest" in dependency_names or "pytest" in tool or "pytest.ini_options" in tool):
            argv = ["uv", "run", "pytest"] if (root / "uv.lock").exists() else ["python", "-m", "pytest"]
            discovered["test"].append(command(argv, required=True))
        if py_data is not None and ("ruff" in dependency_names or "ruff" in tool):
            argv = ["uv", "run", "ruff", "check", "."] if (root / "uv.lock").exists() else ["ruff", "check", "."]
            discovered["lint"].append(command(argv, required=True))
        if py_data is not None and ("mypy" in dependency_names or "mypy" in tool):
            argv = ["uv", "run", "mypy", "."] if (root / "uv.lock").exists() else ["mypy", "."]
            discovered["typecheck"].append(command(argv, required=True))

    if (root / "Cargo.toml").exists():
        discovered["test"].append(command(["cargo", "test"], required=True, timeout=1200))
        discovered["lint"].append(command(["cargo", "clippy", "--all-targets", "--all-features"], required=True, timeout=1200))
        discovered["build"].append(command(["cargo", "build"], timeout=1200))

    if (root / "go.mod").exists():
        discovered["test"].append(command(["go", "test", "./..."], required=True, timeout=1200))
        discovered["build"].append(command(["go", "build", "./..."], timeout=1200))

    makefile = root / "Makefile"
    if makefile.exists():
        text = makefile.read_text(encoding="utf-8", errors="replace")
        targets = set(re.findall(r"(?m)^([A-Za-z0-9_.-]+)\s*:(?![=])", text))
        for group, names in {
            "test": ["test"], "lint": ["lint", "check"], "typecheck": ["typecheck"],
            "build": ["build"], "architecture": ["check-architecture", "architecture"],
            "docs": ["check-docs", "docs-check"],
        }.items():
            name = next((n for n in names if n in targets), None)
            if name and not discovered[group]:
                discovered[group].append(command(["make", name], required=group in {"test", "lint", "typecheck"}))

    for group in discovered:
        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, ...]] = set()
        for item in discovered[group]:
            key = tuple(item["argv"])
            if key not in seen:
                seen.add(key)
                unique.append(item)
        discovered[group] = unique
    return discovered


def analyze(root: Path) -> dict[str, Any]:
    files = relative_files(root)
    file_set = set(files)
    live_files = [path for path in files if is_live_path(path)]
    source_files = [path for path in files if is_source_path(path)]
    languages = Counter()
    source_count = 0
    for rel in source_files:
        language = SOURCE_EXTENSIONS.get(Path(rel).suffix.lower())
        if language:
            languages[language] += 1
            source_count += 1

    manifests = [
        name for name in ("package.json", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "*.sln")
        if ("*" not in name and name in file_set) or ("*" in name and any(root.glob(name)))
    ]
    greenfield = source_count == 0 and not manifests
    guidance = {}
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md"):
        path = root / name
        if path.exists():
            try:
                lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                lines = None
            guidance[name] = {"lines": lines}

    docs = {
        "knowledgeIndex": "docs/INDEX.md" in file_set,
        "architecture": "ARCHITECTURE.md" in file_set or any(p.lower().startswith("docs/architecture/") for p in live_files),
        "productSpecs": any(p.startswith(("docs/product/", "specs/", "openspec/specs/")) for p in live_files),
        "decisions": any(contains_parts(p, ("architecture", "decisions")) or "adr" in tuple(part.lower() for part in Path(p).parts) for p in live_files),
        "activePlans": any(p.startswith("docs/plans/active/") for p in live_files),
        "operations": any(p.startswith("docs/operations/") for p in live_files),
        "quality": any(p.startswith("docs/quality/") for p in live_files),
        "generated": any(p.startswith("docs/generated/") for p in live_files),
    }
    verification = {
        "tests": any(is_test_path(p) for p in files),
        "ci": any(p.startswith((".github/workflows/", ".gitlab-ci")) or p in {"Jenkinsfile", "azure-pipelines.yml"} for p in live_files),
        "harnessManifest": ".ai/harness.json" in file_set,
        "harnessValidator": "tools/ai/validate_harness.py" in file_set,
        "architectureCheck": any(is_architecture_check_path(p) for p in live_files),
    }
    skills = {
        "portable": any(contains_parts(p, (".agents", "skills")) and p.endswith("SKILL.md") for p in live_files),
        "claude": any(contains_parts(p, (".claude", "skills")) and p.endswith("SKILL.md") for p in live_files),
        "kimi": any(contains_parts(p, (".kimi-code", "skills")) and p.endswith("SKILL.md") for p in live_files),
    }
    specs = {
        "specKit": ".specify" in {Path(p).parts[0] for p in files if Path(p).parts},
        "openSpec": any(p.startswith("openspec/") for p in files),
    }
    commands = discover_commands(root)

    findings: list[dict[str, str]] = []
    if not guidance:
        findings.append({"severity": "high", "code": "NO_GUIDANCE", "message": "No repository agent entrypoint was found."})
    if "AGENTS.md" in guidance and (guidance["AGENTS.md"]["lines"] or 0) > 160:
        findings.append({"severity": "high", "code": "GUIDANCE_BLOAT", "message": "Root AGENTS.md exceeds 160 lines; convert it into a map and move procedures on demand."})
    if "AGENTS.md" in guidance and "CLAUDE.md" not in guidance:
        findings.append({"severity": "medium", "code": "NO_CLAUDE_ADAPTER", "message": "Claude Code has no canonical AGENTS.md import adapter."})
    if not docs["architecture"]:
        findings.append({"severity": "high", "code": "NO_ARCH_MAP", "message": "No current-state architecture map was found."})
    if not verification["tests"]:
        findings.append({"severity": "high", "code": "NO_TEST_EVIDENCE", "message": "No conventional test tree was detected; verify whether behavior has an executable oracle."})
    if not verification["architectureCheck"]:
        findings.append({"severity": "medium", "code": "PASSIVE_ARCHITECTURE", "message": "No project-native architecture boundary check was detected."})
    if not docs["activePlans"]:
        findings.append({"severity": "medium", "code": "NO_CONTINUITY", "message": "No versioned active-plan surface was detected for resumable work."})
    if greenfield:
        findings.append({"severity": "info", "code": "GREENFIELD", "message": "No source code or build manifest was detected; initialize the harness before product code."})

    return {
        "root": str(root),
        "modeRecommendation": "greenfield" if greenfield else "brownfield",
        "fileCount": len(files),
        "sourceFileCount": source_count,
        "languages": dict(languages.most_common()),
        "manifests": manifests,
        "guidance": guidance,
        "documentation": docs,
        "verification": verification,
        "skills": skills,
        "specSystems": specs,
        "discoveredCommands": commands,
        "findings": findings,
    }


def to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AI-first Repository Audit", "",
        f"- Root: `{report['root']}`",
        f"- Recommended mode: **{report['modeRecommendation']}**",
        f"- Files/source files: {report['fileCount']}/{report['sourceFileCount']}", "",
        "## Findings", "",
    ]
    if report["findings"]:
        for item in report["findings"]:
            lines.append(f"- **{item['severity'].upper()} {item['code']}**: {item['message']}")
    else:
        lines.append("- No material gaps detected by the universal audit.")
    lines.extend(["", "## Discovered commands", ""])
    for group, items in report["discoveredCommands"].items():
        rendered = [" ".join(item["argv"]) for item in items]
        lines.append(f"- {group}: {', '.join(f'`{x}`' for x in rendered) if rendered else 'none'}")
    return "\n".join(lines) + "\n"


def write_output(parser: argparse.ArgumentParser, value: str, content: str, force: bool) -> None:
    path = Path(value)
    try:
        with path.open("w" if force else "x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError:
        parser.error(f"output already exists: {path}; use --force-output to replace it")
    except OSError as exc:
        parser.error(f"cannot write output {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="Repository or project path")
    parser.add_argument(
        "--scope", choices=("path", "repository"), default="path",
        help="Audit the exact path (default) or expand it to the containing Git repository root",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="Optional report path; stdout is the default")
    parser.add_argument("--force-output", action="store_true", help="Allow --output to replace an existing file")
    args = parser.parse_args()
    requested = Path(args.repo).resolve()
    try:
        root = resolve_root(requested) if args.scope == "repository" else requested
    except ValueError as exc:
        parser.error(str(exc))
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    if args.force_output and not args.output:
        parser.error("--force-output requires --output")
    report = analyze(root)
    content = json.dumps(report, indent=2, ensure_ascii=False) + "\n" if args.format == "json" else to_markdown(report)
    if args.output:
        write_output(parser, args.output, content, args.force_output)
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
