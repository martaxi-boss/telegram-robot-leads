# Roadmap

Status: **PROPOSED**  
Started: **2026-09-07**

This roadmap separates research, architecture decisions, implementation, and production migration. The final architecture must emerge from evidence gathered during Phases 0-7.

## Phase 0 — Baseline & Preservation

**Goal:** preserve and understand the existing system before modifying it.

Deliverables:

- repository structure inventory;
- current `main` commit recorded;
- runtime/deployment inventory;
- configuration inventory without committing secrets;
- current data-store/schema inventory;
- current operational metrics and failure modes where available;
- recovery copy/backup plan before history rewriting or destructive migration;
- baseline audit.

Exit gate:

- current behaviour and important risks are documented;
- destructive remediation has a rollback/recovery plan.

## Phase 1 — Product & Requirements Discovery

**Goal:** define the product we actually intend to build.

Questions include:

- Is this a single-project automation or a reusable Alaska Digital platform?
- Who operates it and with what roles?
- How many projects, Telegram accounts, target communities, and source communities must it support?
- What actions are legitimately required?
- What are acceptable daily/weekly volumes?
- What metrics define success?
- What is the required availability and recovery objective?
- Which functions require human approval?
- Which capabilities are explicitly out of scope?

Deliverables:

- product requirements;
- non-functional requirements;
- scope/non-scope;
- measurable success criteria;
- risk tolerance.

Exit gate:

- requirements are explicit enough to evaluate architecture alternatives.

## Phase 2 — Telegram Platform, Policy & Compliance Research

**Goal:** establish the sustainable operating model before optimizing automation.

Research areas:

- Telegram API and MTProto rules;
- Bot API capabilities and limitations;
- user-account automation constraints;
- account authorization and session lifecycle;
- anti-spam/flood controls;
- invite links and join requests;
- group/channel administration models;
- Telegram API Terms of Service;
- privacy and security obligations;
- GDPR/data-protection implications for collected identifiers and profiles.

Deliverables:

- Telegram platform research report;
- policy/compliance risk register;
- allowed/conditional/prohibited operation matrix;
- open legal/compliance questions for qualified review where needed.

Exit gate:

- architecture candidates do not depend on an operating model contradicted by platform policy or unresolved high-risk compliance assumptions.

## Phase 3 — Telegram Technical Integration Research

**Goal:** choose the correct integration boundary.

Compare:

- Telethon;
- alternative MTProto client libraries if relevant;
- Bot API for eligible workflows;
- user accounts vs bots by responsibility;
- single-account vs multi-account worker models;
- session storage and revocation;
- disconnect/reconnect semantics;
- FloodWait/PeerFlood handling;
- target group permission failures;
- API credential ownership.

Deliverables:

- Telegram integration comparison;
- PoC test plan;
- proposed ADR(s), not yet necessarily accepted.

## Phase 4 — Data, State & Privacy Architecture Research

**Goal:** determine the minimum reliable data model and state machine.

Compare:

- SQLite;
- PostgreSQL;
- queue-in-database patterns;
- separate queue systems only if evidence requires them;
- event/audit log designs;
- idempotency and exactly-once/at-least-once consequences;
- retention and deletion;
- provenance/source tracking;
- suppression/opt-out controls;
- encryption and access controls;
- backup/restore.

Deliverables:

- candidate data models;
- state-machine proposal;
- consistency/failure analysis;
- data-retention proposal;
- datastore ADR candidate.

## Phase 5 — Runtime, Infrastructure & Operations Research

**Goal:** select the simplest infrastructure that meets verified requirements.

Compare at minimum:

- VPS + systemd;
- VPS + Docker Compose;
- containerized application + managed PostgreSQL;
- managed application platform where appropriate.

Do not introduce Redis, Kubernetes, or other infrastructure unless a measured requirement justifies it.

Deliverables:

- infrastructure comparison;
- secrets/session-storage options;
- backup/restore design;
- staging/production separation;
- deployment/release model;
- cost estimates.

## Phase 6 — Architecture Alternatives & Decision Matrix

**Goal:** compare complete end-to-end designs rather than isolated technologies.

Each architecture must be scored against weighted criteria, initially:

| Criterion | Initial weight |
|---|---:|
| Reliability | 20% |
| Telegram sustainability | 20% |
| Security/privacy | 15% |
| Maintainability | 15% |
| Operational simplicity | 10% |
| Scalability | 8% |
| Recovery | 5% |
| Development velocity | 4% |
| Infrastructure cost | 3% |

Weights may change only if the requirements record explains why.

Deliverables:

- 2-4 complete architecture alternatives;
- comparison matrix;
- rejected-alternative reasoning;
- critical assumptions requiring PoCs.

## Phase 7 — Proofs of Concept

**Goal:** test assumptions that materially affect architecture.

Potential PoCs:

- Telegram session manager lifecycle;
- crash between remote API action and local persistence;
- idempotent action handling;
- atomic queue claim under multiple workers;
- database outage/fail-closed policy;
- multi-account isolation;
- session revocation recovery;
- PostgreSQL vs SQLite concurrency under realistic load;
- observability and health semantics;
- backup restoration.

Each PoC must record hypothesis, setup, measurement, result, and architectural consequence.

Exit gate:

- critical architecture assumptions have evidence, not intuition.

## Phase 8 — Final Architecture Decision

**Goal:** approve Architecture v1.0.

Deliverables:

- accepted ADRs;
- final component boundaries;
- data model;
- state machine;
- deployment architecture;
- security model;
- observability model;
- migration strategy;
- rollback strategy;
- implementation sequencing.

Exit gate:

- `Architecture v1.0` ADR status is `ACCEPTED`.

## Phase 9 — Engineering Foundation

Build the platform foundation before migrating business logic:

- project/package structure;
- typed configuration;
- dependency locking;
- test framework;
- lint/format/type-checking;
- CI;
- database migrations;
- structured logging;
- secrets handling;
- staging environment;
- health checks;
- backup validation.

## Phase 10 — Domain Migration

Migrate verified behaviours from the legacy system into explicit components:

- account/session management;
- discovery/ingestion where approved;
- candidate eligibility/policy;
- queue/state transitions;
- Telegram action adapter;
- quotas/rate policies;
- metrics/audit events.

Legacy behaviour is not automatically a requirement. Each migrated behaviour must trace to a requirement or accepted ADR.

## Phase 11 — Hardening & Validation

Required validation:

- unit/integration tests;
- fault injection;
- crash recovery;
- dependency/security scanning;
- backup/restore drill;
- long-running soak tests;
- multi-worker tests;
- account/session recovery;
- operational runbooks;
- production-readiness review.

## Phase 12 — Controlled Production Migration

Migration pattern:

1. shadow/read-only validation where possible;
2. staging validation;
3. limited/canary operation;
4. monitored production cutover;
5. defined rollback window;
6. legacy retirement only after evidence of stability.

## Phase 13 — Optimization

Only after stable production evidence:

- throughput optimization;
- cost optimization;
- operator UX;
- analytics;
- automation of safe operational tasks;
- architecture simplification where measurements allow it.

## Roadmap rule

Optimization must not precede correctness, safety, recovery, and observability. The project will not optimize mechanisms designed to evade platform controls; the operating model itself must first be sustainable and compliant.
