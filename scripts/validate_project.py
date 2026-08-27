#!/usr/bin/env python3
"""Validate an AI-first project harness with no third-party dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
HARNESS_SCHEMA_REFERENCE = "./harness.schema.json"
HARNESS_SCHEMA_FINGERPRINT = "b54b9a41b7a5ccea595cf6f35d35511028e215fb9ba737229224f640b8496a75"
COMMAND_ORDER = ("architecture", "docs", "test", "lint", "typecheck", "build")
PLAN_HEADINGS = (
    "Goal", "Scope and non-goals", "Progress", "Decisions", "Verification",
    "Risks and blockers", "Next action",
)
CANONICAL_STATUSES = {"verified", "observed", "proposed", "generated"}
ACTIVE_PLAN_STATUSES = {"active", "blocked", "paused"}
AGENT_STATUSES = {"active", "idle", "retired"}
TASK_BOARD_IGNORES = {"readme.md", "template.md"}
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
        or value.startswith(("~/", "~\\"))
    )


def fenced_lines(text: str) -> set[int]:
    """Line numbers (1-based) inside fenced code blocks, for link scanning."""
    fenced: set[int] = []
    inside = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if inside:
            fenced.append(number)
    return set(fenced)


def schema_violations(value: Any, schema: dict[str, Any], location: str = "$") -> list[str]:
    """Validate the JSON Schema subset used by harness.schema.json."""
    errors: list[str] = []
    expected = schema.get("type")
    type_checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
    }
    if expected in type_checks and not type_checks[expected](value):
        return [f"{location}: expected {expected}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{location}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location}: value is not in the allowed set")
    if isinstance(value, str) and isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
        errors.append(f"{location}: string is shorter than {schema['minLength']}")
    if isinstance(value, int) and not isinstance(value, bool):
        if isinstance(schema.get("minimum"), int) and value < schema["minimum"]:
            errors.append(f"{location}: value is below {schema['minimum']}")
        if isinstance(schema.get("maximum"), int) and value > schema["maximum"]:
            errors.append(f"{location}: value is above {schema['maximum']}")
    if isinstance(value, list):
        if isinstance(schema.get("minItems"), int) and len(value) < schema["minItems"]:
            errors.append(f"{location}: array has fewer than {schema['minItems']} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(schema_violations(item, item_schema, f"{location}[{index}]"))
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{location}: missing required property {key!r}")
        properties = schema.get("properties", {})
        properties = properties if isinstance(properties, dict) else {}
        for key, child_schema in properties.items():
            if key in value and isinstance(child_schema, dict):
                errors.extend(schema_violations(value[key], child_schema, f"{location}.{key}"))
        additional = schema.get("additionalProperties", True)
        for key in value.keys() - properties.keys():
            if additional is False:
                errors.append(f"{location}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                errors.extend(schema_violations(value[key], additional, f"{location}.{key}"))
    return errors


def schema_fingerprint(schema: dict[str, Any]) -> str:
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    path: str | None = None


class Validator:
    def __init__(self, root: Path, strict: bool = False, include_command_output: bool = False):
        self.root = root.resolve()
        self.strict = strict
        self.include_command_output = include_command_output
        self.findings: list[Finding] = []
        self.manifest: dict[str, Any] = {}
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
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self.add("error", "MANIFEST_INVALID", f"Cannot parse manifest JSON: {exc}", path)
            return
        if not isinstance(value, dict):
            self.add("error", "MANIFEST_INVALID", "Manifest root must be an object.", path)
            return
        self.manifest = value

    def check_structure(self):
        if not self.manifest:
            return
        if self.manifest.get("$schema") != HARNESS_SCHEMA_REFERENCE:
            self.add(
                "error", "SCHEMA_PATH",
                f"$schema must be {HARNESS_SCHEMA_REFERENCE!r}; custom schema locations are not supported.",
                ".ai/harness.json",
            )
        schema_path = self.root / ".ai/harness.schema.json"
        if not schema_path.exists():
            self.add("error", "SCHEMA_MISSING", "Missing fixed harness schema: .ai/harness.schema.json.", schema_path)
        else:
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                if not isinstance(schema, dict) or schema.get("type") != "object":
                    self.add("error", "SCHEMA_INVALID", "Harness schema must be a JSON object schema.", schema_path)
                else:
                    if schema_fingerprint(schema) != HARNESS_SCHEMA_FINGERPRINT:
                        self.add(
                            "error", "SCHEMA_DRIFT",
                            "harness.schema.json differs from the fixed schemaVersion 1 contract.",
                            schema_path,
                        )
                    for violation in schema_violations(self.manifest, schema):
                        self.add("error", "SCHEMA_CONTRACT", violation, ".ai/harness.json")
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                self.add("error", "SCHEMA_INVALID", f"Cannot parse harness schema: {exc}", schema_path)
        guidance = self.manifest.get("guidance")
        if isinstance(guidance, dict):
            self.repo_path(guidance.get("entrypoint"), "GUIDANCE_PATH")
        knowledge = self.manifest.get("knowledge")
        if isinstance(knowledge, dict):
            for key in ("index", "architecture", "product"):
                self.repo_path(knowledge.get(key), f"KNOWLEDGE_{key.upper()}")
            for key in ("plans", "operations", "quality", "generated", "agents", "tasks"):
                if key in knowledge:
                    self.repo_path(knowledge.get(key), f"KNOWLEDGE_{key.upper()}")
        validation = self.manifest.get("validation")
        if isinstance(validation, dict):
            checks = validation.get("requiredChecks")
        else:
            checks = None
        if isinstance(checks, list) and all(isinstance(check, str) for check in checks):
            unknown = sorted(set(checks) - SUPPORTED_CHECKS)
            if unknown:
                self.add("error", "UNKNOWN_CHECK", f"Unknown required checks: {', '.join(unknown)}", ".ai/harness.json")
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
            text = path.read_text(encoding="utf-8", errors="replace")
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
        formatter_config = any((self.root / name).exists() for name in (
            ".prettierrc", ".prettierrc.json", ".editorconfig", "ruff.toml", ".ruff.toml",
            "biome.json", "eslint.config.js", "eslint.config.mjs",
        ))
        if formatter_config:
            leakage = re.findall(r"(?im)^.*\b(indentation|indent|semicolon|single quotes?|double quotes?|line length)\b.*$", text)
            if leakage:
                self.add("warning", "LINT_LEAKAGE", "Guidance may restate formatter rules; keep only non-obvious invocation or exception details.", path)

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
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.add("error", "CLAUDE_READ", f"Cannot read Claude adapter: {exc}", path)
            return
        entry = guidance.get("entrypoint", "AGENTS.md")
        if f"@{entry}" not in text:
            self.add("error", "CLAUDE_IMPORT", f"Claude adapter must import @{entry} or symlink to it.", path)
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
            if not target or target.startswith("#") or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                return
            target = unquote(target.split("#", 1)[0])
            resolved = path.parent / target
            if not self.inside(resolved):
                self.add("error", "LINK_ESCAPE", f"Local link escapes repository: {raw}", path)
            elif not resolved.exists():
                self.add("error", "BROKEN_LINK", f"Broken local link: {raw}", path)

        for path in self.markdown_files():
            text = path.read_text(encoding="utf-8", errors="replace")
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
        validation = self.manifest.get("validation")
        freshness = validation.get("freshnessDays", 90) if isinstance(validation, dict) else 90
        if not isinstance(freshness, int) or freshness < 1:
            freshness = 90
        placeholders: list[Path] = []
        for path in self.canonical_markdown_paths():
            text = path.read_text(encoding="utf-8", errors="replace")
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
                    verified = datetime.strptime(raw_date, "%Y-%m-%d").date()
                    age = (date.today() - verified).days
                    if age < 0:
                        self.add("error", "FUTURE_VERIFICATION", "Last verified date is in the future.", path)
                    elif age > freshness:
                        self.add("warning", "STALE_DOCUMENT", f"Canonical document was last verified {age} days ago.", path)
                except ValueError:
                    self.add("error", "VERIFICATION_DATE", "Last verified must use YYYY-MM-DD.", path)
        if placeholders:
            names = ", ".join(path.relative_to(self.root).as_posix() for path in placeholders[:4])
            suffix = f", and {len(placeholders) - 4} more" if len(placeholders) > 4 else ""
            self.add(
                "warning", "PLACEHOLDER_CONTENT",
                f"{len(placeholders)} canonical document(s) still contain TODO placeholders: {names}{suffix}.",
            )
        knowledge = self.manifest.get("knowledge")
        generated_value = knowledge.get("generated") if isinstance(knowledge, dict) else None
        generated = self.repo_path(generated_value, "GENERATED_PATH", required=False) if generated_value else None
        if generated and generated.exists():
            paths = generated.rglob("*.md") if generated.is_dir() else [generated]
            generator_placeholders: list[Path] = []
            for path in paths:
                text = path.read_text(encoding="utf-8", errors="replace")
                generator = re.search(r"(?mi)^Generator:\s*(\S.*?)\s*$", text)
                if not generator:
                    self.add("error", "GENERATOR_MISSING", "Generated documentation must declare 'Generator:'.", path)
                elif re.search(r"(?i)\b(TODO|register|not configured|unknown)\b", generator.group(1)):
                    generator_placeholders.append(path)
            if generator_placeholders:
                self.add(
                    "warning", "GENERATOR_PLACEHOLDER",
                    f"{len(generator_placeholders)} generated document(s) have no concrete regeneration command yet.",
                )

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
            text = path.read_text(encoding="utf-8", errors="replace")
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
        for path in active.glob("*.md"):
            if path.name.lower() in {"readme.md", "index.md"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for heading in PLAN_HEADINGS:
                if not re.search(rf"(?mi)^##\s+{re.escape(heading)}\s*$", text):
                    self.add("error", "PLAN_FIELD", f"Active plan is missing heading: {heading}", path)
            status = re.search(r"(?mi)^Status:\s*(\S+)", text)
            if not status:
                self.add("error", "PLAN_STATUS", "Active plan is missing Status metadata.", path)
            elif status.group(1).lower() not in ACTIVE_PLAN_STATUSES:
                self.add("error", "PLAN_STATUS", f"Invalid active plan status: {status.group(1)}", path)

    @staticmethod
    def agent_sections(registry_text: str) -> list[tuple[str, str]]:
        """Collect single-token '## <agent-id>' sections, skipping fenced code."""
        sections: list[tuple[str, str]] = []
        fenced = False
        current_id: str | None = None
        body: list[str] = []
        for line in registry_text.splitlines():
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                if current_id is not None:
                    body.append(line)
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
        return sections

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
                for agent_id, body in self.agent_sections(text):
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
                        self.add(
                            "warning", "AGENT_STALE",
                            f"Agent '{agent_id}' was last active {(today - last_active).days} days ago; set Status to idle/retired or refresh the date.",
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
                    f"Task board '{path.name}' has no matching agent section in the registry; add an entry to docs/agents/REGISTRY.md or remove the board.",
                    path,
                )
        archive = tasks_dir / "archive"
        if archive.is_dir():
            for path in sorted(archive.glob("*.md")):
                if path.name.lower() in TASK_BOARD_IGNORES:
                    continue
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-\S+", path.stem):
                    self.add(
                        "warning", "ARCHIVE_NAME",
                        f"Archive file should be named <YYYY-MM-DD>-<agent-id>.md; found '{path.name}'.",
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
        if self.strict and not any(item.get("required") for items in commands.values() for item in items):
            self.add("error", "REQUIRED_COMMANDS", "Strict validation requires at least one registered required command.", ".ai/harness.json")
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
        block = self.manifest.get("architecture", {})
        if not isinstance(block, dict):
            self.add("error", "ARCH_BLOCK", "architecture must be an object.", ".ai/harness.json")
            return
        zones = block.get("zones", [])
        if not isinstance(zones, list):
            self.add("error", "ARCH_ZONES", "architecture.zones must be an array.", ".ai/harness.json")
            return
        ids: set[str] = set()
        for index, zone in enumerate(zones):
            if not isinstance(zone, dict) or not isinstance(zone.get("id"), str) or not zone.get("id", "").strip():
                self.add("error", "ARCH_ZONE", f"architecture.zones[{index}] needs a non-empty string id.", ".ai/harness.json")
                continue
            zone_id = zone["id"]
            if zone_id in ids:
                self.add("error", "ARCH_ZONE_DUPLICATE", f"Duplicate architecture zone id: {zone_id}", ".ai/harness.json")
            ids.add(zone_id)
            paths = zone.get("paths", [])
            if not isinstance(paths, list) or not paths:
                self.add("error", "ARCH_ZONE_PATHS", f"Architecture zone '{zone_id}' has no paths.", ".ai/harness.json")
            else:
                for pattern in paths:
                    if not isinstance(pattern, str) or is_absolute_argument(pattern) or ".." in Path(pattern).parts:
                        self.add("error", "ARCH_ZONE_PATTERN", f"Invalid path pattern in zone '{zone_id}': {pattern}", ".ai/harness.json")
                    elif not any(self.root.glob(pattern)):
                        self.add("warning", "ARCH_ZONE_EMPTY", f"Zone '{zone_id}' pattern matches no files: {pattern}", ".ai/harness.json")
        for zone in zones:
            if not isinstance(zone, dict):
                continue
            dependencies = zone.get("mayDependOn", [])
            if "mayDependOn" not in zone or not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
                self.add("error", "ARCH_DEP_LIST", f"Zone '{zone.get('id')}' mayDependOn must be a string array.", ".ai/harness.json")
                continue
            for dependency in dependencies:
                if dependency not in ids:
                    self.add("error", "ARCH_UNKNOWN_DEP", f"Zone '{zone.get('id')}' references unknown zone '{dependency}'.", ".ai/harness.json")
        if block.get("enforced") is True and not commands.get("architecture"):
            self.add("error", "ARCH_NOT_ENFORCED", "architecture.enforced is true but no architecture command is registered.", ".ai/harness.json")
        elif block.get("enforced") is not True:
            self.add("warning", "ARCH_OBSERVATIONAL", "Architecture is documented but not declared mechanically enforced.", ".ai/harness.json")

    def run_commands(self, commands: dict[str, list[dict[str, Any]]]):
        for group in COMMAND_ORDER:
            for item in commands.get(group, []):
                argv = item["argv"]
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
                        capture_output=True,
                        text=False,
                        timeout=item["timeoutSeconds"],
                    )
                    duration = round(time.monotonic() - start, 3)
                    stdout = (result.stdout or b"").decode("utf-8", errors="replace")
                    stderr = (result.stderr or b"").decode("utf-8", errors="replace")
                    record = {
                        "group": group, "argv": safe_argv, "cwd": str(cwd.relative_to(self.root)),
                        "exitCode": result.returncode, "durationSeconds": duration,
                        "stdoutCharacters": len(stdout), "stderrCharacters": len(stderr),
                    }
                    if self.include_command_output:
                        record["stdoutTail"] = redact_text(stdout[-4000:])
                        record["stderrTail"] = redact_text(stderr[-4000:])
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
        if not self.manifest:
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
        location = f" (`{finding['path']}`)" if finding.get("path") else ""
        lines.append(f"- **{finding['severity'].upper()} {finding['code']}**{location}: {finding['message']}")
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
        help="Run reviewed registered verification groups without a shell; repository commands are trusted code",
    )
    parser.add_argument(
        "--include-command-output", action="store_true",
        help="Include redacted bounded command output in the report; omitted by default",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="Optional report path; stdout is the default")
    parser.add_argument("--force-output", action="store_true", help="Allow --output to replace an existing file")
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    if args.include_command_output and not args.run_commands:
        parser.error("--include-command-output requires --run-commands")
    if args.force_output and not args.output:
        parser.error("--force-output requires --output")
    validator = Validator(root, strict=args.strict, include_command_output=args.include_command_output)
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
