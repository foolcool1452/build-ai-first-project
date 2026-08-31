# Plan: three-round v3 optimization

Status: complete
Last verified: 2026-08-29
Sources: user objective, `V3_DESIGN.md`, `ENGINEERING_PRACTICES.md`

## Goal

Complete three independently backed-up optimization rounds while keeping v3 concise, local-only, unpublished, and uncommitted.

## Scope and non-goals

- In scope: profile decision clarity, implementation duplication, template compactness, regression coverage, documentation consistency, and recovery evidence.
- Non-goals: global installation, Git commits, publishing, adding vendor-specific configuration without a demonstrated need, or altering preserved legacy root files.

## Progress

- [x] Round 0 baseline archived and verified.
- [x] Round 1: optimize profile decision contract and practice traceability.
- [x] Round 2: simplify implementation and generated surfaces without changing the profile contract.
- [x] Round 3: strengthen evaluation, consistency checks, and recovery evidence.
- [x] Final isolation and completion audit.

## Decisions

- Each completed round receives a new immutable archive; no earlier archive is overwritten.
- Measure generated harness size, not only package line count.
- Prefer removal and reuse over new abstraction unless the abstraction eliminates a tested duplication.

## Verification

- Round 0 self-test passed; global installation matched v2.0.1.
- Round 1 self-test passed; audit exposes score 1/threshold 3 on the candidate, and explicit full preview reports the overridden lite recommendation.
- Round 2 self-test passed; lite/full validate with 0 errors and 2 expected warnings. Generated guidance fell from 50/53 to 41/44 lines, and audit no longer duplicates command discovery during scaffolding.
- Round 3 self-test passed; scaffolding is idempotent, unknown template variables fail before writes, and manifest profile drift is detected. Fresh lite/full outputs remain valid with 0 errors and 2 expected warnings.
- Round 3 restored from its immutable archive and passed the full self-test. Local HEAD remained unchanged and the global installed skill still matched v2.0.1.

## Risks and blockers

- More options can erode simplicity; full/lite remains the only concrete choice.
- Documentation about vendor behavior can age; record primary links and keep the portable contract independent of vendor implementation details.

## Next action

No optimization work remains. Publishing, committing, or global installation requires a separate explicit request.
