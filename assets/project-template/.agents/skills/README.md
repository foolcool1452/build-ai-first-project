# Portable repository skills

Place canonical repo-local skills at `.agents/skills/<name>/SKILL.md`. Codex and Kimi Code discover this location directly.

After adding or changing a skill, run:

```text
python tools/ai/sync_skill_adapters.py . --apply
python tools/ai/validate_harness.py .
```

The sync command creates managed mirrors under `.claude/skills/` for Claude Code. Edit only the canonical `.agents/skills/` copy.
