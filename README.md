# build-ai-first-project

AI-first project architecture skill for Codex, Claude Code, Kimi Code, and other coding agents: audit, initialize, or retrofit software repositories so any coding agent can understand, modify, verify, and hand off the project reliably.

## What it does

The skill turns a repository into an **agent harness** instead of a large instruction file:

- a short `AGENTS.md` routing surface with hard constraints;
- progressive knowledge under `docs/` (product intent, current architecture, decisions, resumable plans);
- `.ai/harness.json` as the machine-readable control plane for canonical paths and deterministic commands;
- repo-local skills canonically at `.agents/skills/` with generated Claude mirrors under `.claude/skills/`;
- multi-agent collaboration surfaces: `docs/agents/REGISTRY.md` roster plus per-agent task boards under `docs/tasks/`;
- executable checks (`scripts/validate_project.py`) that keep the harness honest.

## Contents

```text
SKILL.md              # entrypoint: choose audit / init / retrofit / validate
references/
  workflows.md        # greenfield, brownfield, change, recovery workflows
  target-architecture.md  # layout and artifact contracts
  adapters.md         # Codex / Claude Code / Kimi Code portability rules
  validation.md       # validation contract (checks, severity, CI)
scripts/
  audit_project.py    # read-only AI-readiness census
  scaffold_project.py # preview-or-apply harness scaffolding
  validate_project.py # universal harness validator
  sync_skill_adapters.py  # managed .agents -> .claude skill mirrors
  self_test.py        # end-to-end regression suite
assets/project-template/  # template files the scaffold renders
```

## Install

Copy this directory into your agent's skills location:

| Agent | Location |
|---|---|
| Codex | `~/.codex/skills/build-ai-first-project` |
| Claude Code | `~/.claude/skills/build-ai-first-project` |
| Kimi Code | `~/.kimi-code/skills/build-ai-first-project` |

Requires Python 3.11+ for the bundled scripts. No third-party dependencies.

## Quick start

```bash
# Read-only audit of an existing repository
python scripts/audit_project.py path/to/repo

# Preview, then apply, harness scaffolding for a new project
python scripts/scaffold_project.py path/to/repo --mode greenfield
python scripts/scaffold_project.py path/to/repo --mode greenfield --apply

# Scaffold an existing (brownfield) repository incrementally
python scripts/audit_project.py path/to/repo
python scripts/scaffold_project.py path/to/repo --mode brownfield --apply

# Validate a harness (writes nothing)
python scripts/validate_project.py path/to/repo

# Regenerate .claude/skills mirrors after changing .agents/skills
python scripts/sync_skill_adapters.py path/to/repo --apply

# Run the regression suite
python scripts/self_test.py
```

Scaffolding is **preview by default**: it never overwrites existing files and refuses to write when a path conflict exists.

## Multi-agent collaboration

Projects scaffolded with this skill include two lightweight coordination surfaces:

- `docs/agents/REGISTRY.md` — who has joined the project, each agent's status (`active` / `idle` / `retired`), focus areas, and a link to their task board.
- `docs/tasks/<agent-id>.md` — per-agent todo boards with `In progress` and `Done this phase` sections. Ownership is **advisory only**: any registered agent may pick up another's task.

At the end of a phase, completed items are archived to `docs/tasks/archive/<date>-<agent-id>.md` (or deleted if the team prefers). The validator enforces structure and unique agent IDs while keeping coordination advisory rather than locking.

## Design principles

- Separate intended behavior (specifications) from observed implementation (code, tests, generated docs).
- Never invent brownfield architecture; record claims as `Status: observed` until verified.
- Promote mechanically decidable rules into executable checks; keep prose for navigation and judgment.
- Make long work resumable through versioned execution plans, not chat transcripts.
- Preserve existing user files; preview first, merge deliberately.

See [`references/workflows.md`](references/workflows.md) and [`references/target-architecture.md`](references/target-architecture.md) for the full methodology.

## License

[MIT](LICENSE)
