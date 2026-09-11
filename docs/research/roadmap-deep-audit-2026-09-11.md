# Deep Audit for Final Roadmap — 2026-09-11

Status: **IN PROGRESS / AUDIT EVIDENCE**
Date: 2026-09-11
Scope: repository, legacy runtime model, existing architecture-discovery work, roadmap readiness and external platform constraints.

> This document is research evidence. It does not freeze the application architecture and does not authorize production behaviour.

## Executive conclusion

The project is **not ready for a final implementation schedule**, but it is ready for a rigorous evidence-driven roadmap with explicit decision gates.

The existing `architecture-discovery` work is valuable and should be preserved, but it predates the adopted Documentation & Knowledge Governance v1 on `main` and its draft PR #11 now conflicts with current `main`. The correct course is to reconcile/reuse its evidence rather than discard it or force-merge it.

The principal blocker to Architecture Baseline is **product definition**, not a missing technology choice. The repository implements a legacy Telegram acquisition/automation runtime; it does not establish whether the intended product boundary is that subsystem alone or a wider IPTV/VPN/customer/subscription platform. Architecture and delivery dates would be false precision until that boundary, scale, risk tolerance and operating model are explicit.

## Evidence base reviewed

### Current `main`

- `main.py` — legacy Telethon/SQLite runtime (~95.7 KB).
- `.env.example` — configuration defaults and runtime switches.
- `ecosystem.config.js` — PM2 deployment assumptions.
- `requirements.txt` — four direct Python dependencies with lower bounds only.
- `.gitignore` — runtime/secrets exclusions.
- `scripts/check_db.py`, `scripts/telegram-iptvpn-status.sh`, `ver_metricas.py` — operational tooling.
- current Git history, branch state and repository tree.
- Documentation & Knowledge Governance v1, current PROJECT-STATE and governance-level roadmap.

### Existing `architecture-discovery` branch

Preserved and reviewed as prior evidence:

- baseline audit;
- current-behaviour model;
- proposed architecture roadmap;
- requirements register;
- Telegram platform/capability research;
- data/privacy research;
- datastore/queue research;
- runtime/infrastructure research;
- security threat model;
- observability/health research;
- testing strategy;
- work log;
- issues #1–#10 and draft PR #11.

### Current primary external sources revalidated

- Telegram API ID/application guidance.
- Telegram API Terms of Service.
- Telegram Bot API.
- Telegram `channels.inviteToChannel` method documentation.
- Telethon stable session-file documentation.
- SQLite WAL / appropriate-use documentation.
- PostgreSQL locking / `SKIP LOCKED` documentation.
- EDPB guidance on Data Protection by Design and by Default.

## A. Repository and engineering baseline

### FIND-001 — Current repository is operational legacy code plus newly adopted governance

Confirmed.

The executable surface is very small in file count but highly concentrated in one large `main.py`. There is no modular application/package structure and no independent domain/integration layers.

Impact: high. This makes change coupling, testing, failure isolation and safe migration harder.

### FIND-002 — No CI workflow on current `main`

Confirmed.

No `.github/workflows` directory exists in current `main`.

Impact: high before implementation/migration. Tests, type/static checks, dependency checks and documentation validations cannot currently act as merge gates.

### FIND-003 — `main` remains unprotected

Confirmed on 2026-09-11.

Impact: high now that `main` is the authoritative knowledge source. A mistaken direct push could change both code and project truth without review/checks.

### FIND-004 — Dependencies are non-reproducible

Confirmed.

`requirements.txt` contains lower-bound constraints (`>=`) only. Reinstalling at a later date may resolve a different dependency graph. No lock/constraints file or recorded supported Python runtime is authoritative on `main`.

Impact: high for repeatable tests/deployments and incident recovery.

### FIND-005 — Referenced configuration examples are missing

Confirmed.

The code refers to `accounts.json.example` and `telegram_api.json.example`, but neither file exists on current `main`.

Impact: medium-high. A new operator cannot reconstruct the intended runtime contract from Git alone.

### FIND-006 — Deployment is host/path specific

Confirmed.

`ecosystem.config.js` assumes `/root/TELEGRAM-IPTVPN` and a local `.venv`.

Impact: high for least privilege, staging, reproducibility and migration. The actual process identity/permissions on the live VPS remain unverified.

## B. Configuration and source-of-truth audit

### FIND-007 — Configuration drift already exists

Confirmed.

`.env.example` sets `MAX_ADDS_PROJECT_PER_DAY=70`, while `ecosystem.config.js` injects `MAX_ADDS_PROJECT_PER_DAY=100` and `DOTENV_OVERRIDE=1`.

Impact: high. The effective configuration depends on precedence and deployment wrapper rather than a single validated contract.

Required roadmap consequence: typed configuration, startup validation, explicit environment overlays, safe defaults and a documented effective-config diagnostic that redacts secrets.

### FIND-008 — Production-capable actions default to enabled in legacy code/config examples

Confirmed.

Legacy code defaults `TELEGRAM_INVITES_ENABLED` and scraping to enabled when the values are absent, and `.env.example` shows both enabled.

Impact: high. Future production action capability should be explicitly enabled through policy/production state, not accidental absence of configuration.

### FIND-009 — Target/source assumptions are embedded in code/config

Confirmed.

The target `@iptvpncode`, regional buckets, search keywords and many source group handles are embedded in the runtime/configuration.

Impact: high if the target is a reusable or multi-project system; medium if the accepted product is permanently single-project.

## C. State, database and correctness audit

### FIND-010 — Safety/accounting reads can fail open

**Confirmed critical.**

Functions used to determine queue and daily/project action counts catch broad database errors and return `0`; several audit/metric writes catch and ignore exceptions.

This means “authoritative state unavailable” can be interpreted as “zero usage / empty history,” which is unsafe for any action whose authorization depends on counters/state.

Required target property: **fail closed** for external action authorization when required state is unavailable.

### FIND-011 — Remote Telegram action and local persistence are not atomic

**Confirmed high/critical.**

The flow calls `InviteToChannelRequest(...)` and only afterwards updates local user state and metrics. A timeout/crash/network ambiguity after Telegram accepted the operation but before local commit can leave the local record retryable/unknown.

Required roadmap consequence: explicit action state machine, action IDs, idempotency where possible, `OUTCOME_UNKNOWN` semantics and reconciliation/bounded retry.

### FIND-012 — Stale `processing` recovery can amplify ambiguous outcomes

Confirmed.

Claims older than `STALE_PROCESSING_SEC` are reset to `pending`. Without durable remote-action reconciliation, a process that died during/after a successful remote action can later cause another attempt.

### FIND-013 — Two overlapping sources of user/action state exist

Confirmed.

SQLite stores user status, while `estado_bot.json` stores overlapping status/session state. Claim and status-update paths write these stores in different orders. The worker may use JSON final state to overwrite DB state.

Impact: high. Crash/write failure can produce disagreement about what is authoritative.

Required target property: one authoritative state model; caches/derived views must not compete with it.

### FIND-014 — SQLite is not disproven, but its suitability is requirement-dependent

Confirmed by primary SQLite documentation and existing research.

SQLite WAL supports concurrent readers and a writer, but all WAL participants must be on the same host and there is still only one writer at a time. This can be a good fit for an intentionally small single-host design; it is not a sound default for a proven multi-host/multi-writer platform.

The legacy uses WAL plus `PRAGMA synchronous=NORMAL`; SQLite documents that this trades stronger power-loss durability for performance. RPO requirements therefore materially affect the datastore/durability decision.

### FIND-015 — No migration framework / schema version contract

Confirmed.

Schema is created and altered from application startup, including broad exception swallowing around `ALTER TABLE`. There is no explicit migration version history or rollback/test contract.

Impact: high before controlled production migration.

### FIND-016 — Per-candidate ingest commits are operationally chatty

Confirmed.

The scraper commits each successful candidate insert separately. This is not necessarily a current bottleneck, but it should be measured rather than carried into a new architecture by accident.

## D. Telegram integration and operating-model audit

### FIND-017 — Legacy runtime is a user-account MTProto automation, not a Bot API-first design

Confirmed.

It uses Telethon user sessions and `channels.inviteToChannel` semantics to add users directly to a target community.

Telegram's current method documentation states `channels.inviteToChannel` is user-only.

### FIND-018 — Supported opt-in alternatives exist and must be scored

Revalidated.

The current Bot API supports bot-created invite links that create join requests and bot approval/decline of join requests when the bot has the required admin permission. It also exposes invite-link context with the request.

This does not prove that opt-in is the selected product model, but it proves a Bot API-led architecture is a real alternative and must not be excluded by assuming the legacy direct-add mechanism is a requirement.

### FIND-019 — Legacy anti-abuse handling must not become a design objective

**Confirmed critical platform risk.**

The legacy runtime contains extensive “human-like” timing/jitter schedules and retries after `PeerFlood` with comments that it should continue/retry rather than treat the signal as a stop condition.

Current Telegram guidance explicitly warns that API libraries are monitored for abuse and that flooding/spamming can cause permanent bans. The final architecture must treat restrictions as platform/policy state, not something to conceal or optimize around.

### FIND-020 — Project-owned Telegram API credentials are required for a production design

Confirmed.

Legacy code contains the Telegram Android sample/published API ID/hash fallback. Telegram's current guidance states sample API IDs are limited and not suitable for end-user production use; applications must obtain their own API ID.

### FIND-021 — Telethon session files are critical credentials and may also cache personal data

Confirmed.

Telethon stable documentation states the session contains the authorization key and enough information to log into the account, and its default SQLite session can cache entity details. Session compromise therefore belongs in the critical-secret threat model and backup/recovery design.

## E. Privacy/data governance audit

### FIND-022 — Legacy data collection exceeds a minimal membership/action ledger

Confirmed.

The runtime collects Telegram user IDs, usernames, inferred region, source-derived candidates, activity-derived eligibility and action/audit information. Session files may cache additional Telegram entity information.

### FIND-023 — Provenance, retention and suppression are not complete domain concepts

Confirmed.

The existing `users` model has no normalized provenance of why/where a candidate was collected, no accepted retention TTL, no durable suppression model and no rights/deletion workflow.

### FIND-024 — Region classification is heuristic profiling, not verified location

Confirmed.

The current runtime infers PT/ES versus Europe from name characters and `langdetect`; missing values can be defaulted to PT/ES for legacy pending rows.

Impact: medium/high depending on whether region affects eligibility/business decisions. Final requirements must first justify whether this attribute is needed at all.

### FIND-025 — Privacy/legal basis remains a product gate

Open, high impact.

EDPB guidance reinforces that data-protection-by-design/default belongs in system design, not as a later database patch. The lawful basis, transparency, retention and rights-handling model for any personal-data processing requires product-specific and, where necessary, qualified legal/compliance review.

## F. Security/recovery audit

### FIND-026 — A historical runtime database remains in Git history

**Confirmed critical historical exposure.**

Commit `56c4996400e46e43666dfb947679ab1efdaab180` removed `users.db` and added it to `.gitignore`; its parent still references the historical database blob. Do not rewrite history until a tested recovery copy and rollback procedure exist.

### FIND-027 — Live runtime/VPS security posture is still unknown

Open, high/critical impact.

We do not yet have verified current facts for process user, session/.env permissions, firewall/exposure, SSH/admin model, backup location/encryption, reboot behaviour, installed dependency versions, disk/security controls or secondary session/database copies.

This blocks a production security ADR and controlled migration plan.

### FIND-028 — Emergency disable exists only as configuration/runtime behaviour, not a fully designed independent kill switch

Confirmed gap.

Environment flags can disable invitations/accounts, but the target architecture needs a deliberate, testable action-disable mechanism with defined scope and failure semantics.

## G. Testing, delivery and observability audit

### FIND-029 — No automated tests are present in current main

Confirmed from repository tree.

### FIND-030 — No layered health contract exists in implementation

Confirmed.

PM2 status, logs and DB metrics exist, but “process running” does not establish Telegram session authorization, DB safety-state availability, target capability, queue progress or end-to-end operation.

Existing architecture research proposes H0 process -> H1 local dependencies -> H2 Telegram/account -> H3 project capability -> H4 end-to-end. This remains a strong design input.

### FIND-031 — Backup/restore evidence is missing

Confirmed as an open operational requirement. No tested restore evidence is stored in current `main`.

### FIND-032 — Local-first PoC strategy remains sound but workstation evidence is stale

The existing discovery work accepted workstation/WSL2-first testing, moving to staging only for host/session/runtime-specific hypotheses. That principle remains valid. Environment/package status recorded on 2026-09-08 must be rechecked before PoC execution rather than assumed current.

## H. Product/domain scope audit

### FIND-033 — Product scope is still the highest-leverage unanswered question

**Critical roadmap blocker.**

Issue #2 remains open. The repository does not tell us whether the target is:

1. one Telegram community acquisition tool;
2. a reusable internal Telegram operations platform;
3. a multi-project/client platform;
4. a broader IPTV/VPN customer/subscription platform of which Telegram acquisition is one subsystem.

The architecture cost/complexity difference between these models is substantial.

### FIND-034 — The repository does not implement a full IPTV/VPN commerce/provisioning platform

Confirmed from current tree/dependencies.

There is no identifiable domain implementation for customer subscriptions, payments, entitlement, IPTV provider provisioning, VPN provisioning, renewals/suspension, customer credential delivery, support/admin workflow or provider reconciliation.

If any of those are intended final scope, they require dedicated discovery/research workstreams before Architecture v1.0. If they are out of scope, that must be explicitly recorded so the roadmap does not overbuild.

### FIND-035 — Business success criteria and scale remain undefined

Open.

Without accepted targets for projects/accounts/events/users, availability, data retention, operator model, acceptable latency, RTO/RPO and cost envelope, datastore/runtime/scaling decisions cannot be scored rigorously.

## I. Documentation/repository continuity audit

### FIND-036 — Prior research is substantial but lives on a now-conflicting branch

Confirmed.

Draft PR #11 has 23 commits and 19 changed files but is currently not mergeable with `main`. Its research should be imported/reconciled into the adopted v1 knowledge structure rather than duplicated or lost.

### FIND-037 — The new governance structure is currently the authoritative model

Confirmed by ADR-001 on `main`.

Current research should use stable `REQ/RQ/EV/EXP/ADR/RISK` identifiers and `PROJECT-STATE`/checkpoints.

## Roadmap readiness assessment

| Area | Evidence maturity | Decision readiness | Blocks Architecture Baseline? |
|---|---|---|---|
| Legacy code/behaviour | High | High for classification, not migration | Yes, until classification |
| Documentation governance | High | Accepted | No |
| Product scope | Low | Not ready | **Yes — critical** |
| Business KPIs | Low | Not ready | **Yes** |
| Telegram capability facts | High | Candidate designs possible | **Yes — operating model decision** |
| Telegram compliance/sustainability | Medium-high | Needs product/legal boundary | **Yes** |
| Privacy/data purpose | Medium | Needs product/legal inputs | **Yes** |
| Reliability/state-machine problem | High | Design/PoCs needed | **Yes** |
| Datastore | Medium-high | Blocked by scale/RPO | Yes |
| Runtime/infrastructure | Medium | Blocked by live inventory + SLO/scale | Yes |
| Security threat model | Medium-high | Blocked by live inventory/architecture | Yes |
| Observability model | Medium-high | Final metrics blocked by SLO/product | Yes |
| Testing approach | Medium-high | Discovery strategy accepted | No |
| Live VPS inventory | Low | Not ready | **Yes for production plan** |
| CI/release engineering | High gap evidence | Direction clear | No for architecture; yes before implementation merge |
| IPTV/VPN provisioning | Unknown / absent | Conditional on product scope | **Yes if in scope** |
| Payments/subscriptions | Unknown / absent | Conditional on product scope | **Yes if in scope** |
| Migration/cutover | Medium | Blocked by final architecture/runtime inventory | Yes for production |

## Critical-path conclusion

The shortest safe path to a final roadmap is **not** to evaluate more frameworks first. It is:

1. reconcile existing discovery evidence into Governance v1;
2. close product scope and measurable outcome;
3. classify legacy behaviours as PRESERVE / REDESIGN / REMOVE / RESEARCH / LEGACY-DEAD;
4. establish explicit safety/compliance boundaries for Telegram acquisition/actions;
5. define scale, SLO, RTO, RPO, retention and cost envelope;
6. inventory the live runtime/VPS safely;
7. resolve conditional full-platform workstreams (IPTV/VPN/payment/identity) based on product scope;
8. formalize state machine and failure semantics;
9. compare 2–4 complete architecture alternatives with weighted criteria;
10. run only critical PoCs whose outcomes can change the architecture choice;
11. accept Architecture Baseline v1.0 via ADR(s);
12. derive implementation sequencing, effort and calendar from the accepted baseline.

## Recommended no-regret actions before Architecture Baseline

These do not require choosing the final application architecture:

- preserve/reconcile prior research;
- protect authoritative documentation through PR discipline;
- introduce CI for documentation/basic static checks when implementation work starts;
- define configuration contract and missing sanitized examples;
- establish test harness with fake/mock Telegram adapters;
- document live runtime inventory without secrets;
- design/verify backup before history rewrite;
- prevent new runtime DB/secrets from entering Git;
- define all high-impact open requirements;
- make any real external-action testing explicitly bounded, opt-in/test-scoped and reversible.

## Explicit non-decisions

This audit does **not** decide:

- SQLite vs PostgreSQL;
- systemd vs Docker Compose vs managed platform;
- Telethon vs Bot API responsibilities;
- acquisition flow;
- single-project vs multi-project architecture;
- whether IPTV/VPN/payment provisioning is in this repository's scope;
- production migration date;
- capacity targets;
- final component boundaries.

Those choices must be consequences of accepted requirements and evidence, not assumptions inherited from the legacy implementation.
