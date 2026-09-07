# Testing Strategy — Local First, Staging When Needed

Status: **ACCEPTED FOR DISCOVERY / PRE-ARCHITECTURE VALIDATION**  
Date: 2026-09-08  
Related issues: #1, #5, #7, #9

## Decision

Use the developer workstation as the default environment for unit tests, integration tests, static analysis, database/state-machine PoCs, failure-injection tests and architecture experiments.

A dedicated VPS is **not required** to begin the Architecture Discovery Program.

Introduce a dedicated staging VPS only when a test depends materially on Linux host behaviour, long-running unattended execution, stable remote networking/IP, reboot/service-manager behaviour, production-like filesystem permissions, or realistic Telegram session/runtime characteristics that cannot be validated safely and equivalently on the workstation.

## Recommended local environment

Because the developer workstation is Windows, prefer one of these Linux-compatible local environments for tests that depend on Linux semantics:

1. WSL2 + Python virtual environment; or
2. Docker Desktop / Linux containers.

Pure Python unit tests and many SQLite/state-machine tests may also run directly on Windows, but Linux-compatible execution should be used before accepting runtime-sensitive conclusions.

## What should run locally first

- unit tests;
- linting, formatting and type checking;
- dependency/security scanning;
- configuration validation with fake credentials;
- SQLite schema/migrations;
- queue claiming/concurrency PoCs;
- fail-closed database-outage tests;
- crash/restart simulations;
- state-machine tests;
- idempotency/reconciliation logic;
- retention/suppression logic;
- metrics/health model tests;
- Docker/systemd configuration generation and static validation;
- mock/fake Telegram adapter tests;
- architecture benchmarks that do not require real Telegram behaviour.

## Tests that may justify staging VPS later

- actual Linux service lifecycle (systemd/PM2/Compose) and reboot recovery;
- filesystem ownership/permissions for `.session`, secrets and DB files;
- long-running soak tests;
- remote backup/restore drills;
- resource/CPU/RAM/disk measurements under representative runtime;
- stable outbound network behaviour;
- Telegram session reconnect/revocation/recovery where safe and necessary;
- production-like deployment/rollback;
- multi-process behaviour that depends on host/runtime semantics.

## Safety boundary

Local/staging tests must not use real member-acquisition actions merely to validate plumbing. Prefer mocks, isolated test groups/accounts, and non-destructive Telegram operations. Any test capable of sending real invitations or modifying a real community requires an explicit test scope, bounded limits, and a kill switch.

## Architecture implication

Testing locally does **not** select the final production runtime. It reduces cost and risk while collecting evidence. Runtime choice remains open between native VPS/systemd, VPS/Docker Compose, managed application approaches, and other justified alternatives until the Architecture Discovery gates are complete.

## Exit to staging

Move a PoC from local to staging only when all of the following are true:

- the hypothesis cannot be answered reliably on the workstation;
- the expected evidence is defined in advance;
- pass/fail criteria are explicit;
- secrets/data exposure is bounded;
- rollback/cleanup is defined;
- the result will materially affect an architecture decision.
