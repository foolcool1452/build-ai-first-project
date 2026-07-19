# Validation Contract

## Contents

1. Validation levels
2. Universal checks
3. Command checks
4. Severity and adoption
5. Reports and CI

## Validation levels

- **Error**: harness cannot be trusted or a declared contract is broken.
- **Warning**: likely drift, context waste, or incomplete adoption requiring review.
- **Info**: discovery result or optional improvement.

The validator exits nonzero on errors. Use `--strict` to promote warnings for mature projects, not during initial brownfield adoption.

## Universal checks

### Structure

- `.ai/harness.json`, `AGENTS.md`, `ARCHITECTURE.md`, and the declared knowledge index exist.
- manifest paths are relative, remain inside the repository, and resolve when required.
- schema version and supported persistence model are valid.
- core knowledge paths (`index`, `architecture`, and `product`) exist; optional branches are checked only when declared.

### Guidance budget

- root `AGENTS.md` stays under `guidance.maxLines`.
- root guidance links to canonical sources instead of duplicating long procedures.
- warn about likely formatter-rule leakage when formatter configuration exists and guidance restates indentation, semicolon, quote, or line-length rules.

### Adapter consistency

- `CLAUDE.md` imports `@AGENTS.md`, or is a resolvable symlink to it.
- `CLAUDE.md` stays within its budget after the canonical import; a human review remains responsible for deciding whether the remaining text is truly vendor-specific.
- every `.agents/skills/<name>` source has an identical managed `.claude/skills/<name>` mirror or a symlink to the canonical source.
- nested guidance scope and semantic consistency require review; the universal validator does not infer whether instructions conflict.

### Knowledge integrity

- local Markdown links resolve.
- canonical current-state files include `Status`, `Last verified`, and `Sources` metadata.
- generated docs declare their generator or generation command.
- verification dates older than `validation.freshnessDays` warn rather than silently becoming truth.

### Plan state

- every active plan contains Goal, Scope and non-goals, Progress, Decisions, Verification, Risks and blockers, and Next action.
- completed plans are not left under `active/`.
- explicit `Plan ID:` values are unique where they are used; local links are covered by the Markdown check.

### Manifest commands

- commands are argument arrays, never shell strings;
- executable and path arguments are repository-relative or tool names, never machine-specific absolute paths;
- working directories stay within the repository (`.` by default);
- timeouts are positive and bounded (900 seconds by default);
- strict validation requires at least one command marked `required: true`, even if the configured check list omits command execution.

The validator always loads `.ai/harness.schema.json`; `$schema` must remain `./harness.schema.json`, and the schema content must match the canonical schemaVersion 1 fingerprint. It implements the required subset without third-party packages and is not a general-purpose JSON Schema engine.
Keep `tools/ai/validate_harness.py` and `tools/ai/sync_skill_adapters.py` together; the validator imports shared skill-tree and digest helpers from the sync script.

The readiness audit reports evidence and routing heuristics, not a substitute for repository-specific CI and human review. Verify detected commands before scaffolding or running them.

### Architecture

- declared zones have unique identifiers and valid paths;
- dependency targets reference known zones;
- if architecture is declared enforced, an architecture command must exist and pass.

## Command checks

`--run-commands` runs registered commands without a shell, using each command's `argv`, `cwd`, and timeout. Review the manifest before enabling this option. Do not automatically run deploy, release, migration, destructive, or production commands.

Recommended order:

1. architecture and documentation checks;
2. targeted tests;
3. lint and typecheck;
4. broader tests;
5. build.

Capture exit code, duration, and output sizes by default. Add `--include-command-output` only for local diagnosis; bounded tails are then redacted before reporting. Redaction is defense in depth, so do not commit diagnostic output or put secrets in command arguments.

## Severity and adoption

For greenfield projects, missing required commands or architecture checks may be errors once the first vertical slice exists.

For brownfield projects:

1. establish a report-only baseline;
2. fix broken harness structure;
3. promote high-confidence rules to warnings;
4. eliminate or explicitly exempt legacy violations;
5. promote stable rules to errors.

Never make CI blocking solely because an AI guessed a boundary.

## Reports and CI

Write machine-readable reports under `.ai/reports/` and keep them untracked unless audit policy requires versioning. CI should run the repository-owned `tools/ai/validate_harness.py`, then the commands registered as required for the change type.
`--output` creates a new file and refuses to replace an existing path; use `--force-output` only after reviewing the target.
