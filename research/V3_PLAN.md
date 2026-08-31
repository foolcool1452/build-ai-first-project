# Plan: build-ai-first-project v3

Status: complete
Last verified: 2026-08-28
Sources: user objective and `research/V3_DESIGN.md`

## Goal

Produce a concise v3 candidate under `skill/` with explainable AI selection between full and lite harness profiles, while preserving a recoverable pre-v3 baseline and avoiding global installation.

## Scope and non-goals

- In scope: repository layout, profile recommendation, profile-aware scaffolding, manifest validation, templates, documentation, migration guidance, and regression tests.
- Non-goals: installing the candidate globally, publishing a GitHub release, silently converting existing harnesses, or reorganizing the preserved legacy root files.

## Progress

- [x] Capture and verify pre-v3 Git, patch, working-tree, and v2.0.1 archives.
- [x] Isolate the exact v2.0.1 baseline under `skill/`.
- [x] Record profile philosophy, file contracts, selection signals, and acceptance criteria.
- [x] Implement profile recommendation and profile-aware scaffolding.
- [x] Repair generated guidance and restore report ignores.
- [x] Update validator and documentation contracts.
- [x] Add full/lite, override, compatibility, and failure regression tests.
- [x] Run complete verification and review the final diff.

## Decisions

- The repository root is the research workspace; `skill/` is the installable candidate.
- Keep manifest schema version 1 and add a backward-compatible optional concrete profile field.
- Auto recommends from current repository evidence; known intent may override it.
- Lite removes only continuity and coordination branches, not safety or validation depth.

## Verification

- Baseline bundle, tar archive, patch, and source archive have verified SHA-256 hashes.
- Complete candidate self-test passes.
- Independent v2, v3-lite, and v3-full scaffolds validate with 0 errors and the same 2 expected initialization warnings.
- Measured output comparison is recorded in `research/V3_EVALUATION.md`.
- Final diff has no whitespace diagnostics, generated outputs have no unresolved placeholders, and the global installed skill still matches v2.0.1.

## Risks and blockers

- Auto-selection cannot infer future product scope; documentation and preview output must keep the recommendation explicitly overridable.
- Profile-specific prose can drift unless both outputs receive broken-route regression tests.

## Next action

No implementation work remains. Publish or install the verified candidate only after explicit user approval.
