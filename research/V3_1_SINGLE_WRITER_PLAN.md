# Plan: v3.1.0 single-writer invariant

Status: complete
Last verified: 2026-08-31
Sources: user requirement ("one conversation writes at a time"), `research/V3_DESIGN.md`, `skill/references/validation.md`

## Goal

Make "one writer session at a time" a mechanically enforced invariant of the full profile's coordination surface, with precise semantics: subagents of the active conversation and read-only review agents are not independent workers.

## Scope and non-goals

- In scope: `AGENT_MULTIPLE_ACTIVE` validation, registry/task-board template semantics, session-lifecycle guidance, contract documentation, regression tests, immutable round archive.
- Non-goals: publishing, global installation, git commits, touching preserved legacy root files, registering subagents/reviewers, changing lite-profile behavior, downgrading to a warning.

## Progress

- [x] Validator: `check_agents` counts valid `active` entries; two or more fail with `AGENT_MULTIPLE_ACTIVE` naming every active id.
- [x] Registry template: single-writer semantics with the two exemptions stated in the intro and status vocabulary.
- [x] Task-board template: single-session ownership wording; subagent output recorded on the owning session's board.
- [x] `references/validation.md`: invariant bullet plus `AGENT_MULTIPLE_ACTIVE` (E) in the finding-code inventory.
- [x] `references/workflows.md`: session lifecycle steps 2-4 bound to the invariant; ownership rules updated.
- [x] `scripts/self_test.py`: mixed-registry pass scenario and two-active failure scenario.
- [x] Full self-test PASS; full-profile smoke PASS (single active exit 0, double active exit 1 with the new code).

## Decisions

- Severity is error, not warning: the user's operating model has exactly one writer conversation; a second `active` is a contract breach, not drift.
- Invalid-status entries never count toward the invariant (they already fail with `AGENT_STATUS`), so the two findings never mask each other.
- Exemptions are documented, not modeled: subagents and reviewers leave no registry trace, keeping the registry a roster of writer sessions only.

## Verification

- `python skill/scripts/self_test.py` → PASS (including the two new scenarios and the pre-existing no-bytecode-residue check).
- Fresh full-profile scaffold smoke: single `active` validates with exit 0; a second `active` fails with exit 1 and `AGENT_MULTIPLE_ACTIVE`.
- Round-4 immutable archive created and a restore-from-archive self-test drill passed.

## Risks and blockers

- A reviewer agent mistakenly marked `active` by a future session would block validation; mitigated by template and lifecycle wording that reserve `active` for the single writer and exclude reviewers.
- If multi-writer is ever wanted, the natural relaxation is downgrading this finding to a warning; deliberately not implemented now.

## Next action

None. Publishing, committing, and global installation remain deferred to an explicit user request.
