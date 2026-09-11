# Roadmap Readiness Requirements Register

Status: **DRAFT / PROPOSED**
Updated: 2026-09-11
Source: deep roadmap audit and prior architecture-discovery evidence.

These requirements are candidates to be accepted through the roadmap gates. They are **not all accepted yet**. Product-specific values remain intentionally open until the Product Definition and Measurable Requirements gates.

## Safety & correctness

### REQ-001 — Fail-closed external-action authorization

If state required to determine whether an external side effect is allowed cannot be read or validated, the system must not execute the side effect.

Status: **Proposed — P0**
Evidence: legacy DB/count paths can return zero on failure.

### REQ-002 — Explicit external-action lifecycle

Every material external action must have a durable lifecycle sufficient to distinguish planned, authorized, in-flight, succeeded, failed and ambiguous/unknown outcomes where those states apply.

Status: **Proposed — P0**

### REQ-003 — Ambiguous outcomes require reconciliation/bounded retry

A timeout/crash around an external side effect must not silently create an unbounded retry loop or duplicate action. Ambiguous results require explicit reconciliation or a bounded, justified retry policy.

Status: **Proposed — P0**

### REQ-004 — One authoritative state source

Business/action authorization state must have one authoritative durable source. Caches/derived views may exist but must not compete as independent truth.

Status: **Proposed — P0**
Evidence: SQLite + `estado_bot.json` currently overlap.

### REQ-005 — Bounded actions and kill switch

Every automated external-action class must have explicit bounds and an independently testable disable/kill mechanism at appropriate global/project/account/action scope.

Status: **Proposed — P0**

### REQ-006 — Platform restrictions are state, not an evasion target

The system must not be designed to conceal automation or evade platform controls. Rate-limit/restriction/authorization signals must be represented as policy/health state with bounded handling.

Status: **Proposed — P0**

## Telegram / credentials

### REQ-007 — Project-owned Telegram API identity

Production MTProto integration, if retained, must use project-owned API credentials rather than sample/published API IDs intended for testing.

Status: **Proposed — P0**

### REQ-008 — Session credentials treated as critical secrets

Telegram session authorization material must have defined storage, access, backup, rotation/revocation and incident-recovery controls.

Status: **Proposed — P0**

### REQ-009 — Telegram responsibilities must be capability/policy driven

Bot API, user-session MTProto and manual operator responsibilities must be selected per accepted capability and policy need; the legacy use of user sessions is not automatically a requirement.

Status: **Proposed — P0**

## Data & privacy

### REQ-010 — Data purpose and minimization

Every stored personal-data field must have an accepted purpose. Data not required for an accepted product purpose must not be collected or retained merely because the legacy implementation did so.

Status: **Proposed — P0**

### REQ-011 — Provenance, retention and suppression/deletion

Where candidate/customer/user data is in scope, the system must define necessary provenance, retention TTL, access, deletion and durable suppression/opt-out behavior appropriate to the accepted use case.

Status: **Proposed — P0**

### REQ-012 — Derived/inferred attributes carry provenance/confidence

Any inferred attribute used by the system must be explicitly identified as inferred, with evidence/confidence and justification. Heuristic region/language must not be treated as verified location.

Status: **Proposed — P1**

### REQ-013 — Secrets and operational personal data are separate security classes

Session/API/payment/provider credentials must not be stored or backed up as ordinary operational/customer data. Access/retention controls must reflect different risk classes.

Status: **Proposed — P0**

## Configuration & delivery

### REQ-014 — Safe explicit configuration

Production action-capable behavior must be explicitly configured/authorized; missing/invalid configuration must fail safe. Configuration precedence must be deterministic and documented.

Status: **Proposed — P0**

### REQ-015 — Reproducible build/runtime

The project must define a supported runtime, reproducible dependency resolution/lock, deterministic setup and release identity sufficient to rebuild a known version during recovery.

Status: **Proposed — P1 before implementation**

### REQ-016 — Automated verification before production

Production v1 must have automated tests appropriate to the accepted architecture and CI checks protecting material changes.

Status: **Proposed — P1 before implementation**

### REQ-017 — Schema migration contract

Persistent schema changes must use versioned migrations with tested upgrade/recovery behavior rather than ad-hoc broad-exception startup alterations.

Status: **Proposed — P1**

### REQ-018 — Environment separation

Staging/test and production must have explicit configuration/data/session boundaries; production credentials/actions must not be required for routine unit/integration testing.

Status: **Proposed — P1**

## Reliability & operations

### REQ-019 — Measurable SLO/RTO/RPO

Before datastore/runtime architecture is accepted, the project must define measurable availability/SLO, RTO, RPO and acceptable duplicate/lost-event tolerances.

Status: **Proposed process requirement — P0**
Values: **OPEN**

### REQ-020 — Tested backup/restore

A backup is not considered a recovery control until restoration has been tested against accepted RTO/RPO and the complete required state set.

Status: **Proposed — P0 before production**

### REQ-021 — Layered health model

Operational health must distinguish at minimum process liveness, required local dependencies, external integration/session authorization, action capability and end-to-end progress as relevant. Process-running alone is insufficient.

Status: **Proposed — P1**

### REQ-022 — Controlled migration and rollback

Migration to the target architecture must preserve a known rollback path and use staged/shadow/canary validation where applicable. Legacy retirement must follow stability evidence.

Status: **Proposed — P1**

## Product / scope gates

### REQ-023 — Explicit product boundary before Architecture v1

Architecture v1 must not be accepted until the repository's system boundary is explicit, including whether IPTV/VPN provisioning, commerce/subscription and customer lifecycle are inside or outside this system.

Status: **Proposed process requirement — P0**

### REQ-024 — Legacy behavior is not a requirement by default

Each material legacy behavior must be classified and linked to an accepted requirement before migration. Unclassified behavior must not be automatically preserved.

Status: **Proposed process requirement — P0**

### REQ-025 — Quantified v1 scale envelope

Architecture v1 must be justified against explicit numbers/ranges for the dimensions that affect architecture, including projects, accounts/workers, event/candidate volume, data size/retention and expected growth where applicable.

Status: **Proposed process requirement — P0**

### REQ-026 — Product-specific rights/compliance gate

If IPTV/VPN service delivery, commerce or personal-data-driven acquisition is in scope, applicable commercial rights, privacy/legal obligations and provider/platform contractual constraints must be identified before production architecture is approved. Qualified legal/compliance review must be obtained where the project team is not competent to make the determination.

Status: **Proposed — P0 if triggered by scope**

## Governance & traceability

### REQ-027 — Material decisions trace to evidence

Material architecture decisions must be traceable to accepted requirements and relevant research/evidence/experiments under Governance v1.

Status: **Accepted process principle via ADR-001**

### REQ-028 — Decision-changing PoCs only

PoCs must define hypothesis and pass/fail criteria before execution and should be prioritized when their result can materially change an architecture choice or de-risk production.

Status: **Proposed process requirement — P1**

## Values deliberately not invented

The following remain open and must be supplied/validated before Architecture Baseline:

- product model and system boundary;
- primary KPI targets;
- project/account/user/event scale;
- availability/SLO;
- RTO/RPO;
- retention periods;
- operator roles/approvals;
- monthly cost envelope;
- exact allowed Telegram action model;
- whether IPTV/VPN/payment/customer lifecycle belongs in this repository;
- provider/payment contracts if applicable.
