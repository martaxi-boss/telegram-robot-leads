# Research — Datastore, Queue & Concurrency

Status: **DRAFT**  
Started: 2026-09-07  
Related issues: #4, #5, #9

## Objective

Determine whether the final system should retain SQLite, move to PostgreSQL, or use another persistence/queue arrangement. The decision must be based on verified scale, concurrency, recovery, privacy, and operational requirements — not on database fashion.

## Primary sources

SQLite:

- Transactions: https://www.sqlite.org/lang_transaction.html
- Isolation: https://www.sqlite.org/isolation.html
- WAL: https://www.sqlite.org/wal.html
- Appropriate uses: https://www.sqlite.org/whentouse.html

PostgreSQL:

- `SELECT` / locking / `SKIP LOCKED`: https://www.postgresql.org/docs/current/sql-select.html
- Explicit locking: https://www.postgresql.org/docs/current/explicit-locking.html
- Row security: https://www.postgresql.org/docs/current/ddl-rowsecurity.html

## Current legacy pattern

The legacy system uses a single local SQLite database, WAL mode, `BEGIN IMMEDIATE`, and `UPDATE ... RETURNING` to claim pending users.

The approach is reasonable for a small single-host system because it can make queue claiming atomic enough for the current worker model. It should not be discarded without evidence.

However, the same DB also carries safety counters, user/candidate state, audit events and metrics, while multiple helper functions suppress database errors. The reliability problem is therefore not simply 'SQLite is bad'; it is the coupling of safety-critical decisions to error-tolerant data-access semantics.

## Finding DQ-001 — SQLite is single-writer by design

SQLite documentation states that multiple readers can operate concurrently but only one write transaction can proceed at a time. WAL allows readers and a writer to coexist, but there remains one writer at a time.

`BEGIN IMMEDIATE` obtains the write transaction early; if another writer is already active, it can fail with `SQLITE_BUSY`.

**Consequence:**

SQLite can remain a strong candidate if the final architecture is:

- single host;
- low write concurrency;
- modest worker count;
- operationally simple;
- comfortable with serialized writes.

It becomes less attractive if verified requirements include many concurrent writers, multiple application hosts, or database access across a network filesystem.

Status: **HIGH CONFIDENCE**

## Finding DQ-002 — SQLite WAL is host-local architecture

SQLite WAL relies on shared-memory coordination and official documentation states it does not work over a network filesystem in the general case.

**Consequence:**

A final architecture that needs horizontally distributed application hosts should not assume a shared SQLite file as its central queue/database.

Status: **HIGH CONFIDENCE**

## Finding DQ-003 — PostgreSQL has a native multi-consumer queue locking primitive

PostgreSQL supports row-level locking with `FOR UPDATE ... SKIP LOCKED`. Its documentation explicitly notes that `SKIP LOCKED` can be useful for multiple consumers accessing a queue-like table.

**Consequence:**

PostgreSQL is a strong candidate if the verified architecture needs:

- multiple worker processes/hosts claiming jobs concurrently;
- richer relational data/provenance;
- server-managed backup/availability options;
- project isolation or centralized operational access.

This does **not** automatically mean PostgreSQL should replace SQLite for a small single-node workload.

Status: **HIGH CONFIDENCE**

## Finding DQ-004 — Queue correctness requires a state model, not just a locking primitive

Neither `BEGIN IMMEDIATE` nor `SKIP LOCKED` solves the hardest reliability case:

> The remote Telegram action succeeds, then the process dies before local persistence confirms the result.

This is a distributed-state problem because Telegram and the local database cannot participate in one atomic transaction.

Architecture therefore needs explicit states such as (illustrative only):

```text
DISCOVERED
  -> ELIGIBLE
  -> READY
  -> CLAIMED
  -> ACTION_STARTED
  -> SUCCEEDED
  -> FAILED_RETRYABLE
  -> FAILED_FINAL
  -> OUTCOME_UNKNOWN
```

`OUTCOME_UNKNOWN` or equivalent is important because pretending every timeout/crash is a failure can cause duplicate external actions.

Status: **DESIGN REQUIREMENT / MODEL NOT YET APPROVED**

## Finding DQ-005 — Safety counters must be authoritative and fail closed

Quota/safety state is different from optional metrics.

Candidate separation:

- **authoritative policy state**: action limits, account disable state, project disable state, claimed action state;
- **operational audit state**: durable action attempts/results;
- **derived metrics**: dashboards/counters that can be recomputed.

The system may tolerate loss/failure of some derived metrics, but must not execute an action when authoritative policy state is unavailable or ambiguous.

Status: **PROPOSED REQUIREMENT**

## Finding DQ-006 — Do not introduce a separate message queue yet

A database-backed queue may be sufficient for both SQLite and PostgreSQL architecture families.

A separate Redis/RabbitMQ/etc. layer should require evidence such as:

- throughput/latency that database queueing cannot meet;
- independent workload scheduling requirements;
- durability/retry semantics better served by another system;
- multi-service architecture that justifies operational complexity.

Until such evidence exists, a separate queue is **not assumed**.

## Initial option families

### Option A — SQLite as authoritative DB + queue

Best-fit hypothesis:

- one VPS/application host;
- small number of accounts/workers;
- low-to-moderate writes;
- minimal infrastructure;
- straightforward file-level backup plus restore validation.

Key risks:

- one writer at a time;
- single-host coupling;
- backup/runtime coordination;
- application must rigorously handle `BUSY` and fail closed;
- project-level/multi-tenant access controls are application-level.

### Option B — PostgreSQL as authoritative DB + queue

Best-fit hypothesis:

- multiple workers and/or hosts;
- richer provenance/history;
- future multi-project platform;
- stronger centralized operations;
- need for row-level locks and server DB ecosystem.

Key risks/trade-offs:

- more infrastructure and cost;
- network/database dependency;
- connection management;
- migrations/operations are more complex than local SQLite.

### Option C — PostgreSQL + separate queue

Current status: **NOT JUSTIFIED YET**.

Only evaluate if PoCs/requirements show database-backed work claiming is insufficient.

## PoCs required before datastore ADR

### POC-DQ-01 — Legacy-scale SQLite concurrency

Measure:

- realistic worker count;
- queue claims/sec;
- writes/sec;
- lock waits/BUSY events;
- recovery after worker kill.

### POC-DQ-02 — Fail-closed database outage

Verify that action authorization is denied when safety state cannot be loaded or committed.

### POC-DQ-03 — Ambiguous remote outcome

Inject failure after a mocked/controlled external action success and before final persistence. Evaluate reconciliation/state-machine design.

### POC-DQ-04 — PostgreSQL multi-consumer claim

Implement a minimal queue using row locking / `SKIP LOCKED` and compare operational complexity and behaviour with SQLite.

### POC-DQ-05 — Restore test

Restore both candidate DB designs from backup and measure actual recovery process/RTO.

## Decision dependencies

The datastore ADR cannot be accepted until #2 establishes at least:

- expected number of projects;
- active accounts/workers;
- whether workers can remain on one host;
- data retention/volume estimate;
- RTO/RPO;
- whether project-level DB isolation/access control is required.

## Current conclusion

No datastore is selected yet.

SQLite remains viable for a deliberately small single-host architecture. PostgreSQL becomes increasingly compelling as concurrency, multi-project scope, centralized operations and relational data-governance requirements increase. The final decision must be made after requirements and PoCs, not by defaulting to the more complex technology.
