# Research — Security Threat Model

Status: **DRAFT**  
Started: 2026-09-07  
Related issue: #6

## Objective

Identify high-value assets, trust boundaries, likely failure/attack paths, and architecture controls before implementation choices lock in the security model.

## Scope

Current and candidate future components:

- GitHub repository and CI/CD;
- deployment host(s);
- Telegram API credentials;
- Telegram user sessions / bot tokens;
- candidate/user data;
- audit events and metrics;
- database and backups;
- operators/administrators;
- Telegram APIs;
- future web/admin interfaces if introduced.

## Security principles

1. Telegram session credentials are equivalent to account-login capability and must be treated as secrets.
2. Safety-critical authorization fails closed.
3. Runtime services use least privilege and do not require interactive root access for normal operation.
4. Secrets are not stored in Git, issue bodies, logs, or ordinary diagnostic bundles.
5. Candidate/personal data is separated from authentication secrets.
6. External actions are bounded and auditable.
7. Recovery paths are tested before destructive remediation.
8. Architecture minimizes the number of components that can perform Telegram actions.

## Asset inventory

| Asset | Sensitivity | Current observation | Target control direction |
|---|---|---|---|
| Telethon `.session` files | CRITICAL | Local runtime files, ignored by Git | Dedicated service identity, strict permissions, revocation inventory |
| Telegram API ID/hash | HIGH | `.env` / local config paths supported | Project-owned credentials, secret storage, no sample production fallback |
| Bot token(s), if introduced | CRITICAL | Not part of legacy runtime | Secret manager/file permissions, rotation, scoped bot admin rights |
| `accounts.json` / phone identifiers | HIGH | Local config, ignored by Git | Minimize stored phone data, restricted config access |
| Candidate/user DB | HIGH | Local SQLite; historical copy was committed to Git | Access control, retention/deletion, encrypted backup policy, provenance |
| Audit events/logs | MEDIUM-HIGH | Local DB/log file | Avoid unnecessary PII/secrets, retention, integrity |
| GitHub repository | HIGH | Private | PR discipline, secret scanning where available, sanitized history |
| VPS/service host | CRITICAL | Current paths are under `/root/TELEGRAM-IPTVPN` | Dedicated service user, patching, restricted SSH/admin, filesystem isolation |
| Backups | HIGH/CRITICAL | Not yet inventoried | Encryption/access/retention/restore testing |

## Trust boundaries

### TB-01 — GitHub -> deployment

Risk: source or CI credential compromise can change production behaviour.

Questions:

- Is deployment manual or automated today?
- What identity can push/deploy?
- Are production secrets ever present on developer machines or CI?

### TB-02 — Application -> Telegram

Risk: application code can act as authenticated Telegram user(s) or bot(s).

Control direction:

- narrow adapters;
- explicit policy authorization before actions;
- per-account disable state;
- bounded action classes;
- auditable outcomes.

### TB-03 — Operator -> secrets / action controls

Risk: human error or compromised operator account can trigger unintended actions or expose credentials.

Control direction:

- role separation where justified;
- confirmation for high-impact operations;
- kill switch;
- no need for direct session-file access during normal operations.

### TB-04 — Runtime -> database/backups

Risk: app or host compromise exposes candidate data and action history.

Control direction:

- least-privilege DB/service credentials;
- project isolation if multi-project architecture is accepted;
- backup access separate from ordinary application operation where practical.

## Threat register

### ST-001 — Telegram session theft

Severity: **CRITICAL**

Telethon documents that session files contain the authorization key and that possession can allow login as the account.

Potential paths:

- broad filesystem permissions;
- backup leakage;
- accidental upload;
- diagnostic bundle;
- malicious dependency/process on the same host;
- copied StringSession in environment/logs.

Controls to evaluate:

- dedicated service OS user;
- mode `0600`-equivalent access to session files;
- separate session directory outside source checkout;
- no session contents in logs/CI;
- documented active-session revocation procedure;
- decide whether sessions are backed up or re-authorized after disaster.

### ST-002 — Accidental mass action

Severity: **CRITICAL**

Potential causes:

- corrupted/missing quota state;
- configuration error;
- retry loop;
- duplicate workers;
- deployment with stale state;
- operator mistake.

Controls:

- fail-closed policy engine;
- per-project/per-account hard caps stored authoritatively;
- global kill switch;
- dry-run/shadow mode;
- explicit production enable state;
- idempotent/reconciled action attempts;
- alerting on unusual action rate.

### ST-003 — Database unavailable interpreted as zero usage

Severity: **CRITICAL**

Observed legacy risk: some data-access helpers return zero or swallow exceptions.

Controls:

- distinguish `0` from `UNKNOWN/UNAVAILABLE`;
- deny external action when authoritative state is unavailable;
- DB health surfaced separately from metrics.

### ST-004 — Git history contains sensitive runtime database

Severity: **CRITICAL**

Observed historical `users.db` blob.

Controls:

- tracked remediation issue #10;
- verified backup before history rewrite;
- post-rewrite validation;
- prevent runtime DB paths through `.gitignore` plus pre-commit/CI checks where possible.

### ST-005 — Secret leakage through configuration/logging

Severity: **HIGH**

Controls:

- typed secret fields/redaction;
- never log API hashes, bot tokens, session strings, full phone numbers;
- secret scanning where available;
- example configs contain placeholders only.

### ST-006 — Running application with excessive OS privilege

Severity: **HIGH**

Current deployment paths point to `/root`, but actual process identity is not yet verified.

Controls:

- inventory current PM2 user/process ownership;
- target non-root service account;
- restrict source/runtime directories;
- separate deploy privileges from runtime privileges.

### ST-007 — Malicious/compromised dependency

Severity: **HIGH**

Legacy dependencies are lower-bound only and not locked.

Controls:

- supported Python version;
- lockfile/constraints with hashes where appropriate;
- dependency scanning;
- minimize third-party session-storage plugins;
- review upgrades through PR/CI.

### ST-008 — Candidate/PII disclosure

Severity: **HIGH**

Controls:

- collect minimum data;
- role/access policy;
- retention/deletion;
- backups subject to same classification;
- logs avoid unnecessary identifiers;
- project isolation if required.

### ST-009 — Compromised Telegram account/session continues operating

Severity: **HIGH**

Controls:

- account health state;
- immediate disable mechanism independent of worker process;
- session revocation/runbook;
- authorization check at worker start and periodically where appropriate;
- no automatic fallback to another account purely to maintain volume after policy/security disable.

### ST-010 — Cross-project data/action leakage

Severity: **HIGH if multi-project architecture is selected**

Controls to evaluate:

- project ID on all scoped records;
- service-layer authorization;
- DB row security or separate schemas/databases only if requirements justify it;
- per-project Telegram credentials/session bindings.

## Required runtime inventory before security ADR

The following facts must be collected from the actual deployment without committing secrets:

- OS/distribution and patch level;
- process user for PM2/application;
- ownership/mode of `.env`, `accounts.json`, `.session`, `users.db`, logs;
- SSH/admin access model;
- firewall/network exposure;
- backup mechanism and location;
- Python/Telethon versions installed;
- PM2 startup/restart configuration;
- disk encryption status if relevant;
- whether session files exist in any secondary copies/snapshots.

## Candidate security ADRs

- ADR: Telegram session storage and recovery.
- ADR: Runtime service identity and filesystem layout.
- ADR: Secrets-management approach.
- ADR: Production action authorization / kill-switch model.
- ADR: Backup security and retention.

## Current conclusion

No specific secret manager or deployment security stack is selected yet. The architecture must first determine whether the final runtime is a single VPS, containerized host, or managed environment. The non-negotiable constraint is that Telegram sessions are treated as critical credentials and external action capability is tightly bounded and auditable.
