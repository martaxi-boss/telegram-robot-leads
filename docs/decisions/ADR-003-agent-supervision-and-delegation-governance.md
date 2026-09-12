# ADR-003 — Agent supervision and delegation governance

Status: Accepted
Date: 2026-09-12

## Context

The repository already treats Git as the persistent project knowledge source and requires evidence-backed decision gates, but it did not yet define a canonical repository-level operating contract for agents explicitly acting as Supervisor, Auditor or Supervisor/Auditor, nor a canonical executor delegation template.

Without such a contract, a supervising agent could over-rely on chat claims or stale checkpoints, accept executor self-reporting without Git verification, infer authority from a roadmap or green checks, or accidentally broaden a human authorization when delegating implementation.

The project owner explicitly authorized persisting this convention in Git as an agent-governance-only change and required a minimal, non-duplicative design.

## Decision drivers / constraints

- Live repository/source/certification evidence must outrank chat assertions and stale/static anchors for consequential claims.
- Supervisory agents need a durable posture for audit, drift detection, roadmap-first governance and authorization control.
- Delegation must preserve, never expand, explicit human authority.
- Executors need one canonical prompt template rather than copied mutable policy text in multiple places.
- The change must not alter production source, public contracts, versions, release state, runtime/deployment state, ownership/routing policy or ChatGPT Project UI instructions.
- Existing Documentation & Knowledge Governance v1 requires a new ADR for governance changes.

## Options considered

### A. Store the full convention only in `docs/GOVERNANCE.md`

Rejected. This would make agent-specific operating instructions less discoverable to repository agents and would mix the general knowledge-governance policy with an execution-specific entrypoint.

### B. Duplicate the full supervisor and executor rules in several governance files

Rejected. Multiple mutable copies would create drift and conflicting authority.

### C. Add one repository-level agent entrypoint plus one canonical executor template, with an ADR documenting adoption

Accepted. `AGENTS.md` is the authoritative agent entrypoint; it references `.ai/EXECUTOR_AGENT_PROMPT_TEMPLATE.md` instead of embedding a second independently maintained executor template. This ADR records the governance decision and rationale.

## Evidence / research

Repository state verified before adoption:

- `main` at `012f855707ae638297219a13f9db2db9c1426e73` before this change;
- open PR #11 on `architecture-discovery`, with no overlapping `AGENTS.md` or `.ai/` changes;
- no pre-existing `AGENTS.md`;
- no `.ai/project.json` or equivalent router state on `main`;
- no GitHub Actions workflow or commit-status certification associated with the pre-change `main`;
- `docs/GOVERNANCE.md` requires governance changes to use a new/superseding ADR;
- `docs/PROJECT-STATE.md` identifies the repository as persistent project knowledge and chat as a working/reasoning surface.

No separate research/evidence IDs are required because this decision concerns repository-local governance mechanics directly verified from current source and GitHub state.

## Decision

Adopt the following repository-wide agent governance convention:

1. `AGENTS.md` is the canonical repository-level agent entrypoint.
2. When explicitly assigned as Supervisor, Auditor or Supervisor/Auditor, an agent must reconstruct and verify live repository, certification and authorization evidence before consequential claims; audit executor reports against persisted evidence; distinguish live truth from chat/history/static anchors; detect drift/scope/authority violations; use roadmap-first governance; compare alternatives; and avoid consequential implementation without explicit human authorization.
3. Insufficient evidence must be surfaced as `UNVERIFIED`, `PENDING` or `DECISION_REQUIRED`, not guessed.
4. Delegation must never create authority. A Supervisor/Auditor may not give an executor a broader grant than the human explicitly provided.
5. `.ai/EXECUTOR_AGENT_PROMPT_TEMPLATE.md` is the single canonical executor delegation template.
6. If a phase is not explicitly authorized, only a `NOT_AUTHORIZED` proposed executor prompt may be produced and it must not instruct consequential mutation or promotion.
7. Branch/PR, exact-head, pre-merge reconfirmation, expected-head guarded merge, exact-main and terminal-reconciliation disciplines apply whenever the repository's available promotion mechanism supports them.
8. This convention is agent-governance-only and does not itself authorize or require production, release, registry, consumer, runtime, infrastructure, ownership, Shared Core or ChatGPT Project UI changes.

## Consequences

### Positive

- Supervisor/Auditor behavior becomes durable and repository-scoped rather than chat-dependent.
- Executor delegation has one canonical, reviewable template.
- Human authorization boundaries are explicit and non-expandable by delegation.
- Live-state verification and exact-SHA certification semantics reduce stale-head and self-reporting errors.
- The design minimizes duplicate mutable policy.

### Negative / trade-offs

- Consequential phases require more explicit evidence reconstruction and authorization bookkeeping.
- Repositories without automated certification must report certification as unavailable/`UNVERIFIED` unless a repository-valid manual certification record is deliberately created.
- Supervisory workflows may stop at `DECISION_REQUIRED` more often when authorization or evidence is incomplete.

## Risks

- Future agents may ignore `AGENTS.md`; mitigation is to keep it at repository root as the entrypoint and reference the single executor template.
- A copied executor prompt can become stale after repository policy changes; mitigation is to regenerate delegations from the canonical template and re-verify live state before execution.
- Certification terminology can be mistaken for authorization; the entrypoint and template explicitly state that certification does not create authority.

## Supersedes

None

## Superseded by

None

## Verification / follow-up

- Verify the merged `main` contains `AGENTS.md`, `.ai/EXECUTOR_AGENT_PROMPT_TEMPLATE.md` and this ADR.
- Verify the entrypoint explicitly requires human authorization for consequential implementation and states that delegation cannot create authority.
- Verify the executor template contains authorization basis/state, live-state reconstruction, exact scope/mutations/exclusions, qualification/adversarial testing, bounded remediation, isolated PR workflow, exact-head and exact-main certification, pre-merge reconfirmation, guarded merge, terminal reconciliation, next authorization boundary and final evidence reporting.
- Verify no production/release/runtime surfaces changed as part of adoption.
