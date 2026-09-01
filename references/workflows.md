# Greenfield and Brownfield Workflows

## Contents

1. Greenfield workflow
2. Brownfield workflow
3. Change workflow
4. Work rounds
5. Recovery and handoff
6. Multi-agent collaboration
7. Continuous gardening

## Greenfield workflow

1. Capture goal, users, acceptance criteria, risks, operational environment, and non-goals before choosing framework details.
2. Select a stable, well-documented stack with deterministic local commands. Prefer inspectable abstractions and text or JSON interfaces.
3. Preview scaffolding with `scaffold_project.py <repo> --mode greenfield --profile auto`. Review the evidence: keep `lite` for small single-agent work, or select `full` when known scope requires resumable plans or coordination.
4. Choose a specification model explicitly. Default to `living` when product specifications will remain contracts.
5. Create the harness before substantive product code: guidance, manifest, product intent, current architecture skeleton, and validation entrypoint. The full profile also creates plans and collaboration surfaces.
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
- Choose the profile from both census evidence and known intent. Existing plans, multiple agents, a monorepo, regulated evidence, or a broad migration favor `full`; a bounded single-purpose repository favors `lite`.
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

## Work rounds

A work round is the standard unit for non-trivial changes: **Open** (commit the round's goal, its verification command, and the red baseline) → **Execute** → **Verify** → **Review** (review subagent re-runs verification) → repeat until convergence → **Close** (reconcile docs). Rounds are required when a change alters behavior, touches the manifest or canonical docs, spans multiple files, or crosses a boundary; single-file cosmetic changes go straight through the Change workflow with a one-line note in an existing plan.

**Round lifecycle**

1. **Open**: mark the registry `active`; append the round entry: goal, the **Verify command** (anchored on the harness's registered checks plus round-specific assertions), the subagent budget, and the writer partition if writing subagents will run in parallel. Then run Verify once and record the **baseline** — a round is valid only if the baseline fails, or fails to exercise the round's change. A baseline that already passes makes the commitment vacuous: narrow the command or extend it with the missing check before executing anything. Record evidence as one line: `baseline: exit <code> — <summary>`.
2. **Execute**: make the change in-session or through writing subagents inside the partition. Failed approaches stay in the entry — kept failures are evidence, not embarrassment.
3. **Verify**: run the Verify command unpiped (pipes can mask exit codes) and append `verified: exit <code> — <summary> — <command>`. The expected trajectory is baseline-red → verified-green.
4. **Review**: a review subagent with zero shared context receives the goal, the combined diff (including subagent-written changes), the evidence, and the Verify command, and **re-runs the verification itself**. Its output must include a coverage declaration (what it re-ran and read) and append its own line: `reviewer: exit <code> — <summary>`. Findings are accepted or rejected with one-line reasons; an accepted finding lands as a fix plus a re-Verify, or becomes an explicit ticket. A review with zero findings is an anomaly signal, not a pass — re-check the Verify's strength first.
5. Repeat Execute/Verify/Review until a review returns no new findings. Two consecutive reviews returning only rejected-with-reason findings means the loop is oscillating: stop and re-plan.
6. **Close**: reconcile specs, architecture, and the routing index (or declare "no reconciliation needed") and mark the entry closed.

**Subagent rules**

1. **Shared identity, owned output**: subagents may research, review, and write. Everything a subagent changes carries the session's identity — the session owns the result, and subagent-written changes receive the same review as the session's own.
2. **Partition parallel writers**: record the partition in the entry as `partition: <writer-id> = <path or glob>[; ...]`. Partitions must not overlap and must cover every file the round may touch; the review checks the changed-file list against the partition.
3. **Budget on the table**: one review subagent per round by default; research subagents are on demand, justified in the entry — research need concentrates in the first round, and precision spent writing the round entry is the cheapest token you will spend. Anything beyond the default requires written justification: extra subagents are bought token-per-performance and must pay for themselves.
4. **Zero-shared-context review**: the review subagent receives the goal, the combined diff (including subagent-written changes), the evidence, and the Verify command — never the working conversation. Reviewers without shared context catch more and praise less.
5. **Disposition discipline**: every review finding is accepted or rejected with a one-line reason in the round entry; an accepted finding must land as a fix plus a re-Verify, or become an explicit ticket. Silent drops and "accepted but not done" are how defects ship.

**When not to spawn**: the task is answerable with a few direct reads; the change is single-file; a subagent would only re-read what the session already knows; or nothing about the outcome is independently verifiable. Marginal gains from extra agents are often smaller than their coordination and token cost.

**Session boundary**: rounds loop inside one session by default. After two or three closed rounds, prefer a clean break at a round boundary — set the registry to `idle`, let the plan's Next action carry the handoff, and let the next session re-open from the plan: a fresh context with structured handoff outperforms a degrading one. If a session must end mid-round, the round is **suspended**, not closed: set the registry to `idle`, write `Close: suspended <date> — <state reached>`, put the single next safe action in the plan's Next action, and stop. The next session sets `active` and appends `Resumed <date>:` sub-lines to the same entry without rewriting the suspension record. A suspension older than roughly a week — or one whose red baseline has drifted for unrelated reasons — is void: re-open as a new round from Plan.

**Archive**: closing the last round does not archive a plan. To archive: reconcile docs, set `Status: completed`, move the file from `docs/plans/active/` to `docs/plans/completed/` in the same edit, and re-run validation — a completed plan left in `active/` fails validation by design. Suspended round entries that get archived are historical records.

**Division of labor across surfaces**: plans answer "what is being changed and why"; the registry answers "who is here, in what state, and which session is the writer"; boards answer "what small items are queued"; rounds answer "how this piece of work was verified and reviewed".

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

The full profile provides a registry and task boards so identity, presence, and division of labor remain visible without hidden knowledge. Lite projects add and declare these branches only when collaboration becomes real.

**Session lifecycle**

1. On the first session in a project, register in `docs/agents/REGISTRY.md` (one `## <agent-id>` section) and create `docs/tasks/<agent-id>.md`.
2. At session start, set your `Status: active` and refresh `Last active`. This project allows a single writer session: while your entry is `active`, no other session may claim the role.
3. While working, keep lightweight todos on your board; reference cross-session plans rather than duplicating them. Subagents spawned by your session and read-only review agents work under your identity — they are not registered and never set `active`.
4. At session end or context handoff, set `Status: idle`, update `Last active`, and leave the board consistent with the active plan's state. The next session then claims `active`.
5. When a phase ends, groom boards: archive finished items to `docs/tasks/archive/<YYYY-MM-DD>-<agent-id>.md` (default) or delete them if the team prefers no history.

**Ownership rules (advisory)**

- The single-writer invariant is enforced by validation (`AGENT_MULTIPLE_ACTIVE`); everything else about ownership stays a display convention.
- Task-board ownership is a display convention. With one writer session at a time, takeovers happen between sessions; note the handover so history stays legible.
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
