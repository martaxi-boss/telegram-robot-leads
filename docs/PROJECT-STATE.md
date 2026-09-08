# Current Project State

Updated: 2026-09-08

## Phase

**Discovery / Architecture Research**

## Objective

Audit the existing Telegram-IPTVPN project, investigate requirements and viable technical/operational alternatives, then establish a justified architecture baseline before final implementation.

## Architecture status

**Not frozen / not baselined.** Existing code is implementation evidence/reference and must not be assumed to represent the final architecture.

## Governance status

Documentation & Knowledge Governance v1 is **adopted** via `ADR-001`.

The repository is the persistent source of project knowledge; chat is a working surface.

## Confirmed process decisions

- Preserve research and evidence before final architecture selection.
- Use Docs-as-Code.
- Use stable IDs for requirements, research questions, evidence, experiments, ADRs and risks.
- Preserve accepted/superseded decisions rather than rewriting history.
- Use `PROJECT-STATE.md` + checkpoints for conversation/session continuity.
- Use GitHub Issues/Projects for transient work tracking, not as the sole store of durable architectural knowledge.
- Produce an explicit Architecture Baseline before treating implementation architecture as final.

## Current research

- Documentation/knowledge governance: completed and adopted.
- Application/domain/technical architecture: still under investigation.

## Accepted decisions

- `ADR-001` — Adopt continuous project knowledge governance model.

## Open decision areas

To be investigated and decomposed into explicit research questions before final architecture decisions, including:

- product/domain boundaries and user flows;
- Telegram integration architecture;
- IPTV provider/integration model;
- VPN provisioning/integration model;
- identity/authentication/authorization;
- payments and subscription lifecycle;
- persistence/data model;
- hosting/deployment strategy;
- security/secrets/threat model;
- observability, backups and operations;
- migration/reuse strategy for the existing implementation.

## Current risks

See `risks/risk-register.md`.

## Next phase gate

Do **not** freeze final application architecture until material research questions, requirements, constraints, risks and evidence have been captured and the proposed architecture has been validated against them.

## Resume point

Continue Discovery by inventorying the current repository/audit findings and establishing the first numbered application research questions and requirements. Use the latest file in `checkpoints/` for session-specific continuity.