# Compaction-based collaboration decision (v3.3.0-wip)

Status: accepted
Last verified: 2026-08-31
Sources: user decisions (2026-08-31); GPT-5.1-Codex-Max compaction and Anthropic structured-handoff evidence in the 2026-08 research report

## Decision

1. **One-time registry.** `docs/agents/REGISTRY.md` is a roster, not a control surface: an agent registers once when it first works in the repository (id, model, joined date, optional focus/notes) and nothing is maintained afterwards. Statuses, Last-active freshness, task boards, and the single-writer `AGENT_MULTIPLE_ACTIVE` check are removed.
2. **Session state compacts into the plan.** When a session ends — normally or mid-round — its state is compressed into the plan's Next action and round entries; a fresh session rebuilds from those artifacts instead of any registry or history. This mirrors the compaction pattern behind 24h+ agent sessions (self-summarize near the window, then restart) and directly targets METR's worst-reported weakness: implicit state recovery.
3. **Work rounds are a reference, not a ritual.** The five-phase loop (Open/Execute/Verify/Review/Close) stays in `references/workflows.md` as guidance for non-trivial changes; small edits go straight through the Change workflow; the plan template carries a compact Round entry format but no mandatory round bookkeeping.

## What was removed

- Registry fields: `Status`, `Last active` (and the freshness window, `AGENT_STALE`, `AGENT_MULTIPLE_ACTIVE`).
- Task boards: `docs/tasks/`, per-agent board files, `TASK_BOARD_UNREGISTERED`, `ARCHIVE_NAME`.
- Validator codes: `AGENT_STATUS`, `AGENT_STALE`, `AGENT_MULTIPLE_ACTIVE`, `TASK_BOARD_UNREGISTERED`, `ARCHIVE_NAME`.
- Landing: full profile drops `docs/tasks/README.md` (12 paths); lite unchanged (9 paths).

## What stayed

- `AGENT_ID_DUPLICATE`, `AGENT_FIELD` (Model + Joined), `AGENT_DATE` (Joined not in the future), `AGENT_FENCE_UNCLOSED` (W) — the structural minimum that keeps the roster trustworthy at near-zero maintenance cost.
- Red-green verification discipline in the Work rounds reference; suspend/resume semantics now expressed purely through plan state.
