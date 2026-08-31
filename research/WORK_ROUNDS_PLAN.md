# Plan: optional work rounds with subagent rules

Status: complete
Last verified: 2026-08-31
Sources: user requirement ("research → execute → subagent review, repeatable, then maintain docs"; subagents must not be abused; subagents are not required to be read-only), `research/V3_DESIGN.md`, industry evidence in the 2026-08 research report

## Goal

Add an optional standard work-round workflow to the full profile: Plan (research, optional subagents) → Execute → Review subagent → repeat Execute/Review → Reconcile docs. Codify anti-abuse rules so the loop stays cheap and honest.

## Scope and non-goals

- In scope: "Work rounds" section in `references/workflows.md`; optional `## Rounds` log section in `docs/plans/TEMPLATE.md`; subagent rule set; regression assertions; this plan.
- Non-goals: publishing, global installation, git commits, new validation codes, new CLI flags, per-round files, enforcing subagent budgets mechanically (usage is in-conversation; budgets are normative prose with a written trail), touching lite-profile behavior or preserved legacy root files.

## Progress

- [x] "Work rounds" section added to `references/workflows.md` with round definition, five subagent rules, when-not-to-spawn criteria, and surface division of labor.
- [x] `docs/plans/TEMPLATE.md` gained the optional `## Rounds` section with a `### Round N` entry format (research/execute/review/disposition/over-budget/docs reconciliation).
- [x] Self-test asserts the full-profile landing renders the Rounds section; lite remains plans-free.
- [x] Subagent semantics per user correction: subagents may write; their changes carry the session's identity; parallel writing subagents require strict file/region partitioning; review covers the combined diff.
- [x] Full self-test PASS; single-writer invariant unchanged (`AGENT_MULTIPLE_ACTIVE` unaffected — writes by session subagents belong to the session's identity).

## Decisions

- Documentation-first: rounds are procedure plus plan-log, not machinery — no validator codes, no round state machine, no per-round files.
- Default subagent budget: one research plus one review per round; over-budget use requires written justification in the round entry.
- Zero-shared-context review is normative: the reviewer sees goal, combined diff, and evidence — never the working conversation.
- Every review finding must be accepted or rejected with a one-line reason; silent drops are defects.
- Version stays 3.1.0 (unpublished local release folds this feature in); traceability via the round-5 archive.

## Verification

- `python skill/scripts/self_test.py` → PASS (including the new full-landing Rounds-section assertions).
- Lite landing unchanged and plans-free.
- Round-5 immutable archive created; restore-from-archive self-test drill passed.

## Risks and blockers

- Subagent budgets cannot be mechanically enforced; mitigation is the written trail in the round entry plus review coverage of the combined diff.
- Parallel writing subagents without partitioning cause conflicts; the rules require strict partitioning or serialization.

## Next action

None. Publishing, committing, and global installation remain deferred to an explicit user request.
