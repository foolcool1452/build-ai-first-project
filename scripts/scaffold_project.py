#!/usr/bin/env python3
"""Safely preview or apply an AI-first project harness scaffold."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True

from audit_project import analyze


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "project-template"
VALIDATOR_SOURCE = SKILL_ROOT / "scripts" / "validate_project.py"
SKILL_ADAPTER_SOURCE = SKILL_ROOT / "scripts" / "sync_skill_adapters.py"
FULL_ONLY_BRANCHES = (".ai", "docs/agents", "docs/plans")
TEMPLATE_TOKEN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")


def render(text: str, replacements: dict[str, str]) -> str:
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def template_files(profile: str) -> list[tuple[Path, Path]]:
    files = []
    for path in TEMPLATE_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(TEMPLATE_ROOT)
        if profile == "lite" and any(
            relative.as_posix().startswith(prefix + "/") for prefix in FULL_ONLY_BRANCHES
        ):
            continue
        files.append((path, relative))
    if profile == "full":
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
        "--profile", choices=("auto", "lite", "full"), default="auto",
        help="Landing set: auto recommends from audit evidence; lite keeps the verified core; full adds plans and agent coordination",
    )
    parser.add_argument("--apply", action="store_true", help="Create missing files; default is preview only")
    parser.add_argument("--diff", action="store_true",
                        help="Read-only: classify the landing set against existing files (missing/same/DIFFER)")
    parser.add_argument("--write-new", action="store_true",
                        help="With --diff: write rendered copies of differing files as <path>.suggested; never overwrites")
    args = parser.parse_args()
    if args.diff and args.apply:
        parser.error("--diff and --apply are mutually exclusive")
    if args.write_new and not args.diff:
        parser.error("--write-new requires --diff")

    root = Path(args.repo).resolve()
    if not root.is_dir():
        parser.error(f"project directory must already exist: {root}")
    report = analyze(root)
    mode = report["modeRecommendation"] if args.mode == "auto" else args.mode
    profile = report["profileRecommendation"] if args.profile == "auto" else args.profile
    spec_model = args.spec_model or ("living" if mode == "greenfield" else "flow-forward")
    project_name = args.project_name or root.name
    commands_json = json.dumps(report["discoveredCommands"], indent=2, ensure_ascii=False).replace("\n", "\n  ")
    arch_status = "observed"
    intent_status = "proposed" if mode == "greenfield" else "observed"
    replacements = {
        "PROJECT_NAME": project_name,
        "PROJECT_NAME_JSON": json.dumps(project_name, ensure_ascii=False),
        "MODE": mode,
        "PROFILE": profile,
        "SPEC_MODEL": spec_model,
        "DATE": date.today().isoformat(),
        "ARCH_STATUS": arch_status,
        "INTENT_STATUS": intent_status,
        "COMMANDS_JSON": commands_json,
        "PLANS_PROPOSAL_HINT": (
            "`docs/plans/active/` or a change proposal" if profile == "full" else
            "a change proposal (create and declare a plans branch first)"
        ),
        "OPTIONAL_KNOWLEDGE": (
            ',\n    "plans": "docs/plans",\n    "agents": "docs/agents/REGISTRY.md"'
            if profile == "full" else ""
        ),
        "PROFILE_REQUIRED_CHECKS": (
            ',\n      "plan-state",\n      "agents"' if profile == "full" else ""
        ),
        "PROFILE_PROJECT_MAP": (
            "- Resumable plans: `docs/plans/active/` (start from `docs/plans/TEMPLATE.md`)\n"
            "- Agent roster: `docs/agents/REGISTRY.md` (one-time registration)"
            if profile == "full" else
            "- Plans and agent registration are intentionally omitted in the lite profile; add and declare them when work needs cross-session recovery or a shared roster."
        ),
        "PROFILE_ROUTING_ROWS": (
            "| Agents that worked here | [Agent registry](agents/REGISTRY.md) (one-time registration) |\n"
            "| Resumable multi-step work | [Plan template](plans/TEMPLATE.md) and [active plans](plans/active/) |"
            if profile == "full" else
            "| Plans and agent registration | Intentionally omitted by the lite profile; add and declare them when needed. |"
        ),
        "PROFILE_WORKFLOW": (
            "- For work that crosses sessions or components, create or update a plan from `docs/plans/TEMPLATE.md` in `docs/plans/active/`.\n"
            "- The first time you work here, register once in `docs/agents/REGISTRY.md` — no maintenance afterwards; when a session ends, compact its state into the plan's Next action."
            if profile == "full" else
            "- If work grows beyond one agent or session, re-run the scaffold with `--profile full` to add the plans and registry branches before relying on them."
        ),
        "PROFILE_SOURCES_LINE": (
            "`.ai/harness.json` and linked repository artifacts"
            if profile == "full" else "linked repository artifacts"
        ),
        "PROFILE_START_HERE": (
            "- Read `.ai/harness.json` for canonical paths and commands.\n"
            "- Read `docs/INDEX.md` to locate the canonical knowledge that this profile actually provides."
            if profile == "full" else
            "- Read `docs/INDEX.md` to locate project knowledge. This profile is documentation-only: "
            "no manifest, no machine layer — re-run the scaffold with `--profile full` when the project needs validation."
        ),
        "PROFILE_SKILLS_LINE": (
            "- Canonical repo-local skills: `.agents/skills/`; generate Claude mirrors with `tools/ai/sync_skill_adapters.py`"
            if profile == "full" else
            "- No machine layer in this profile; re-run the scaffold with `--profile full` to add `.ai/` and `tools/ai/` when the project needs validation."
        ),
        "PROFILE_SYNC_LINE": (
            "- After changing `.agents/skills/`, run `python tools/ai/sync_skill_adapters.py . --apply`, then validate."
            if profile == "full" else ""
        ),
        "PROFILE_INVARIANTS": (
            "- Harness validation: `python tools/ai/validate_harness.py .`\n"
            "- TODO: register project-native architecture checks in `.ai/harness.json`."
            if profile == "full" else
            "- No machine layer in this profile; re-run the scaffold with `--profile full` to add `.ai/` and `tools/ai/` when the project needs validation."
        ),
        "PROFILE_DONE": (
            "- The active plan records final verification and leaves `docs/plans/active/` when complete."
            if profile == "full" else
            "- Any handoff state needed for unfinished work is preserved in a declared canonical artifact."
        ),
    }

    if args.diff:
        same = differ = missing = 0
        for source, relative in template_files(profile):
            target = root / relative
            if not target.exists():
                missing += 1
                print(f"  missing  {relative.as_posix()}  (created by --apply)")
                continue
            if source.suffix.lower() in {".md", ".json", ".py", ""}:
                rendered = render(source.read_text(encoding="utf-8"), replacements).encode("utf-8")
            else:
                rendered = source.read_bytes()
            if target.read_bytes() == rendered:
                same += 1
                continue
            differ += 1
            print(f"  DIFFER   {relative.as_posix()}")
            if args.write_new:
                suggested = target.with_name(target.name + ".suggested")
                if suggested.exists():
                    print(f"  skip     {suggested.name} already exists")
                else:
                    suggested.write_bytes(rendered)
                    print(f"  wrote    {suggested.name}")
        print(f"\nDiff summary: {same} same, {differ} differ, {missing} missing (missing files are created by --apply).")
        return 0

    def is_link_like(path: Path) -> bool:
        try:
            return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())
        except OSError:
            return True

    resolved_root = root.resolve()
    operations: list[tuple[str, Path, Path | None]] = []
    blockers: list[tuple[Path, str]] = []
    for source, relative in template_files(profile):
        target = root / relative
        if target.is_symlink():
            blockers.append((target, "target is a symlink"))
            action = "block"
        elif target.exists() and target.is_dir():
            blockers.append((target, "a directory exists where a file is required"))
            action = "block"
        else:
            action = "skip" if target.exists() else "create"
        if action == "create":
            parent = target.parent
            while parent != root:
                if is_link_like(parent):
                    blockers.append((parent, "ancestor is a symlink or junction"))
                    action = "block"
                    break
                if parent.exists() and not parent.is_dir():
                    blockers.append((parent, "a file blocks a required directory"))
                    action = "block"
                    break
                parent = parent.parent
            # Final containment net: resolution follows junctions, so a target
            # whose parents were rewritten outside the root can never slip past.
            try:
                target_resolved = target.resolve()
                resolves_inside = (
                    target_resolved == resolved_root or resolved_root in target_resolved.parents
                )
            except OSError:
                resolves_inside = False
            if action == "create" and not resolves_inside:
                blockers.append((relative.as_posix(), "path resolves outside the repository root"))
                action = "block"
        operations.append((action, target, source))

    print(f"Project: {root}")
    print(f"Mode: {mode}")
    if args.profile == "auto":
        print(f"Profile: {profile} (audit recommendation; score {report['profileScore']}/{report['profileThreshold']})")
        for signal in report["profileSignals"]:
            print(f"  {signal}")
    else:
        print(
            f"Profile: {profile} (explicit override; audit recommended "
            f"{report['profileRecommendation']} at {report['profileScore']}/{report['profileThreshold']})"
        )
    print(f"Specification model: {spec_model}")
    print("Operations:")
    for action, target, _ in operations:
        print(f"  {action:6} {target.relative_to(root).as_posix()}")

    conflicts = [target for action, target, _ in operations if action == "skip"]
    if conflicts:
        print("\nExisting files will be preserved. Review and merge them manually after scaffolding.")
    if blockers:
        print("\nBlocking path conflicts:")
        seen: set[tuple[Path | str, str]] = set()
        for blocker_entry, reason in blockers:
            if (blocker_entry, reason) not in seen:
                seen.add((blocker_entry, reason))
                label = (
                    blocker_entry.relative_to(root).as_posix()
                    if isinstance(blocker_entry, Path) else blocker_entry
                )
                print(f"  error  {label}: {reason}")
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
            template = source.read_text(encoding="utf-8")
            unknown = sorted(set(TEMPLATE_TOKEN.findall(template)) - replacements.keys())
            if unknown:
                print(f"Unknown template variables in {source.relative_to(SKILL_ROOT)}: {', '.join(unknown)}")
                print("No files were written.")
                return 1
            prepared[target] = ("text", render(template, replacements))
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
    if profile == "full":
        active = root / "docs" / "plans" / "active"
        active.mkdir(parents=True, exist_ok=True)
        (active / ".gitkeep").write_bytes(b"")  # keep the empty dir in git
    print(f"\nCreated {created} files. Preserved {len(conflicts)} existing files.")
    print("Validate with: python tools/ai/validate_harness.py .")
    if mode == "brownfield":
        print("Brownfield note: replace TODOs only with code-backed observations; keep proposed changes in active plans.")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
