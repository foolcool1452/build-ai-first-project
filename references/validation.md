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
- manifest structure is enforced by hand-written contract checks (`MANIFEST_CONTRACT` findings name the violated field): `schemaVersion` is the integer 1, `project` carries a valid adoption mode and persistence model plus an optional `harnessProfile` of `lite` or `full`, and `guidance`/`knowledge`/`commands`/`validation` have the required shapes. Full must declare plans and agents knowledge plus plan-state and agents checks; a lite manifest with that complete shape warns as `PROFILE_DRIFT`.
- manifest paths are relative, remain inside the repository, and resolve when required.
- core knowledge paths (`index`, `architecture`, and `product`) exist; optional branches are checked only when declared.
- the full profile declares the agent registry (`knowledge.agents`); the lite profile omits it. Optional branches are validated whenever declared and their checks are enabled.

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
- generated docs *should* declare their generator or generation command — a project convention, not a validator-enforced rule.
- verification dates must parse as YYYY-MM-DD and stay in the past; staleness itself is a review concern, not an enforced rule.

### Plan state

- every active plan contains Goal, Scope and non-goals, Progress, Decisions, Verification, Risks and blockers, and Next action.
- completed plans are not left under `active/`.
- explicit `Plan ID:` values are unique where they are used; local links are covered by the Markdown check.

### Agent coordination

Checked when `validation.requiredChecks` includes `agents` (the scaffolded default):

- the declared `knowledge.agents` registry path exists;
- registration is one-time: registry sections use unique single-token `## <agent-id>` ids, case-insensitively (`AGENT_ID_DUPLICATE` error) with `- Model` and `- Joined` fields present (`AGENT_FIELD` error);
- `- Joined` uses YYYY-MM-DD, parses as a calendar date, and stays in the past (`AGENT_DATE` error);
- an unclosed code fence in the registry warns (`AGENT_FENCE_UNCLOSED`) — sections after it are ignored;
- there is nothing else to maintain: no statuses, no freshness, no boards. Session state lives in plans and round entries (compacted at session end), not in the registry.

### Manifest commands

- commands are argument arrays, never shell strings;
- executable and path arguments are repository-relative or tool names, never machine-specific absolute paths;
- sensitive values are not command arguments; use environment or credential-provider configuration;
- working directories stay within the repository (`.` by default);
- timeouts are positive and bounded (900 seconds by default);
- every populated command group outside the runnable order (`architecture`, `docs`, `test`, `lint`, `typecheck`, `build`) warns (`COMMAND_GROUP_NEVER_RUNS`); `deploy`/`release`/`migrate`/`production` additionally warn as `UNSAFE_COMMAND_GROUP`. The reserved `setup` group is exempt: it records the manual bootstrap route and is intentionally never executed by validation.

### Untrusted-input handling

Manifests and skill markers are data from possibly hostile repositories, so the validator treats them like parser fuzz:

- JSON is loaded with duplicate-key rejection (`MANIFEST_INVALID` names the offending key) and a 2 MB size cap; parse failures, recursion, or memory exhaustion surface as findings instead of tracebacks.
- manifest structure is enforced by hand-written total checks, so there is no schema engine to drift and no deeply nested schema to walk.
- registered argv elements are capped at 4096 characters (`COMMAND_ARGV_LENGTH`) before any redaction pass runs.
- Markdown report output folds control characters and newlines out of every finding, so untrusted text cannot forge headings, fake findings, or unclosed fences in `--format markdown`.

The validator is dependency-free and implements its manifest contract directly; there is no external schema file to keep in sync. Agents reading the contract should treat `references/validation.md` and the `MANIFEST_CONTRACT` findings as the single source of truth.
Keep `tools/ai/validate_harness.py` and `tools/ai/sync_skill_adapters.py` together; the validator imports shared skill-tree and digest helpers from the sync script.

The readiness audit reports evidence and routing heuristics, not a substitute for repository-specific CI and human review. Verify detected commands before scaffolding or running them.

### Architecture

- `architecture.enforced: true` requires a registered runnable `architecture` command; otherwise the harness is flagged as observational;
- zone graphs and dependency rules belong to project-native linters (ArchUnit, import-linter, dependency-cruiser); the universal validator intentionally does not re-implement them.

### Finding-code inventory

Exhaustive codes the universal validator can emit, grouped by check (severity):

| Check | Codes |
|---|---|
| Manifest & structure | `MANIFEST_MISSING`/`MANIFEST_INVALID`/`MANIFEST_CONTRACT` (E); `UNKNOWN_CHECK` (E); `GUIDANCE_PATH`, `KNOWLEDGE_*`, `NESTED_SKILL_NOT_PORTABLE` (E); `PROFILE_DRIFT`, `PROFILE_PROMOTION_PENDING` (W) |
| Guidance budget | `GUIDANCE_BLOAT` (E), `GUIDANCE_READ` (E), `GUIDANCE_NEAR_BUDGET` >85% lines (W) |
| Adapter consistency | `ADAPTER_BLOCK` (E), `CLAUDE_ADAPTER_UNDECLARED` (W), `CLAUDE_IMPORT`/`CLAUDE_SYMLINK`/`CLAUDE_READ` (E), `CLAUDE_BLOAT` (W); skills: `CLAUDE_SKILL_ADAPTER`, `CLAUDE_SKILL_ORPHAN` (E) |
| Links | `BROKEN_LINK`, `LINK_ESCAPE`, `UNDEFINED_LINK_REFERENCE` (E) |
| Metadata | `METADATA_MISSING`, `METADATA_STATUS`, `VERIFICATION_DATE`, `FUTURE_VERIFICATION` (E); `PLACEHOLDER_CONTENT` (W) |
| Plan state | `PLAN_FIELD`, `PLAN_STATUS`, `PLAN_ID_DUPLICATE` (E); `ACTIVE_PLANS_DIR` (W) |
| Agent coordination | `AGENT_ID_DUPLICATE`, `AGENT_FIELD`, `AGENT_DATE` (E); `AGENT_FENCE_UNCLOSED` (W). One-time registration: no statuses, no freshness, no task boards |
| Commands | `COMMAND_BLOCK/GROUP/SHAPE/ARGV/ARGV_LENGTH/ABSOLUTE_PATH/SECRET_ARGUMENT/CWD/CWD_TYPE/TIMEOUT/REQUIRED` (E); `COMMAND_GROUP_NEVER_RUNS`, `UNSAFE_COMMAND_GROUP` (W) |
| Architecture | `ARCH_BLOCK`, `ARCH_NOT_ENFORCED` (E); `ARCH_OBSERVATIONAL` (W). Zone-graph validation is deliberately left to project-native linters |
| Command execution (`--run-commands`) | records exit code and duration only — command output is discarded, not captured; failures surface as `COMMAND_FAILED`, `COMMAND_MISSING`, `COMMAND_TIMEOUT`, or `COMMAND_EXECUTION` with severity following each command's `required` flag |

(E)=error, (W)=warning. Audit findings live in `scripts/audit_project.py` and are reported read-only; they never block.

## Command checks

`--run-commands` runs reviewed registered commands without a shell, using each command's `argv`, `cwd`, and timeout. The absence of a shell prevents shell-string expansion but does not make an arbitrary executable safe. Treat commands from an untrusted repository exactly like build scripts: review the manifest and referenced executables before enabling this option. Do not automatically run deploy, release, migration, destructive, or production commands.

Recommended order:

1. architecture and documentation checks;
2. targeted tests;
3. lint and typecheck;
4. broader tests;
5. build.

Capture exit code and duration only; command output is discarded rather than captured, so there is nothing to redact or leak in reports. Redaction still applies to echoed argv. Never register commands whose safety depends on nobody reading their output, and never put secrets in command arguments — those are rejected outright (`COMMAND_SECRET_ARGUMENT`).

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
