#!/usr/bin/env python3
"""Validate an AI-first project harness with no third-party dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import unquote

sys.dont_write_bytecode = True

from sync_skill_adapters import (
    MARKER as SKILL_MARKER,
    destination_for,
    managed_mirrors,
    nested_skills,
    portable_skills,
    read_marker,
    tree_digest,
)


SUPPORTED_CHECKS = {
    "structure", "guidance-budget", "adapter-consistency", "links", "metadata",
    "plan-state", "agents", "commands", "architecture",
}
COMMAND_ORDER = ("architecture", "docs", "test", "lint", "typecheck", "build")
PLAN_HEADINGS = (
    "Goal", "Scope and non-goals", "Progress", "Decisions", "Verification",
    "Risks and blockers", "Next action",
)
CANONICAL_STATUSES = {"verified", "observed", "proposed", "generated"}
ACTIVE_PLAN_STATUSES = {"active", "blocked", "paused"}
AGENT_STATUSES = {"active", "idle", "retired"}
TASK_BOARD_IGNORES = {"readme.md", "template.md"}
MANIFEST_MAX_BYTES = 2_000_000
MAX_ARGV_ELEMENT_CHARS = 4096


def is_link_like(path: Path) -> bool:
    """Treat symlinks and Windows junctions as indirections (3.11 has no is_junction)."""
    try:
        return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())
    except OSError:
        return True


def read_text_sig(path: Path) -> str:
    """Read text tolerating a UTF-8 BOM so anchored regexes see real line starts."""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def load_json_strict(path: Path, description: str) -> dict[str, Any]:
    """Parse JSON rejecting duplicate keys and oversized files; raises ValueError/RecursionError."""
    size = path.stat().st_size
    if size > MANIFEST_MAX_BYTES:
        raise ValueError(f"{description} exceeds the {MANIFEST_MAX_BYTES} byte limit ({size} bytes).")
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise json.JSONDecodeError(f"duplicate key {key!r}", "", 0)
            result[key] = value
        return result
    loaded = json.loads(read_text_sig(path), object_pairs_hook=reject_duplicate_keys)
    if not isinstance(loaded, dict):
        raise ValueError(f"{description} root must be a JSON object.")
    return loaded
SKIP_LINK_DIRS = {".git", "node_modules", "vendor", "dist", "build", "target", ".venv", "venv"}
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?ix)"
    r"(?P<prefix>"
    r"(?:\\?[\"'])?[A-Z0-9-]*(?:API[_-]?KEY|TOKEN|SECRET(?:[_-]ACCESS[_-]KEY)?|PASSWORD|PASSWD|AUTHORIZATION|COOKIE|PRIVATE[_-]?KEY)"
    r"[A-Z0-9_-]*(?:\\?[\"'])?\s*[:=]\s*(?:\\?[\"'])?"
    r")"
    r"(?P<value>[^\s,;\\\"']+)"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.DOTALL)
SENSITIVE_OPTION_RE = re.compile(
    r"(?i)^--?(?:api[-_]?key|access[-_]?token|auth[-_]?token|token|secret|password|passwd|"
    r"authorization|cookie|private[-_]?key)$"
)


def redact_text(value: str) -> str:
    value = PRIVATE_KEY_RE.sub("[REDACTED PRIVATE KEY]", value)
    value = BEARER_RE.sub("Bearer [REDACTED]", value)
    return SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group('prefix')}[REDACTED]", value)


def redact_argv(argv: list[str]) -> list[str]:
    redacted: list[str] = []
    redact_next = False
    for value in argv:
        if redact_next:
            redacted.append("[REDACTED]")
            redact_next = False
            continue
        if SENSITIVE_OPTION_RE.fullmatch(value):
            redacted.append(value)
            redact_next = True
            continue
        option, separator, _ = value.partition("=")
        if separator and SENSITIVE_OPTION_RE.fullmatch(option):
            redacted.append(f"{option}=[REDACTED]")
            continue
        redacted.append(redact_text(value))
    return redacted


def sensitive_argument_positions(argv: list[str]) -> list[int]:
    positions: list[int] = []
    for index, value in enumerate(argv):
        option, separator, _ = value.partition("=")
        if separator and SENSITIVE_OPTION_RE.fullmatch(option):
            positions.append(index)
        elif index + 1 < len(argv) and SENSITIVE_OPTION_RE.fullmatch(value):
            positions.append(index + 1)
    return positions


def is_absolute_argument(value: str) -> bool:
    return (
        Path(value).is_absolute()
        or PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).is_absolute()
        or value.startswith(("~",))
        or re.match(r"(?i)^[A-Za-z]:(?:[^/\\]|$)", value) is not None
    )


def fenced_lines(text: str) -> set[int]:
    """Line numbers (1-based) inside fenced code blocks (``` or ~~~), for link scanning."""
    fenced: set[int] = []
    fence_token: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if fence_token:
            if stripped.startswith(fence_token):
                fence_token = None
            else:
                fenced.append(number)
            continue
        if stripped.startswith("```"):
            fence_token = "```"
        elif stripped.startswith("~~~"):
            fence_token = "~~~"
    return set(fenced)


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    path: str | None = None


class Validator:
    def __init__(self, root: Path, strict: bool = False):
        self.root = root.resolve()
        self.strict = strict
        self.findings: list[Finding] = []
        self.manifest: dict[str, Any] = {}
        self.manifest_loaded = False
        self.command_results: list[dict[str, Any]] = []

    def add(self, severity: str, code: str, message: str, path: Path | str | None = None):
        if self.strict and severity == "warning":
            severity = "error"
        rendered = None
        if path is not None:
            try:
                rendered = Path(path).resolve().relative_to(self.root).as_posix()
            except (OSError, ValueError):
                rendered = str(path)
        self.findings.append(Finding(severity, code, message, rendered))

    def inside(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.root)
            return True
        except (OSError, ValueError):
            return False

    def repo_path(self, value: Any, code: str, required: bool = True) -> Path | None:
        if not isinstance(value, str) or not value.strip():
            self.add("error", code, "Expected a non-empty repository-relative path.")
            return None
        path = self.root / value
        if Path(value).is_absolute() or not self.inside(path):
            self.add("error", code, f"Path escapes the repository: {value}")
            return None
        if required and not path.exists():
            self.add("error", code, f"Required path does not exist: {value}", path)
        return path

    def load_manifest(self):
        path = self.root / ".ai/harness.json"
        if not path.exists():
            self.add("error", "MANIFEST_MISSING", "Missing .ai/harness.json.", path)
            return
        try:
            value = load_json_strict(path, "harness.json")
        except (OSError, UnicodeError, ValueError, RecursionError, MemoryError) as exc:
            self.add("error", "MANIFEST_INVALID", f"Cannot parse manifest JSON: {exc}", path)
            return
        self.manifest = value
        self.manifest_loaded = True

    def check_structure(self):
        if not self.manifest_loaded:
            return
        manifest_path = ".ai/harness.json"
        schema_version = self.manifest.get("schemaVersion")
        if schema_version != 1 or isinstance(schema_version, bool):
            self.add("error", "MANIFEST_CONTRACT", "schemaVersion must be the integer 1.", manifest_path)
        project = self.manifest.get("project")
        if not isinstance(project, dict):
            self.add("error", "MANIFEST_CONTRACT", "project must be an object with name, adoptionMode, and specPersistence.", manifest_path)
        else:
            if not isinstance(project.get("name"), str) or not project.get("name", "").strip():
                self.add("error", "MANIFEST_CONTRACT", "project.name must be a non-empty string.", manifest_path)
            if project.get("adoptionMode") not in ("greenfield", "brownfield"):
                self.add("error", "MANIFEST_CONTRACT", "project.adoptionMode must be 'greenfield' or 'brownfield'.", manifest_path)
            if project.get("specPersistence") not in ("living", "flow-forward", "flow-back"):
                self.add("error", "MANIFEST_CONTRACT", "project.specPersistence must be 'living', 'flow-forward', or 'flow-back'.", manifest_path)
            if "harnessProfile" in project and project.get("harnessProfile") not in ("lite", "full"):
                self.add("error", "MANIFEST_CONTRACT", "project.harnessProfile must be 'lite' or 'full' when present.", manifest_path)
        guidance = self.manifest.get("guidance")
        if not isinstance(guidance, dict) or not isinstance(guidance.get("entrypoint"), str) or not guidance.get("entrypoint", "").strip():
            self.add("error", "MANIFEST_CONTRACT", "guidance.entrypoint must be a non-empty string.", manifest_path)
        knowledge = self.manifest.get("knowledge")
        if not isinstance(knowledge, dict):
            self.add("error", "MANIFEST_CONTRACT", "knowledge must be an object with index, architecture, and product paths.", manifest_path)
            knowledge = None
        else:
            for key in ("index", "architecture", "product"):
                value = knowledge.get(key)
                if not isinstance(value, str) or not value.strip():
                    self.add("error", "MANIFEST_CONTRACT", f"knowledge.{key} must be a non-empty repository-relative path.", manifest_path)
        if not isinstance(self.manifest.get("commands"), dict):
            self.add("error", "MANIFEST_CONTRACT", "commands must be an object of command groups.", manifest_path)
        if isinstance(guidance, dict) and "maxLines" in guidance:
            max_lines = guidance.get("maxLines")
            if not isinstance(max_lines, int) or isinstance(max_lines, bool) or not 20 <= max_lines <= 400:
                self.add("error", "MANIFEST_CONTRACT", "guidance.maxLines must be an integer between 20 and 400; out-of-range values would silently disable the budget check.", manifest_path)
        validation = self.manifest.get("validation")
        checks = validation.get("requiredChecks") if isinstance(validation, dict) else None
        if not isinstance(checks, list) or not all(isinstance(check, str) for check in checks):
            self.add("error", "MANIFEST_CONTRACT", "validation.requiredChecks must be an array of check names.", manifest_path)
        elif unknown := sorted(set(checks) - SUPPORTED_CHECKS):
            self.add("error", "UNKNOWN_CHECK", f"Unknown required checks: {', '.join(unknown)}", manifest_path)
        profile = project.get("harnessProfile") if isinstance(project, dict) else None
        full_paths = {"plans", "agents", "tasks"}
        declared_paths = set(knowledge) if isinstance(knowledge, dict) else set()
        declared_checks = set(checks) if isinstance(checks, list) else set()
        full_shape = full_paths <= declared_paths and {"plan-state", "agents"} <= declared_checks
        if profile == "full" and not full_shape:
            self.add("error", "MANIFEST_CONTRACT", "The full harness profile must declare plans, agents, and tasks knowledge plus plan-state and agents checks.", manifest_path)
        elif profile == "lite" and full_shape:
            self.add("warning", "PROFILE_DRIFT", "The lite manifest now has the complete full-profile shape; update project.harnessProfile to 'full'.", manifest_path)
        if isinstance(guidance, dict):
            self.repo_path(guidance.get("entrypoint"), "GUIDANCE_PATH")
        if knowledge is not None:
            for key in ("index", "architecture", "product"):
                self.repo_path(knowledge.get(key), f"KNOWLEDGE_{key.upper()}")
            for key in ("plans", "operations", "quality", "generated", "agents", "tasks"):
                if key in knowledge:
                    self.repo_path(knowledge.get(key), f"KNOWLEDGE_{key.upper()}")
        if profile == "lite" and isinstance(knowledge, dict):
            undeclared = [
                name for name, key in (("docs/plans", "plans"), ("docs/agents", "agents"), ("docs/tasks", "tasks"))
                if key not in knowledge and (self.root / name).exists()
            ]
            if undeclared:
                self.add(
                    "warning", "PROFILE_PROMOTION_PENDING",
                    f"Coordination surfaces exist on disk but are not declared in knowledge ({', '.join(undeclared)}); "
                    "declare them, enable plan-state/agents checks, and set project.harnessProfile to 'full' — or remove the directories.",
                    manifest_path,
                )
        for source in nested_skills(self.root):
            self.add(
                "error", "NESTED_SKILL_NOT_PORTABLE",
                "Nested .agents/skills are not discoverable across all supported tools; move this workflow to the nearest Git root.",
                source,
            )

    def check_guidance_budget(self):
        guidance = self.manifest.get("guidance", {})
        if not isinstance(guidance, dict):
            return
        path = self.repo_path(guidance.get("entrypoint"), "GUIDANCE_PATH", required=False)
        if path is None or not path.exists():
            return
        try:
            text = read_text_sig(path)
        except OSError as exc:
            self.add("error", "GUIDANCE_READ", f"Cannot read guidance: {exc}", path)
            return
        lines = len(text.splitlines())
        max_lines = guidance.get("maxLines", 120)
        if not isinstance(max_lines, int) or not 20 <= max_lines <= 400:
            return
        elif lines > max_lines:
            self.add("error", "GUIDANCE_BLOAT", f"Guidance has {lines} lines; declared maximum is {max_lines}.", path)
        elif lines > int(max_lines * 0.85):
            self.add("warning", "GUIDANCE_NEAR_BUDGET", f"Guidance uses {lines}/{max_lines} lines.", path)

    def check_adapter(self):
        guidance = self.manifest.get("guidance", {})
        if not isinstance(guidance, dict):
            return
        self.check_skill_adapters()
        adapters = guidance.get("adapters", {})
        if not isinstance(adapters, dict):
            self.add("error", "ADAPTER_BLOCK", "guidance.adapters must be an object.", ".ai/harness.json")
            return
        claude_value = adapters.get("claude")
        if not claude_value:
            self.add("warning", "CLAUDE_ADAPTER_UNDECLARED", "No Claude adapter is declared.", ".ai/harness.json")
            return
        path = self.repo_path(claude_value, "CLAUDE_ADAPTER")
        if path is None or not path.exists():
            return
        try:
            if path.is_symlink():
                if path.resolve() != (self.root / guidance.get("entrypoint", "AGENTS.md")).resolve():
                    self.add("error", "CLAUDE_SYMLINK", "Claude adapter symlink does not resolve to canonical guidance.", path)
                return
            text = read_text_sig(path)
        except OSError as exc:
            self.add("error", "CLAUDE_READ", f"Cannot read Claude adapter: {exc}", path)
            return
        entry = guidance.get("entrypoint", "AGENTS.md")
        if not re.search(rf"(?m)^@{re.escape(entry)}\s*$", text):
            self.add("error", "CLAUDE_IMPORT", f"Claude adapter must contain a line importing @{entry} (or symlink to it).", path)
        if len(text.splitlines()) > 60:
            self.add("warning", "CLAUDE_BLOAT", "Claude adapter exceeds 60 lines; move shared content to canonical guidance or on-demand rules.", path)

    def portable_skill_dirs(self):
        yield from portable_skills(self.root)

    def check_skill_adapters(self):
        expected_destinations: set[Path] = set()
        for source in self.portable_skill_dirs():
            scope = source.parent.parent.parent
            destination = destination_for(source)
            expected_destinations.add(destination.resolve())
            source_relative = source.relative_to(self.root).as_posix()
            marker_source = source.relative_to(scope).as_posix()
            try:
                source_digest = tree_digest(source)
            except (OSError, ValueError) as exc:
                self.add("error", "CLAUDE_SKILL_ADAPTER", str(exc), source)
                continue
            if destination.is_symlink():
                if destination.resolve() != source.resolve():
                    self.add("error", "CLAUDE_SKILL_ADAPTER", f"Claude skill symlink does not target {source_relative}.", destination)
                continue
            if not destination.is_dir():
                self.add("error", "CLAUDE_SKILL_ADAPTER", f"Missing Claude mirror for portable skill: {source_relative}", destination)
                continue
            marker = read_marker(destination / SKILL_MARKER)
            if not marker:
                self.add("error", "CLAUDE_SKILL_ADAPTER", "Claude skill mirror is unmanaged or has an invalid source marker.", destination)
                continue
            try:
                destination_digest = tree_digest(destination)
            except (OSError, ValueError) as exc:
                self.add("error", "CLAUDE_SKILL_ADAPTER", str(exc), source)
                continue
            if (
                not isinstance(marker, dict)
                or marker.get("source") != marker_source
                or marker.get("digest") != source_digest
                or destination_digest != source_digest
            ):
                self.add("error", "CLAUDE_SKILL_ADAPTER", f"Claude skill mirror is stale or diverged from {source_relative}.", destination)
        for destination in managed_mirrors(self.root):
            if destination.resolve() not in expected_destinations:
                self.add(
                    "error", "CLAUDE_SKILL_ORPHAN",
                    "Managed Claude skill mirror has no canonical .agents/skills source; inspect it before pruning.",
                    destination,
                )

    def markdown_files(self):
        selected: set[Path] = set()
        guidance = self.manifest.get("guidance", {})
        if isinstance(guidance, dict):
            adapters = guidance.get("adapters", {})
            adapter_values = list(adapters.values()) if isinstance(adapters, dict) else []
            for value in [guidance.get("entrypoint"), *adapter_values]:
                path = self.repo_path(value, "MARKDOWN_PATH", required=False) if value else None
                if path and path.is_file() and path.suffix.lower() == ".md":
                    selected.add(path)
        knowledge = self.manifest.get("knowledge", {})
        if isinstance(knowledge, dict):
            index = self.repo_path(knowledge.get("index"), "KNOWLEDGE_INDEX", required=False)
            if index and index.exists():
                knowledge_root = index.parent
                for path in knowledge_root.rglob("*.md"):
                    relative_parts = path.relative_to(self.root).parts
                    if not any(part in SKIP_LINK_DIRS for part in relative_parts):
                        selected.add(path)
            for value in knowledge.values():
                path = self.repo_path(value, "KNOWLEDGE_LINK_PATH", required=False) if value else None
                if path and path.is_file() and path.suffix.lower() == ".md":
                    selected.add(path)
        for source in self.portable_skill_dirs():
            selected.update(path for path in source.rglob("*.md") if path.is_file())
        yield from sorted(selected)

    def check_links(self):
        inline_re = re.compile(
            r"!?\[[^\]]*\]\(\s*(?:<(?P<angle>[^>]+)>|(?P<plain>[^\s)]+))"
            r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
        )
        definition_re = re.compile(r"(?mi)^\s*\[([^\]]+)\]:\s*(?:<([^>]+)>|(\S+))")
        use_re = re.compile(r"(?<!!)\[([^\]]+)\]\[([^\]]*)\]")

        def normalized_label(value: str) -> str:
            return " ".join(value.strip().lower().split())

        def check_target(path: Path, raw: str):
            target = raw.strip()
            if not target or target.startswith("#"):
                return
            if re.match(r"(?i)^[A-Za-z]:(\\|/)", target):
                self.add("error", "LINK_ESCAPE", f"Local link must stay inside the repository (machine-specific drive path): {raw}", path)
                return
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                return
            target = unquote(target.split("#", 1)[0])
            resolved = path.parent / target
            if not self.inside(resolved):
                self.add("error", "LINK_ESCAPE", f"Local link escapes repository: {raw}", path)
            elif not resolved.exists():
                self.add("error", "BROKEN_LINK", f"Broken local link: {raw}", path)

        for path in self.markdown_files():
            text = read_text_sig(path)
            in_fence = fenced_lines(text)

            def line_of(offset: int) -> int:
                return text.count("\n", 0, offset) + 1

            definitions: dict[str, str] = {}
            for match in definition_re.finditer(text):
                if line_of(match.start()) in in_fence:
                    continue
                label, angle, plain = match.groups()
                definitions[normalized_label(label)] = angle or plain
                check_target(path, angle or plain)
            for match in inline_re.finditer(text):
                if line_of(match.start()) in in_fence:
                    continue
                check_target(path, match.group("angle") or match.group("plain"))
            for match in use_re.finditer(text):
                if line_of(match.start()) in in_fence:
                    continue
                label, reference = match.group(1), match.group(2)
                key = normalized_label(reference or label)
                if key not in definitions:
                    self.add("error", "UNDEFINED_LINK_REFERENCE", f"Undefined Markdown link reference: {reference or label}", path)

    def canonical_markdown_paths(self) -> list[Path]:
        result: set[Path] = set()
        knowledge = self.manifest.get("knowledge", {})
        if isinstance(knowledge, dict):
            for key in ("index", "architecture", "product", "operations", "quality", "generated"):
                value = knowledge.get(key)
                if value is None:
                    continue
                path = self.repo_path(value, "CANONICAL_PATH", required=False)
                if path and path.exists():
                    if path.is_dir():
                        result.update(path.rglob("*.md"))
                    elif path.suffix.lower() == ".md":
                        result.add(path)
                        if key in {"product", "operations", "quality"}:
                            result.update(path.parent.rglob("*.md"))
            index = self.repo_path(knowledge.get("index"), "CANONICAL_PATH", required=False)
            if index and index.is_file():
                architecture_details = index.parent / "architecture"
                if architecture_details.is_dir():
                    result.update(architecture_details.rglob("*.md"))
        return sorted(result)

    def check_metadata(self):
        placeholders: list[Path] = []
        for path in self.canonical_markdown_paths():
            text = read_text_sig(path)
            for field in ("Status", "Last verified", "Sources"):
                if not re.search(rf"(?mi)^{re.escape(field)}:\s*\S", text):
                    self.add("error", "METADATA_MISSING", f"Canonical document is missing '{field}:' metadata.", path)
            match = re.search(r"(?mi)^Last verified:\s*(\S.*?)\s*$", text)
            status = re.search(r"(?mi)^Status:\s*(\S+)\s*$", text)
            if status and status.group(1).lower() not in CANONICAL_STATUSES:
                self.add("error", "METADATA_STATUS", f"Unknown canonical document status: {status.group(1)}", path)
            if re.search(r"(?i)\bTODO\b", text):
                placeholders.append(path)
            if match:
                raw_date = match.group(1)
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
                    self.add("error", "VERIFICATION_DATE", "Last verified must use YYYY-MM-DD.", path)
                    continue
                try:
                    if datetime.strptime(raw_date, "%Y-%m-%d").date() > date.today():
                        self.add("error", "FUTURE_VERIFICATION", "Last verified date is in the future.", path)
                except ValueError:
                    self.add("error", "VERIFICATION_DATE", "Last verified must use YYYY-MM-DD.", path)
        if placeholders:
            names = ", ".join(path.relative_to(self.root).as_posix() for path in placeholders[:4])
            suffix = f", and {len(placeholders) - 4} more" if len(placeholders) > 4 else ""
            self.add(
                "warning", "PLACEHOLDER_CONTENT",
                f"{len(placeholders)} canonical document(s) still contain TODO placeholders: {names}{suffix}.",
            )
        # Generated-document branches stay link- and metadata-checked via the
        # generic canonical scan above; their generator declarations are a
        # project-native convention, not something this validator enforces.

    def check_plans(self):
        knowledge = self.manifest.get("knowledge", {})
        if not isinstance(knowledge, dict):
            return
        plans_value = knowledge.get("plans")
        if plans_value is None:
            return
        plans = self.repo_path(plans_value, "PLANS_PATH", required=False)
        if plans is None or not plans.exists():
            return
        identifiers: dict[str, Path] = {}
        for path in plans.rglob("*.md"):
            if path.name.lower() in {"readme.md", "index.md", "template.md"}:
                continue
            text = read_text_sig(path)
            match = re.search(r"(?mi)^Plan ID:\s*(\S+)\s*$", text)
            if not match:
                continue
            identifier = match.group(1).lower()
            if identifier in identifiers:
                self.add("error", "PLAN_ID_DUPLICATE", f"Plan ID '{match.group(1)}' is also used by {identifiers[identifier].relative_to(self.root).as_posix()}.", path)
            else:
                identifiers[identifier] = path
        active = plans / "active"
        if not active.exists():
            self.add("warning", "ACTIVE_PLANS_DIR", "Plans directory has no active/ subdirectory.", plans)
            return
        for path in sorted(active.rglob("*.md")):
            if path.name.lower() in {"readme.md", "index.md"}:
                continue
            text = read_text_sig(path)
            for heading in PLAN_HEADINGS:
                if not re.search(rf"(?mi)^##\s+{re.escape(heading)}\s*$", text):
                    self.add("error", "PLAN_FIELD", f"Active plan is missing heading: {heading}", path)
            status = re.search(r"(?mi)^Status:\s*(\S+)", text)
            if not status:
                self.add("error", "PLAN_STATUS", "Active plan is missing Status metadata.", path)
            elif status.group(1).lower() not in ACTIVE_PLAN_STATUSES:
                self.add("error", "PLAN_STATUS", f"Invalid active plan status: {status.group(1)}", path)

    @staticmethod
    def agent_sections(registry_text: str) -> tuple[list[tuple[str, str]], bool]:
        """Collect single-token '## <agent-id>' sections, skipping fenced code.

        Returns the sections and whether a fence was left open at the end —
        sections after an unclosed fence cannot be trusted."""
        sections: list[tuple[str, str]] = []
        fence_token: str | None = None
        current_id: str | None = None
        body: list[str] = []
        for line in registry_text.splitlines():
            stripped = line.lstrip()
            if fence_token:
                if stripped.startswith(fence_token):
                    fence_token = None
                elif current_id is not None:
                    body.append(line)
                continue
            if stripped.startswith("```"):
                fence_token = "```"
                continue
            if stripped.startswith("~~~"):
                fence_token = "~~~"
                continue
            heading = re.match(r"^##\s+(\S+)\s*$", line)
            if heading:
                if current_id is not None:
                    sections.append((current_id, "\n".join(body)))
                current_id = heading.group(1)
                body = []
            elif current_id is not None:
                body.append(line)
        if current_id is not None:
            sections.append((current_id, "\n".join(body)))
        return sections, fence_token is not None

    def parsed_agent_date(self, raw: str, code: str, field: str, path: Path) -> date | None:
        value = raw.strip().strip("`")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            self.add("error", code, f"{field} must use YYYY-MM-DD.", path)
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            self.add("error", code, f"{field} is not a valid calendar date: {value}", path)
            return None

    def check_agents(self):
        knowledge = self.manifest.get("knowledge", {})
        if not isinstance(knowledge, dict):
            return
        validation = self.manifest.get("validation")
        freshness = validation.get("freshnessDays", 90) if isinstance(validation, dict) else 90
        if not isinstance(freshness, int) or freshness < 1:
            freshness = 90

        registry_value = knowledge.get("agents")
        registered: dict[str, Path] = {}
        if registry_value is not None:
            registry = self.repo_path(registry_value, "AGENTS_REGISTRY_PATH", required=False)
            if registry is not None and registry.is_file():
                text = registry.read_text(encoding="utf-8", errors="replace")
                seen: dict[str, Path] = {}
                active_ids: list[str] = []
                sections, fence_unclosed = self.agent_sections(text)
                for agent_id, body in sections:
                    key = agent_id.lower()
                    if key in seen:
                        self.add(
                            "error", "AGENT_ID_DUPLICATE",
                            f"Agent id '{agent_id}' appears more than once in the registry "
                            "(ids must be unique, case-insensitively).",
                            registry,
                        )
                        continue
                    seen[key] = registry
                    registered[key] = registry
                    fields = {}
                    for name in ("Model", "Joined", "Status", "Last active"):
                        field_match = re.search(rf"(?mi)^-\s*{name}:\s*(.*?)\s*$", body)
                        if field_match is not None and field_match.group(1):
                            fields[name] = field_match.group(1)
                    missing = [name for name in ("Model", "Joined", "Status", "Last active") if name not in fields]
                    if missing:
                        self.add("error", "AGENT_FIELD", f"Agent '{agent_id}' is missing required field(s): {', '.join(missing)}.", registry)
                    status = fields.get("Status")
                    if status is not None and status.strip().lower() not in AGENT_STATUSES:
                        self.add(
                            "error", "AGENT_STATUS",
                            f"Agent '{agent_id}' has invalid Status '{status}'; use one of: {', '.join(sorted(AGENT_STATUSES))}.",
                            registry,
                        )
                    if status is not None and status.strip().lower() == "active":
                        active_ids.append(agent_id)
                    joined = self.parsed_agent_date(fields["Joined"], "AGENT_DATE", "Joined", registry) if "Joined" in fields else None
                    last_active_raw = fields.get("Last active")
                    last_active = None
                    if last_active_raw is not None:
                        last_active = self.parsed_agent_date(last_active_raw, "AGENT_DATE", "Last active", registry)
                    today = date.today()
                    if joined is not None and joined > today:
                        self.add("error", "AGENT_DATE", f"Agent '{agent_id}' Joined date is in the future.", registry)
                    if last_active is not None and last_active > today:
                        self.add("error", "AGENT_DATE", f"Agent '{agent_id}' Last active date is in the future.", registry)
                    elif last_active is not None and (today - last_active).days > freshness:
                        advice = "" if (status or "").strip().lower() == "retired" else " Refresh Last active or set Status to idle/retired."
                        self.add(
                            "warning", "AGENT_STALE",
                            f"Agent '{agent_id}' was last active {(today - last_active).days} days ago.{advice}",
                            registry,
                        )
                if fence_unclosed:
                    self.add(
                        "warning", "AGENT_FENCE_UNCLOSED",
                        "Registry has an unclosed code fence; agent sections after it are ignored. Close the fence or remove it.",
                        registry,
                    )
                if len(active_ids) > 1:
                    self.add(
                        "error", "AGENT_MULTIPLE_ACTIVE",
                        f"{len(active_ids)} agents are marked active ({', '.join(active_ids)}); "
                        "this repository allows a single writer session — set all but one to idle/retired.",
                        registry,
                    )

        tasks_value = knowledge.get("tasks")
        if tasks_value is None:
            return
        tasks_dir = self.repo_path(tasks_value, "TASKS_PATH", required=False)
        if tasks_dir is None or not tasks_dir.is_dir():
            return
        for path in sorted(tasks_dir.glob("*.md")):
            if path.name.lower() in TASK_BOARD_IGNORES:
                continue
            agent_key = path.stem.lower()
            if agent_key not in registered:
                self.add(
                    "warning", "TASK_BOARD_UNREGISTERED",
                    f"Task board '{path.name}' has no matching section in the configured agent registry; register it or remove the board.",
                    path,
                )
        archive = tasks_dir / "archive"
        if archive.is_dir():
            for path in sorted(archive.glob("*.md")):
                if path.name.lower() in TASK_BOARD_IGNORES:
                    continue
                stem_match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(\S+)", path.stem)
                if stem_match is None:
                    self.add(
                        "warning", "ARCHIVE_NAME",
                        f"Archive file should be named <YYYY-MM-DD>-<agent-id>.md; found '{path.name}'.",
                        path,
                    )
                    continue
                try:
                    datetime.strptime(stem_match.group(1), "%Y-%m-%d")
                except ValueError:
                    self.add(
                        "warning", "ARCHIVE_NAME",
                        f"Archive date '{stem_match.group(1)}' is not a valid calendar day in '{path.name}'.",
                        path,
                    )

    def normalized_commands(self) -> dict[str, list[dict[str, Any]]]:
        block = self.manifest.get("commands", {})
        if not isinstance(block, dict):
            self.add("error", "COMMAND_BLOCK", "commands must be an object.", ".ai/harness.json")
            return {}
        normalized: dict[str, list[dict[str, Any]]] = {}
        for group, value in block.items():
            if not isinstance(value, list):
                self.add("error", "COMMAND_GROUP", f"commands.{group} must be an array.", ".ai/harness.json")
                continue
            items = value
            normalized[group] = []
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    self.add("error", "COMMAND_SHAPE", f"commands.{group}[{index}] must be an object.", ".ai/harness.json")
                    continue
                argv = item.get("argv")
                if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
                    self.add("error", "COMMAND_ARGV", f"commands.{group}[{index}].argv must be a non-empty string array.", ".ai/harness.json")
                    continue
                oversized = [position for position, value in enumerate(argv) if len(value) > MAX_ARGV_ELEMENT_CHARS]
                if oversized:
                    self.add("error", "COMMAND_ARGV_LENGTH", f"commands.{group}[{index}] has argument(s) over {MAX_ARGV_ELEMENT_CHARS} characters at positions: {', '.join(map(str, oversized))}.", ".ai/harness.json")
                    continue
                absolute_indexes = [position for position, value in enumerate(argv) if is_absolute_argument(value)]
                if absolute_indexes:
                    positions = ", ".join(str(position) for position in absolute_indexes)
                    self.add("error", "COMMAND_ABSOLUTE_PATH", f"commands.{group}[{index}] uses machine-specific absolute path arguments at positions: {positions}.", ".ai/harness.json")
                    continue
                sensitive_indexes = sensitive_argument_positions(argv)
                if sensitive_indexes:
                    positions = ", ".join(str(position) for position in sensitive_indexes)
                    self.add(
                        "error", "COMMAND_SECRET_ARGUMENT",
                        f"commands.{group}[{index}] appears to store sensitive values at argument positions: {positions}; use environment or credential-provider configuration instead.",
                        ".ai/harness.json",
                    )
                    continue
                cwd_value = item.get("cwd", ".")
                cwd = self.repo_path(cwd_value, "COMMAND_CWD", required=True)
                if cwd is None or not cwd.is_dir():
                    if cwd is not None and cwd.exists():
                        self.add("error", "COMMAND_CWD_TYPE", f"commands.{group}[{index}].cwd must be a directory.", cwd)
                    continue
                timeout = item.get("timeoutSeconds", 900)
                if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 7200:
                    self.add("error", "COMMAND_TIMEOUT", f"commands.{group}[{index}] timeout must be 1..7200 seconds.", ".ai/harness.json")
                    continue
                required = item.get("required", False)
                if not isinstance(required, bool):
                    self.add("error", "COMMAND_REQUIRED", f"commands.{group}[{index}].required must be boolean.", ".ai/harness.json")
                    continue
                normalized[group].append({**item, "argv": argv, "cwdPath": cwd, "timeoutSeconds": timeout})
        return normalized

    def check_commands(self) -> dict[str, list[dict[str, Any]]]:
        commands = self.normalized_commands()
        for group, items in sorted(commands.items()):
            if not items:
                continue
            if group in ("deploy", "release", "migrate", "production"):
                self.add(
                    "warning", "UNSAFE_COMMAND_GROUP",
                    f"'{group}' commands are recorded but will never run through the universal validator.",
                    ".ai/harness.json",
                )
            elif group != "setup" and group not in COMMAND_ORDER:
                self.add(
                    "warning", "COMMAND_GROUP_NEVER_RUNS",
                    f"Command group '{group}' is registered but the universal validator only runs "
                    f"{', '.join(COMMAND_ORDER)} ('setup' is the reserved manual bootstrap group); "
                    f"document how '{group}' executes or fold it into a runnable group.",
                    ".ai/harness.json",
                )
        return commands

    def check_architecture(self, commands: dict[str, list[dict[str, Any]]]):
        # Zone graphs belong to project-native linters (ArchUnit, import-linter,
        # dependency-cruiser). The universal validator only enforces the glue:
        # declaring enforcement requires a runnable architecture command.
        block = self.manifest.get("architecture", {})
        if not isinstance(block, dict):
            self.add("error", "ARCH_BLOCK", "architecture must be an object.", ".ai/harness.json")
            return
        if block.get("enforced") is True and not commands.get("architecture"):
            self.add("error", "ARCH_NOT_ENFORCED", "architecture.enforced is true but no architecture command is registered.", ".ai/harness.json")
        elif block.get("enforced") is not True:
            self.add("warning", "ARCH_OBSERVATIONAL", "Architecture is documented but not declared mechanically enforced.", ".ai/harness.json")

    def run_commands(self, commands: dict[str, list[dict[str, Any]]]):
        for group in COMMAND_ORDER:
            for item in commands.get(group, []):
                argv = item["argv"]
                # Bare tool names are resolved through PATH (never the current
                # directory) so a repo-local same-named executable cannot shadow
                # the registered command on Windows.
                executable = argv[0]
                if not Path(executable).drive and not PurePosixPath(executable).is_absolute() and "/" not in executable and "\\" not in executable:
                    resolved = shutil.which(executable)
                    if resolved:
                        argv = [resolved, *argv[1:]]
                safe_argv = redact_argv(argv)
                cwd = item.get("cwdPath")
                if cwd is None:
                    continue
                start = time.monotonic()
                try:
                    result = subprocess.run(
                        argv,
                        cwd=cwd,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=item["timeoutSeconds"],
                    )
                    duration = round(time.monotonic() - start, 3)
                    record = {
                        "group": group, "argv": safe_argv, "cwd": str(cwd.relative_to(self.root)),
                        "exitCode": result.returncode, "durationSeconds": duration,
                    }
                    self.command_results.append(record)
                    if result.returncode != 0:
                        severity = "error" if item.get("required", False) else "warning"
                        self.add(severity, "COMMAND_FAILED", f"Command failed ({result.returncode}): {' '.join(safe_argv)}", cwd)
                except FileNotFoundError:
                    self.add("error" if item.get("required", False) else "warning", "COMMAND_MISSING", f"Command executable not found: {safe_argv[0]}", cwd)
                except subprocess.TimeoutExpired:
                    self.add("error" if item.get("required", False) else "warning", "COMMAND_TIMEOUT", f"Command timed out: {' '.join(safe_argv)}", cwd)
                except OSError as exc:
                    self.add(
                        "error" if item.get("required", False) else "warning",
                        "COMMAND_EXECUTION",
                        f"Command could not start: {redact_text(str(exc))}",
                        cwd,
                    )

    def validate(self, run_commands: bool = False):
        self.load_manifest()
        self.check_structure()
        if not self.manifest_loaded:
            return
        validation = self.manifest.get("validation")
        raw_checks = validation.get("requiredChecks") if isinstance(validation, dict) else None
        checks = set(raw_checks) if isinstance(raw_checks, list) and all(isinstance(x, str) for x in raw_checks) else SUPPORTED_CHECKS
        if "guidance-budget" in checks:
            self.check_guidance_budget()
        if "adapter-consistency" in checks:
            self.check_adapter()
        if "links" in checks:
            self.check_links()
        if "metadata" in checks:
            self.check_metadata()
        if "plan-state" in checks:
            self.check_plans()
        if "agents" in checks:
            self.check_agents()
        commands = self.check_commands() if self.strict or "commands" in checks or "architecture" in checks or run_commands else {}
        if "architecture" in checks:
            self.check_architecture(commands)
        if run_commands:
            self.run_commands(commands)

    def report(self) -> dict[str, Any]:
        counts = {severity: sum(1 for finding in self.findings if finding.severity == severity) for severity in ("error", "warning", "info")}
        return {
            "root": str(self.root),
            "valid": counts["error"] == 0,
            "strict": self.strict,
            "counts": counts,
            "findings": [asdict(finding) for finding in self.findings],
            "commandResults": self.command_results,
        }


def sanitize_markdown(value: str) -> str:
    """Neutralize markdown structure injection from untrusted finding text.

    Folding control characters and newlines means one finding always renders as
    exactly one bullet line: no fake headings, no opening code fences.
    """
    return re.sub(r"[\x00-\x1f\x7f]+", " ", value)


def report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AI-first Harness Validation", "",
        f"- Root: `{report['root']}`",
        f"- Result: **{'PASS' if report['valid'] else 'FAIL'}**",
        f"- Errors/warnings/info: {report['counts']['error']}/{report['counts']['warning']}/{report['counts']['info']}", "",
        "## Findings", "",
    ]
    if not report["findings"]:
        lines.append("- No findings.")
    for finding in report["findings"]:
        location = f" (`{sanitize_markdown(finding['path'])}`)" if finding.get("path") else ""
        lines.append(f"- **{finding['severity'].upper()} {sanitize_markdown(finding['code'])}**{location}: {sanitize_markdown(finding['message'])}")
    if report["commandResults"]:
        lines.extend(["", "## Commands", ""])
        for item in report["commandResults"]:
            lines.append(f"- `{ ' '.join(item['argv']) }`: exit {item['exitCode']} in {item['durationSeconds']}s")
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
    parser.add_argument("--strict", action="store_true", help="Promote warnings to errors")
    parser.add_argument(
        "--run-commands", action="store_true",
        help="Run reviewed registered verification groups without a shell; repository commands are trusted code and their output is discarded",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="Optional report path; stdout is the default")
    parser.add_argument("--force-output", action="store_true", help="Allow --output to replace an existing file")
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    if args.force_output and not args.output:
        parser.error("--force-output requires --output")
    validator = Validator(root, strict=args.strict)
    validator.validate(run_commands=args.run_commands)
    report = validator.report()
    content = json.dumps(report, indent=2, ensure_ascii=False) + "\n" if args.format == "json" else report_markdown(report)
    if args.output:
        write_output(parser, args.output, content, args.force_output)
    else:
        sys.stdout.write(content)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
