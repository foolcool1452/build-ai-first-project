# Agent Registry

Status: verified
Last verified: {{DATE}}
Sources: agent session records; update this roster whenever an agent joins, changes status, or retires

Roster of every coding agent that works in this repository. Coordination here is
advisory: nothing in the registry locks a file or reserves a task. One agent
usually works at a time; the roster keeps identity and presence visible so any
new session can orient quickly.

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

- `active` — currently working in the repository.
- `idle` — has worked here before; no open claims.
- `retired` — no longer expected to return; keep the history.

Update `Last active` when starting and finishing a work session. Create your
task board from `../tasks/README.md`, and archive completed items as described
there when a phase ends.
