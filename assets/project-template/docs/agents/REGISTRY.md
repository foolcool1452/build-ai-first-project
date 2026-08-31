# Agent Registry

Status: verified
Last verified: {{DATE}}
Sources: agent session records; update this roster whenever an agent joins, changes status, or retires

Roster of every coding agent that works in this repository. This project
enforces a **single writer session**: one conversation works on the repository
at a time, and validation fails while more than one registry entry is marked
`active`. Subagents spawned by the active conversation are part of that
session — what they write belongs to its single writer identity, and they are
never registered or set `active`. Read-only review agents are likewise not
independent workers and leave no roster entry.

## How to join

Append one section per agent at the end of this file. The section heading is
the stable agent id used on task boards (`docs/tasks/<agent-id>.md`).

```markdown
## <agent-id>

- Model: tool name and model version
- Joined: YYYY-MM-DD
- Status: active
- Last active: YYYY-MM-DD
- Focus: usual areas of responsibility (informational)
- Task board: ../tasks/<agent-id>.md
- Notes: anything the next session should know
```


## Status vocabulary

- `active` — the single writer session currently working in the repository.
  Set it when your session starts and back to `idle` when it ends; validation
  fails while two or more entries are `active`.
- `idle` — has worked here before; no open claims.
- `retired` — no longer expected to return; keep the history.

Update `Last active` when starting and finishing a work session. Create your
task board from `../tasks/README.md`, and archive completed items as described
there when a phase ends.
