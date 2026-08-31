# Agent task boards

Lightweight per-agent todo boards. This repository runs a single writer
session at a time, so boards mostly record what that session is doing and
what it hands to the next one. Items produced by the session's subagents or
read-only reviewers are recorded on the owning session's board, not on
separate boards.

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
- Because only one writer session runs at a time, takeovers happen between
  sessions: move unfinished items to the next session's board (or note the
  handover there) instead of editing the previous session's board.
- Cross-session, multi-step work belongs in `docs/plans/active/` instead;
  boards are for lightweight todos. Reference the plan from both places.

## Phase-end grooming

When a phase or milestone completes, archive each board's finished items to
`archive/<YYYY-MM-DD>-<agent-id>.md` (one file per agent per grooming run;
create the `archive/` directory on first use). Deleting completed items
outright is allowed for teams that prefer no history. Then update `Last
active` and trim `Done this phase` to empty on every board.
