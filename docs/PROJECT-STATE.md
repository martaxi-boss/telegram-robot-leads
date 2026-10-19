# Current Project State

Updated: 2026-10-19 (feature branch; production status remains dated 2026-10-18)

## New capability under test (not yet proven in production)

Public niche-group discovery has been added to the existing safe PM2 runtime.
It queries only the Telegram public-chat search API and records public group
usernames/titles, **not members**. The daily runner is enabled in the new
`ecosystem.config.js` and shares both existing project accounts without
creating a new worker. Public voluntary joining via the target group's
public URL requires no additional BotFather token. See
`docs/PUBLIC_GROUP_DISCOVERY.md`.

**Deployment note:** the already prepared 2026-10-20 activation is pinned to
source commit `5e18982`. Merging this feature is not evidence that the VPS
was upgraded: the new commit must be staged and independently verified.
Consent, privacy and Telegram restriction guards remain operative.

## Canonical runtime update (2026-10-18)

The live `main` branch now uses a short `main.py` wrapper which invokes `scripts/safe_runtime.py`; the historical 2,312-line discovery/scraping/addition engine is **not the active entrypoint**. The canonical process name is `telegram-robot-leads` in `ecosystem.config.js`. Allowed input files are `group_allowlist.txt` and `approved_users.txt` in the project-specific private vault. The new runtime has durable state, a pre-network-action ambiguity journal and single-instance file locking. It does not harvest members or discover other groups. The presence of these files never substitutes for valid, demonstrable user permission.

The older architecture assessment and original 49-test result below are **historical evidence, not the latest implementation certification**. The latest safe runtime was integrated by PR #22, and the subsequent reliability/hygiene changes are tracked separately in PR #24. Before a production claim, certify the exact merged commit, verify private application credentials, state and path permissions, and execute a separately bounded VPS deployment check. Do not operate the former legacy engine or reuse the unrelated IPTV bot's credentials or processes.

## Phase

**Legacy recovery and safe diagnostics; discovery architecture still unapproved for production**

## Current verified operational state (2026-10-18)

- Official repo: `martaxi-boss/telegram-robot-leads`, previously labeled `TELEGRAM-IPTVPN` as an operational name. Do not confuse with an independent IPTV posting bot or the Project Leader Telegram Supervisor.
- Canonical protected VPS vault `/root/project-secrets/telegram-robot-leads/` retains the two existing `.session` files and account configuration. The separate former Leads vault directory was removed by a verified rename, not by deleting/recreating credentials.
- [Real two-account online verification](https://github.com/martaxi-boss/VPS/actions/runs/39166864689): both sessions authenticated, connected, identities confirmed, and phone numbers matched the vault account configuration. No members were added, no messages sent.
- The direct SQLiteSession constructor failed with `ValueError` for these stored sessions under the probe Telethon version. A read-only four-column SQLite extraction into Telethon `MemorySession` succeeded for **both**, without mutating either original session.
- [Last verified repository CI](https://github.com/martaxi-boss/telegram-robot-leads/actions/runs/39160879832) passed 49 offline tests; this does **not** certify the old 2,312-line direct-add `main.py`, which has only syntax checking in that CI.
- The read-only VPS audit #39160115127 found **no active Telegram Robot Leads worker**. The original PM2 config still points at an old, nonexistent runtime path; do not run it unchanged.
- New `scripts/telethon_sessions.py` adds independent offline/live session diagnosis and optional explicit voluntary group-link creation with the two existing Telethon identities. It does not run or repair the legacy direct-add engine and does not require a BotFather token.
- Original `main.py` does direct additions by `InviteToChannelRequest`, not just share links. Its third-party group scraping, unsolicited additions, flood-retry logic and unproven data consent/retention remain excluded from production approval.
- Exact source/CI, deploy proof for new scripts, the consent-based operating model and a controlled end-to-end test remain required before claiming a production-ready service.

## Objective

Use the legacy repository, existing architecture-discovery evidence and current external platform constraints to close the high-impact requirements/risks needed for an evidence-backed Architecture Baseline and final implementation roadmap.

## Architecture status

**Not frozen / not baselined.**

The current `main.py` is a legacy operational baseline and evidence source. It is not the requirements specification and must not be scaled/refactored as if its current behaviors were already approved.

## Governance status

Documentation & Knowledge Governance v1 is **adopted** via `ADR-001`.

The audit-derived roadmap discovery program is **adopted** via `ADR-002`.

Agent supervision and delegation governance is **adopted** via `ADR-003`. Root `AGENTS.md` is the canonical repository agent entrypoint and `.ai/EXECUTOR_AGENT_PROMPT_TEMPLATE.md` is the canonical Supervisor-to-Executor delegation template. Delegation cannot expand explicit human authorization.

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
- a minimal offline CI has since been added (49 tests on 2026-10-18), but legacy `main.py` runtime behavior and branch protection are not certified;
- dependency resolution is not reproducibly locked;
- runtime/configuration has competing values/precedence (including project daily cap drift);
- DB-dependent safety/accounting paths can fail open by returning zero or suppressing failures;
- external Telegram action and local persistence have an ambiguous crash/timeout window;
- SQLite and `estado_bot.json` overlap as state sources;
- Telegram session files are critical credentials;
- published/sample Telegram API credential fallback is unsuitable as a production target;
- historical `users.db` remains in Git history and requires recovery-first remediation;
- live vault, session and backup evidence has now been partly verified; the original active service is still absent and disaster recovery remains unproven;
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

On 2026-09-12, the project owner explicitly authorized persistence of the Supervisor/Auditor posture, non-expanding delegation rule and canonical executor prompt as a Git-side agent-governance convention. This approval is captured in `ADR-003` and does not authorize any application, release, runtime, infrastructure or subsequent implementation phase.

## Resume point

Continue from `roadmap/roadmap-v0.9-audit-derived.md` at **Stage 1 / G1 Product Definition** while parallel evidence collection proceeds. Use `research/roadmap-research-questions.md` as the ordered research backlog.
