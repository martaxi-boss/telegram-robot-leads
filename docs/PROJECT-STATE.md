# Current Project State

Updated: 2026-09-11

## Phase

**Discovery / Final-Roadmap Preparation**

## Objective

Use the legacy repository, existing architecture-discovery evidence and current external platform constraints to close the high-impact requirements/risks needed for an evidence-backed Architecture Baseline and final implementation roadmap.

## Architecture status

**Not frozen / not baselined.**

The current `main.py` is a legacy operational baseline and evidence source. It is not the requirements specification and must not be scaled/refactored as if its current behaviors were already approved.

## Governance status

Documentation & Knowledge Governance v1 is **adopted** via `ADR-001`.

The audit-derived roadmap discovery program is **adopted** via `ADR-002`.

The repository is the persistent project knowledge source; chat is a working/reasoning surface.

## Roadmap audit status

Deep roadmap audit completed at repository/evidence level on 2026-09-11 and recorded in:

- `research/roadmap-deep-audit-2026-09-11.md`
- `research/roadmap-research-questions.md`
- `evidence/EV-001-roadmap-audit-source-register.md`
- `requirements/roadmap-readiness-requirements.md`
- `roadmap/roadmap-v0.9-audit-derived.md`
- `risks/risk-register.md`
- `decisions/ADR-002-roadmap-discovery-program.md`

`roadmap-v0.9-audit-derived.md` is now the **accepted discovery/program structure**, but it is still **not a calendar commitment and not yet the final implementation roadmap**. Acceptance covers its gates, ordering logic and evidence discipline; technical hypotheses and proposed requirements remain subject to their own decision gates.

## Key confirmed findings

- legacy implementation is concentrated in a large Telethon/SQLite `main.py` with project-specific behavior;
- current repository has no automated CI workflow and `main` was unprotected when audited;
- dependency resolution is not reproducibly locked;
- runtime/configuration has competing values/precedence (including project daily cap drift);
- DB-dependent safety/accounting paths can fail open by returning zero or suppressing failures;
- external Telegram action and local persistence have an ambiguous crash/timeout window;
- SQLite and `estado_bot.json` overlap as state sources;
- Telegram session files are critical credentials;
- published/sample Telegram API credential fallback is unsuitable as a production target;
- historical `users.db` remains in Git history and requires recovery-first remediation;
- live VPS/process/filesystem/backup posture is not yet verified;
- legacy user-account direct-add behavior must not be assumed to be the accepted future operating model;
- current repo does not implement a full IPTV/VPN/payment/customer provisioning platform.

## Highest-priority open decisions

### G1 — Product Definition

- Is the system an acquisition subsystem, internal Telegram platform, multi-project platform, or full IPTV/VPN customer platform?
- What measurable outcome/KPIs define success?
- Which legacy behaviors are required vs removed/redesigned?
- What actions are allowed/conditional/prohibited and which require approval?

### G2 — Measurable Requirements

- scale/capacity envelope;
- SLO/availability;
- RTO/RPO;
- retention;
- operator model;
- cost/resource envelope.

### G3/G4 — Operating & Domain Boundary

- Bot API vs MTProto responsibilities;
- privacy/data purpose/retention/suppression;
- session/credential lifecycle;
- whether IPTV/VPN/payment/entitlement/customer lifecycle is in or out of this repo's system boundary.

## Critical engineering risks

See `risks/risk-register.md`. Current P0/critical themes include:

- fail-open authorization;
- ambiguous external-action outcomes;
- historical runtime DB in Git;
- session credential compromise;
- platform-policy sustainability;
- product-scope ambiguity;
- unknown live runtime/recovery posture.

## Prior architecture-discovery work

The `architecture-discovery` branch and draft PR #11 contain valuable prior research (23 commits / 19 changed files at audit time) but currently conflict with newer `main` governance. Preserve and reconcile their evidence; do not force-merge or discard them.

## Next gate

**G1 — Product Definition Gate** is the next decision gate on the critical path.

In parallel, evidence-only work may continue on:

- sanitized live VPS inventory;
- reconciliation/import of prior discovery research;
- security/privacy data inventory;
- repository-history recovery plan;
- local mock/test harness readiness.

These activities may reduce uncertainty but must not freeze application architecture independently.

## Architecture Baseline rule

Do **not** accept Architecture Baseline v1.0 until product scope, measurable quality/scale requirements, sustainable platform/data operating model, conditional IPTV/VPN/payment boundaries, correctness/state semantics, runtime/recovery model and decision-changing PoCs are sufficiently resolved.

## Schedule rule

Do not attach implementation dates to the final roadmap before Architecture Baseline v1.0. Track current progress by gates/evidence maturity; derive effort/calendar after the baseline is accepted.

## Approval record

On 2026-09-11, the project owner explicitly approved recording the full deep-audit output and adopting the audit-derived roadmap discovery program. This approval is captured in `ADR-002` and does not pre-approve unresolved technical choices.

## Resume point

Continue from `roadmap/roadmap-v0.9-audit-derived.md` at **Stage 1 / G1 Product Definition** while parallel evidence collection proceeds. Use `research/roadmap-research-questions.md` as the ordered research backlog.
