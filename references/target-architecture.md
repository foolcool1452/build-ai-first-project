# Target Repository Architecture

## Contents

1. Design goals
2. Recommended layout
3. Artifact contracts
4. Manifest contract
5. Architecture enforcement
6. Small-project and monorepo variants

## Design goals

Optimize for agent legibility, deterministic verification, progressive disclosure, recovery after context loss, and tool neutrality. Do not optimize for maximum documentation volume.

Use two linked truth lanes:

- **Intent lane**: product specifications, accepted decisions, invariants, and active change plans.
- **Implementation lane**: code, tests, schemas, generated API or database documentation, logs, metrics, and reproducible UI evidence.

Tests and drift checks reconcile the lanes. Neither lane may silently redefine the other.

## Recommended layout

```text
repo/
|-- AGENTS.md                       # short map, hard rules, verification route
|-- CLAUDE.md                       # @AGENTS.md plus Claude-only differences
|-- ARCHITECTURE.md                 # current high-level system map
|-- .ai/
|   |-- harness.json                # machine-readable control plane
|   |-- harness.schema.json         # manifest schema
|   |-- .gitignore                  # reports and temporary state
|   `-- reports/                    # generated, normally untracked
|-- .agents/
|   `-- skills/                     # canonical Codex/Kimi repo-local workflows
|-- .claude/
|   `-- skills/                     # managed Claude mirrors; do not edit directly
|-- docs/
|   |-- INDEX.md                    # knowledge routing table
|   |-- product/
|   |   `-- index.md                # product intent and acceptance vocabulary
|   |-- agents/
|   |   `-- REGISTRY.md             # roster: who joined, status, focus, board link
|   |-- tasks/
|   |   |-- <agent-id>.md           # per-agent todo boards; ownership advisory
|   |   `-- archive/                # grooming output; created on first use
|   |-- architecture/
|   |   |-- index.md                # detailed current architecture
|   |   `-- decisions/              # durable rationale, one decision per file
|   |-- plans/
|   |   |-- TEMPLATE.md
|   |   |-- active/                 # resumable multi-step work
|   |   `-- completed/              # retained only when history is useful
|   |-- operations/
|   |   `-- index.md                # run, debug, deploy, observe, recover
|   |-- workflows/                  # optional repeatable procedures; scope only where a repo-local skill would not fit
|   |-- quality/
|   |   `-- QUALITY.md              # evidenced gaps and bounded technical debt
|   `-- generated/
|       `-- index.md                # derivation commands; never hand-edit output
`-- tools/
    `-- ai/
        |-- sync_skill_adapters.py   # generate/check Claude skill mirrors
        `-- validate_harness.py      # validation entrypoint; imports the paired sync helper
```

Create only relevant branches. A library without operations or UI does not need empty operational ceremony. The routing index must state intentionally omitted sections.

## Artifact contracts

### `AGENTS.md`

Target 60-120 lines. Include only:

- project purpose in one paragraph;
- map to canonical artifacts and important code roots;
- exact setup and verification route, preferably by referencing `.ai/harness.json`;
- hard safety or architectural constraints not already enforced elsewhere;
- definition of done;
- instruction-update routing.

Exclude tutorials, full architecture prose, formatter rules, release procedures, and task-specific checklists.

### `ARCHITECTURE.md`

Describe current implementation, not aspiration. Include boundaries, dependency direction, entry points, data stores, external systems, and the command that validates architecture. Each claim should link to code or generated evidence.

For brownfield projects, use `Status: observed` until verified. Write unknowns explicitly.

### Canonical documentation metadata

Start canonical files with a compact block:

```text
Status: verified | observed | proposed | generated
Last verified: YYYY-MM-DD
Sources: path, command, or plan identifier
```

`proposed` content belongs in a change or plan, not in current-state architecture.

### Execution plans

Use plans only for changes that cross sessions, components, or review checkpoints. Required headings:

- Status
- Goal
- Scope and non-goals
- Progress
- Decisions
- Verification
- Risks and blockers
- Next action

Update the plan during work. When complete, preserve durable rationale in an ADR or canonical doc; then archive or delete the plan according to the chosen persistence model.

### Agent registry and task boards

`docs/agents/REGISTRY.md` records who has worked in the repository: one `## <agent-id>` section per agent with single-token ids and fields `- Model`, `- Joined: YYYY-MM-DD`, `- Status` (`active`, `idle`, or `retired`), `- Last active: YYYY-MM-DD`, `- Focus`, `- Task board`, `- Notes`. Set `Status: active` at session start and back to `idle` when finishing; `Last active` older than the freshness window warns via validation.

Coordination is advisory by design — nothing locks a file or reserves work:

- one lightweight board per registered agent at `docs/tasks/<agent-id>.md`, split into `In progress` and `Done this phase`;
- any registered agent may pick up another's item; note the handover on their own board;
- multi-session work belongs in `docs/plans/active/`; boards reference it rather than duplicating it;
- when a phase ends, groom boards: move finished items to `archive/<YYYY-MM-DD>-<agent-id>.md` (default) or delete them if the team prefers no history, and reset each board's done section.

The validator enforces structure (unique ids, status vocabulary, date formats), not territory. A project may omit both branches by removing the declarations from `.ai/harness.json`, deleting the directories, and dropping the routing rows that pointed at them.

### Generated documentation

Generated files must state their generator and source inputs; keeping them reproducible is a project-native convention this skill documents but does not mechanically enforce.

## Manifest contract

`.ai/harness.json` is the machine-readable control plane. It records:

- schema version, project name, adoption mode, and specification persistence model;
- canonical file paths and context budgets;
- setup, test, lint, typecheck, build, architecture, and documentation commands as argument arrays;
- required validation checks and freshness policy;
- optional architecture zones and ownership metadata.

Keep `$schema` fixed at `./harness.schema.json`; schema version 1 has one structural contract, and the validator checks its canonical fingerprint before trusting it.

The `knowledge.index`, `knowledge.architecture`, and `knowledge.product` paths are core. `knowledge.agents` and `knowledge.tasks` (the collaboration surfaces) are declared by default in the scaffolded manifest; `plans`, `operations`, `quality`, and `generated` are optional. Declare a path only when the project uses that branch, and keep the routing index consistent with intentional omissions.

Do not put secrets, credentials, user-specific absolute paths, or shell pipelines in the manifest.

Commands use this shape:

```json
{
  "argv": ["pnpm", "test"],
  "cwd": ".",
  "timeoutSeconds": 900,
  "required": true
}
```

Only `argv` is mandatory. `cwd`, `timeoutSeconds`, and `required` default to `.`, `900`, and `false`.

## Architecture enforcement

The universal validator checks manifest and documentation structure. It cannot truthfully infer language-specific dependency semantics.

Add project-native architecture checks when boundaries are known:

- TypeScript/JavaScript: dependency-cruiser, ESLint import boundaries, or a focused AST check.
- Python: import-linter or a focused module graph test.
- JVM: ArchUnit.
- .NET: NetArchTest or architecture tests.
- Go/Rust: package or crate graph checks plus focused structural tests.

Register the check under `commands.architecture`. Error messages should name the invariant, violating edge, source file, and intended remediation.

## Small-project and monorepo variants

For a small project, keep the routing index, `ARCHITECTURE.md`, one product spec, and the manifest. Add plans, operations, quality, and generated branches only when they serve a real project need.

For a monorepo:

- keep shared rules and global dependency boundaries at the root;
- place component `AGENTS.md` and architecture pages nearest their code;
- keep portable auto-discovered skills at the nearest Git root `.agents/skills/` and namespace component-specific workflows there; the universal sync and validator reject nested component skills that are not their own Git root;
- give every component a stable identifier;
- review nested guidance for conflicts with root hard rules; the universal validator checks structure and links, not semantic consistency;
- make every command declare its `cwd`;
- avoid copying the same constitution or workflow into every package; link or generate adapters from one canonical source.
- audit a component with the default path scope; use `--scope repository` only for an intentional whole-repository census.
