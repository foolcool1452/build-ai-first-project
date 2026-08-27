# Greenfield and Brownfield Workflows

## Contents

1. Greenfield workflow
2. Brownfield workflow
3. Change workflow
4. Recovery and handoff
5. Multi-agent collaboration
6. Continuous gardening

## Greenfield workflow

1. Capture goal, users, acceptance criteria, risks, operational environment, and non-goals before choosing framework details.
2. Select a stable, well-documented stack with deterministic local commands. Prefer inspectable abstractions and text or JSON interfaces.
3. Preview scaffolding with `scaffold_project.py <repo> --mode greenfield`; the fixed landing set covers routing, product intent, architecture, plans, and the collaboration surfaces, with everything else omitted until needed.
4. Choose a specification model explicitly. Default to `living` when product specifications will remain contracts.
5. Create the harness before substantive product code: guidance, manifest, product intent, current architecture skeleton, validation entrypoint, and a plan template when multi-session work requires it.
6. Implement one vertical golden path that exercises setup, test, logging, error handling, and user-visible validation.
7. Register real commands in the manifest. Delete placeholder commands rather than pretending they work.
8. Add the first architecture boundary as an executable check.
9. Run validation and a fresh-agent onboarding test.

Greenfield exit criteria: a fresh agent can locate the right files, run the project, make a small change, verify it, and explain remaining uncertainty without hidden human knowledge.

## Brownfield workflow

### Phase 0: protect the baseline

- Start from a clean or deliberately understood working tree.
- Record existing tests and their current pass/fail state.
- Do not mix application reorganization with harness installation.
- Preserve all existing guidance and configuration until conflicts are reviewed.

### Phase 1: read-only census

- Run `audit_project.py <repo-or-component>`. It audits the exact path by default; add `--scope repository` for an intentional whole-repository census.
- Inspect manifests, entry points, CI, deploy files, tests, schemas, docs, and recent representative changes.
- Identify which commands are authoritative from CI rather than guessing from README prose.
- Mark architecture claims `observed`, `verified`, `proposed`, or `unknown`.

### Phase 2: minimal entry surface

- Add or trim root `AGENTS.md` to a map and hard rules.
- Add `CLAUDE.md` as `@AGENTS.md` plus only Claude-specific behavior.
- Create the manifest with existing commands and canonical paths.
- Link existing useful docs instead of duplicating them.
- Keep repo-local skills canonical under `.agents/skills/` and follow the sync procedure in `adapters.md`.

### Phase 3: current-state map

- Write `ARCHITECTURE.md` from code evidence.
- Record entry points, data flow, dependency direction, external systems, and known inconsistencies.
- Keep desired reorganizations in a proposal or active plan, never in the current-state map.

### Phase 4: incremental enforcement

- Start with one high-value invariant already respected by most code.
- Add a check in warning mode if legacy violations exist.
- Track violations as bounded debt with locations and owners.
- Move to blocking only after the baseline is clean or exemptions are explicit.

### Phase 5: representative evaluation

- Ask a fresh agent to explain one subsystem using only repository artifacts.
- Give it a small bug or feature with an objective test.
- Interrupt after partial progress and resume from the execution plan.
- Compare file discovery, tool calls, correctness, cost, and instruction violations against the pre-harness baseline when possible.

Brownfield exit criteria: the harness improves routing and verification without requiring a broad code rewrite or introducing unverified architectural fiction.

## Change workflow

1. **Specify**: state user-visible behavior, scenarios, constraints, and non-goals.
2. **Plan**: identify impacted boundaries, decisions, migration, observability, and validation.
3. **Task**: create small ordered units with explicit evidence of completion.
4. **Implement**: change the smallest coherent surface; keep the plan current.
5. **Verify**: run targeted checks first, then required repository checks; capture structured evidence.
6. **Review**: inspect the diff for unintended scope, missing tests, stale docs, and leaked private data.
7. **Reconcile**: update specifications when intent changed, architecture when current structure changed, ADRs when rationale is durable, and generated docs via generators.
8. **Adapt**: follow `adapters.md` after any canonical `.agents/skills/` change.
9. **Archive**: close or retain the plan according to the recorded persistence model.

Use flow-forward for strong audit history, living specs for stable product contracts, and flow-back only when the team commits to explicit reconciliation after implementation discoveries.

## Recovery and handoff

On pause or context loss, update the active plan with:

- last verified repository state;
- completed and incomplete tasks;
- exact modified files;
- commands run and outcomes;
- current hypothesis or decision;
- next safe action;
- blockers requiring judgment.

Do not create a separate `HANDOFF.md` when the active plan already owns this state. Do not commit raw session logs or credentials.

## Multi-agent collaboration

Usually one agent works at a time; the registry and task boards make identity, presence, and division of labor visible so any session can orient without hidden knowledge.

**Session lifecycle**

1. On the first session in a project, register in `docs/agents/REGISTRY.md` (one `## <agent-id>` section) and create `docs/tasks/<agent-id>.md`.
2. At session start, set your `Status: active` and refresh `Last active`.
3. While working, keep lightweight todos on your board; reference cross-session plans rather than duplicating them.
4. At session end or context handoff, set `Status: idle`, update `Last active`, and leave the board consistent with the active plan's state.
5. When a phase ends, groom boards: archive finished items to `docs/tasks/archive/<YYYY-MM-DD>-<agent-id>.md` (default) or delete them if the team prefers no history.

**Ownership rules (advisory)**

- Task-board ownership is a display convention. Any registered agent may work any item; note the takeover on your own board so history stays legible.
- Never edit another agent's registry section except to retire it after explicit handover; update only your own entry.
- Retired agents keep their sections and archives as history; their boards may be deleted at grooming time.

**Division of responsibility**: plans answer "what is being changed and why", the registry answers "who is here and in what state", boards answer "what small items are queued". If a board item grows plan-worthy, promote it instead of fattening the board.

When omitting both branches from a project, remove the declarations from `.ai/harness.json`, delete `docs/agents/` and `docs/tasks/`, and drop the routing rows that referenced them.

## Continuous gardening

Run periodically or after repeated agent failures:

- check guidance budgets, broken links, stale verification dates, and conflicting scoped rules;
- regenerate derived documentation;
- scan for repeated local helpers, boundary violations, untyped external data, and opaque errors;
- update evidenced quality gaps and technical-debt entries;
- remove rules now enforced mechanically;
- forward-test the harness on representative tasks before expanding always-loaded guidance.
