# Architecture Discovery Work Log

This log records material work in chronological order. Detailed findings belong in the linked documents/issues/PRs.

## 2026-09-07 — Discovery program initialized

### Repository access

- Confirmed ChatGPT Codex Connector installation for `Alaska-Digital`.
- Confirmed access to private repository `Alaska-Digital/telegram-iptvpn`.

### Baseline inspection

- Audited current `main` at `5a9623d191c5d2294cbc29b7af68194613bf5302`.
- Mapped complete current repository tree.
- Reviewed `.env.example`, `.gitignore`, PM2 config, support scripts, dependencies, and the full `main.py` implementation.
- Reviewed current Git history and branch state.
- Confirmed `main` is unprotected.
- Confirmed no current CI workflow associated with the audited HEAD.
- Confirmed no existing PRs/issues at baseline.

### Material findings

- Historical `users.db` remains in the initial Git commit even though removed from current HEAD.
- Current quota/metrics error handling can fail open when database state is unavailable.
- Remote Telegram action and local persistence have an ambiguous-outcome window.
- Legacy design contains extensive human-like timing/retry behaviour around Telegram limits.
- Legacy code supports Telegram published/sample Android API credentials as a fallback.
- Telethon session files are high-value credentials stored locally in the current VPS-oriented model.
- `main.py` is a monolithic ~96 KB module with import-time live configuration.
- No automated tests/CI/dependency locking exist at baseline.
- Personal-data provenance/retention/suppression are not sufficiently modeled.

### Research started

Official Telegram sources reviewed:

- API application/API ID guidance;
- API Terms of Service;
- Bot API documentation;
- user authorization documentation;
- Telegram Terms of Service.

Official EU source reviewed:

- GDPR principles and lawfulness of processing (EUR-Lex).

### Engineering process established

- Created branch `architecture-discovery` from `main`.
- Established GitHub as authoritative engineering memory.
- Added phased roadmap.
- Added requirements register.
- Added baseline audit.
- Added initial Telegram platform research.
- Added initial data/privacy research.
- Added ADR template.
- Accepted ADR-001: research-first architecture discovery before final implementation.
- Started decision log and work log.

### Next work

- Create tracked research issues/workstreams.
- Complete Telegram capability/permission matrix.
- Inventory actual runtime/VPS state without committing secrets.
- Define measurable product requirements with the project owner.
- Research datastore/state-machine alternatives.
- Build threat model.
- Compare runtime/infrastructure alternatives.
- Define PoCs required before Architecture v1.0.
