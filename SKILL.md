---
name: build-ai-first-project
description: Audit, initialize, or retrofit software repositories so Codex, Claude Code, Kimi Code, and other coding agents can understand, modify, verify, and hand off the project reliably. Use for new-project scaffolding, brownfield AI-readiness migration, AGENTS.md or CLAUDE.md redesign, agent-facing documentation architecture, specification and execution-plan workflows, multi-agent coordination (agent registry, task boards, handoff), executable guardrails, repository continuity, or validation of an existing AI-first project harness.
---

# Build AI-First Project

Build a repository harness for agents, not a large instruction file. Keep durable knowledge local and versioned, load it progressively, and promote important prose constraints into executable checks.

Resolve every `scripts/`, `references/`, and `assets/` path below relative to the directory containing this `SKILL.md`; do not assume the agent's current working directory is the skill directory.
Use Python 3.11 or newer for the bundled audit, scaffold, sync, and validation scripts.

## Choose the operation

1. **Audit only**: Run `scripts/audit_project.py <repo>`. Do not modify the repository.
2. **Initialize a new project**: Follow the greenfield workflow in `references/workflows.md`, preview with `scripts/scaffold_project.py <repo> --mode greenfield`, then rerun with `--apply` after review. Branches beyond the fixed landing set are created on first need and declared in `.ai/harness.json`.
3. **Retrofit an existing project**: Follow the brownfield workflow in `references/workflows.md`. Audit first, establish a passing baseline, preview `--mode brownfield`, and add constraints incrementally.
4. **Validate or repair a harness**: Run `scripts/validate_project.py <repo>`. Read `references/validation.md` before changing severity, budgets, or freshness rules.

Read `references/target-architecture.md` before creating or reorganizing project artifacts. Read `references/adapters.md` when Codex, Claude Code, Kimi Code, monorepos, or repo-local skills are in scope.

## Non-negotiable principles

- Treat `AGENTS.md` as a short routing and hard-constraint surface, not a repository encyclopedia.
- Separate intended behavior from observed implementation. Specifications describe intent; code, tests, schemas, and generated documentation describe current implementation.
- Never invent brownfield architecture. Record claims as `observed` with source paths until verified.
- Preserve existing user files. Preview first, create missing files, and merge deliberately; never overwrite instruction, configuration, or documentation files silently.
- Keep task procedures in on-demand skills or workflow documents, not always-loaded guidance.
- Do not repeat formatter, linter, or type-checker rules in agent guidance unless the agent must know a non-obvious invocation or exception.
- Make commands deterministic, non-interactive, and runnable with argument arrays rather than shell strings when possible.
- Encode strict invariants in tests, linters, hooks, schemas, or CI. Use prose for navigation and judgment.
- Make long work resumable through versioned execution plans; do not commit raw chat summaries, private session state, or throwaway handoff notes.
- Validate changes with the repository's own checks and review the final diff.

## Core workflow

### 1. Discover

- Resolve the actual Git or project root.
- Inspect manifests, CI, test layout, documentation, instruction files, skills, specs, and build entry points.
- Run the audit script and verify its findings against code.
- Ask only for product intent, risk tolerance, or ownership facts that cannot be discovered safely.

### 2. Classify knowledge

Place each fact in exactly one primary surface:

- Always-needed map or hard rule -> root or nearest scoped `AGENTS.md`.
- Product contract -> `docs/product/`.
- Current architecture map -> `ARCHITECTURE.md` and `docs/architecture/`.
- Durable rationale -> architecture decision record.
- Multi-step change state -> `docs/plans/active/`.
- Agent identity and presence -> `docs/agents/REGISTRY.md`; lightweight per-agent todos -> `docs/tasks/` (ownership is advisory; see `references/workflows.md`).
- Repeatable procedure -> repo-local skill or `docs/workflows/`.
- Mechanically decidable rule -> executable check.
- Derived fact -> generated documentation; do not hand-edit it.

### 3. Design before applying

- Choose and record the specification persistence model: `living`, `flow-forward`, or `flow-back`.
- Define canonical artifacts, generated artifacts, commands, budgets, and freshness policy in `.ai/harness.json`.
- For monorepos, define repository-wide rules at the root and put component-specific guidance nearest its scope. Keep cross-tool auto-discovered skills at the repository-root `.agents/skills/`; namespace component workflows there because Kimi project discovery is rooted at the nearest `.git` directory.
- Keep repo-local skills canonical under `.agents/skills/`; generate and validate Claude mirrors with `tools/ai/sync_skill_adapters.py`.
- Present the proposed file operations and any conflicts before applying them.

### 4. Apply minimally

- Use `scripts/scaffold_project.py` with `--apply` only after preview.
- In brownfield projects, do not reorganize application code during harness installation.
- Register existing commands before adding new wrappers.
- Add one enforceable architecture invariant at a time, beginning with dependency direction or boundary validation that is already evidenced by the code.

### 5. Validate and forward-test

- Run `scripts/validate_project.py <repo>`.
- Treat registered commands as repository code. Run with `--run-commands` only after reviewing every executable, argument, working directory, and side effect.
- Test one representative onboarding question, one small change, and one interrupted/resumed task with a fresh agent context.
- Convert repeated failures into a better map, tool, check, or scoped skill. Do not respond by expanding the root instruction file reflexively.

## Completion criteria

Finish only when:

- the root entrypoint is within its declared context budget;
- Codex and Kimi can read the canonical guidance and Claude has a working import adapter;
- repository-root Codex/Kimi repo-local skills have current, validated Claude discovery mirrors;
- canonical knowledge files are linked and have verification metadata;
- setup and verification commands are recorded and at least the safe relevant subset has passed;
- active plans use the required resumability fields;
- the agent registry and task boards, when present, pass the `agents` validation check;
- no pre-existing project file was silently replaced;
- brownfield claims distinguish observed facts from intended changes;
- the audit and validation reports identify remaining gaps explicitly.
