#!/usr/bin/env python3
"""Safely preview or apply an AI-first project harness scaffold."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True

from audit_project import analyze, discover_commands


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "project-template"
VALIDATOR_SOURCE = SKILL_ROOT / "scripts" / "validate_project.py"
SKILL_ADAPTER_SOURCE = SKILL_ROOT / "scripts" / "sync_skill_adapters.py"


def render(text: str, replacements: dict[str, str]) -> str:
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", value)
    return text


OPTIONAL_BRANCHES = ("docs/plans", "docs/operations", "docs/quality", "docs/generated")


def template_files(profile: str) -> list[tuple[Path, Path]]:
    files = []
    for path in TEMPLATE_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(TEMPLATE_ROOT)
        if profile == "core" and any(relative.as_posix().startswith(prefix + "/") for prefix in OPTIONAL_BRANCHES):
            continue
        files.append((path, relative))
    files.append((VALIDATOR_SOURCE, Path("tools/ai/validate_harness.py")))
    files.append((SKILL_ADAPTER_SOURCE, Path("tools/ai/sync_skill_adapters.py")))
    return sorted(files, key=lambda item: item[1].as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="Repository or project path")
    parser.add_argument("--mode", choices=("auto", "greenfield", "brownfield"), default="auto")
    parser.add_argument("--spec-model", choices=("living", "flow-forward", "flow-back"))
    parser.add_argument("--project-name")
    parser.add_argument(
        "--knowledge-profile", choices=("core", "full"), default="core",
        help="Create core knowledge (default), or include plans/operations/quality/generated branches",
    )
    parser.add_argument("--apply", action="store_true", help="Create missing files; default is preview only")
    args = parser.parse_args()

    root = Path(args.repo).resolve()
    if not root.is_dir():
        parser.error(f"project directory must already exist: {root}")
    report = analyze(root)
    mode = report["modeRecommendation"] if args.mode == "auto" else args.mode
    spec_model = args.spec_model or ("living" if mode == "greenfield" else "flow-forward")
    project_name = args.project_name or root.name
    commands_json = json.dumps(discover_commands(root), indent=2, ensure_ascii=False)
    arch_status = "observed"
    intent_status = "proposed" if mode == "greenfield" else "observed"
    replacements = {
        "PROJECT_NAME": project_name,
        "PROJECT_NAME_JSON": json.dumps(project_name, ensure_ascii=False),
        "MODE": mode,
        "SPEC_MODEL": spec_model,
        "DATE": date.today().isoformat(),
        "ARCH_STATUS": arch_status,
        "INTENT_STATUS": intent_status,
        "COMMANDS_JSON": commands_json,
        "OPTIONAL_KNOWLEDGE": (
            ',\n    "plans": "docs/plans",\n    "operations": "docs/operations/index.md",'
            '\n    "quality": "docs/quality/QUALITY.md",\n    "generated": "docs/generated"'
            if args.knowledge_profile == "full" else ""
        ),
        "OPTIONAL_PROJECT_MAP": (
            "- Active execution plans: `docs/plans/active/`\n"
            "- Operations and debugging: `docs/operations/index.md`\n"
            "- Quality and debt: `docs/quality/`\n"
            "- Generated knowledge: `docs/generated/` (do not hand-edit generated output)"
            if args.knowledge_profile == "full" else
            "- Optional plans, operations, quality, and generated branches are intentionally omitted; add and declare them when needed."
        ),
        "OPTIONAL_ROUTING_ROWS": (
            "| Current multi-step work | [Active plans](plans/active/) |\n"
            "| Run, debug, observe, recover | [Operations](operations/index.md) |\n"
            "| Quality gaps and technical debt | [Quality](quality/) |\n"
            "| Derived schemas and references | [Generated knowledge](generated/) |"
            if args.knowledge_profile == "full" else
            "| Optional knowledge branches | Intentionally omitted; declare them in `.ai/harness.json` when they become useful. |"
        ),
        "OPTIONAL_PLAN_WORKFLOW": (
            "- For work that crosses sessions or components, create or update a plan from `docs/plans/TEMPLATE.md`."
            if args.knowledge_profile == "full" else
            "- For multi-session work, add and declare `docs/plans/` before creating an active plan."
        ),
    }

    operations: list[tuple[str, Path, Path | None]] = []
    blockers: list[tuple[Path, str]] = []
    for source, relative in template_files(args.knowledge_profile):
        target = root / relative
        if target.is_symlink():
            blockers.append((target, "target is a symlink"))
            action = "block"
        elif target.exists() and target.is_dir():
            blockers.append((target, "a directory exists where a file is required"))
            action = "block"
        else:
            action = "skip" if target.exists() else "create"
        parent = target.parent
        while parent != root:
            if parent.is_symlink():
                blockers.append((parent, "ancestor is a symlink"))
                action = "block"
                break
            if parent.exists() and not parent.is_dir():
                blockers.append((parent, "a file blocks a required directory"))
                action = "block"
                break
            parent = parent.parent
        operations.append((action, target, source))

    print(f"Project: {root}")
    print(f"Mode: {mode}")
    print(f"Specification model: {spec_model}")
    print(f"Knowledge profile: {args.knowledge_profile}")
    print("Operations:")
    for action, target, _ in operations:
        print(f"  {action:6} {target.relative_to(root).as_posix()}")

    conflicts = [target for action, target, _ in operations if action == "skip"]
    if conflicts:
        print("\nExisting files will be preserved. Review and merge them manually after scaffolding.")
    if blockers:
        print("\nBlocking path conflicts:")
        seen: set[tuple[Path, str]] = set()
        for target, reason in blockers:
            if (target, reason) not in seen:
                seen.add((target, reason))
                print(f"  error  {target.relative_to(root).as_posix()}: {reason}")
        print("No files were written.")
        return 1
    if not args.apply:
        print("\nPreview only. Re-run with --apply to create missing files.")
        return 0

    prepared: dict[Path, tuple[str, str | bytes]] = {}
    for action, target, source in operations:
        if action != "create" or source is None:
            continue
        if source.suffix.lower() in {".md", ".json", ".py", ""}:
            prepared[target] = ("text", render(source.read_text(encoding="utf-8"), replacements))
        else:
            prepared[target] = ("bytes", source.read_bytes())

    created = 0
    for action, target, source in operations:
        if action != "create" or source is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        kind, content = prepared[target]
        if kind == "text":
            target.write_text(content, encoding="utf-8", newline="\n")
        else:
            target.write_bytes(content)
        created += 1
    print(f"\nCreated {created} files. Preserved {len(conflicts)} existing files.")
    print("Validate with: python tools/ai/validate_harness.py .")
    if mode == "brownfield":
        print("Brownfield note: replace TODOs only with code-backed observations; keep proposed changes in active plans.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
