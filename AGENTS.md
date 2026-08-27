# Agent Guide

This repository *is* the build-ai-first-project skill: it teaches other repositories how to be agent-legible. Keep this file a short map plus hard rules.

## Start here

- Entry point and operations (audit / scaffold / retrofit / validate): `SKILL.md`
- When to read which reference: `references/workflows.md` (flows), `references/target-architecture.md` (artifact contracts), `references/adapters.md` (Codex/Claude/Kimi portability), `references/validation.md` (check contract)
- Verification route: `python scripts/self_test.py` (Python 3.11+, no third-party deps; Git on PATH unlocks extra scenarios)

## Hard constraints

- Scripts stay dependency-free; `tomllib` import pins Python 3.11+.
- Scaffolding is preview-by-default; never write over an existing project file, and keep the junction/containment guards in every write path.
- Manifests, schemas, and `.ai-source.json` markers are untrusted input: parse with the strict loader (size caps, duplicate-key rejection) and never let parse failures crash without a finding.
- Manifest commands run only through argv arrays, never shells.
- After changing validator behavior, extend `scripts/self_test.py` in the same change and run it before committing.

## Why there is no .ai/harness.json here yet

This repo ships reference material that downstream projects copy verbatim; the current validator's canonical metadata check would force `Status:/Last verified:` headers onto those copied files. A minimal/lightweight harness profile is the planned prerequisite before this repo can honestly eat its own dog food (see the architecture proposal). Until then the omission is deliberate, not drift.

## Definition of done

- Self-test passes on your machine (`git` present preferred).
- Behavior changes update `references/validation.md` or the matching contract doc in the same commit.
- Version tag bumped for anything pushed to main.
