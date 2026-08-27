# Agent task boards

Lightweight per-agent todo boards. Ownership is a display convention, not a
claim: any registered agent (see `../agents/REGISTRY.md`) may pick up any item.

## Creating your board

One file per registered agent, named `docs/tasks/<agent-id>.md` using the same
id as the registry section:

```markdown
# Tasks: <agent-id>

Last updated: YYYY-MM-DD

## In progress

- [ ] One concrete outcome per line; link plans or issues when useful.

## Done this phase

- [x] Completed items awaiting phase-end grooming.
```

## Rules

- Keep items outcome-oriented and small enough to verify in one session.
- Taking over another agent's item: check it off only in their board's spirit —
  move it to `In progress` on your own board and note the handover there.
- Cross-session, multi-step work belongs in `docs/plans/active/` instead;
  boards are for lightweight todos. Reference the plan from both places.

## Phase-end grooming

When a phase or milestone completes, archive each board's finished items to
`archive/<YYYY-MM-DD>-<agent-id>.md` (one file per agent per grooming run).
Deleting completed items outright is allowed for teams that prefer no history.
Then update `Last active` and trim `Done this phase` to empty on every board.
