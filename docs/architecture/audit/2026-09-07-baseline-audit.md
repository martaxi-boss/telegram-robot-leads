# Baseline Repository Audit — 2026-09-07

Status: **RECORDED BASELINE**  
Repository: `Alaska-Digital/telegram-iptvpn`  
Audited branch: `main`  
Audited HEAD: `5a9623d191c5d2294cbc29b7af68194613bf5302`

## Executive summary

The current repository is a Telegram user-account automation system built around Telethon and SQLite. It discovers Telegram groups, extracts candidate users, stores them in a local queue, and attempts to add selected users to a configured target group using one or more Telegram accounts.

The code contains useful operational work — queue claiming, Telegram error handling, account staggering, metrics, rotating logs, and basic runtime scripts — but it is not yet production-grade as a maintainable Alaska Digital platform.

The main risks are architectural, operational, privacy/compliance-related, and governance-related rather than a single isolated code defect.

## Current repository shape

At the audited HEAD the repository contains a very small number of source/configuration files:

- `.env.example`
- `.gitignore`
- `ecosystem.config.js`
- `main.py`
- `requirements.txt`
- `scripts/check_db.py`
- `scripts/telegram-iptvpn-status.sh`
- `ver_metricas.py`

There was no README, test suite, CI workflow, package structure, migration framework, or architecture documentation at baseline.

`main.py` is approximately 96 KB and contains most of the system responsibilities in a single module.

## Current functional model

The legacy system combines:

- Telegram API credential loading;
- multiple Telethon sessions/accounts;
- Telegram group discovery;
- participant scraping;
- heuristic regional classification;
- SQLite queue/state management;
- invitation/action execution;
- per-account and project-level quotas;
- rate-limit/FloodWait/PeerFlood handling;
- human-like timing/randomisation;
- operational metrics and logs;
- PM2 deployment assumptions.

The target group and several source/discovery groups are configurable or embedded in the current implementation.

## Positive engineering elements to preserve or re-evaluate

The current system includes several concepts worth retaining if they remain requirements:

1. Atomic-ish queue claiming using SQLite transactions and `UPDATE ... RETURNING`.
2. WAL mode and SQLite busy-timeout handling.
3. Explicit handling for common Telegram RPC failures.
4. Multi-account login staggering.
5. Cleanup/disconnect handling for Telethon clients.
6. Daily/event metrics persisted in SQLite.
7. Rotating logs.
8. Disk-space warning.
9. Runtime status scripts.
10. Separation of real `.env`, session files, `accounts.json`, logs, and runtime DB from the current Git HEAD via `.gitignore`.

These are implementation ideas, not automatically approved final-architecture decisions.

## Critical / high-priority findings

### A-001 — Historical `users.db` committed to Git

Severity: **CRITICAL**

The initial commit contained `users.db` (~2.8 MB). A subsequent commit removed the file and added it to `.gitignore`, but the blob remains in Git history until history is rewritten.

Potential contents are defined by the application schema and may include Telegram user IDs, usernames, regions, processing state, session/account attribution, and operational events.

Required response:

- preserve a recoverable repository backup before history rewriting;
- determine who/what had access to the private repository during the exposure window;
- sanitize Git history;
- validate that the sensitive blob is no longer reachable from rewritten refs;
- record the remediation and any credential/data-response decisions.

### A-002 — Safety/rate-limit accounting can fail open

Severity: **CRITICAL**

Several metrics/quota reads return zero on database failure and several metric writes swallow exceptions. Where these values gate Telegram actions, a database error can be interpreted as "no actions performed yet" rather than "state unknown".

Required architectural principle:

> If a safety/quota state cannot be read or durably updated, action execution must fail closed.

### A-003 — Remote action and local persistence are not one transaction

Severity: **HIGH**

Telegram action success and local DB state cannot be committed atomically. A process crash after the remote action but before durable local persistence can create duplicate/unknown outcomes.

Required research:

- idempotency strategy;
- reconciliation strategy;
- action-attempt state machine;
- recovery after ambiguous remote outcomes.

### A-004 — Anti-abuse signals are treated as retry/timing problems

Severity: **HIGH**

The legacy code contains extensive randomised "human" scheduling and logic to continue retrying after PeerFlood/rate-limit events. This should not be optimized further until Telegram policy research determines a sustainable operating model.

Architecture requirement:

- platform controls must be treated as policy/safety constraints, not obstacles to disguise or bypass.

### A-005 — Published/sample Telegram API credentials supported as fallback

Severity: **HIGH**

The code supports a fallback to credentials published with Telegram's Android open-source client. Telegram's own API documentation states sample/published API IDs are limited and not suitable for production/end-user applications.

Required response:

- final production design must use project-owned API credentials;
- remove production reliance on published/sample credentials.

### A-006 — Telegram session files are high-value credentials

Severity: **HIGH**

Telethon `.session` files represent authenticated user sessions. They are excluded from Git, but the current runtime assumes local storage beside the application on a VPS.

Required research:

- dedicated non-root service identity;
- minimum filesystem permissions;
- encrypted backups if any;
- session revocation/recovery;
- secrets/session inventory and rotation procedures.

### A-007 — Monolithic architecture and import-time configuration

Severity: **HIGH**

`main.py` mixes configuration, persistence, Telegram integration, discovery, classification, scheduling, policy, metrics, workers, and the entry point. Credentials/accounts are loaded at import time, making isolated tests and tooling difficult.

Required response:

- define component boundaries only after requirements/research;
- remove import-time dependence on live credentials in the final design.

### A-008 — No automated tests or CI

Severity: **HIGH**

At baseline there is no `tests/` directory and no GitHub Actions workflow. There is no automated validation of queue semantics, quota safety, configuration, state transitions, or failure recovery.

Required response:

- test strategy before migration;
- CI in Engineering Foundation phase;
- fault/recovery testing for critical state transitions.

### A-009 — `main` is unprotected

Severity: **HIGH**

The repository currently has only `main`, and the branch is not protected. No enforceable private-repository ruleset is available through the current GitHub tier exposed to the connector.

Operational mitigation until enforcement is available:

- branch + PR workflow;
- no direct architectural work on `main`;
- record review/validation evidence in PRs.

### A-010 — Personal-data governance is incomplete

Severity: **HIGH**

The current system can collect Telegram user IDs, usernames and inferred region from third-party groups. The schema does not provide sufficient provenance, retention, deletion, suppression/opt-out, or lawful-basis evidence for a mature data-governance model.

Required research:

- data inventory;
- purpose and lawful-basis assessment;
- source/provenance field requirements;
- retention TTL;
- deletion and suppression workflow;
- minimum-data design;
- access control and auditability.

### A-011 — Region classification is weak evidence

Severity: **MEDIUM**

The system infers PT/ES vs Europe using name characters and `langdetect`; some scraping modes relax the filter and assign the scraper account's region to extracted users. This can create false geographic attribution.

Required response:

- determine whether region is truly a product requirement;
- if yes, define an evidence-based classification model and confidence/provenance;
- otherwise remove the attribute.

### A-012 — Scrape limit measures inserted users, not necessarily examined participants

Severity: **MEDIUM**

The current `TELEGRAM_SCRAPE_MAX_PER_GROUP` counter increments when a new DB row is successfully inserted. A group with many already-known users may result in far more participants being iterated than the configured value implies.

Required response:

- separate `participants_examined` from `new_candidates_inserted` if discovery remains an approved workflow.

### A-013 — Configuration contains stale/contradictory intent

Severity: **MEDIUM**

Some configuration/comments imply a daily PeerFlood stop threshold while the current runtime path continues retrying with adaptive waits. There are also legacy helper functions whose intended policy is not clearly enforced.

Required response:

- requirements must replace comments/legacy variables as the source of truth;
- remove dead configuration during migration only after behaviour is documented.

### A-014 — Dependencies are not locked

Severity: **MEDIUM**

`requirements.txt` uses lower bounds (`>=`) only. Environments created at different times may resolve to different dependency versions.

Required response:

- define supported Python version;
- introduce reproducible dependency locking/constraints;
- automated dependency/security checks.

### A-015 — Deployment is tightly coupled to one VPS path

Severity: **MEDIUM**

PM2 and support scripts assume `/root/TELEGRAM-IPTVPN` and local runtime files.

Required research:

- service identity;
- filesystem layout;
- container vs non-container deployment;
- staging/prod separation;
- backup and restore;
- health monitoring.

### A-016 — Documentation is insufficient to rebuild the system

Severity: **MEDIUM**

The code references example account/API JSON files that are not present in the repository, and the baseline had no README/runbook.

Required response:

- architecture and operations documentation becomes mandatory deliverable, not an afterthought.

## Baseline governance findings

- Repository is private.
- Default branch is `main`.
- `main` was unprotected at audit time.
- No open PRs/issues existed at baseline.
- No GitHub Actions workflow was associated with the audited HEAD.
- Recent commits were unsigned.
- Architecture/research history was not previously recorded in the repository.

## Immediate policy before final architecture

Until the discovery program reaches Architecture v1.0:

- do not optimize human-simulation/anti-rate-limit evasion behaviour;
- do not add infrastructure solely for perceived professionalism;
- do not rewrite the whole application before requirements are established;
- preserve the legacy runtime until migration/rollback is designed;
- prioritize evidence, safety, data governance, reproducibility, and recovery.

## Audit disposition

The project is **worth retaining and redesigning**, because useful operational logic exists. The recommended strategy is controlled architecture discovery followed by staged migration, not an unstructured rewrite and not continued scaling of the current monolith.
