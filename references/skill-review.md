# Repo-local skill review (on explicit request)

A review checklist for `.agents/skills/*/SKILL.md` — run only when someone
asks for a skill review or improvement pass. It is advisory: findings are
suggestions with evidence, never validation errors, and nothing here runs
automatically.

## Method

1. Read each repo-local skill end to end (SKILL.md plus its references and
   scripts).
2. For each checklist item below, record a finding: **pass**, or
   **finding + evidence (quote/path) + suggested improvement + strength**
   (strong / moderate / weak).
3. Deliver the report in chat or as a file the requester names. Do not edit
   the skills as part of the review.

## Checklist

1. **Trigger quality**: does the frontmatter `description` state both what
   the skill does and when to use it? Would the right request trigger it and
   the wrong one not?
2. **Progressive disclosure**: is SKILL.md the short router, with detail in
   `references/` and deterministic behavior in `scripts/`? Body should stay
   well under a few hundred lines.
3. **Single job**: one skill, one repeatable job. Two jobs in one skill is a
   split candidate.
4. **Deterministic scripts over prose**: anything mechanically checkable is
   a script, not instructions; scripts are zero-dependency and self-tested.
5. **Portability**: standard Markdown, relative paths, no tool-specific
   slash commands, no assumptions beyond a file-reading agent.
6. **Security posture**: no shell strings, no secrets in examples, manifest
   and markers treated as untrusted.
7. **Single-writer compatibility**: the skill never assumes registry
   statuses, locks, or parallel writers.
8. **Test-weakening surface**: if the skill can touch tests or checks, do
   its instructions make weakening them harder, not easier?
9. **Drift**: do bundled scripts/templates still match the repo's current
   reality? Does anything reference files that no longer exist?

## Improvement-suggestion format

Each suggestion: the finding, the evidence for it, the smallest concrete
change that fixes it, and what the fix costs. Prefer removal and reuse over
new machinery — a suggestion that adds ceremony must justify the ceremony.
