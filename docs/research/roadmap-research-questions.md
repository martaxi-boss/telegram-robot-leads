# Roadmap Research Question Register

Status: **IN PROGRESS**
Updated: 2026-09-11
Purpose: enumerate the high-impact questions that must be resolved before Architecture Baseline v1.0 and a final implementation roadmap can be accepted.

The ordering below follows dependency/decision impact, not convenience.

## Priority model

Priority is driven by:

`Architecture impact x uncertainty x downstream decisions blocked`

P0 questions block the final architecture or can invalidate major work. P1 questions materially influence design/operations. P2 questions may be deferred until an architecture candidate exists.

| ID | Priority | Research question | Current evidence | Exit condition |
|---|---|---|---|---|
| RQ-001 | P0 | What is the final product boundary: single Telegram acquisition tool, reusable Telegram ops platform, multi-project platform, or broader IPTV/VPN customer platform? | Low; Issue #2 open | Explicit accepted scope/non-scope and system boundary |
| RQ-002 | P0 | What primary measurable business outcome must the system improve, and which KPIs prove success? | Low | 1–3 primary KPIs plus guardrail metrics accepted |
| RQ-003 | P0 | Which Telegram acquisition/membership actions are acceptable, prohibited, opt-in, or human-approved? | Medium-high platform evidence; business policy open | Allowed/conditional/prohibited action matrix accepted |
| RQ-004 | P0 | Which legacy behaviours are real requirements vs implementation accidents? | High behaviour evidence | Every material legacy behaviour classified PRESERVE/REDESIGN/REMOVE/RESEARCH/LEGACY-DEAD |
| RQ-005 | P0 | What scale must v1 support: projects, communities, accounts, candidates/events, concurrent workers, database size and retention? | Low | Numeric v1 baseline + growth envelope accepted |
| RQ-006 | P0 | What reliability targets apply: SLO/availability, RTO, RPO, duplicate/lost-event tolerance and degraded-mode policy? | Low | Measurable reliability requirements accepted |
| RQ-007 | P0 | What is the sustainable Telegram capability split between Bot API and MTProto user sessions? | High capability evidence, product choice open | Responsibility matrix and architecture constraint accepted |
| RQ-008 | P0 | What personal data is necessary, for what purpose, lawful basis, retention, provenance, suppression/deletion and access policy? | Medium research; legal/business inputs open | Data inventory/purpose/retention + qualified review where needed |
| RQ-009 | P0 | What authoritative state machine prevents duplicate/unbounded external actions across crashes/timeouts? | High problem evidence | State machine + ambiguous outcome/reconciliation semantics accepted |
| RQ-010 | P0 | What is the authoritative datastore/queue topology once RQ-005/RQ-006 are known? | Medium-high technical evidence | SQLite/PostgreSQL/other choice justified by requirements + PoC if needed |
| RQ-011 | P0 | What is the verified live runtime/VPS baseline? | Low/stale | Sanitized inventory of OS, process identity, versions, permissions, storage, networking, backups, resources and reboot behavior |
| RQ-012 | P0 | How are Telegram sessions/API credentials and other secrets stored, accessed, rotated, revoked and backed up? | Medium-high threat evidence | Accepted secrets/session lifecycle and recovery model |
| RQ-013 | P0 | What health, alerting, audit and kill-switch model is required? | Medium-high research | Layered health contract, critical alerts and action-disable semantics accepted |
| RQ-014 | P0 | If the broader IPTV/VPN product is in scope, what exact provider/provisioning contracts exist? | Absent in repo | Provider capabilities/API contracts, failure modes, credentials and test environment evidenced, or explicitly out of scope |
| RQ-015 | P0 | If commerce/subscriptions are in scope, what payment, subscription, entitlement, refund/chargeback and webhook model is required? | Absent in repo | Payment/entitlement lifecycle defined, or explicitly out of scope |
| RQ-016 | P0 | If full customer lifecycle is in scope, how is Telegram identity linked to customer/subscription identity? | Absent in repo | Identity/account model accepted, or explicitly out of scope |
| RQ-017 | P0 | What legal/commercial rights and compliance constraints apply to the actual IPTV/VPN offering and acquisition workflow? | Product-specific evidence absent | Qualified confirmation of allowed business/service model and documented constraints |
| RQ-018 | P1 | Which operator/admin/support roles exist and which actions require approval/separation of duties? | Low | Role/permission matrix accepted |
| RQ-019 | P1 | What deployment model best meets accepted requirements: systemd VPS, Compose VPS, managed runtime, or other? | Medium technical research | Runtime ADR supported by live inventory + SLO/cost requirements |
| RQ-020 | P1 | What backup/restore architecture achieves accepted RPO/RTO for DB, configuration and session credentials? | Low practical evidence | Restore test passes against defined objectives |
| RQ-021 | P1 | What migration strategy safely replaces or decomposes the legacy runtime while preserving service continuity? | Medium | Shadow/staging/canary/cutover/rollback design accepted |
| RQ-022 | P1 | How should historical `users.db` exposure be remediated without losing repository recoverability? | High evidence; action pending | Backup/rollback validated, history sanitized, re-clone/search validation complete |
| RQ-023 | P1 | What build/test/release contract guarantees reproducible deployments? | High gap evidence | Supported Python version, locked dependencies, CI checks, migrations and release identification defined |
| RQ-024 | P1 | What cost/resource envelope constrains v1 architecture? | Low | Monthly infra/tooling budget and operator constraints accepted |
| RQ-025 | P2 | Which metrics/analytics are needed beyond operational health to measure product KPIs? | Low until RQ-002 | KPI-derived event/metric contract accepted |
| RQ-026 | P2 | Which performance/cost optimizations are justified by production evidence? | None; deliberately deferred | Only evaluated after stable baseline measurements |

## Dependency groups

### Gate A — Product Definition
Resolve: RQ-001, RQ-002, RQ-003, RQ-004, RQ-005, RQ-006, RQ-017, RQ-018, RQ-024.

### Gate B — Sustainable Operating Model
Resolve: RQ-007, RQ-008, RQ-012, RQ-013 and product-dependent compliance consequences.

### Gate C — Conditional Business Domain
Resolve RQ-014, RQ-015, RQ-016 only if RQ-001 includes IPTV/VPN commerce/provisioning/customer lifecycle in this system boundary. If not, mark each explicitly out of scope and identify the external systems/contracts instead.

### Gate D — Correctness & Runtime
Resolve: RQ-009, RQ-010, RQ-011, RQ-019, RQ-020, RQ-023.

### Gate E — Architecture & Migration
Use Gates A–D to answer RQ-021 and select complete end-to-end architecture alternatives; run only PoCs capable of changing the decision.

### Post-baseline
RQ-025 and RQ-026 should be derived from accepted product goals and production evidence; they must not drive premature complexity.
