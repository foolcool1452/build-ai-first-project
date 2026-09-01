#!/usr/bin/env python3
"""End-to-end regression tests for the AI-first project skill scripts."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path


sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
SCAFFOLD = SCRIPTS / "scaffold_project.py"
AUDIT = SCRIPTS / "audit_project.py"
VALIDATE = SCRIPTS / "validate_project.py"


def invoke(argv: list[str], expected: int = 0) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTHONUTF8", None)
    env.pop("PYTHONIOENCODING", None)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    # Manifest commands address interpreters by bare name ("python"), which on
    # Windows may resolve to the Microsoft Store alias; that stub can block
    # indefinitely in headless sessions. Prefer the directory of the running
    # interpreter so the real one wins PATH resolution.
    interpreter_dir = Path(sys.executable).resolve().parent
    env["PATH"] = str(interpreter_dir) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        argv, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60, env=env,
    )
    if result.returncode != expected:
        raise AssertionError(
            f"Expected exit {expected}, got {result.returncode}: {' '.join(argv)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def run(script: Path, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    return invoke([sys.executable, str(script), *args], expected=expected)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def assert_no_template_tokens(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".py"}:
            assert not re.search(r"\{\{[A-Z][A-Z0-9_]*\}\}", path.read_text(encoding="utf-8")), path


def create_directory_link(link: Path, target: Path) -> bool:
    try:
        link.symlink_to(target, target_is_directory=True)
        return True
    except OSError:
        if os.name != "nt":
            return False
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    return result.returncode == 0


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ai-harness-self-test-") as temp:
        base = Path(temp)

        unicode_repo = base / "项目-Δ"
        unicode_repo.mkdir()
        unicode_audit = json.loads(run(AUDIT, str(unicode_repo), "--format", "json").stdout)
        assert Path(unicode_audit["root"]) == unicode_repo.resolve()

        lite = base / "lite-greenfield"
        lite.mkdir()
        lite_preview = run(SCAFFOLD, str(lite), "--mode", "greenfield")
        assert "Profile: lite (audit recommendation; score 0/3)" in lite_preview.stdout
        assert "+0 no full-profile complexity signals detected" in lite_preview.stdout
        run(SCAFFOLD, str(lite), "--mode", "greenfield", "--apply")
        lite_manifest = json.loads((lite / ".ai/harness.json").read_text(encoding="utf-8"))
        assert lite_manifest["project"]["harnessProfile"] == "lite"
        assert not {"plans", "agents", "tasks"} & set(lite_manifest["knowledge"])
        assert "plan-state" not in lite_manifest["validation"]["requiredChecks"]
        assert "agents" not in lite_manifest["validation"]["requiredChecks"]
        for omitted in (
            "docs/agents/REGISTRY.md", "docs/tasks/README.md",
            "docs/plans/TEMPLATE.md", "docs/plans/active/README.md",
        ):
            assert not (lite / omitted).exists(), omitted
        assert (lite / ".ai/.gitignore").read_text(encoding="utf-8") == "reports/\ntmp/\n"
        lite_guidance = (lite / "AGENTS.md").read_text(encoding="utf-8")
        for ghost_route in (
            "docs/architecture/index.md", "docs/architecture/decisions/",
            ".agents/skills/README.md", "docs/agents/REGISTRY.md",
            "docs/tasks/", "docs/plans/TEMPLATE.md",
        ):
            assert ghost_route not in lite_guidance
        for ghost_doc in ("ARCHITECTURE.md", "docs/INDEX.md"):
            ghost_text = (lite / ghost_doc).read_text(encoding="utf-8")
            assert "docs/plans/active/" not in ghost_text, ghost_doc
        assert_no_template_tokens(lite)
        run(VALIDATE, str(lite))
        lite_snapshot = {path.relative_to(lite): path.read_bytes() for path in lite.rglob("*") if path.is_file()}
        run(SCAFFOLD, str(lite), "--mode", "greenfield", "--profile", "lite", "--apply")
        assert lite_snapshot == {path.relative_to(lite): path.read_bytes() for path in lite.rglob("*") if path.is_file()}

        # Official promotion path: lite landing, then full --apply adds the
        # coordination files. The manifest stays lite until reconciled, and
        # validation must surface the pending promotion instead of staying silent.
        run(SCAFFOLD, str(lite), "--mode", "greenfield", "--profile", "full", "--apply")
        promotion_report = run(VALIDATE, str(lite))
        assert promotion_report.returncode == 0
        assert "PROFILE_PROMOTION_PENDING" in promotion_report.stdout

        green = base / "full-greenfield"
        green.mkdir()
        preview = run(SCAFFOLD, str(green), "--mode", "greenfield", "--profile", "full")
        assert "Preview only" in preview.stdout
        assert "Profile: full (explicit override; audit recommended lite at 0/3)" in preview.stdout
        assert not (green / "AGENTS.md").exists()
        run(SCAFFOLD, str(green), "--mode", "greenfield", "--profile", "full", "--apply")
        assert '\n    "setup": []' in (green / ".ai/harness.json").read_text(encoding="utf-8")
        full_manifest = json.loads((green / ".ai/harness.json").read_text(encoding="utf-8"))
        assert full_manifest["project"]["harnessProfile"] == "full"
        assert {"plans", "agents", "tasks"} <= set(full_manifest["knowledge"])
        assert {"plan-state", "agents"} <= set(full_manifest["validation"]["requiredChecks"])
        for tracked in (
            "AGENTS.md", "CLAUDE.md", "ARCHITECTURE.md",
            "docs/INDEX.md", "docs/product/index.md",
            "docs/agents/REGISTRY.md", "docs/tasks/README.md",
            "docs/plans/TEMPLATE.md", "docs/plans/active/README.md",
            ".ai/harness.json",
            ".ai/.gitignore",
            "tools/ai/sync_skill_adapters.py", "tools/ai/validate_harness.py",
        ):
            assert (green / tracked).is_file(), tracked
        plan_template_text = (green / "docs/plans/TEMPLATE.md").read_text(encoding="utf-8")
        assert "## Rounds" in plan_template_text and "### Round 1" in plan_template_text
        assert "- Verify:" in plan_template_text and "- Review:" in plan_template_text
        assert "- Close:" in plan_template_text and "partition" in plan_template_text
        for removed in (".ai/harness.schema.json", "docs/quality/QUALITY.md", "docs/operations/index.md"):
            assert not (green / removed).exists(), removed
        full_guidance = (green / "AGENTS.md").read_text(encoding="utf-8")
        for ghost_route in (
            "docs/architecture/index.md", "docs/architecture/decisions/", ".agents/skills/README.md",
        ):
            assert ghost_route not in full_guidance
        assert_no_template_tokens(green)
        run(VALIDATE, str(green))
        audit = run(AUDIT, str(green), "--format", "json")
        report = json.loads(audit.stdout)
        assert report["verification"]["harnessValidator"] is True
        assert "score" not in report
        assert report["sourceFileCount"] == 0 and report["modeRecommendation"] == "greenfield"
        assert report["profileRecommendation"] == "full" and report["profileScore"] >= 3

        complex_repo = base / "auto-full"
        (complex_repo / "src").mkdir(parents=True)
        for index in range(50):
            (complex_repo / f"src/module_{index}.py").write_text("VALUE = 1\n", encoding="utf-8")
        complex_preview = run(SCAFFOLD, str(complex_repo))
        assert "Profile: full (audit recommendation; score 3/3)" in complex_preview.stdout
        complex_audit = json.loads(run(AUDIT, str(complex_repo), "--format", "json").stdout)
        assert complex_audit["profileRecommendation"] == "full" and complex_audit["profileScore"] >= 3

        output = green / "existing-report.md"
        output.write_text("sentinel\n", encoding="utf-8")
        run(AUDIT, str(green), "--output", str(output), expected=2)
        assert output.read_text(encoding="utf-8") == "sentinel\n"
        run(VALIDATE, str(green), "--output", str(output), expected=2)
        assert output.read_text(encoding="utf-8") == "sentinel\n"
        run(AUDIT, str(green), "--output", str(output), "--force-output")
        assert output.read_text(encoding="utf-8").startswith("# AI-first Repository Audit")

        blocked = base / "blocked-scaffold"
        blocked.mkdir()
        (blocked / "docs").write_text("directory collision\n", encoding="utf-8")
        collision = run(SCAFFOLD, str(blocked), "--apply", expected=1)
        assert "Blocking path conflicts" in collision.stdout
        assert not (blocked / ".ai").exists()

        unknown_skill = base / "unknown-template-skill"
        shutil.copytree(SCRIPTS.parent, unknown_skill,
                        ignore=shutil.ignore_patterns("__pycache__"))
        with (unknown_skill / "assets/project-template/AGENTS.md").open("a", encoding="utf-8") as handle:
            handle.write("\n{{UNKNOWN_TEMPLATE_VARIABLE}}\n")
        unknown_target = base / "unknown-template-target"
        unknown_target.mkdir()
        unknown_result = run(unknown_skill / "scripts/scaffold_project.py", str(unknown_target), "--apply", expected=1)
        assert "UNKNOWN_TEMPLATE_VARIABLE" in unknown_result.stdout and "No files were written" in unknown_result.stdout
        assert not any(unknown_target.iterdir())

        quoted_name = base / "quoted-name"
        quoted_name.mkdir()
        run(SCAFFOLD, str(quoted_name), "--project-name", 'bad"name', "--apply")
        quoted_manifest = json.loads((quoted_name / ".ai/harness.json").read_text(encoding="utf-8"))
        assert quoted_manifest["project"]["name"] == 'bad"name'
        run(VALIDATE, str(quoted_name))

        if shutil.which("git"):
            clone = base / "clone"
            invoke(["git", "-C", str(green), "init", "-q"])
            invoke(["git", "-C", str(green), "add", "-A"])
            invoke([
                "git", "-C", str(green), "-c", "user.name=Self Test",
                "-c", "user.email=self-test@example.invalid", "commit", "-qm", "scaffold",
            ])
            invoke(["git", "clone", "-q", str(green), str(clone)])
            run(VALIDATE, str(clone))

        brown = base / "brownfield"
        (brown / "src").mkdir(parents=True)
        (brown / "src/index.ts").write_text("export const answer = 42;\n", encoding="utf-8")
        existing_guidance = "# Existing project rules\n\n- Preserve this user-owned guidance.\n"
        (brown / "AGENTS.md").write_text(existing_guidance, encoding="utf-8")
        (brown / "package.json").write_text(
            json.dumps({"name": "brownfield", "scripts": {"test": "node --test", "lint": "eslint .", "build": "tsc"}}),
            encoding="utf-8",
        )
        run(SCAFFOLD, str(brown), "--mode", "brownfield", "--profile", "full", "--apply")
        assert (brown / "AGENTS.md").read_text(encoding="utf-8") == existing_guidance
        manifest_path = brown / ".ai/harness.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["project"]["specPersistence"] == "flow-forward"
        assert manifest["project"]["harnessProfile"] == "full"
        assert manifest["commands"]["test"][0]["argv"] == ["npm", "run", "test"]
        run(VALIDATE, str(brown))

        python_repo = base / "python-repo"
        python_repo.mkdir()
        (python_repo / "pyproject.toml").write_text(
            '[project]\nname = "demo"\nversion = "0.1.0"\n[tool.pytest.ini_options]\n',
            encoding="utf-8",
        )
        run(SCAFFOLD, str(python_repo), "--mode", "brownfield", "--apply")
        python_manifest = json.loads((python_repo / ".ai/harness.json").read_text(encoding="utf-8"))
        python_argv = python_manifest["commands"]["test"][0]["argv"]
        assert python_argv == ["python", "-m", "pytest"]
        assert not Path(python_argv[0]).is_absolute()
        python_manifest["commands"]["test"][0]["argv"][0] = sys.executable
        write_json(python_repo / ".ai/harness.json", python_manifest)
        absolute_command = run(VALIDATE, str(python_repo), expected=1)
        assert "COMMAND_ABSOLUTE_PATH" in absolute_command.stdout
        python_manifest["commands"]["test"][0]["argv"][0] = "/usr/bin/python3"
        write_json(python_repo / ".ai/harness.json", python_manifest)
        posix_absolute = run(VALIDATE, str(python_repo), expected=1)
        assert "COMMAND_ABSOLUTE_PATH" in posix_absolute.stdout

        malformed = json.loads(manifest_path.read_text(encoding="utf-8"))
        malformed["validation"] = "oops"
        write_json(manifest_path, malformed)
        malformed_report = run(VALIDATE, str(brown), expected=1)
        assert "MANIFEST_CONTRACT" in malformed_report.stdout and "Traceback" not in malformed_report.stderr
        baseline_manifest = json.loads((green / ".ai/harness.json").read_text(encoding="utf-8"))
        for block in ("project", "guidance", "knowledge", "commands", "validation", "architecture"):
            for malformed_value in (None, "oops", []):
                malformed_shape = json.loads(json.dumps(baseline_manifest))
                malformed_shape[block] = malformed_value
                write_json(manifest_path, malformed_shape)
                shape_report = run(VALIDATE, str(brown), expected=1)
                assert "Traceback" not in shape_report.stderr, (block, malformed_value)
        # Strict mode only promotes warnings now; there is no required-command rule.
        strict_manifest = json.loads((green / ".ai/harness.json").read_text(encoding="utf-8"))
        strict_manifest["project"].pop("harnessProfile")
        strict_manifest["commands"] = {}
        strict_manifest["validation"]["requiredChecks"] = ["structure"]
        write_json(manifest_path, strict_manifest)
        run(VALIDATE, str(brown), "--strict")
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        missing_name = json.loads(manifest_path.read_text(encoding="utf-8"))
        missing_name["project"].pop("name")
        write_json(manifest_path, missing_name)
        name_report = run(VALIDATE, str(brown), expected=1)
        assert "MANIFEST_CONTRACT" in name_report.stdout
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        legacy_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        legacy_manifest["project"].pop("harnessProfile")
        write_json(manifest_path, legacy_manifest)
        run(VALIDATE, str(brown))

        invalid_profile = json.loads(manifest_path.read_text(encoding="utf-8"))
        invalid_profile["project"]["harnessProfile"] = "huge"
        write_json(manifest_path, invalid_profile)
        profile_report = run(VALIDATE, str(brown), expected=1)
        assert "MANIFEST_CONTRACT" in profile_report.stdout and "harnessProfile" in profile_report.stdout
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        incomplete_full = json.loads(manifest_path.read_text(encoding="utf-8"))
        incomplete_full["knowledge"].pop("agents")
        write_json(manifest_path, incomplete_full)
        incomplete_report = run(VALIDATE, str(brown), expected=1)
        assert "MANIFEST_CONTRACT" in incomplete_report.stdout and "full harness profile" in incomplete_report.stdout

        drifted_lite = json.loads((green / ".ai/harness.json").read_text(encoding="utf-8"))
        drifted_lite["project"]["harnessProfile"] = "lite"
        write_json(manifest_path, drifted_lite)
        drift_report = run(VALIDATE, str(brown))
        assert "PROFILE_DRIFT" in drift_report.stdout
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        minimal_command = json.loads(manifest_path.read_text(encoding="utf-8"))
        minimal_command["commands"] = {"test": [{"argv": ["python", "-c", "pass"]}]}
        write_json(manifest_path, minimal_command)
        run(VALIDATE, str(brown))
        minimal_json_report = run(VALIDATE, str(brown), "--run-commands", "--format", "json")
        assert '"exitCode"' in minimal_json_report.stdout
        for leaked in ("stdoutTail", "stderrTail", "stdoutCharacters"):
            assert leaked not in minimal_json_report.stdout
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        grouped = json.loads((green / ".ai/harness.json").read_text(encoding="utf-8"))
        grouped["commands"] = {
            "format": [{"argv": ["node", "--version"]}],
            "deploy": [{"argv": ["echo", "deploying"]}],
        }
        write_json(manifest_path, grouped)
        groups_report = run(VALIDATE, str(brown))
        assert "COMMAND_GROUP_NEVER_RUNS" in groups_report.stdout
        assert "UNSAFE_COMMAND_GROUP" in groups_report.stdout
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        (brown / ".ai/harness.json").write_text("{}\n", encoding="utf-8", newline="\n")
        empty_manifest = run(VALIDATE, str(brown), expected=1)
        assert "MANIFEST_CONTRACT" in empty_manifest.stdout
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        (brown / ".ai/harness.json").write_text(
            '{"schemaVersion":1,"schemaVersion":2}\n', encoding="utf-8", newline="\n"
        )
        duplicate_keys = run(VALIDATE, str(brown), expected=1)
        assert "MANIFEST_INVALID" in duplicate_keys.stdout and "duplicate key" in duplicate_keys.stdout
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        deep_value = '{"commands":' + '{"nested":' * 400 + "1" + "}" * 400 + "}"
        (brown / ".ai/harness.json").write_text(deep_value + "\n", encoding="utf-8", newline="\n")
        deep_report = run(VALIDATE, str(brown), expected=1)
        assert "Traceback" not in deep_report.stderr
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        hidden_plan_dir = brown / "docs/plans/active/wip"
        hidden_plan_dir.mkdir(parents=True)
        (hidden_plan_dir / "nested.md").write_text(
            "Status: banana\nNo headings here.\n", encoding="utf-8", newline="\n"
        )
        hidden_plan_report = run(VALIDATE, str(brown), expected=1)
        assert "PLAN_FIELD" in hidden_plan_report.stdout and "PLAN_STATUS" in hidden_plan_report.stdout
        shutil.rmtree(hidden_plan_dir)

        product_doc = brown / "docs/product/index.md"
        original_product = product_doc.read_text(encoding="utf-8")
        product_doc.write_text(
            original_product
            + "\n~~~md\n[tilde-doc](missing-under-tilde.md)\n~~~\n",
            encoding="utf-8", newline="\n",
        )
        index_doc = brown / "docs/INDEX.md"
        original_index = index_doc.read_text(encoding="utf-8")
        index_doc.write_text(
            "\ufeff[pwned]: #ignored-anchor\n[use][pwned]\n" + original_index,
            encoding="utf-8", newline="\n",
        )
        fences_report = run(VALIDATE, str(brown))
        assert "missing-under-tilde" not in fences_report.stdout
        assert "UNDEFINED_LINK_REFERENCE" not in fences_report.stdout
        product_doc.write_text(original_product, encoding="utf-8", newline="\n")
        index_doc.write_text(original_index, encoding="utf-8", newline="\n")

        claude_doc = brown / "CLAUDE.md"
        original_claude = claude_doc.read_text(encoding="utf-8")
        claude_doc.write_text(
            "# Vendor notes\nTeam contact: ops@AGENTS.md.invalid - plain mention only.\n",
            encoding="utf-8", newline="\n",
        )
        decoy_report = run(VALIDATE, str(brown), expected=1)
        assert "CLAUDE_IMPORT" in decoy_report.stdout
        claude_doc.write_text(original_claude, encoding="utf-8", newline="\n")

        bad_cwd = json.loads(manifest_path.read_text(encoding="utf-8"))
        bad_cwd["commands"] = {
            "test": [{"argv": ["python", "-c", "pass"], "cwd": "AGENTS.md", "required": True}]
        }
        write_json(manifest_path, bad_cwd)
        cwd_report = run(VALIDATE, str(brown), "--run-commands", expected=1)
        assert "COMMAND_CWD_TYPE" in cwd_report.stdout and "Traceback" not in cwd_report.stderr

        bad_exec = json.loads((green / ".ai/harness.json").read_text(encoding="utf-8"))
        bad_exec["commands"] = {"test": [{"argv": ["."], "required": True}]}
        write_json(manifest_path, bad_exec)
        execution_report = run(VALIDATE, str(brown), "--run-commands", expected=1)
        assert "COMMAND_EXECUTION" in execution_report.stdout and "Traceback" not in execution_report.stderr, execution_report.stdout
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        sensitive_command = json.loads((green / ".ai/harness.json").read_text(encoding="utf-8"))
        sensitive_command["commands"] = {
            "test": [
                {"argv": ["example-tool", "--password", "do-not-print-this"], "required": True},
                {"argv": ["example-tool", "--api-key=also-do-not-print-this"], "required": True},
            ]
        }
        write_json(manifest_path, sensitive_command)
        sensitive_report = run(VALIDATE, str(brown), expected=1)
        assert "COMMAND_SECRET_ARGUMENT" in sensitive_report.stdout
        assert "do-not-print-this" not in sensitive_report.stdout
        assert "also-do-not-print-this" not in sensitive_report.stdout
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        active_plan = brown / "docs/plans/active/duplicate.md"
        completed_plan = brown / "docs/plans/completed/duplicate.md"
        completed_plan.parent.mkdir(parents=True, exist_ok=True)
        plan_body = (brown / "docs/plans/TEMPLATE.md").read_text(encoding="utf-8").replace("Status: active", "Status: complete")
        plan_body = plan_body.replace("Sources:", "Plan ID: PLAN-1\nSources:")
        active_plan.write_text(plan_body, encoding="utf-8")
        completed_plan.write_text(plan_body, encoding="utf-8")
        plan_report = run(VALIDATE, str(brown), expected=1)
        assert "PLAN_STATUS" in plan_report.stdout and "PLAN_ID_DUPLICATE" in plan_report.stdout
        active_plan.unlink()
        completed_plan.unlink()

        # Intentional omission: plans can be undeclared and removed wholesale.
        optional = json.loads(manifest_path.read_text(encoding="utf-8"))
        optional["project"]["harnessProfile"] = "lite"
        optional["knowledge"].pop("plans")
        write_json(manifest_path, optional)
        shutil.rmtree(brown / "docs/plans")
        knowledge_index = brown / "docs/INDEX.md"
        index_lines = knowledge_index.read_text(encoding="utf-8").splitlines()
        knowledge_index.write_text(
            "\n".join(line for line in index_lines if "(plans/" not in line) + "\n",
            encoding="utf-8",
        )
        run(VALIDATE, str(brown))

        architecture = brown / "ARCHITECTURE.md"
        original_architecture = architecture.read_text(encoding="utf-8")
        architecture.write_text(
            original_architecture.replace(
                next(line for line in original_architecture.splitlines() if line.startswith("Last verified:")),
                "Last verified: yesterday",
            ),
            encoding="utf-8",
        )
        bad_date = run(VALIDATE, str(brown), expected=1)
        assert "VERIFICATION_DATE" in bad_date.stdout
        architecture.write_text(original_architecture, encoding="utf-8")

        architecture.write_text(original_architecture.replace("Status: observed", "Status: imaginary").replace(
            next(line for line in original_architecture.splitlines() if line.startswith("Last verified:")),
            "Last verified: 2026-99-99",
        ), encoding="utf-8")
        metadata_report = run(VALIDATE, str(brown), expected=1)
        assert "METADATA_STATUS" in metadata_report.stdout and "VERIFICATION_DATE" in metadata_report.stdout
        architecture.write_text(original_architecture, encoding="utf-8")

        spaced = brown / "docs/space file.md"
        spaced.write_text(
            "# Spaced\n\nStatus: observed\nLast verified: 2026-07-19\nSources: test\n",
            encoding="utf-8",
        )
        with knowledge_index.open("a", encoding="utf-8") as handle:
            handle.write("\n[spaced](<space file.md>)\n[spaced-ref][spaced-doc]\n[spaced-doc]: <space file.md>\n")
        run(VALIDATE, str(brown))

        # Secrets never belong in argv: rejected before anything runs.
        pre_secret_manifest = manifest_path.read_text(encoding="utf-8")
        secret_manifest = json.loads(pre_secret_manifest)
        secret_manifest["commands"] = {
            "test": [{
                "argv": ["python", "-c", "pass", "--api-key=do-not-print"],
                "cwd": ".", "required": False, "timeoutSeconds": 30,
            }]
        }
        write_json(manifest_path, secret_manifest)
        rejected = run(VALIDATE, str(brown), expected=1)
        assert "COMMAND_SECRET_ARGUMENT" in rejected.stdout
        write_json(manifest_path, json.loads(pre_secret_manifest))

        portable = brown / ".agents/skills/example"
        portable.mkdir(parents=True)
        (portable / "SKILL.md").write_text(
            "---\nname: example\ndescription: Example repository workflow.\n---\n\nRun the example.\n",
            encoding="utf-8",
        )
        missing_adapter = run(VALIDATE, str(brown), expected=1)
        assert "CLAUDE_SKILL_ADAPTER" in missing_adapter.stdout
        sync = brown / "tools/ai/sync_skill_adapters.py"
        run(sync, str(brown), "--apply")
        run(VALIDATE, str(brown))
        with (portable / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write("\nVerify the result.\n")
        stale_adapter = run(VALIDATE, str(brown), expected=1)
        assert "CLAUDE_SKILL_ADAPTER" in stale_adapter.stdout
        run(sync, str(brown), "--apply")
        run(VALIDATE, str(brown))
        mirror_skill = brown / ".claude/skills/example/SKILL.md"
        with mirror_skill.open("a", encoding="utf-8") as handle:
            handle.write("\nManual divergence.\n")
        refused = run(sync, str(brown), "--apply", expected=1)
        assert "managed mirror was edited" in refused.stdout and "canonical source" in refused.stdout
        shutil.copy2(portable / "SKILL.md", mirror_skill)
        run(VALIDATE, str(brown))
        outside = brown / "outside-reference.txt"
        outside.write_text("outside\n", encoding="utf-8")
        symlink = portable / "outside-link.txt"
        try:
            symlink.symlink_to(outside)
        except OSError:
            pass
        else:
            symlink_report = run(sync, str(brown), "--apply", expected=1)
            assert "contains a symlink" in symlink_report.stdout
            symlink.unlink()

        guarded = base / "guarded-sync"
        guarded.mkdir()
        run(SCAFFOLD, str(guarded), "--mode", "greenfield", "--apply")
        guarded_skill = guarded / ".agents/skills/example"
        guarded_skill.mkdir(parents=True)
        (guarded_skill / "SKILL.md").write_text(
            "---\nname: example\ndescription: Guarded repository workflow.\n---\n", encoding="utf-8"
        )
        outside_claude = base / "outside-claude"
        outside_claude.mkdir()
        shutil.rmtree(guarded / ".claude", ignore_errors=True)
        link_created = create_directory_link(guarded / ".claude", outside_claude)
        if os.name == "nt":
            assert link_created, "Windows junction creation should be available for the destination guard test"
        if link_created:
            guarded_report = run(
                guarded / "tools/ai/sync_skill_adapters.py", str(guarded), "--apply", expected=1
            )
            assert "ancestor is a symlink or junction" in guarded_report.stdout
            assert not (outside_claude / "skills/example").exists()
        for path in (portable / "SKILL.md", mirror_skill):
            path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8", newline="\r\n")
        run(VALIDATE, str(brown))

        orphan_source = brown / ".agents/skills/orphan"
        orphan_source.mkdir()
        (orphan_source / "SKILL.md").write_text(
            "---\nname: orphan\ndescription: Temporary test skill.\n---\n", encoding="utf-8"
        )
        run(sync, str(brown), "--apply")
        shutil.rmtree(orphan_source)
        orphan_report = run(sync, str(brown), expected=1)
        assert "orphan" in orphan_report.stdout
        orphan_validation = run(VALIDATE, str(brown), expected=1)
        assert "CLAUDE_SKILL_ORPHAN" in orphan_validation.stdout
        run(sync, str(brown), "--prune")
        assert not (brown / ".claude/skills/orphan").exists()

        registry = brown / "docs/agents/REGISTRY.md"
        assert registry.is_file()
        tasks_dir = brown / "docs/tasks"
        today = date.today().isoformat()
        stale_day = (date.today() - timedelta(days=200)).isoformat()
        last_active_value = today

        def write_registry(text: str) -> None:
            registry.write_text(text + "\n", encoding="utf-8", newline="\n")

        def valid_agent_text(status_value: str, last_active_value_arg: str) -> str:
            return (
                "# Agent Registry\n\n"
                "## atlas\n\n"
                f"- Model: example-model\n- Joined: {today}\n- Status: {status_value}\n"
                f"- Last active: {last_active_value_arg}\n\n"
            )

        write_registry(valid_agent_text("active", today))
        (tasks_dir / "atlas.md").write_text(
            "# Tasks: atlas\n\nLast updated: " + today + "\n\n## In progress\n\n- [ ] demo item\n",
            encoding="utf-8", newline="\n",
        )
        run(VALIDATE, str(brown))

        write_registry(valid_agent_text("active", today) + valid_agent_text("active", today).replace("## atlas", "## Atlas"))
        duplicate_report = run(VALIDATE, str(brown), expected=1)
        assert "AGENT_ID_DUPLICATE" in duplicate_report.stdout
        write_registry(valid_agent_text("haunted", today))
        status_report = run(VALIDATE, str(brown), expected=1)
        assert "AGENT_STATUS" in status_report.stdout
        bad_joined = valid_agent_text("active", today).replace(f"- Joined: {today}", "- Joined: 2026/08/01")
        write_registry(bad_joined)
        date_report = run(VALIDATE, str(brown), expected=1)
        assert "AGENT_DATE" in date_report.stdout
        future_last = valid_agent_text("active", "tomorrow")
        write_registry(future_last)
        future_report = run(VALIDATE, str(brown), expected=1)
        assert "AGENT_DATE" in future_report.stdout
        write_registry(valid_agent_text("active", stale_day))
        stale_report = run(VALIDATE, str(brown))
        assert "AGENT_STALE" in stale_report.stdout
        write_registry(valid_agent_text("active", stale_day).replace("- Model: example-model\n", ""))
        missing_field = run(VALIDATE, str(brown), expected=1)
        assert "AGENT_FIELD" in missing_field.stdout
        write_registry(valid_agent_text("active", stale_day))
        (tasks_dir / "ghost.md").write_text("# Tasks: ghost\n", encoding="utf-8", newline="\n")
        ghost_report = run(VALIDATE, str(brown))
        assert "TASK_BOARD_UNREGISTERED" in ghost_report.stdout
        (tasks_dir / "ghost.md").unlink()
        archive_dir = tasks_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_note = archive_dir / "atlas-notes.md"
        archive_note.write_text("historical items\n", encoding="utf-8", newline="\n")
        archive_report = run(VALIDATE, str(brown))
        assert "ARCHIVE_NAME" in archive_report.stdout
        archive_note.unlink()

        # Single-writer invariant: one active passes, two fail.
        write_registry(valid_agent_text("active", today) + valid_agent_text("idle", stale_day).replace("## atlas", "## nova"))
        mixed_report = run(VALIDATE, str(brown))
        assert "AGENT_MULTIPLE_ACTIVE" not in mixed_report.stdout
        write_registry(valid_agent_text("active", today) + valid_agent_text("active", today).replace("## atlas", "## nova"))
        multi_report = run(VALIDATE, str(brown), expected=1)
        assert "AGENT_MULTIPLE_ACTIVE" in multi_report.stdout
        write_registry(valid_agent_text("active", today))

        # Tilde fences are skipped exactly like backtick fences; an unclosed
        # fence warns instead of silently swallowing later sections.
        write_registry(valid_agent_text("active", today)
                       + "\n~~~md\n## ghost\n\n- Model: m\n- Joined: " + today
                       + "\n- Status: active\n- Last active: " + today + "\n\n~~~\n")
        tilde_report = run(VALIDATE, str(brown))
        assert "AGENT_MULTIPLE_ACTIVE" not in tilde_report.stdout
        write_registry(valid_agent_text("active", today) + "\n```md\n## ghost\n- Status: active\n")
        unclosed_report = run(VALIDATE, str(brown))
        assert "AGENT_FENCE_UNCLOSED" in unclosed_report.stdout
        write_registry(valid_agent_text("active", today))

        baseline_manifest_obj = json.loads(manifest_path.read_text(encoding="utf-8"))
        omitting = json.loads(json.dumps(baseline_manifest_obj))
        for key in ("agents", "tasks"):
            omitting["knowledge"].pop(key)
        write_json(manifest_path, omitting)
        index_path = brown / "docs/INDEX.md"
        index_lines = index_path.read_text(encoding="utf-8").splitlines()
        index_path.write_text(
            "\n".join(
                line for line in index_lines
                if not any(token in line for token in ("(agents/", "(tasks/"))
            ) + "\n",
            encoding="utf-8", newline="\n",
        )
        shutil.rmtree(tasks_dir)
        shutil.rmtree(registry.parent)
        run(VALIDATE, str(brown))

        # Restore a valid coordination surface so later scenarios keep passing.
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))
        registry.parent.mkdir(parents=True, exist_ok=True)
        write_registry(valid_agent_text("idle", today))
        tasks_dir.mkdir(parents=True, exist_ok=True)




        monorepo = base / "monorepo"
        component = monorepo / "packages/api"
        (monorepo / "fixtures/example").mkdir(parents=True)
        component.joinpath("tests").mkdir(parents=True)
        (monorepo / "fixtures/example/ARCHITECTURE.md").write_text("# Example only\n", encoding="utf-8")
        (component / "tests/test_api.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
        (component / "package.json").write_text('{"name":"api"}\n', encoding="utf-8")
        if shutil.which("git"):
            invoke(["git", "-C", str(monorepo), "init", "-q"])
        component_audit = json.loads(run(AUDIT, str(component), "--format", "json").stdout)
        assert Path(component_audit["root"]) == component.resolve()
        assert component_audit["verification"]["tests"] is True
        assert component_audit["documentation"]["architecture"] is False
        if shutil.which("git"):
            repository_audit = json.loads(run(
                AUDIT, str(component), "--scope", "repository", "--format", "json"
            ).stdout)
            assert Path(repository_audit["root"]) == monorepo.resolve()
            assert repository_audit["documentation"]["architecture"] is False
            assert repository_audit["verification"]["tests"] is True

        if shutil.which("git"):
            component_skill = component / ".agents/skills/component-skill"
            component_skill.mkdir(parents=True)
            (component_skill / "SKILL.md").write_text(
                "---\nname: component-skill\ndescription: Component workflow.\n---\n", encoding="utf-8"
            )
            run(SCAFFOLD, str(monorepo), "--mode", "brownfield", "--apply")
            nested_sync = run(SCRIPTS / "sync_skill_adapters.py", str(monorepo), "--apply", expected=1)
            assert "not cross-tool portable" in nested_sync.stdout
            assert not (component / ".claude/skills/component-skill").exists()
            nested_validation = run(VALIDATE, str(monorepo), expected=1)
            assert "NESTED_SKILL_NOT_PORTABLE" in nested_validation.stdout
            component_sync = run(SCRIPTS / "sync_skill_adapters.py", str(component), expected=1)
            assert "not cross-tool portable" in component_sync.stdout

        heuristic = base / "heuristic-audit"
        (heuristic / "tests").mkdir(parents=True)
        (heuristic / "tests/README.md").write_text("not executable\n", encoding="utf-8")
        (heuristic / "architecture_test_notes.md").write_text("notes only\n", encoding="utf-8")
        (heuristic / "pyproject.toml").write_text("# pytest ruff mypy\n[project]\nname='notes'\nversion='0.1'\n", encoding="utf-8")
        heuristic_report = json.loads(run(AUDIT, str(heuristic), "--format", "json").stdout)
        assert heuristic_report["verification"]["tests"] is False
        assert heuristic_report["verification"]["architectureCheck"] is False
        assert not any(heuristic_report["discoveredCommands"][group] for group in ("test", "lint", "typecheck"))

        lua_repo = base / "lua-repo"
        lua_repo.mkdir()
        (lua_repo / "main.lua").write_text("return 42\n", encoding="utf-8")
        lua_report = json.loads(run(AUDIT, str(lua_repo), "--format", "json").stdout)
        assert lua_report["modeRecommendation"] == "brownfield" and lua_report["languages"]["Lua"] == 1

        pnpm_repo = base / "pnpm-repo"
        pnpm_repo.mkdir()
        (pnpm_repo / "package.json").write_text(
            '{"name":"pnpm-demo","packageManager":"pnpm@10.0.0","scripts":{"test":"node --test"}}\n',
            encoding="utf-8",
        )
        pnpm_commands = json.loads(run(AUDIT, str(pnpm_repo), "--format", "json").stdout)["discoveredCommands"]
        assert pnpm_commands["setup"][0]["argv"][:2] == ["pnpm", "install"]
        assert pnpm_commands["test"][0]["argv"] == ["pnpm", "test"]

        conflict_repo = base / "manager-conflict"
        conflict_repo.mkdir()
        (conflict_repo / "package.json").write_text(
            '{"name":"stale","packageManager":"pnpm@9.0.0","scripts":{"test":"node --test"}}\n',
            encoding="utf-8",
        )
        (conflict_repo / "yarn.lock").write_text("# orphaned lockfile from a yarn era\n", encoding="utf-8")
        conflict_commands = json.loads(run(AUDIT, str(conflict_repo), "--format", "json").stdout)["discoveredCommands"]
        assert conflict_commands["setup"][0]["argv"] == ["yarn", "install", "--frozen-lockfile"]
        assert conflict_commands["test"][0]["argv"] == ["yarn", "test"]

        invalid_package = base / "invalid-package"
        invalid_package.mkdir()
        (invalid_package / "package.json").write_text("{not-json", encoding="utf-8")
        invalid_commands = json.loads(run(AUDIT, str(invalid_package), "--format", "json").stdout)["discoveredCommands"]
        assert not any(invalid_commands.values())

        template_code = base / "template-code"
        (template_code / "src/templates").mkdir(parents=True)
        (template_code / "src/templates/render.lua").write_text("return 1\n", encoding="utf-8")
        template_report = json.loads(run(AUDIT, str(template_code), "--format", "json").stdout)
        assert template_report["sourceFileCount"] == 1 and template_report["modeRecommendation"] == "brownfield"

        fixture_only = base / "fixture-only"
        (fixture_only / "fixtures/example").mkdir(parents=True)
        (fixture_only / "fixtures/example/main.py").write_text("print('example')\n", encoding="utf-8")
        fixture_report = json.loads(run(AUDIT, str(fixture_only), "--format", "json").stdout)
        assert fixture_report["sourceFileCount"] == 0 and fixture_report["modeRecommendation"] == "greenfield"

        build_ancestor = base / "build/repo"
        build_ancestor.mkdir(parents=True)
        run(SCAFFOLD, str(build_ancestor), "--apply")
        with (build_ancestor / "docs/INDEX.md").open("a", encoding="utf-8") as handle:
            handle.write("\n[broken](missing-under-build.md)\n")
        build_link_report = run(VALIDATE, str(build_ancestor), expected=1)
        assert "BROKEN_LINK" in build_link_report.stdout

        no_git = base / "no-git"
        no_git.mkdir()
        no_repo_scope = run(AUDIT, str(no_git), "--scope", "repository", expected=2)
        assert "requires a containing Git repository" in no_repo_scope.stderr

        original_guidance = (brown / "AGENTS.md").read_text(encoding="utf-8")
        (brown / "AGENTS.md").write_text(original_guidance + "\n" + "extra\n" * 130, encoding="utf-8")
        failed = run(VALIDATE, str(brown), expected=1)
        assert "GUIDANCE_BLOAT" in failed.stdout

        # A typo'd maxLines must fail the contract, not silently disable the budget.
        current_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        current_manifest["guidance"]["maxLines"] = 5000
        write_json(manifest_path, current_manifest)
        typo_report = run(VALIDATE, str(brown), expected=1)
        assert "MANIFEST_CONTRACT" in typo_report.stdout and "maxLines" in typo_report.stdout
        assert not list(base.rglob("__pycache__"))

    print("self-test: PASS")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
