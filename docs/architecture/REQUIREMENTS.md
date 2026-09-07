# Requirements Register

Status: **DRAFT**  
Owner: Alaska Digital  
Started: 2026-09-07

This document is intentionally incomplete. It records what must be discovered before architecture is approved.

## 1. Product identity

### RQ-001 — Product scope

Question: Is the target product:

- a single automation for one Telegram community;
- a reusable internal Alaska Digital Telegram operations platform;
- a multi-project/multi-client platform;
- another model?

Status: **OPEN**

### RQ-002 — Primary business outcome

Question: What measurable outcome is the system expected to improve?

Potential examples to validate rather than assume:

- community growth;
- qualified opt-in membership;
- lead acquisition;
- engagement;
- operator efficiency;
- analytics.

Status: **OPEN**

### RQ-003 — Explicitly prohibited outcomes

The system must not be designed around bypassing platform controls, concealing automated behaviour to evade enforcement, or creating unbounded unsolicited activity.

Status: **PROPOSED REQUIREMENT**

## 2. Users and roles

Questions:

- Who operates the system?
- Is there one administrator or multiple operators?
- Are there project-level roles?
- Which actions require approval?
- Who can access Telegram sessions, credentials, source groups, candidates, or metrics?

Status: **OPEN**

## 3. Project/account scale

Required values to determine:

- number of active projects;
- number of Telegram target communities per project;
- number of Telegram user accounts per project;
- number of bots, if any;
- expected candidate/event volume;
- peak concurrent workers;
- expected database growth;
- retention period.

Status: **OPEN**

## 4. Functional capabilities

Each capability must ultimately be classified as `REQUIRED`, `OPTIONAL`, `REJECTED`, or `RESEARCH REQUIRED`.

| Capability | Current status |
|---|---|
| Telegram account/session management | RESEARCH REQUIRED |
| Target community configuration | RESEARCH REQUIRED |
| Source community discovery | RESEARCH REQUIRED |
| Candidate ingestion | RESEARCH REQUIRED |
| Candidate provenance tracking | PROPOSED REQUIRED |
| Candidate eligibility/policy evaluation | PROPOSED REQUIRED |
| Automated member addition | RESEARCH REQUIRED / POLICY GATE |
| Invite links / join requests | RESEARCH REQUIRED |
| Operator approval queue | RESEARCH REQUIRED |
| Rate/quota enforcement | PROPOSED REQUIRED |
| Account health tracking | PROPOSED REQUIRED |
| Action audit trail | PROPOSED REQUIRED |
| Data deletion/suppression | PROPOSED REQUIRED |
| Metrics and reporting | PROPOSED REQUIRED |
| Multi-project isolation | OPEN |

## 5. Safety requirements

### SR-001 — Fail-closed action authorization

If the system cannot reliably read the state required to determine whether an external action is allowed, it must not execute the action.

Status: **PROPOSED REQUIRED**

### SR-002 — Durable audit trail

Externally visible actions and material state transitions must generate an auditable record sufficient for operational investigation.

Status: **PROPOSED REQUIRED**

### SR-003 — Bounded actions

Every automated external action class must have explicit limits and a clear disable/kill mechanism.

Status: **PROPOSED REQUIRED**

### SR-004 — Ambiguous outcome handling

A crash/timeout around a remote Telegram action must not silently cause duplicate/unbounded retries. Ambiguous results require reconciliation or bounded retry semantics.

Status: **PROPOSED REQUIRED**

## 6. Data/privacy requirements

Questions and candidate requirements:

- define each personal-data field and purpose;
- store source/provenance where justified;
- collect only data necessary for accepted product purposes;
- define retention TTLs;
- define suppression/opt-out/deletion behaviour;
- separate secrets/session credentials from operational records;
- define access controls;
- define backup retention and deletion propagation;
- determine lawful basis and notice obligations with qualified legal review where required.

Status: **RESEARCH REQUIRED**

## 7. Reliability requirements

Values to determine:

- acceptable downtime;
- recovery time objective (RTO);
- recovery point objective (RPO);
- acceptable duplicate-action probability;
- acceptable lost-event probability;
- behaviour during database outage;
- behaviour during Telegram outage;
- behaviour after session revocation;
- behaviour after VPS restart;
- backup frequency and restore-test frequency.

Status: **OPEN**

## 8. Security requirements

The threat model must cover at minimum:

- Telegram session theft;
- API credential leakage;
- repository secret leakage;
- VPS compromise;
- malicious/compromised dependency;
- operator error;
- accidental mass action;
- database disclosure;
- backup disclosure;
- compromised Telegram account;
- unauthorized project crossover in a future multi-project design.

Status: **RESEARCH REQUIRED**

## 9. Observability requirements

Candidate health/metrics dimensions:

- service process health;
- Telegram connectivity;
- account authorization/session health;
- queue depth;
- action attempts/success/failure;
- rate-limit events;
- database health;
- disk/storage health;
- backup age;
- worker liveness;
- last successful end-to-end operation;
- suppressed/blocked actions due to safety policy.

Status: **PROPOSED REQUIRED**

## 10. Delivery/governance requirements

Proposed requirements:

- architecture decisions documented as ADRs;
- changes through branches/PRs;
- tests and CI before Production v1.0;
- reproducible dependencies;
- documented migrations and rollback;
- documented production runbooks;
- research evidence preserved in GitHub.

Status: **PROPOSED REQUIRED**

## 11. Decision gate

Architecture alternatives must not be scored until the high-impact open requirements above have enough evidence to distinguish between designs.
