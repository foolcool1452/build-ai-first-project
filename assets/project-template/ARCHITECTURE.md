# Architecture

Status: {{ARCH_STATUS}}
Last verified: {{DATE}}
Sources: repository manifests and code entry points; replace this line with exact paths and commands

## System purpose

Describe the system boundary and primary users in two or three sentences. Do not copy the product roadmap here.

## Entry points

- TODO: list runtime, CLI, API, worker, UI, or library entry points with source paths.

## Components and dependency direction

- TODO: describe current components and allowed dependency direction from code evidence.
- Per component, record one stable identifier, path, responsibility, and public interface.
- Record only dependency rules supported by current code or accepted decisions.
- Unknowns must remain explicit.

## Data and external systems

- TODO: list stores, queues, APIs, trust boundaries, and schemas with evidence.

## Runtime and observability

- TODO: link startup, logs, metrics, traces, UI inspection, and failure-reproduction routes.

## Change impact routes

- TODO: map common change types to code, tests, schemas, generated docs, and operational checks.

## Enforced invariants

- Harness validation: `python tools/ai/validate_harness.py .`
- TODO: register project-native architecture checks in `.ai/harness.json`.

## Proposed changes

Keep proposed architecture in `docs/plans/active/` or a change proposal. Link accepted decisions here only after implementation.

