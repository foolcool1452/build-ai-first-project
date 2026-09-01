# build-ai-first-project

Version: **3.3.0** — current mainline release.

## Upgrading a project from v2.x

A v2.x harness upgrades in place; the v3 validator stays backward-compatible:

1. Replace `tools/ai/validate_harness.py` and `tools/ai/sync_skill_adapters.py` with the v3 copies (keep the pair together — the validator imports helpers from the sync script).
2. Delete `.ai/harness.schema.json`; remove the `$schema` and `validation.freshnessDays` keys from `.ai/harness.json` (leaving them does not break validation, but they are no longer part of the contract).
3. Choose a profile. Without `project.harnessProfile` the manifest validates as before; set `"harnessProfile": "full"` (plus the `plan-state`/`agents` checks and the two knowledge paths, if not already declared) or `"lite"` and remove the undeclared branches. The v3 scaffold re-run over the project also reconciles missing files — it never overwrites existing ones.
4. Note the relaxed registry: registration is one-time (agent id, model, joined date) — statuses and last-active maintenance are gone, so old registries with `Status:` or `Last active:` lines simply keep those lines as history (or trim them).
5. Run `python tools/ai/validate_harness.py .` and resolve any findings.

### Upgrading between v3.x versions

Minor releases keep the manifest contract, so the upgrade is always the same three moves:

1. Replace the `tools/ai/` pair (`validate_harness.py` + `sync_skill_adapters.py`) with the new copies — together, never one alone.
2. Re-read the release notes for removed or renamed surfaces (e.g. v3.3 removed task boards and registry statuses — old files become inert history you can delete at leisure).
3. Run `python tools/ai/validate_harness.py .` and reconcile findings; surface removals surface as nothing — files left behind are simply no longer validated.

AI-first project architecture skill for Codex, Claude Code, Kimi Code, and other coding agents: audit, initialize, or retrofit software repositories so any coding agent can understand, modify, verify, and hand off the project reliably.

## What it does

The skill turns a repository into an **agent harness** instead of a large instruction file:

- a short `AGENTS.md` routing surface with hard constraints;
- progressive knowledge under `docs/` (product intent, current architecture, decisions, resumable plans);
- `.ai/harness.json` as the machine-readable control plane for canonical paths and deterministic commands;
- explainable `auto`, `lite`, and `full` scaffold profiles, with explicit AI/user override;
- repo-local skills canonically at `.agents/skills/` with generated Claude mirrors under `.claude/skills/`;
- a one-time agent registry: `docs/agents/REGISTRY.md`;
- executable checks (`scripts/validate_project.py`) that keep the harness honest.

## Contents

```text
SKILL.md              # entrypoint: choose audit / init / retrofit / validate
VERSION               # candidate version marker
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
| Kimi Code | `~/.kimi-code/skills/build-ai-first-project` **or** `~/.agents/skills/build-ai-first-project` (the shared cross-tool dir Kimi also scans) |
| Any tool scanning `~/.agents/skills/` | same as above |

On Windows, a **junction** to a single canonical copy keeps every tool in sync (this is how this machine is set up — one physical copy under `~/.codex/skills/`, junctioned from the others):

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.agents\skills\build-ai-first-project" -Target "$env:USERPROFILE\.codex\skills\build-ai-first-project"
```

Requires Python 3.11+ for the bundled scripts. No third-party dependencies. The skill is picked up when a session starts — restart open sessions to load it.

> **Windows note:** a bare `python` may resolve to the Microsoft Store alias, which can hang headless sessions. Prefer `py -3` or the full interpreter path.

## Quick start

```bash
# Read-only audit of an existing repository
python scripts/audit_project.py path/to/repo

# Machine-readable output, saved to a new file
python scripts/audit_project.py path/to/repo --format json --output report.json

# Expand a component path to its whole Git repository for the census
python scripts/audit_project.py packages/api --scope repository --format json

# Preview, then apply, harness scaffolding for a new project
python scripts/scaffold_project.py path/to/repo --mode greenfield --profile auto
python scripts/scaffold_project.py path/to/repo --mode greenfield --profile auto --apply

# Scaffold an existing (brownfield) repository incrementally
python scripts/audit_project.py path/to/repo
python scripts/scaffold_project.py path/to/repo --mode brownfield --profile auto --apply

# Validate a harness (writes nothing)
python scripts/validate_project.py path/to/repo

# Regenerate .claude/skills mirrors after changing .agents/skills
python scripts/sync_skill_adapters.py path/to/repo --apply

# Run the regression suite
python scripts/self_test.py
```

Scaffolding is **preview by default**: it never overwrites existing files and refuses to write when a path conflict exists.

## Profiles

- `lite` creates the verified core: routing, product intent, observed architecture, manifest, adapters, report ignores, and validation tools.
- `full` adds resumable plans and the one-time agent registry. It is the v2-style landing set with corrected routes.
- `auto` scores current repository evidence and prints every signal. An AI or user should explicitly override it when product intent, risk, future scope, or team shape is more informative than the file census.

Both profiles keep the same untrusted-input, path-containment, command, adapter, and knowledge-integrity protections.

## Full-profile collaboration

Projects scaffolded with the full profile include a deliberately minimal coordination surface:

- `docs/agents/REGISTRY.md` — a one-time roster: who has worked in the project (agent id, model, joined date, optional focus/notes). Registration happens once when a session first works here; there are no statuses to maintain.
- Ongoing state is not tracked in the registry — when a session ends, its state is compacted into the active plan (the Next action and round entries), and the next session rebuilds from those artifacts. The validator enforces structure and unique agent IDs while keeping coordination advisory rather than locking.

## Design principles

- Separate intended behavior (specifications) from observed implementation (code, tests, generated docs).
- Never invent brownfield architecture; record claims as `Status: observed` until verified.
- Promote mechanically decidable rules into executable checks; keep prose for navigation and judgment.
- Make long work resumable through versioned execution plans, not chat transcripts.
- Preserve existing user files; preview first, merge deliberately.

See [`references/workflows.md`](references/workflows.md) and [`references/target-architecture.md`](references/target-architecture.md) for the full methodology.

## License

[MIT](LICENSE)
