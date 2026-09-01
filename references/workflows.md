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

A work round is the standard loop for non-trivial changes: **Open** (state the goal and how it will be proven) → **Execute** → **Verify** → **Review** (one zero-context review subagent) → **Close** (reconcile docs). Repeat execute/review until the review comes back clean. Single-file cosmetic edits skip rounds and go straight through the Change workflow.

**Round sizing**: one round ≈ one focused session — an increment a human could review in under two hours. Larger work splits into multiple rounds under the same plan; if a round keeps growing, the goal or the partition was wrong.

**Recon (optional, before Open)**: for unfamiliar areas, spawn read-only research subagents (0-2; more needs a written reason in the entry) to map files, interfaces, and prior art. Their findings are compressed into the entry's Research line — conclusions, not dumps. Research subagents never write; spending on precise research is the cheapest token you will spend.

```text
session start
      │
round? ──no──► Change workflow (small edits, no round entry)
      │yes
Recon? ──yes── read-only research subagents; findings → entry
      │
Open ──── entry: goal + how this round is proven
      │
Execute ─ make the change (writing subagents allowed; partition if parallel)
      │
Verify ── run the proof; it must pass before closing
      │
Review ── one zero-context review subagent:
      │    goal + combined diff + evidence; re-runs the proof
      │
findings? ──yes──► disposition (fix, or reject with a reason) ──┐
      │no / all dispositioned                                   │
      ◄─────────────────────────────────────────────────────────┘
Close ──── reconcile docs; mark the entry closed
      │
more work? ──yes──► next round (back to Open)
      │no
session end ── compact state into the plan; archive or suspend it
```

**Rules**

- **Subagents share the session's identity**: they may research, review, and write; what they change belongs to the session. Parallel writing subagents must have a file/region partition, recorded in the Execute line.
- **One review subagent per round** by default; anything more needs a written justification in the entry.
- **The reviewer sees only** the goal, the combined diff, the evidence, and the verification — never the working conversation — and re-runs the proof itself. Zero findings is unusual: re-check whether the verification is strong enough before celebrating.
- **Every finding is accepted or rejected with a one-line reason.** Accepted means fixed and re-verified, or turned into an explicit ticket.
- **A session that must end mid-round suspends it**: entry marked `suspended <date> — <state>`, and the plan's Next action carries the single next safe step. The next writer session resumes the same round; a suspension older than about a week is stale and goes back to Plan.
- **Closing the last round does not archive a plan**: reconcile docs, set `Status: completed`, move the plan to `docs/plans/completed/`, and re-validate.

**When not to spawn**: the task is answerable with a few direct reads; the change is single-file; a subagent would only re-read what the session already knows; or nothing about the outcome is independently verifiable. Marginal gains from extra agents are often smaller than their coordination and token cost.

**Division of labor across surfaces**: plans answer "what is being changed and why"; the registry answers "who has worked here"; rounds answer "how this piece of work was verified and reviewed".

## Recovery and handoff

On pause or context loss, update the active plan with:

- last verified repository state;
- completed and incomplete tasks;
- exact modified files;
- commands run and outcomes;
- current hypothesis or decision;
- next safe action;
- blockers requiring judgment.

Do not create a separate `HANDOFF.md` when the active plan already owns this state. Do not commit raw session logs or credentials. Treat every session end as a **compaction point** — the pattern behind 24h+ agent sessions: compress everything that matters into the plan's Next action and the round entries, so a fresh session rebuilds from artifacts instead of history.

## Multi-agent collaboration

Coordination in this harness is deliberately minimal. The full profile provides a one-time registry: the first session that works in the repository appends its `## <agent-id>` section to `docs/agents/REGISTRY.md` — nothing else is maintained. There are no statuses to flip and no boards to groom; when a session ends, its state is compacted into the active plan (the Next action and round entries), and the next session rebuilds from those artifacts.

- One writer session at a time remains the working norm; if two sessions ever overlap, coordinate directly — the registry records participation, not locks.
- Subagents of a session and read-only reviewers work under that session's identity; they are not registered.
- The registry answers "who has worked here"; plans answer "what is being changed and why"; rounds answer "how a piece of work was verified and reviewed".

When omitting the branch from a project, remove the `knowledge.agents` declaration from `.ai/harness.json` and delete `docs/agents/`.

## Continuous gardening

Run periodically or after repeated agent failures:

- check guidance budgets, broken links, stale verification dates, and conflicting scoped rules;
- regenerate derived documentation;
- scan for repeated local helpers, boundary violations, untyped external data, and opaque errors;
- update evidenced quality gaps and technical-debt entries;
- remove rules now enforced mechanically;
- forward-test the harness on representative tasks before expanding always-loaded guidance.
