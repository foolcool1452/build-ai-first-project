#!/usr/bin/env python3
"""End-to-end regression tests for the AI-first project skill scripts."""

from __future__ import annotations

import json
import os
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

        green = base / "greenfield"
        green.mkdir()
        preview = run(SCAFFOLD, str(green), "--mode", "greenfield")
        assert "Preview only" in preview.stdout
        assert not (green / "AGENTS.md").exists()
        run(SCAFFOLD, str(green), "--mode", "greenfield", "--knowledge-profile", "full", "--apply")
        assert '\n    "setup": []' in (green / ".ai/harness.json").read_text(encoding="utf-8")
        for tracked in (
            "docs/plans/active/README.md", "docs/plans/completed/README.md",
            ".agents/skills/README.md", ".claude/skills/README.md",
            "tools/ai/sync_skill_adapters.py", "tools/ai/validate_harness.py",
        ):
            assert (green / tracked).is_file(), tracked
        run(VALIDATE, str(green))
        audit = run(AUDIT, str(green), "--format", "json")
        report = json.loads(audit.stdout)
        assert report["verification"]["harnessValidator"] is True
        assert "score" not in report
        assert report["sourceFileCount"] == 0 and report["modeRecommendation"] == "greenfield"

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

        core = base / "core-profile"
        core.mkdir()
        run(SCAFFOLD, str(core), "--mode", "greenfield", "--apply")
        core_manifest = json.loads((core / ".ai/harness.json").read_text(encoding="utf-8"))
        assert all(key not in core_manifest["knowledge"] for key in ("plans", "operations", "quality", "generated"))
        assert not (core / "docs/plans").exists()
        core_validation = run(VALIDATE, str(core))
        assert core_validation.stdout.count("PLACEHOLDER_CONTENT") == 1

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
        run(SCAFFOLD, str(brown), "--mode", "brownfield", "--knowledge-profile", "full", "--apply")
        assert (brown / "AGENTS.md").read_text(encoding="utf-8") == existing_guidance
        manifest_path = brown / ".ai/harness.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["project"]["specPersistence"] == "flow-forward"
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
        assert "SCHEMA_CONTRACT" in malformed_report.stdout and "Traceback" not in malformed_report.stderr
        malformed = json.loads((green / ".ai/harness.json").read_text(encoding="utf-8"))
        malformed["architecture"]["zones"] = [{"id": "app", "paths": ["docs/**"], "mayDependOn": None}]
        write_json(manifest_path, malformed)
        dependency_report = run(VALIDATE, str(brown), expected=1)
        assert "ARCH_DEP_LIST" in dependency_report.stdout and "Traceback" not in dependency_report.stderr
        baseline_manifest = json.loads((green / ".ai/harness.json").read_text(encoding="utf-8"))
        for block in ("project", "guidance", "knowledge", "commands", "validation", "architecture"):
            for malformed_value in (None, "oops", []):
                malformed_shape = json.loads(json.dumps(baseline_manifest))
                malformed_shape[block] = malformed_value
                write_json(manifest_path, malformed_shape)
                shape_report = run(VALIDATE, str(brown), expected=1)
                assert "Traceback" not in shape_report.stderr, (block, malformed_value)
        strict_manifest = json.loads((green / ".ai/harness.json").read_text(encoding="utf-8"))
        strict_manifest["commands"] = {}
        strict_manifest["validation"]["requiredChecks"] = ["structure"]
        write_json(manifest_path, strict_manifest)
        strict_report = run(VALIDATE, str(brown), "--strict", expected=1)
        assert "REQUIRED_COMMANDS" in strict_report.stdout
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        schema_path = brown / ".ai/harness.schema.json"
        schema_content = schema_path.read_bytes()
        schema_path.unlink()
        missing_schema = run(VALIDATE, str(brown), expected=1)
        assert "SCHEMA_MISSING" in missing_schema.stdout
        schema_path.write_bytes(schema_content)
        schema_path.write_text('{"type":"object"}\n', encoding="utf-8")
        weakened_manifest = {
            "$schema": "./harness.schema.json", "schemaVersion": 1,
            "validation": {"requiredChecks": ["structure"]},
        }
        write_json(manifest_path, weakened_manifest)
        weakened_report = run(VALIDATE, str(brown), expected=1)
        assert "SCHEMA_DRIFT" in weakened_report.stdout
        schema_path.write_bytes(schema_content)
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))
        missing_name = json.loads(manifest_path.read_text(encoding="utf-8"))
        missing_name["project"].pop("name")
        write_json(manifest_path, missing_name)
        name_report = run(VALIDATE, str(brown), expected=1)
        assert "SCHEMA_CONTRACT" in name_report.stdout
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        loose_schema = brown / ".ai/loose.schema.json"
        loose_schema.write_text('{"type":"object"}\n', encoding="utf-8")
        bypass = json.loads(manifest_path.read_text(encoding="utf-8"))
        bypass["$schema"] = "./loose.schema.json"
        bypass["commands"] = {"test": [{"argv": "not-an-array"}]}
        bypass["validation"]["requiredChecks"] = ["structure"]
        write_json(manifest_path, bypass)
        bypass_report = run(VALIDATE, str(brown), expected=1)
        assert "SCHEMA_PATH" in bypass_report.stdout and "$.commands.test[0].argv" in bypass_report.stdout
        loose_schema.unlink()
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

        minimal_command = json.loads(manifest_path.read_text(encoding="utf-8"))
        minimal_command["commands"] = {"test": [{"argv": ["python", "-c", "pass"]}]}
        write_json(manifest_path, minimal_command)
        run(VALIDATE, str(brown))
        write_json(manifest_path, json.loads((green / ".ai/harness.json").read_text(encoding="utf-8")))

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
        plan_body = (brown / "docs/plans/TEMPLATE.md").read_text(encoding="utf-8").replace("Status: active", "Status: complete")
        plan_body = plan_body.replace("Sources:", "Plan ID: PLAN-1\nSources:")
        active_plan.write_text(plan_body, encoding="utf-8")
        completed_plan.write_text(plan_body, encoding="utf-8")
        plan_report = run(VALIDATE, str(brown), expected=1)
        assert "PLAN_STATUS" in plan_report.stdout and "PLAN_ID_DUPLICATE" in plan_report.stdout
        active_plan.unlink()
        completed_plan.unlink()

        optional = json.loads(manifest_path.read_text(encoding="utf-8"))
        for key in ("plans", "operations", "quality", "generated"):
            optional["knowledge"].pop(key)
        write_json(manifest_path, optional)
        for branch in ("plans", "operations", "quality", "generated"):
            shutil.rmtree(brown / "docs" / branch)
        knowledge_index = brown / "docs/INDEX.md"
        index_lines = knowledge_index.read_text(encoding="utf-8").splitlines()
        knowledge_index.write_text(
            "\n".join(
                line for line in index_lines
                if not any(token in line for token in ("(plans/", "(operations/", "(quality/", "(generated/"))
            ) + "\n",
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

        details = brown / "docs/architecture/index.md"
        original_details = details.read_text(encoding="utf-8")
        details.write_text(original_details.replace("Status: observed", "Status: imaginary").replace(
            next(line for line in original_details.splitlines() if line.startswith("Last verified:")),
            "Last verified: 2026-99-99",
        ), encoding="utf-8")
        metadata_report = run(VALIDATE, str(brown), expected=1)
        assert "METADATA_STATUS" in metadata_report.stdout and "VERIFICATION_DATE" in metadata_report.stdout
        details.write_text(original_details, encoding="utf-8")

        spaced = brown / "docs/space file.md"
        spaced.write_text(
            "# Spaced\n\nStatus: observed\nLast verified: 2026-07-19\nSources: test\n",
            encoding="utf-8",
        )
        with knowledge_index.open("a", encoding="utf-8") as handle:
            handle.write("\n[spaced](<space file.md>)\n[spaced-ref][spaced-doc]\n[spaced-doc]: <space file.md>\n")
        run(VALIDATE, str(brown))

        secret_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        secret_manifest["commands"] = {
            "test": [{
                "argv": ["python", "-c", (
                    "import os,sys;"
                    "os.write(1,b'GITHUB_TOKEN=github-secret\\xff\\nMY_API_KEY=api-secret\\n');"
                    "sys.stderr.write('{\\\"token\\\": \\\"json-secret\\\"} AWS_SECRET_ACCESS_KEY=aws-secret')"
                )],
                "cwd": ".", "required": False, "timeoutSeconds": 30,
            }]
        }
        write_json(manifest_path, secret_manifest)
        safe_report = run(VALIDATE, str(brown), "--run-commands", "--format", "json")
        for secret in ("github-secret", "api-secret", "json-secret", "aws-secret"):
            assert secret not in safe_report.stdout
        assert "stdoutTail" not in safe_report.stdout
        detailed_report = run(
            VALIDATE, str(brown), "--run-commands", "--include-command-output", "--format", "json"
        )
        for secret in ("github-secret", "api-secret", "json-secret", "aws-secret"):
            assert secret not in detailed_report.stdout
        assert "[REDACTED]" in detailed_report.stdout
        assert "stdoutTail" in detailed_report.stdout

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
        guarded_skill.mkdir()
        (guarded_skill / "SKILL.md").write_text(
            "---\nname: example\ndescription: Guarded repository workflow.\n---\n", encoding="utf-8"
        )
        outside_claude = base / "outside-claude"
        outside_claude.mkdir()
        shutil.rmtree(guarded / ".claude")
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
        archive_note = tasks_dir / "archive" / "atlas-notes.md"
        archive_note.write_text("historical items\n", encoding="utf-8", newline="\n")
        archive_report = run(VALIDATE, str(brown))
        assert "ARCHIVE_NAME" in archive_report.stdout
        archive_note.unlink()

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
        assert not list(base.rglob("__pycache__"))

    print("self-test: PASS")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
