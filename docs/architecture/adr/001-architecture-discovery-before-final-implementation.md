# ADR-001 — Architecture Discovery Before Final Implementation

Status: **ACCEPTED**  
Date: 2026-09-07  
Decision owners: Alaska Digital

## Context

The current repository contains a working but highly coupled Telegram automation implementation. A direct refactor or rewrite would risk preserving accidental legacy behaviour, selecting infrastructure without measured requirements, and losing the reasoning behind future technical decisions.

The project owner explicitly requires a research-first roadmap and a durable record of what was investigated, decided, rejected, and implemented.

## Decision drivers

- Preserve institutional memory.
- Avoid premature architecture choices.
- Separate requirements from legacy implementation details.
- Compare alternatives before introducing new infrastructure.
- Ensure security/privacy/platform constraints influence design early.
- Enable future maintainers to understand why the system exists in its final form.
- Preserve recovery paths before risky changes.

## Alternatives considered

### Option A — Refactor the existing `main.py` immediately

Pros:

- fastest path to visible code cleanup;
- low initial planning overhead.

Cons:

- risks turning accidental legacy behaviour into permanent architecture;
- no validated product boundary;
- platform/compliance assumptions remain unresolved;
- hard to justify datastore/runtime choices;
- loses a clean decision history.

Decision: **REJECTED**.

### Option B — Rewrite immediately using a conventional modern stack

Example assumption: Python services + PostgreSQL + Redis + Docker.

Pros:

- clean codebase quickly;
- familiar architecture patterns.

Cons:

- technology selection precedes requirements;
- may be unnecessary operational complexity;
- could optimize a Telegram operating model that should itself change;
- migration/recovery risks are not yet known.

Decision: **REJECTED**.

### Option C — Evidence-driven Architecture Discovery Program

Pros:

- product, platform, data, reliability, security and infrastructure requirements are investigated first;
- critical assumptions can be tested with PoCs;
- final architecture can be compared quantitatively;
- rejected alternatives remain documented;
- implementation can trace to accepted decisions.

Cons:

- delays large implementation changes;
- requires disciplined documentation and research.

Decision: **SELECTED**.

## Decision

The project will execute Phases 0-8 of `docs/architecture/ROADMAP.md` before approving Architecture v1.0 and beginning the final implementation/migration phases.

Incremental safety fixes may still be performed before Phase 8 when necessary to protect data, credentials, accounts, or recovery. Such changes must be documented and must not silently establish a final architecture.

GitHub will be the authoritative record for research, issues, ADRs, work logs, experiments, PRs, and implementation decisions.

## Consequences

### Positive

- final architecture is evidence-based;
- easier onboarding and maintenance;
- clearer rollback/migration reasoning;
- security and compliance risks become first-class design constraints;
- architecture can remain intentionally simple when requirements allow it.

### Negative / trade-offs

- more documentation before implementation;
- some current code debt remains temporarily;
- research questions may reveal that current business workflows need redesign.

## Validation

This ADR is being validated by:

- the `architecture-discovery` branch;
- phased roadmap;
- requirements register;
- baseline audit;
- research documents;
- research tracking issues;
- future architecture decision matrix and PoCs.

## Rollback / supersession

This decision may be superseded by a future ADR if the project scope changes materially. Any superseding ADR must preserve the existing research/decision history rather than deleting it.
