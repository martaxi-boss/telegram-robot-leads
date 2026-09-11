# Roadmap v0.9 — Audit-Derived Program

Status: **DRAFT — NOT YET FINAL / NOT AN IMPLEMENTATION SCHEDULE**
Updated: 2026-09-11
Derived from: `../research/roadmap-deep-audit-2026-09-11.md`, `../research/roadmap-research-questions.md`, `../evidence/EV-001-roadmap-audit-source-register.md`

## Purpose

Define the shortest evidence-driven path from the current legacy Telegram runtime to an approved Architecture Baseline and then to a verified production system, without inventing dates before product scope, scale, reliability and architecture are known.

## Roadmap model

Every phase has:

`Inputs -> Work -> Deliverables -> Exit Gate`

A phase is complete only when its gate is evidenced. Workstreams may overlap where dependencies allow, but a downstream decision may not use an unresolved upstream assumption as fact.

---

## Stage 0 — Evidence Reconciliation & Recovery Baseline

### Goal

Make sure the project can safely reason from one current knowledge system and can recover before risky remediation.

### Inputs

- current `main` Governance v1;
- legacy code at current `main`;
- `architecture-discovery` branch / PR #11;
- issues #1–#10;
- historical `users.db` finding.

### Work

- map useful old discovery documents into Governance v1 categories;
- preserve source commit/branch references;
- resolve duplicated ADR numbering/semantics without rewriting history;
- produce sanitized live-runtime inventory plan;
- define repository backup/recovery procedure before Git-history rewrite;
- record current branch/CI/security controls.

### Deliverables

- reconciled research index;
- legacy evidence catalogue;
- recovery plan for history remediation;
- current runtime inventory checklist;
- updated risk register.

### Exit Gate G0

- no material prior research is orphaned;
- recovery path exists before destructive repository/history operations;
- current source of truth is unambiguous.

---

## Stage 1 — Product Boundary & Success Definition

### Goal

Decide what product is actually being built before selecting architecture.

### Resolve

- RQ-001 product boundary;
- RQ-002 business outcome/KPIs;
- RQ-003 accepted/prohibited action classes;
- RQ-004 legacy behavior classification;
- RQ-018 operator roles;
- RQ-024 cost/resource envelope.

### Required decisions

Explicitly choose whether this repository is:

A. one Telegram acquisition/community subsystem;
B. a reusable internal Telegram operations platform;
C. a multi-project/client platform;
D. a wider IPTV/VPN commerce/customer/provisioning platform.

### Deliverables

- vision/scope/non-scope;
- actors and roles;
- customer/operator journeys;
- 1–3 primary KPIs plus guardrails;
- legacy behavior matrix: PRESERVE / REDESIGN / REMOVE / RESEARCH / LEGACY-DEAD;
- explicit list of capabilities not in v1.

### Exit Gate G1 — Product Definition Gate

Architecture work may proceed only when:

- system boundary is explicit;
- success can be measured;
- prohibited/approval-required actions are explicit;
- legacy code is no longer acting as the requirements specification.

---

## Stage 2 — Quantified Quality, Scale & Recovery Requirements

### Goal

Turn vague “production-ready” expectations into measurable architecture inputs.

### Resolve

- RQ-005 scale/capacity;
- RQ-006 SLO/RTO/RPO/failure tolerance;
- data retention volumes;
- expected projects/accounts/communities/workers;
- growth envelope;
- maintenance/operator constraints.

### Deliverables

- accepted functional requirements;
- quality scenarios;
- v1 capacity envelope;
- availability/SLO target;
- RTO/RPO;
- duplicate/lost-event tolerances;
- degraded-mode behavior;
- retention requirements.

### Exit Gate G2 — Measurable Requirements Gate

Competing architectures can be scored with numbers/explicit constraints rather than intuition.

---

## Stage 3 — Sustainable Telegram & Data-Use Operating Model

### Goal

Select a platform-sustainable interaction model before implementation optimizations.

### Resolve

- RQ-007 Bot API vs MTProto responsibility split;
- RQ-008 personal-data purpose/retention/provenance/suppression;
- RQ-012 session/API credential lifecycle;
- RQ-017 product-specific compliance constraints;
- relevant part of RQ-003.

### Work

Compare at least:

1. Bot-led opt-in invite/join-request workflow where product-compatible;
2. hybrid Bot API + narrowly scoped user-session adapter where justified;
3. any required user-only action model, explicitly risk-scored and policy-reviewed.

Do not treat legacy “human-like” timing or repeated attempts after anti-abuse signals as a target capability.

### Deliverables

- Telegram capability/responsibility matrix;
- allowed/conditional/prohibited action matrix;
- credential/session lifecycle;
- data inventory + purpose + provenance + retention/suppression model;
- qualified legal/compliance questions and answers where needed;
- proposed platform/data ADR constraints.

### Exit Gate G3 — Sustainable Operating Model Gate

No Architecture v1 candidate depends on an action model contradicted by platform rules, an unresolved critical privacy assumption, or sample/shared API credentials.

---

## Stage 4 — Conditional IPTV/VPN/Commerce Domain Discovery

### Goal

Prevent the project name or business context from silently expanding architecture scope.

### Trigger

Run this stage only to the depth required by the product boundary selected at G1.

### If broader platform is IN scope, resolve

- RQ-014 IPTV/VPN provider/provisioning contracts;
- RQ-015 payments/subscriptions/entitlements/refunds/reconciliation;
- RQ-016 customer/Telegram/service identity mapping;
- support/admin operations;
- provider credential/security boundaries;
- provider failure/retry/reconciliation semantics;
- licensing/commercial constraints relevant to the offered service.

### If broader platform is OUT of scope

Document IPTV/VPN/payment/customer systems as external actors/contracts and stop expanding this repository into them.

### Deliverables

Either:

- provider/API capability evidence, lifecycle state machines and external contracts;

or:

- explicit non-scope/external-system boundary.

### Exit Gate G4 — Domain Boundary Gate

No unidentified external provider/payment/customer lifecycle can later force a fundamental architecture rewrite.

---

## Stage 5 — Correctness, State Machine & Datastore

### Goal

Design safety/correctness around the real failure boundary: external side effect plus local durable state.

### Resolve

- RQ-009 state machine/reconciliation;
- RQ-010 datastore/queue;
- retention/audit implications from G2/G3/G4.

### Required design properties

- one authoritative state source;
- explicit action attempt ID/correlation ID;
- fail-closed authorization when required state is unavailable;
- states for planned/authorized/in-flight/succeeded/failed/outcome-unknown/reconciled where applicable;
- bounded retry policy;
- durable audit record;
- suppression/eligibility controls before side effects;
- concurrency semantics proven for expected worker count.

### Datastore candidates

At minimum compare:

- single-host SQLite with deliberate writer model;
- PostgreSQL authoritative database + DB-backed work queue;
- separate queue only if measured requirements justify it.

### Critical PoCs

- DB outage -> external action prohibited;
- crash/timeout around remote action -> no silent duplicate loop;
- stale claim recovery;
- multiple-worker claim correctness;
- backup/restore against RPO/RTO;
- SQLite durability/concurrency under expected load if it remains a candidate;
- PostgreSQL multi-consumer claim if multi-worker/multi-host is a candidate.

### Exit Gate G5 — Correctness Gate

State-machine/datastore candidate satisfies failure scenarios and measurable requirements with evidence.

---

## Stage 6 — Live Runtime, Security, Deployment & Operations

### Goal

Choose the simplest deployment topology that meets verified requirements and can be safely operated/recovered.

### Resolve

- RQ-011 live VPS inventory;
- RQ-012 secrets/session implementation;
- RQ-013 health/alerts/kill switch;
- RQ-019 runtime topology;
- RQ-020 backup/restore;
- RQ-023 build/release reproducibility.

### Compare

- dedicated VPS + systemd;
- dedicated VPS + Docker Compose;
- managed/container runtime + managed PostgreSQL if requirements justify it;
- other models only with evidence.

### Required common properties

- non-root service identity where feasible;
- explicit secrets/session filesystem/access boundary;
- staging vs production separation;
- reproducible release artifact/dependency set;
- migrations;
- layered health model;
- action kill switch;
- bounded restart behavior;
- backup + tested restore;
- release identification/rollback;
- resource/disk monitoring.

### Exit Gate G6 — Operability Gate

A selected runtime candidate can be deployed, observed, disabled, restored and rolled back according to G2 requirements.

---

## Stage 7 — Complete Architecture Alternatives

### Goal

Compare end-to-end systems, not isolated technology preferences.

### Produce

2–4 coherent alternatives that include:

- system/context boundary;
- Telegram operating model;
- domain/provider boundaries if applicable;
- state/data model;
- concurrency model;
- secrets/security model;
- deployment topology;
- health/operations model;
- migration path;
- cost/complexity.

### Initial scoring dimensions

Weights must be re-approved after G1/G2. Suggested starting point:

| Criterion | Starting weight |
|---|---:|
| Correctness / reliability | 20% |
| Platform sustainability / policy fit | 17% |
| Security / privacy | 15% |
| Maintainability / changeability | 13% |
| Operational simplicity / recovery | 12% |
| Product fit / extensibility | 10% |
| Scalability to verified v1 envelope | 6% |
| Delivery risk / migration complexity | 4% |
| Infrastructure cost | 3% |

### Exit Gate G7 — Alternative Selection Gate

- every architecture satisfies hard constraints;
- score differences are explained by evidence;
- unresolved assumptions are isolated;
- only decision-changing assumptions remain for PoCs.

---

## Stage 8 — Decision-Changing PoCs

### Goal

Test only uncertainties capable of changing the architecture selection.

### Rule

Each `EXP-xxx` must state hypothesis, environment, pass/fail criteria, rollback/cleanup, evidence and architectural consequence **before execution**.

Use local/WSL/mock environments by default. Use staging/real Telegram only when the hypothesis cannot be answered equivalently and the test is bounded, safe and authorized.

### Exit Gate G8 — Evidence Gate

Critical architecture assumptions are empirically supported or the candidate architecture is revised.

---

## Stage 9 — Architecture Baseline v1.0

### Goal

Approve the architecture that implementation will follow.

### Deliverables

- accepted architecture ADR(s);
- C4 Context + Container views;
- component views only for high-risk areas;
- authoritative state machine;
- data model;
- integration/provider contracts;
- security/trust boundaries;
- deployment view;
- observability/health model;
- backup/restore model;
- migration/rollback strategy;
- explicit known risks/deferred decisions.

### Exit Gate G9 — Architecture Baseline

`Architecture Baseline v1.0` is explicitly **ACCEPTED**. Only now may the team convert the roadmap into reliable implementation estimates/calendar commitments.

---

## Stage 10 — Engineering Foundation

### Goal

Create a testable/reproducible skeleton before moving legacy business behavior.

### Deliverables

- package/module boundaries;
- supported Python/runtime version;
- typed validated configuration;
- sanitized configuration examples;
- pinned/locked dependencies;
- test framework;
- lint/format/type/static/security checks as justified;
- CI required checks;
- database migration framework;
- structured logging/audit abstraction;
- secret/session abstraction;
- fake/mock external adapters;
- health endpoints/checks;
- release/version metadata;
- staging deployment path.

### Exit Gate G10

A minimal vertical slice can be built/tested/deployed without importing unsafe legacy coupling.

---

## Stage 11 — MVP Vertical Slices

### Goal

Implement accepted product outcomes in thin end-to-end slices with traceability.

### Sequence principle

Prioritize irreversible/risky foundations before feature breadth:

1. identity/config/project boundary;
2. authoritative state + audit;
3. policy/authorization + kill switch;
4. Telegram/provider adapters in safe/test mode;
5. accepted ingestion/opt-in flow;
6. reconciliation/failure handling;
7. operator/admin workflow;
8. KPI/health reporting;
9. conditional commerce/provisioning slices if in scope.

Each slice: `REQ -> ADR -> implementation -> automated verification -> docs`.

### Exit Gate G11 — MVP Verified

All MVP requirements are implemented and verified; no critical/high unresolved correctness/security issue is accepted accidentally.

---

## Stage 12 — Hardening & Production Readiness

### Required validation

- unit/integration/system tests;
- fault injection for DB/network/session/provider failures;
- crash/restart/reconciliation tests;
- concurrency/load tests at accepted envelope;
- dependency/security scanning;
- secret/session recovery/revocation drill;
- backup/restore drill meeting RPO/RTO;
- disk/resource exhaustion handling;
- long-running soak where relevant;
- alerts/runbooks;
- kill-switch drill;
- deployment/rollback rehearsal;
- privacy/retention/deletion verification.

### Exit Gate G12 — Production Readiness

Formal checklist passes with evidence and named accepted residual risks.

---

## Stage 13 — Controlled Migration / Cutover

### Pattern

1. preserve current production state and rollback path;
2. shadow/read-only comparison where possible;
3. staging validation;
4. bounded canary;
5. monitored cutover;
6. defined rollback window;
7. legacy retirement only after stability evidence;
8. history/data remediation only with verified recovery procedure.

### Exit Gate G13

Target architecture is authoritative in production; rollback/legacy retirement evidence is recorded.

---

## Stage 14 — Production Evolution

### Goal

Operate, learn and simplify from measurements.

Only now optimize:

- performance/throughput;
- infrastructure cost;
- operator UX;
- analytics;
- safe operational automation;
- architecture simplification;
- future multi-project scaling if product evidence requires it.

New material choices create new RQs/EVs/EXPs/ADRs under Governance v1.

---

## Critical path to a **final** roadmap

`G0 Evidence -> G1 Product -> G2 Measurable NFRs -> G3 Platform/Data Operating Model -> G4 Conditional Domain -> G5 Correctness/Data -> G6 Runtime/Ops -> G7 Alternatives -> G8 Critical PoCs -> G9 Architecture Baseline -> implementation estimates/schedule`

## What can run in parallel

After G1 begins, the following can partially overlap:

- Telegram platform evidence refresh;
- live VPS inventory;
- security threat modeling;
- privacy data inventory;
- local test harness setup;
- historical repository remediation planning;
- provider contract discovery, but only if G1 indicates it is in scope.

They may gather evidence in parallel but cannot independently freeze architecture.

## Schedule policy

No calendar duration is committed in v0.9.

Dates/effort become defensible after G9, when scope, architecture, migration strategy and risk-reduction PoCs are known. Before that point, report progress by gates and evidence maturity rather than estimated completion dates.
