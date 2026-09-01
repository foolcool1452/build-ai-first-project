# Plan: Short task name

Status: active
Last verified: {{DATE}}
Sources: user request, issue, specification, and relevant code paths

## Goal

Define the observable outcome and acceptance criteria.

## Scope and non-goals

- In scope:
- Non-goals:

## Progress

- [ ] First verifiable milestone

## Decisions

- None yet.

## Verification

- Commands and evidence still required.

## Risks and blockers

- None known.

## Next action

State one safe, concrete next action.

## Rounds

The standard loop for non-trivial changes (single-file cosmetic edits skip
rounds). One entry per round: state how the round is proven up front, then
execute → verify → review until the review is clean, and reconcile docs.
Subagents share this session's identity and may write — partition parallel
writers by file or region, one review subagent per round by default, and
give reviewers only the goal, the combined diff, the evidence, and the
verification.

### Round 1 — {{DATE}} — <goal>

- Verify: <how this round is proven — run it before closing>.
- Execute: what changed; partition if parallel writing subagents ran.
- Review: findings; each accepted or rejected with a reason; proof re-ran.
- Close: docs reconciled or "none"; "suspended <date> — <state>"; or
  "closed".

