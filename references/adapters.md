# Agent Adapters

## Contents

1. Canonical surfaces
2. Codex
3. Claude Code
4. Kimi Code
5. Repo-local skills
6. Portability rules

## Canonical surfaces

Use `AGENTS.md` for cross-tool project guidance. Keep repo-local skill content canonical at `.agents/skills/<name>/SKILL.md`, then generate Claude Code discovery mirrors under `.claude/skills/`. Keep detailed project knowledge under normal repository paths so every tool can read it with file tools.

## Codex

- Put durable repository instructions in root and scoped `AGENTS.md` files.
- Put reusable task workflows in Agent Skills rather than expanding `AGENTS.md`.
- Keep repository-specific Codex settings in `.codex/config.toml` only when needed; do not encode product knowledge there.
- Use project-native scripts for deterministic checks so the workflow is not tied to one Codex surface.

## Claude Code

Claude Code reads `CLAUDE.md`, not `AGENTS.md` directly. Use this adapter on every platform:

```markdown
@AGENTS.md

# Claude Code differences

- Add only behavior that cannot be expressed portably.
```

Prefer the import on Windows because symlink creation may require additional privileges. Use `.claude/rules/` for Claude-only path-scoped behavior. Claude Code discovers project skills under `.claude/skills/`, not `.agents/skills/`; generate managed mirrors with `python tools/ai/sync_skill_adapters.py . --apply` and validate their source digest. Never edit a generated mirror directly.

## Kimi Code

Kimi Code reads project `AGENTS.md` and supports `.agents/skills/` directly. Its project skill root is the nearest ancestor containing `.git`; nested component `.agents/skills/` directories are rejected as a portable surface unless the component is its own Git root. Keep cross-tool component workflows at the nearest Git root with scoped names and descriptions. Keep Kimi-only instructions in `.kimi-code/AGENTS.md` and Kimi-only skills in root `.kimi-code/skills/` only when the portable form is insufficient.

Kimi subagents have isolated contexts. Task descriptions must include the goal, scope, evidence locations, constraints, and expected result; do not assume the parent conversation is visible.

## Repo-local skills

Use one skill for one repeatable workflow, such as:

- implement-change;
- review-diff;
- run-ui-journey;
- inspect-observability;
- release-package;
- garden-docs;
- score-quality.

Keep `SKILL.md` concise. Put detailed references in `references/`, deterministic helpers in `scripts/`, and output templates in `assets/`. The description must state both capability and triggering situations.

After adding or changing a canonical skill:

```text
python tools/ai/sync_skill_adapters.py . --apply
python tools/ai/validate_harness.py .
```

The sync script refreshes only mirrors whose marker proves they were generated and remain unmodified. It refuses to overwrite unmanaged or manually edited Claude skill directories.
If a canonical skill is removed, the script reports the unchanged managed mirror as orphaned; inspect it, then use `--prune` for explicit removal. If a mirror was edited, preserve or reconcile the edits manually before regenerating it. Canonical portable skill trees must not contain symlinks, because mirrors must not copy content from outside the declared skill tree.
The marker is an ownership and drift signal, not a cryptographic authenticity guarantee. Review skills from an untrusted repository before allowing any agent to load or run them.

In canonical skill instructions, refer to bundled files with paths relative to the skill directory, such as `scripts/check.py`. Use `${KIMI_SKILL_DIR}` only in a Kimi-specific adapter; it is not a cross-tool placeholder.

Do not turn stable facts such as module paths into a skill; keep them in canonical project documentation. Do not turn strict safety enforcement into a skill; use permissions, hooks, or code.

## Portability rules

- Use standard Markdown and relative repository paths.
- Avoid tool-specific slash commands in canonical specifications and execution plans.
- Store command arguments in the manifest and let adapters present tool-specific invocations.
- Do not assume symlink support.
- Detect capability differences and degrade to normal file reading rather than copying knowledge.
- Treat instruction files as behavioral guidance, not a security boundary.

Official discovery references: [Codex skills](https://developers.openai.com/codex/skills), [Claude Code skills](https://code.claude.com/docs/en/slash-commands), and [Kimi Code skills](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html).
