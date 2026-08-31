# Agent Guide

{{PROJECT_NAME}} is maintained through repository-local specifications, executable checks, and resumable plans. Keep this file as a short map and hard-constraint surface.

## Start here

- Read `.ai/harness.json` for canonical paths and commands.
- Read `docs/INDEX.md` to locate the canonical knowledge that this profile actually provides.
- Read the nearest scoped `AGENTS.md` before changing files under a subsystem.
- Treat current code and tests as implementation evidence; treat verified product specifications as intended behavior.

## Project map

- Product intent: `docs/product/index.md`
- Current architecture: `ARCHITECTURE.md`
{{PROFILE_PROJECT_MAP}}
- Canonical repo-local skills: `.agents/skills/`; generate Claude mirrors with `tools/ai/sync_skill_adapters.py`
- Decisions, operations, quality, and generated knowledge are intentionally omitted; create and declare a branch when first needed.

## Hard constraints

- Do not present proposed architecture as current architecture.
- For brownfield discoveries, cite source files or commands and use `Status: observed` until verified.
- Keep changes focused, preserve user work, and never overwrite or delete project files silently.
- Do not commit secrets, private session logs, raw agent traces, or throwaway handoff notes.
- Promote mechanically decidable rules into tests, lint, hooks, schemas, or CI instead of adding prose here.

## Working workflow

{{PROFILE_WORKFLOW}}
- Record discoveries in the closest artifact, then reconcile product intent, architecture, decisions, tests, and generated docs before completion.
- Run targeted checks first and the required manifest commands before declaring completion.
- After changing `.agents/skills/`, run `python tools/ai/sync_skill_adapters.py . --apply`, then validate.
- Review the final diff for scope, regressions, stale documentation, generated-file drift, and private data.

## Definition of done

- Requested behavior and acceptance criteria are satisfied.
- Relevant tests and registered required checks pass, or remaining failures are reported with evidence.
- Current-state architecture and product intent remain consistent with the change.
{{PROFILE_DONE}}
