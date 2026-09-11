# ADR-002 — Adopt audit-derived roadmap discovery program

Status: Accepted
Date: 2026-09-11

## Context

A deep repository and roadmap audit was completed on 2026-09-11. The audit consolidated the current `main` governance baseline, the legacy Telegram runtime, prior `architecture-discovery` research, open issues, confirmed code risks, missing product/domain boundaries, and the evidence needed before Architecture Baseline v1.0 can be accepted.

The audit produced a gate-based roadmap (`docs/roadmap/roadmap-v0.9-audit-derived.md`), an ordered research-question backlog, a roadmap-readiness requirements register, an expanded risk register, and a checkpoint.

The human project owner explicitly approved recording the complete audit and using it as the official program for continuing discovery toward the final roadmap.

## Decision drivers / constraints

- Preserve the distinction between verified facts, hypotheses, proposed requirements, and accepted architectural decisions.
- Avoid selecting implementation technology before product scope, scale, reliability, policy and recovery requirements are known.
- Preserve prior architecture-discovery work without force-merging conflicting historical branches.
- Keep GitHub as the persistent engineering memory.
- Make roadmap progress measurable through evidence-backed gates instead of premature calendar commitments.

## Options considered

1. Treat the current legacy implementation as the target architecture and start refactoring immediately.
2. Adopt the prior `architecture-discovery` roadmap unchanged.
3. Adopt the 2026-09-11 audit-derived gate program as the official discovery path, while preserving earlier research as evidence.

## Evidence / research

- `docs/research/roadmap-deep-audit-2026-09-11.md`
- `docs/research/roadmap-research-questions.md`
- `docs/evidence/EV-001-roadmap-audit-source-register.md`
- `docs/requirements/roadmap-readiness-requirements.md`
- `docs/roadmap/roadmap-v0.9-audit-derived.md`
- `docs/checkpoints/2026-09-11-roadmap-deep-audit.md`
- GitHub issues #1-#10 and prior draft PR #11

## Decision

Adopt `docs/roadmap/roadmap-v0.9-audit-derived.md` as the official gate-based program for completing discovery, architecture selection, implementation readiness, production hardening and controlled migration.

This acceptance applies to the **program structure, ordering logic, evidence requirements and gates**. It does **not** automatically accept every proposed requirement, architecture hypothesis, datastore choice, Telegram operating model, infrastructure option, provider integration, or implementation technology contained in supporting research.

The next critical-path gate is **G1 — Product Definition**.

Implementation dates and calendar commitments must not be attached to the final engineering roadmap until Architecture Baseline v1.0 is accepted, except for independently justified administrative/security remediation work that does not prejudge application architecture.

## Consequences

### Positive

- The project now has one explicit path from discovery to Architecture Baseline and production.
- Prior research remains reusable without being confused with accepted architecture.
- Major decisions must be backed by requirements/evidence/experiments.
- Technical work can proceed in parallel where it does not bypass upstream gates.
- Future chats and agents can recover the program state directly from GitHub.

### Negative / trade-offs

- Some implementation decisions and dates remain intentionally deferred.
- Product owners must resolve scope and measurable outcomes before architecture can be frozen.
- Additional runtime inventory and PoCs are required before production architecture selection.

## Risks

- Pressure to treat proposed requirements as accepted merely because the roadmap program is accepted.
- Premature implementation can still create architecture lock-in if gate discipline is ignored.
- Direct writes to an unprotected `main` branch remain an operational governance risk until repository controls are improved.

## Supersedes

None. Prior architecture-discovery roadmap material remains historical/evidential input.

## Superseded by

None

## Verification / follow-up

- Update `docs/PROJECT-STATE.md` to record ADR-002 and G1 as the active critical-path gate.
- Update the current governance-level roadmap to point to the adopted audit-derived program.
- Keep proposed requirements in proposed state until their corresponding gates explicitly accept them.
- Preserve and reconcile useful evidence from `architecture-discovery` / PR #11.
- Continue from G1 Product Definition.
