# Risk Register

Updated: 2026-09-11

| ID | Risk | Probability | Impact | Status | Mitigation / next action |
|---|---|---|---|---|---|
| RISK-001 | Knowledge/decision context is lost across long sessions or project phases | Medium | High | Mitigating | Governance v1, `PROJECT-STATE.md`, ADRs and checkpoints adopted |
| RISK-002 | Existing implementation is mistaken for the final target architecture before investigation completes | Medium | High | Mitigating | Treat legacy as evidence; Architecture Baseline gate required |
| RISK-003 | Documentation becomes excessive, duplicated or stale | Medium | Medium | Mitigating | Just-enough-docs rule, authority separation, links over duplication, update triggers |
| RISK-004 | Assumptions about external IPTV/VPN/payment/provider behavior are accepted without empirical validation | Medium | High | Open | RQ-014/RQ-015/RQ-016 conditional discovery before architecture if in scope |
| RISK-005 | Security/credential handling weaknesses are inherited from prototype/current code | High | Critical | Open | Security/session lifecycle, live runtime inventory and Architecture Baseline controls |
| RISK-006 | Safety/quota authorization fails open when database state is unavailable | Medium | Critical | Open | REQ: fail closed; EXP: inject DB failures before external action |
| RISK-007 | Telegram action succeeds remotely but local state is not committed, causing unknown outcome or duplicate retry | Medium | Critical | Open | Explicit state machine, action IDs, OUTCOME_UNKNOWN + reconciliation/bounded retry |
| RISK-008 | `estado_bot.json` and SQLite disagree and stale state is treated as authoritative | Medium | High | Open | Select one authoritative state store; remove competing durable state semantics |
| RISK-009 | Historical `users.db` containing project/user data remains retrievable from Git history | High | Critical | Open | Recovery-first history-sanitization plan; validate backup/rollback before rewrite |
| RISK-010 | Telegram user-session credentials are stolen from disk, backup or operator environment | Medium | Critical | Open | Least privilege, strict filesystem/backup controls, lifecycle/revocation/runbook |
| RISK-011 | Legacy direct-add operating model triggers platform restrictions or conflicts with accepted policy/consent requirements | High | Critical | Open | G3 operating-model decision; score opt-in Bot API flows; treat restriction signals as stop/policy state |
| RISK-012 | Published/sample Telegram API credentials are used in a production path | Medium | High | Open | Require project-owned API ID/hash; remove fallback from production architecture |
| RISK-013 | Effective production configuration differs from documented configuration | High | High | Open | Typed config, one precedence contract, safe defaults, redacted effective-config diagnostics |
| RISK-014 | Action-capable features start enabled because configuration is missing/defaulted | Medium | High | Open | Safe-by-default action disabled; explicit production authorization/kill switch |
| RISK-015 | Product scope remains ambiguous, causing the wrong architecture to be optimized/built | High | Critical | Open | RQ-001 Product Definition Gate before architecture scoring |
| RISK-016 | Full IPTV/VPN/payment/customer lifecycle is intended but absent from discovery/code, forcing late redesign | Medium | Critical | Open | Conditional G4 domain discovery; explicitly include or exclude these boundaries |
| RISK-017 | Personal-data collection/profiling lacks accepted purpose, provenance, retention, suppression or deletion model | High | High | Open | RQ-008; data inventory, minimization, retention/suppression and qualified review where needed |
| RISK-018 | Heuristic region inference is treated as reliable location/eligibility data | High | Medium | Open | Justify/remove attribute; record provenance/confidence; do not use as verified location |
| RISK-019 | Unpinned dependency graph changes between builds/recovery attempts | High | High | Open | Supported runtime + lock/constraints + CI/release artifact |
| RISK-020 | Live VPS/process/filesystem/network/backup posture is materially different from repository assumptions | Unknown | Critical | Open | Sanitized live runtime inventory before security/deployment ADR |
| RISK-021 | No CI/branch protection allows unreviewed changes to authoritative code/documentation | Medium | High | Open | Introduce required checks/review protection before implementation becomes active |
| RISK-022 | Missing config examples and hard-coded `/root/TELEGRAM-IPTVPN` prevent reliable rebuild/migration | High | High | Open | Reproducible deployment contract, sanitized examples, non-root runtime design |
| RISK-023 | Backup exists but cannot meet RTO/RPO or cannot restore SQLite/WAL/session state consistently | Unknown | Critical | Open | Define RTO/RPO then execute restore EXP with complete state set |
| RISK-024 | Multi-process/multi-host scaling invalidates in-process action locks and single-host SQLite assumptions | Medium if scaled | High | Open | Do not scale before RQ-005; prove concurrency model against selected topology |
| RISK-025 | Old architecture-discovery branch/PR and Governance v1 diverge, fragmenting project truth | High | High | Mitigating | Reconcile prior evidence into Governance v1; do not force-merge conflicting PR #11 |
| RISK-026 | Roadmap dates are committed before scope/architecture/risk reduction is known | Medium | High | Mitigating | Use gate-based roadmap until Architecture Baseline G9; estimate afterwards |
| RISK-027 | Logging/metrics expose usernames, Telegram IDs or other operational personal data beyond justified retention/access | Medium | High | Open | Logging data classification/redaction, retention/access policy, production review |

Risk statuses: `Open`, `Mitigating`, `Accepted`, `Closed`.

Add new risks with stable sequential IDs; do not reuse IDs.
