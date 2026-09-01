# Version 3 design: an elastic agent harness

Status: verified
Last verified: 2026-08-29
Sources: upstream tags v1.4.0, v2.0.0, v2.0.1; current scripts and regression suite; official adapter links in `skill/references/adapters.md`

## Problem

Version 1 offered configurable knowledge branches but accumulated templates and a duplicated schema contract. Version 2 removed that machinery and made resumable plans plus multi-agent coordination the single landing set. The subtraction improved maintainability, but it also made very small repositories pay for collaboration surfaces they may never use. Version 2 additionally left generated guidance pointing at files that the scaffold no longer created.

Version 3 must preserve v2's reliable full harness while providing a genuinely small landing set. The choice must be explainable, overridable, testable, and safe for an AI agent to make.

## Philosophy

1. **One invariant core, elastic branches.** Every profile keeps routing, intent, observed architecture, tool adapters, a machine-readable manifest, and executable validation. Plans and agent coordination are branches, not prerequisites for legibility.
2. **Profiles budget attention, not capability.** `lite` is not a weaker validator and `full` is not a quality badge. They differ only in which collaboration and continuity surfaces land on day one.
3. **Evidence recommends; intent decides.** Repository census can estimate current complexity but cannot know product risk, future team size, or regulatory needs. Auto-selection exposes its signals, while an AI or user may explicitly select either profile.
4. **No ghost architecture.** Generated guidance and indexes may refer only to artifacts created by the selected profile. Optional future branches are named as omissions, never as present routes.
5. **One fact, one canonical surface.** The manifest records paths and commands; guidance routes; product docs state intent; architecture states observed implementation; tests enforce decidable rules.
6. **Development and installation are separate.** The repository root owns research and recovery. The installable skill lives under `skill/`, one level deeper, so experiments cannot silently replace a global installation.
7. **Promotion is additive and deliberate.** A lite project can add plans or coordination when real work needs them. Existing files remain user-owned; promotion previews missing files and requires deliberate manifest/guidance reconciliation rather than overwriting local knowledge.

## Profiles

### Lite

Use for a small, single-purpose repository where work normally fits one session and one agent.

```text
repo/
|-- AGENTS.md
|-- CLAUDE.md
|-- ARCHITECTURE.md
|-- .ai/
|   |-- .gitignore
|   `-- harness.json
|-- docs/
|   |-- INDEX.md
|   `-- product/index.md
`-- tools/ai/
    |-- sync_skill_adapters.py
    `-- validate_harness.py
```

The manifest omits `knowledge.plans`, `knowledge.agents`, and `knowledge.tasks`, and it omits their corresponding checks. Security, path containment, adapter, link, metadata, command, and architecture validation stay unchanged.

### Full

Use for work that crosses sessions or components, multiple agents, a monorepo, high-risk changes, or an existing coordination workflow. It is v2's intended landing set, corrected so every route exists.

```text
repo/
|-- <all lite files>
`-- docs/
    |-- agents/REGISTRY.md
    |-- tasks/README.md
    `-- plans/
        |-- TEMPLATE.md
        `-- active/README.md
```

The manifest declares the three branches and enables `plan-state` plus `agents` validation.

## Selection contract

The CLI accepts `--profile auto|lite|full`; `auto` is the default.

Auto-selection computes an explainable complexity score from the read-only audit:

| Signal | Points |
|---|---:|
| At least 12 source files | 1 |
| At least 50 source files | one additional point |
| At least 40 repository files | 1 |
| At least 150 repository files | one additional point |
| Two or more detected implementation languages | 1 |
| Two or more root build manifests | 1 |
| Existing active plans or agent registry | 3 |
| Both tests and CI are present | 1 |

Score 3 or greater recommends `full`; otherwise it recommends `lite`. Audit JSON exposes both `profileScore` and `profileThreshold`; previews show `score/threshold`. An explicit override also prints the audit recommendation it replaced. Thresholds are intentionally conservative and regression-tested: they are a reproducible fallback, not a substitute for product judgment.

An AI must override the census to `full` when the known task requires cross-session recovery, concurrent agents, regulated evidence, or a broad multi-component migration. It may override to `lite` when a large file census is mostly generated or vendored material that the audit could not classify correctly. The preview prints both the selected profile and the evidence.

## Manifest contract

Version 3 keeps `schemaVersion: 1` for backward compatibility and adds optional `project.harnessProfile: "lite" | "full"`. A v3 scaffold always writes the resolved concrete profile. The validator accepts older manifests without the field, rejects an incomplete full declaration, and warns when a lite manifest has acquired the complete full shape.

This is a compatible extension: optional knowledge paths already define whether plans and coordination exist. A lite project may add one branch as needed; once it declares all full branches and checks, it updates the profile field. A schema-version bump would add migration machinery without increasing safety.

## Safety and backup model

- Scaffolding remains preview-only by default and never overwrites existing files.
- Profile selection does not weaken untrusted-input limits, symlink/junction containment, argv validation, or output redaction.
- `.ai/.gitignore` is restored so `.ai/reports/` and `.ai/tmp/` remain local by default.
- The pre-v3 state is recoverable from a verified Git bundle, binary patch, full working-tree archive, and an exact v2.0.1 source archive under the ignored `backups/` directory.
- No v3 candidate is copied to a global Codex, Claude, or Kimi skill directory during research.

## Rejected alternatives

- **Return to v1's `core/full` knowledge profile:** it grouped unrelated operations, quality, generated docs, and plans into one heavy option. The new profiles vary only continuity and coordination.
- **Make `full` the default without inspection:** this recreates v2's small-project tax.
- **Make `lite` the unconditional default:** repository size is not the only risk; known multi-session or multi-agent intent must take precedence.
- **Maintain two validators or complete template trees:** duplicated contracts drift. Profiles share scripts and common templates, with small rendered conditional sections.
- **Automatically rewrite a lite harness during promotion:** preserving user-owned guidance is more important than a one-command conversion. Promotion stays previewed and additive until a dedicated migration contract is designed.

## Acceptance criteria

- Auto-selection is deterministic and reports reasons.
- Explicit `lite` and `full` always win over the recommendation.
- Both profiles scaffold and validate successfully on greenfield and brownfield examples.
- Lite creates no plans, registry, or task-board files and contains no references to them as existing routes.
- Full creates and declares all three surfaces and contains no broken or stale routes.
- v2 manifests without `project.harnessProfile` still validate.
- Invalid profile values fail with `MANIFEST_CONTRACT`.
- Existing project files are never overwritten.
- The complete self-test passes without third-party dependencies or bytecode residue.
