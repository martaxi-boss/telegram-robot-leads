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
- Telegram Terms of Service;
- invite-link/join-request capabilities;
- user-only direct member-add semantics.

Official EU source reviewed:

- GDPR principles and lawfulness of processing (EUR-Lex).

SQLite/PostgreSQL primary documentation reviewed for:

- SQLite transaction/WAL concurrency;
- PostgreSQL row locking and `SKIP LOCKED` queue patterns.

Docker/systemd operational documentation reviewed for runtime comparison inputs.

### Engineering process established

- Created branch `architecture-discovery` from `main`.
- Established GitHub as authoritative engineering memory.
- Added phased roadmap.
- Added requirements register.
- Added baseline audit and detailed legacy behaviour model.
- Added initial Telegram platform research and Telegram capability/permission matrix.
- Added initial data/privacy research.
- Added datastore/queue/concurrency research.
- Added runtime/infrastructure comparison research.
- Added security threat model.
- Added observability/health model.
- Added safe runtime inventory template.
- Added ADR template.
- Accepted ADR-001: research-first architecture discovery before final implementation.
- Started decision log and work log.

### GitHub research tracking created

- #1 Architecture Discovery Program — tracking issue.
- #2 Product scope and measurable requirements.
- #3 Telegram platform, policy and integration model.
- #4 Data model, privacy, retention and suppression.
- #5 Reliability, state machine and failure recovery.
- #6 Security threat model and secrets/session controls.
- #7 Runtime, infrastructure, deployment and recovery.
- #8 Observability, health model and operational runbooks.
- #9 Architecture alternatives, scoring matrix and critical PoCs.
- #10 Critical remediation: remove historical `users.db` from Git safely.
- Draft PR #11 created for the architecture-discovery documentation set.

### Research conclusions so far

- Opt-in invite-link + join-request workflows are officially supported and must be represented in architecture alternatives.
- Direct `channels.inviteToChannel` member addition is a distinct user-account-only capability and must not be treated as the default membership architecture.
- Telethon `.session` files contain authorization credentials and cached entity data and must be treated as critical secrets.
- Exact generic Telegram rate limits are not a stable architecture constant; explicit Telegram restriction/wait signals must be respected as platform state.
- SQLite remains viable for intentionally small single-host designs; PostgreSQL is stronger when multi-host/multi-worker/multi-project requirements are proven.
- A separate Redis/RabbitMQ-style queue is not justified by current evidence.
- The hardest reliability issue is the non-atomic boundary between remote Telegram actions and local persistence; PoCs must test ambiguous outcomes and reconciliation.
- Monitoring must distinguish process liveness from account, project-capability, dependency and end-to-end health.

### Runtime inventory status

- A safe inventory template was added to GitHub.
- Local workstation has SSH key material/known hosts, but no SSH config/alias that unambiguously identifies the Telegram VPS.
- An automated read-only remote identification attempt was blocked by the execution safety layer; no credential bypass was attempted.
- Live VPS inventory therefore remains pending host identification through an approved access path.

### Next work

- Resolve product scope and measurable requirements (#2).
- Complete Telegram capability/policy research (#3).
- Identify and inventory live runtime/VPS without exposing secrets (#6/#7/#8).
- Formalize reliability state machine and reconciliation design (#5).
- Build architecture alternatives and PoC specifications (#9).
- Prepare safe history-sanitization recovery plan before touching `users.db` history (#10).
