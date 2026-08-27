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

- `.ai/harness.json` exists and the declared guidance entrypoint, architecture path, and knowledge index exist (a renamed entrypoint shifts what is checked, not a literal `AGENTS.md` name).
- manifest paths are relative, remain inside the repository, and resolve when required.
- schema version and supported persistence model are valid.
- core knowledge paths (`index`, `architecture`, and `product`) exist; optional branches are checked only when declared.
- the collaboration surfaces (`knowledge.agents` registry, `knowledge.tasks` directory) are declared and validated by default in scaffolded projects.

### Guidance budget

- root `AGENTS.md` stays under `guidance.maxLines`.
- root guidance links to canonical sources instead of duplicating long procedures.
- warn about likely formatter-rule leakage when formatter configuration exists and guidance restates indentation, semicolon, quote, or line-length rules.

### Adapter consistency

- `CLAUDE.md` contains a whole-line import of the canonical entrypoint (`@AGENTS.md`) or is a resolvable symlink to it; bare mentions inside sentences do not count.
- `CLAUDE.md` stays within 60 raw lines; a human review remains responsible for deciding whether its text is truly vendor-specific.
- every `.agents/skills/<name>` source has an identical managed `.claude/skills/<name>` mirror or a symlink to the canonical source.
- nested guidance scope and semantic consistency require review; the universal validator does not infer whether instructions conflict.

### Knowledge integrity

- local Markdown links resolve; scanning ignores fenced code blocks (``` and ~~~) and tolerates a UTF-8 BOM. Four-space indented code blocks are *not* recognized — show link examples inside fences.
- Windows drive-letter links (`C:/...`) always fail as `LINK_ESCAPE`: knowledge must travel with the repository.
- canonical current-state files include `Status`, `Last verified`, and `Sources` metadata.
- generated docs declare their generator or generation command.
- verification dates older than `validation.freshnessDays` warn rather than silently becoming truth.

### Plan state

- every active plan contains Goal, Scope and non-goals, Progress, Decisions, Verification, Risks and blockers, and Next action.
- completed plans are not left under `active/`.
- explicit `Plan ID:` values are unique where they are used; local links are covered by the Markdown check.

### Agent coordination

Checked when `validation.requiredChecks` includes `agents` (the scaffolded default):

- declared `knowledge.agents` registry and `knowledge.tasks` directory paths exist;
- registry sections use unique single-token `## <agent-id>` ids, case-insensitively (`AGENT_ID_DUPLICATE` error) with `- Model`, `- Joined`, `- Status`, `- Last active` fields present (`AGENT_FIELD` error);
- status vocabulary is `active` / `idle` / `retired` (`AGENT_STATUS` error); dates use YYYY-MM-DD, parse as calendar dates, and stay in the past (`AGENT_DATE` error);
- `- Last active` older than the freshness window warns (`AGENT_STALE`) rather than silently becoming truth;
- task boards whose file stem matches no registered agent warn (`TASK_BOARD_UNREGISTERED`); archive files not named `<YYYY-MM-DD>-<agent-id>.md` — including impossible calendar dates like `2026-99-99` — warn (`ARCHIVE_NAME`);
- ownership stays advisory: the check enforces structure only, never locking or territory.

### Manifest commands

- commands are argument arrays, never shell strings;
- executable and path arguments are repository-relative or tool names, never machine-specific absolute paths;
- sensitive values are not command arguments; use environment or credential-provider configuration;
- working directories stay within the repository (`.` by default);
- timeouts are positive and bounded (900 seconds by default);
- strict validation requires at least one command marked `required: true`, even if the configured check list omits command execution;
- every populated command group outside the runnable order (`architecture`, `docs`, `test`, `lint`, `typecheck`, `build`) warns (`COMMAND_GROUP_NEVER_RUNS`); `deploy`/`release`/`migrate`/`production` additionally warn as `UNSAFE_COMMAND_GROUP`. The reserved `setup` group is exempt: it records the manual bootstrap route and is intentionally never executed by validation.

### Untrusted-input handling

Manifests, schemas, and skill markers are data from possibly hostile repositories, so the validator treats them like parser fuzz:

- JSON is loaded with duplicate-key rejection (`MANIFEST_INVALID` names the offending key) and a 2 MB size cap; parse failures, recursion, or memory exhaustion surface as findings instead of tracebacks.
- `harness.schema.json` keeps its fingerprint check and schema walking is depth-bounded, so neither a drifted nor an oversized schema can exhaust the stack.
- registered argv elements are capped at 4096 characters (`COMMAND_ARGV_LENGTH`) before any redaction pass runs.
- Markdown report output folds control characters and newlines out of every finding, so untrusted text cannot forge headings, fake findings, or unclosed fences in `--format markdown`.

The validator always loads `.ai/harness.schema.json`; `$schema` must remain `./harness.schema.json`, and the schema content must match the canonical schemaVersion 1 fingerprint. It implements the required subset without third-party packages and is not a general-purpose JSON Schema engine.
Keep `tools/ai/validate_harness.py` and `tools/ai/sync_skill_adapters.py` together; the validator imports shared skill-tree and digest helpers from the sync script.

The readiness audit reports evidence and routing heuristics, not a substitute for repository-specific CI and human review. Verify detected commands before scaffolding or running them.

### Architecture

- declared zones have unique identifiers and valid paths;
- dependency targets reference known zones;
- if architecture is declared enforced, an architecture command must exist and pass.

### Finding-code inventory

Exhaustive codes the universal validator can emit, grouped by check (severity):

| Check | Codes |
|---|---|
| Manifest & structure | `MANIFEST_MISSING`/`MANIFEST_INVALID` (E); `SCHEMA_PATH`, `SCHEMA_MISSING`, `SCHEMA_INVALID`, `SCHEMA_DRIFT`, `SCHEMA_CONTRACT` (E); `UNKNOWN_CHECK` (E); `GUIDANCE_PATH`, `KNOWLEDGE_*`, `NESTED_SKILL_NOT_PORTABLE` (E) |
| Guidance budget | `GUIDANCE_BLOAT` (E), `GUIDANCE_NEAR_BUDGET` >85% lines (W), `LINT_LEAKAGE` (W) |
| Adapter consistency | `CLAUDE_ADAPTER_UNDECLARED` (W), `CLAUDE_IMPORT`/`CLAUDE_SYMLINK`/`CLAUDE_READ` (E), `CLAUDE_BLOAT` (W); skills: `CLAUDE_SKILL_ADAPTER`, `CLAUDE_SKILL_ORPHAN` (E) |
| Links | `BROKEN_LINK`, `LINK_ESCAPE`, `UNDEFINED_LINK_REFERENCE` (E) |
| Metadata | `METADATA_MISSING`, `METADATA_STATUS`, `VERIFICATION_DATE`, `FUTURE_VERIFICATION` (E); `STALE_DOCUMENT`, `PLACEHOLDER_CONTENT`, `GENERATOR_PLACEHOLDER` (W); `GENERATOR_MISSING` (E) |
| Plan state | `PLAN_FIELD`, `PLAN_STATUS`, `PLAN_ID_DUPLICATE` (E); `ACTIVE_PLANS_DIR` (W) |
| Agent coordination | `AGENT_ID_DUPLICATE`, `AGENT_FIELD`, `AGENT_STATUS`, `AGENT_DATE` (E); `AGENT_STALE`, `TASK_BOARD_UNREGISTERED`, `ARCHIVE_NAME` (W) |
| Commands | `COMMAND_BLOCK/GROUP/SHAPE/ARGV/ARGV_LENGTH/ABSOLUTE_PATH/SECRET_ARGUMENT/CWD/CWD_TYPE/TIMEOUT/REQUIRED` (E); `REQUIRED_COMMANDS` (E, strict only); `COMMAND_GROUP_NEVER_RUNS`, `UNSAFE_COMMAND_GROUP` (W) |
| Architecture | `ARCH_BLOCK/ZONES/ZONE/ZONE_DUPLICATE/ZONE_PATHS/ZONE_PATTERN/DEP_LIST/UNKNOWN_DEP/NOT_ENFORCED` (E); `ARCH_ZONE_EMPTY`, `ARCH_OBSERVATIONAL` (W) |
| Command execution (`--run-commands`) | `COMMAND_FAILED`, `COMMAND_TIMEOUT`, `COMMAND_EXECUTION` (severity follows each command's `required` flag); `COMMAND_MISSING` as listed |

(E)=error, (W)=warning. Audit findings live in `scripts/audit_project.py` and are reported read-only; they never block.

## Command checks

`--run-commands` runs reviewed registered commands without a shell, using each command's `argv`, `cwd`, and timeout. The absence of a shell prevents shell-string expansion but does not make an arbitrary executable safe. Treat commands from an untrusted repository exactly like build scripts: review the manifest and referenced executables before enabling this option. Do not automatically run deploy, release, migration, destructive, or production commands.

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
