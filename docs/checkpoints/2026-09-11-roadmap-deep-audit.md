# Project Checkpoint — Deep Roadmap Audit

Date: 2026-09-11
Phase: Discovery / Final-Roadmap Preparation

## Objective

Audit repository, prior architecture-discovery evidence, external platform constraints and roadmap gaps deeply enough to define the decision gates required before final Architecture v1.0 and an implementation schedule.

## Work completed

- audited current `main` repository tree, branch protection and CI absence;
- inspected current legacy `main.py` across startup/config, queue/state, scraping, external-action and recovery paths;
- verified `.env.example`, PM2 configuration, dependencies and `.gitignore`;
- verified historical `users.db` removal commit while confirming historical retention risk;
- reviewed prior `architecture-discovery` branch, roadmap, requirements, research, issues and PR #11;
- revalidated Telegram capability/terms/session facts against current official sources;
- revalidated SQLite/PostgreSQL architectural constraints against primary docs;
- revalidated data-protection-by-design as an architecture concern;
- identified the product-boundary gap between the legacy Telegram acquisition runtime and any broader IPTV/VPN/payment/customer platform;
- created ordered RQ register, expanded risk register, candidate requirements and audit-derived roadmap v0.9;
- updated `PROJECT-STATE.md`.

## Durable artifacts created/updated

- `docs/research/roadmap-deep-audit-2026-09-11.md`
- `docs/research/roadmap-research-questions.md`
- `docs/evidence/EV-001-roadmap-audit-source-register.md`
- `docs/requirements/roadmap-readiness-requirements.md`
- `docs/roadmap/roadmap-v0.9-audit-derived.md`
- `docs/risks/risk-register.md`
- `docs/PROJECT-STATE.md`

## Architecture decisions accepted

None beyond existing governance `ADR-001`.

No application architecture, datastore, runtime, Telegram integration or product-scope choice was frozen during this audit.

## Most important confirmed findings

1. product boundary is still the highest-impact uncertainty;
2. DB-dependent action authorization can fail open in legacy code;
3. remote Telegram side effect + local persistence has an ambiguous-outcome window;
4. SQLite + `estado_bot.json` create overlapping state authority;
5. direct-add/user-session Telegram behavior must be re-evaluated against current platform capabilities/policy rather than preserved automatically;
6. session files are critical credentials;
7. historical `users.db` remains a recovery-first remediation item;
8. production config has drift/precedence ambiguity;
9. no CI and current main was unprotected at audit time;
10. live VPS/recovery facts remain unverified;
11. no full IPTV/VPN/payment/customer provisioning implementation exists in current repo;
12. the prior discovery PR #11 is valuable evidence but currently conflicts with new `main` governance.

## Current roadmap state

`docs/roadmap/roadmap-v0.9-audit-derived.md` defines 14 stages/gates from evidence reconciliation through production evolution.

It is intentionally **DRAFT**, because final implementation sequencing/dates depend on resolving G1–G9, especially product scope and measurable requirements.

## Next critical gate

**G1 — Product Definition Gate**.

Resolve at minimum:

- RQ-001 product/system boundary;
- RQ-002 measurable business outcome/KPIs;
- RQ-003 allowed/conditional/prohibited external actions;
- RQ-004 legacy behavior classification;
- operator/approval model;
- cost/resource envelope direction.

## Parallel no-regret evidence work

- sanitized live VPS inventory;
- reconcile/import prior discovery evidence into Governance v1;
- security/privacy inventory;
- repository history remediation recovery plan;
- local mock/test harness readiness.

## Exact resume point

Read in order:

1. `docs/PROJECT-STATE.md`
2. `docs/roadmap/roadmap-v0.9-audit-derived.md`
3. `docs/research/roadmap-research-questions.md`
4. `docs/research/roadmap-deep-audit-2026-09-11.md`
5. `docs/risks/risk-register.md`

Then continue Stage 1 / G1 Product Definition. Do not convert the draft roadmap into calendar commitments before Architecture Baseline v1.0 is accepted.
