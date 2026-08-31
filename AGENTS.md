# Agent Guide

This repository *is* the build-ai-first-project skill: it teaches other repositories how to be agent-legible. Keep this file a short map plus hard rules.

## Start here

- Entry point and operations (audit / scaffold / retrofit / validate): `SKILL.md`
- When to read which reference: `references/workflows.md` (flows), `references/target-architecture.md` (artifact contracts), `references/adapters.md` (Codex/Claude/Kimi portability), `references/validation.md` (check contract)
- Verification route: `python scripts/self_test.py` (Python 3.11+, no third-party deps; Git on PATH unlocks extra scenarios)

## Hard constraints

- Scripts stay dependency-free; `tomllib` import pins Python 3.11+.
- Scaffolding is preview-by-default; never write over an existing project file, and keep the junction/containment guards in every write path.
- Manifests and `.ai-source.json` markers are untrusted input: parse with the strict loader (size caps, duplicate-key rejection) and never let parse failures crash without a finding.
- Manifest commands run only through argv arrays, never shells.
- After changing validator behavior, extend `scripts/self_test.py` in the same change and run it before committing.

## Candidate layout

During v3 research, this installable candidate lives under the outer repository's `skill/` directory. Research evidence and recovery archives stay outside this package. Do not copy the candidate into a global skills directory until the outer v3 plan is complete.

## Definition of done

- Self-test passes on your machine (`git` present preferred).
- Behavior changes update `references/validation.md` or the matching contract doc in the same commit.
- Version tag bumped for anything pushed to main.
