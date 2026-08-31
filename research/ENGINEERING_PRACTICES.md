# Engineering practices applied to v3

Status: verified
Last verified: 2026-08-29
Sources: official Codex, Agent Skills, Claude Code, and Kimi Code documentation linked below

## Applied practices

| Source practice | Project adaptation |
|---|---|
| Codex layers `AGENTS.md` from project root toward the working directory and caps combined project guidance. | Keep root guidance as a short map; use scoped files only for genuinely local rules and validate a tighter project budget. |
| Codex discovers a skill from its name and description before loading the body; descriptions may be shortened under context pressure. | Front-load the action and triggers in a concise skill description; keep detailed methods in `references/`. |
| Agent Skills recommends progressive disclosure: metadata, activated instructions, then resources on demand; the main file should remain under 500 lines. | Keep `SKILL.md` as the operation router and load architecture, workflows, adapters, or validation rules only when relevant. |
| Codex recommends one job per skill, imperative steps, explicit inputs/outputs, and deterministic scripts only when needed. | Keep one repository-harness mission; use Python only for audit, scaffold, sync, and validation behavior that prose cannot guarantee. |
| Claude treats always-loaded guidance as context, recommends concise concrete rules, and moves procedures to skills or path-scoped rules. | Keep `CLAUDE.md` as a five-line import adapter; do not duplicate canonical guidance. |
| Claude distinguishes behavioral guidance from permissions and hooks that enforce hard limits. | Keep safety claims in validation and filesystem guards rather than promising security through prose. |
| Kimi resolves project skills from the nearest Git root and supports `.agents/skills/`; project configuration is untrusted input. | Keep portable skills at the Git root, reject non-portable nested sources, and retain strict parsing and path-containment checks. |

## Deliberate non-adoptions

- Do not mirror every vendor-specific feature. The portable core remains normal Markdown, relative paths, argument arrays, and project-native scripts.
- Do not increase the root guidance budget to match vendor maximums. A maximum is a safety ceiling, not a content target.
- Do not turn auto profile selection into opaque model judgment. The repository census stays deterministic and explainable; known intent remains an explicit override.
- Do not add hooks or permissions files without a project-specific enforcement need. Empty security ceremony is still ceremony.

## Primary references

- [Codex AGENTS.md discovery](https://developers.openai.com/codex/guides/agents-md/)
- [Codex skill authoring](https://developers.openai.com/codex/skills/)
- [Agent Skills specification](https://agentskills.io/specification)
- [Claude Code project memory](https://code.claude.com/docs/en/memory)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Kimi Code Agent Skills](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html)
- [Kimi Code agents and trust model](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/agents)
