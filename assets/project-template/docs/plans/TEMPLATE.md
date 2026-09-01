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

Required for non-trivial changes (behavior, manifest, canonical docs,
multi-file, or boundary-crossing; single-file cosmetic edits may go straight
through the Change workflow). One entry per round: Open commits the Verify
command and its red baseline; Execute/Verify/Review repeat until convergence;
Close reconciles docs. Reference files with backticked repository-relative
paths — markdown links in entries must resolve from this directory. Full
conventions: the harness skill's "Work rounds" section.

### Round 1 — {{DATE}} — <goal>

- Verify: <command anchored on registered checks + round-specific assertions>.
- Baseline: exit <code> — <why it fails before the change>. A passing
  baseline makes this round vacuous; narrow or extend the command instead.
- Research: findings or decision; subagents used: 0 by default (N with
  justification).
- Execute: what changed; evidence; partition: <writer = path/glob>[; ...].
- Review: findings with dispositions; coverage declaration;
  `reviewer: exit <code> — <summary>` (reviewer re-ran Verify).
- Close: docs reconciled or "none"; "suspended <date> — <state>" while in
  progress; or "closed".

