# Research — Observability, Health & Operations

Status: **DRAFT**  
Started: 2026-09-07  
Related issue: #8

## Objective

Define what 'healthy' means for the final system and what evidence operators need to diagnose failures without reading source code or assuming that a running process equals a functioning Telegram service.

## Legacy baseline

Current operational visibility includes:

- PM2 process state;
- rotating application log;
- SQLite `adder_daily` metrics;
- SQLite `adder_events`;
- helper scripts showing DB counts and recent logs;
- disk-free warning.

These are useful primitives, but there is no explicit health model or alerting contract.

## Finding OH-001 — Process liveness is not service health

A process can be running while:

- Telegram session is unauthorized;
- target community cannot be resolved;
- database writes are failing;
- safety state is unavailable;
- queue is stuck;
- account is rate-limited/disabled;
- backups are stale;
- all external actions are failing.

Therefore health must be layered.

## Proposed health hierarchy

### H0 — Process

Examples:

- process exists;
- event loop responds;
- no crash loop.

### H1 — Local dependencies

Examples:

- configuration valid;
- DB reachable/read-write as required;
- filesystem/session path accessible;
- sufficient disk space.

### H2 — Telegram connectivity/account

Examples:

- API connection available;
- session authorized;
- account identity matches configured binding;
- no account-level disabled/security state.

### H3 — Project capability

Examples:

- target community resolves;
- required permissions exist;
- required bot/admin/user capability available;
- authoritative policy/quota state accessible.

### H4 — End-to-end operation

Examples:

- intake/discovery receives expected events;
- queue progresses;
- permitted actions complete;
- audit result persists;
- reconciliation backlog stays bounded.

A deployment can be `PROCESS_UP` but `SERVICE_DEGRADED` or `ACTION_DISABLED`.

## Candidate top-level service states

```text
STARTING
HEALTHY
DEGRADED
ACTION_DISABLED
DEPENDENCY_UNAVAILABLE
ACCOUNT_UNAUTHORIZED
ACCOUNT_RESTRICTED
CONFIGURATION_ERROR
RECOVERY_REQUIRED
STOPPED
```

These names are hypotheses; final state semantics must align with the accepted architecture.

## Core metrics candidates

### Service/runtime

- process uptime;
- restart/crash count;
- event-loop lag if relevant;
- CPU/memory;
- disk free;
- release commit/version.

### Database

- connection/write health;
- transaction failures;
- lock/BUSY rate for SQLite or lock-wait metrics for PostgreSQL;
- migration/schema version;
- backup age;
- last restore-test date.

### Queue/state

- ready queue depth;
- oldest ready item age;
- claimed/in-flight count;
- `OUTCOME_UNKNOWN`/reconciliation count;
- retryable failures by reason;
- permanently rejected by reason.

### Telegram account/session

- authorized boolean/state;
- last successful low-risk API interaction;
- permission/capability status for target project;
- FloodWait/platform restriction events;
- account disable state;
- session age/last authorization check where useful.

### Actions

- authorized action requests;
- denied-by-policy actions;
- attempted actions;
- successful actions;
- failed actions by class;
- ambiguous outcomes;
- action rate by project/account;
- safety cap utilization.

### Intake/acquisition

Depends on accepted product model. Potential metrics:

- invite-link views/clicks where externally measurable;
- join requests received;
- approvals/declines;
- candidate ingestion count;
- provenance/source distribution;
- conversion rate.

## Event design principles

1. Events should have stable machine-readable `event_type` values.
2. Human message text is supplemental, not the schema.
3. Avoid unnecessary usernames/phone numbers in logs.
4. Include project/account/action identifiers needed for correlation without leaking credentials.
5. External-action events should be traceable from authorization -> attempt -> result/reconciliation.
6. Important disable/safety transitions should be durable.

## Proposed action correlation

```text
action_id
request_id
project_id
account_id
candidate/request identity reference
policy_decision_id
attempt_no
remote_result_class
local_state
created_at / updated_at
```

Exact fields depend on the final data model.

## Alerts — candidate classes

### Critical

- session credential suspected compromised;
- production safety state unavailable while workers request actions;
- unexpected action-rate spike;
- all target accounts unauthorized;
- DB unavailable beyond threshold;
- backup restore validation failed;
- disk close to exhaustion.

### High

- repeated account restriction/FloodWait pattern;
- target permissions lost;
- reconciliation/unknown outcomes growing;
- worker crash loop;
- queue age exceeds accepted SLA.

### Informational/operational

- deployment completed;
- session intentionally disabled;
- daily business cap reached;
- backup completed;
- planned maintenance mode.

## Kill switch requirements

The final architecture should expose a way to stop external Telegram actions while preserving diagnostics/read-only health where safe.

Candidate levels:

- global action disable;
- per-project disable;
- per-account disable;
- per-action-class disable.

A kill switch should not depend on the same unavailable component that caused the unsafe condition where practical.

This requires architecture-specific design in Phase 6/7.

## Runbook structure

Each material alert/state should eventually link to a runbook containing:

1. meaning;
2. immediate safe action;
3. diagnostic checks;
4. recovery steps;
5. rollback/escalation;
6. evidence to capture;
7. conditions for re-enabling actions.

Initial runbooks required before production:

- Telegram session unauthorized/revoked;
- Telegram account restriction;
- DB outage;
- disk full/low space;
- worker crash loop;
- ambiguous external action outcome;
- backup restore;
- emergency global action disable;
- deployment rollback.

## Observability architecture options

Do not select a full monitoring stack yet.

Potential progression:

### Minimal single-host

- structured application logs;
- DB-backed health state;
- systemd/Docker health;
- local metrics endpoint or lightweight exporter;
- external uptime/alert check if justified.

### Growing/multi-host

- centralized logs;
- metrics/time-series backend;
- alert manager;
- dashboards.

Selection depends on actual scale and operational ownership. A complex observability platform is not automatically required for a small service.

## Production-readiness evidence

A release is not production-ready merely because tests pass. Required evidence should eventually include:

- health states verified;
- critical alerts tested;
- kill switch tested;
- backup restore tested;
- crash recovery tested;
- session-revocation runbook tested;
- release/rollback identified by commit/version;
- operator can diagnose a degraded service without source-code inspection.

## Current conclusion

The final architecture must make health an explicit domain concept. Existing metrics/logs are useful but should be reorganized around authoritative safety state, account/project capability, action lifecycle and recovery rather than only counts and log text.
