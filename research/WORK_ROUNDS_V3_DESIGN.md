# Work Rounds v3: red-baseline discipline (design)

Status: accepted
Last verified: 2026-08-31
Sources: two independent review agents (protocol design critic + practitioner red-team) on the v2 design; 2026-08 research report; user decision to deepen without publishing

## Problem (v2 design gaps, found by review)

1. **No red-green baseline**: the Verify command committed at Open necessarily fails before the change is implemented, but nothing said so — an executor could write a perpetually-green fake Verify and the protocol could not tell hollow verification from a real one.
2. **No evidence form**: "reviewer re-ran Verify" left no filesystem trace; pipes can mask exit codes.
3. **Silent suspend/resume conflicts**: re-opening the same round id overwrote the suspended narrative; handoff was double-written in Close and Next action without a division of labor.
4. **Undocumented archive mechanics**: a completed plan must physically move from `active/` to `completed/` — nowhere written.
5. **Loose ends**: lite-style ghost routes (`docs/plans/active/` in lite's ARCHITECTURE.md), tilde fences in registries, stale-advice for retired agents, partition format without a checkable form, missing suspended-round pointer in AGENT_STALE, trivial-round friction without criteria.

## Protocol (v3)

**Open** — registry `active`; entry gains goal, the **Verify command** (anchored on the harness's registered checks plus round-specific assertions), subagent budget, and the writer partition. Then run Verify once and record the **red baseline**: a round is valid only if the baseline fails or does not yet exercise the change. A passing baseline makes the round vacuous — narrow or extend the command instead of executing.

**Execute** — in-session or via partitioned writing subagents (`partition: <writer-id> = <path or glob>[; ...]`; non-overlapping, covering every file the round may touch). Failed approaches stay in the entry.

**Verify** — run the command unpiped; append `verified: exit <code> — <summary> — <command>`. Trajectory: baseline-red → verified-green.

**Review** — zero-shared-context subagent receives goal + combined diff + evidence + Verify command, **re-runs the verification**, states a coverage declaration (what it re-ran and read), appends `reviewer: exit <code> — <summary>`, and produces findings with dispositions. Zero findings is an anomaly signal: re-check the Verify's strength first.

**Convergence** — stop when a review returns no new findings; two consecutive reviews with only rejected-with-reason findings means oscillation: re-plan.

**Close** — docs reconciled or "none"; entry closed. Mid-round session end → `suspended <date> — <state>` with registry `idle` and the handoff on the plan's Next action; resumption appends `Resumed <date>:` sub-lines without rewriting the suspension record. A suspension older than about a week, or one whose red baseline drifted, is void — re-open as a new round from Plan.

**Budget** — one review subagent per round by default; research subagents on demand with justification. Research need concentrates in the first round; precision spent on the entry is the cheapest token.

**Scope** — rounds are required for behavior, manifest, canonical-doc, multi-file, or boundary-crossing changes; single-file cosmetic edits go straight through the Change workflow.

**Archive** — last round closed → reconcile docs → `Status: completed` → move the file to `docs/plans/completed/` in the same edit → re-validate.

## Deliberately not mechanized

Subagent budgets, finding dispositions, partition correctness, reviewer honesty: all are normative prose with a written trail. Mechanical enforcement would either be gameable or turn review into ritual.

## Implementation

`references/workflows.md` (Work rounds section rewrite), `docs/plans/TEMPLATE.md` (entry format), `scripts/validate_project.py` (AGENT_STALE suspended-rounds pointer), `scripts/self_test.py` (template assertions), VERSION/README 3.3.0. Version: 3.3.0 — unpublished, local artifact by request.
