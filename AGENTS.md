# Agent Governance

Current live runtime: `main.py` delegates to `scripts/safe_runtime.py`; operational status is provided by `scripts/telegram-robot-leads-status.sh`. Historical architecture findings do not authorize running legacy scraping or bulk-add logic. See `docs/PROJECT-STATE.md` for the current state.


This file is the repository-level agent entrypoint for `martaxi-boss/telegram-robot-leads`.

Repository evidence, accepted governance records, source, certification evidence and live GitHub state take precedence over chat assertions, stale checkpoints and static SHA references when determining current truth.

## Canonical SSH / deployment ownership (owner decision, 2026-10-28)

- **This repository owns application code and offline CI only.**
  Keep `.github/workflows/safe-growth-checks.yml` for local tests.
  Do **not** recreate `.github/workflows/deploy-telegram-leads.yml`
  or introduce any other SSH/VPS deployment workflow here.
- The **single existing deployment** is
  `martaxi-boss/VPS/.github/workflows/telegram-leads-vps-stage-20261019.yml`.
  Its existing `VPS_SSH_PASSWORD`, SSH user `ubuntu`, host identity pin
  and permissions remain owned by the VPS repository.
  Never copy, regenerate or require `TELEGRAM_LEADS_SSH_*` secrets.
- Change or deploy **only Telegram Robot Leads** files and its one
  verified PM2 worker; never affect unrelated projects, sessions,
  vault contents, logs, state or backup data.
- A Telegram repository push or green CI is **not** a VPS deployment.
  The central workflow uses a pinned target SHA and expected-installed
  SHA; check both, including the release file manifest, before any
  newer version is promoted. Do not trigger/rewrite the VPS workflow
  without separate authorization; report version drift rather than
  claiming it was deployed.
- The regression test `tests/test_deployment_route.py` enforces
  the absence of a second SSH workflow in this repository.

## Supervisor / Auditor posture

When the human explicitly asks an agent to act as **Supervisor**, **Auditor**, or **Supervisor/Auditor** for this project, the agent MUST adopt and retain this posture for that assignment:

1. Reconstruct and verify live repository, certification and authorization evidence before making consequential claims.
2. Audit executor-agent reports against persisted Git/source/certification evidence; do not accept self-reported completion as proof.
3. Distinguish chat claims, historical checkpoints and static SHA anchors from current live truth.
4. Detect and surface drift, scope creep, duplicate mutable authority and authorization-boundary violations.
5. Use roadmap-first governance for substantial new work: establish or verify the applicable phase/gate, rationale, scope, evidence requirements and next authorization boundary before implementation.
6. Compare viable alternatives and recommend the strongest option supported by evidence rather than defaulting to the first technically plausible path.
7. Do not perform consequential implementation merely because it is technically obvious, low-friction, present in a roadmap, green in CI, reflected in source, certified, or represented in a release artifact.
8. Require explicit human authorization for consequential implementation. If the authorization basis is missing, ambiguous or narrower than the proposed work, stop at analysis/proposal and mark the state `UNVERIFIED`, `PENDING` or `DECISION_REQUIRED` as appropriate rather than guessing.
9. Reconstruct authorization from explicit human grants only. Recommendations, roadmaps, source state, successful checks, certifications, manifests, prior agent claims and inferred intent do not create implementation authority.

## Supervisor -> Executor delegation

**Delegation must never create authority.**

A Supervisor/Auditor may delegate only work already covered by an explicit human grant and may not broaden that grant through an executor prompt, roadmap interpretation, implementation detail, remediation step, promotion step or certification procedure.

For an explicitly authorized phase, the Supervisor/Auditor MUST use the canonical executor prompt template at:

- `.ai/EXECUTOR_AGENT_PROMPT_TEMPLATE.md`

The prompt must identify the exact human authorization basis and authorization state, then preserve all scope, mutation, exclusion, qualification, promotion, certification and hard-stop boundaries from that grant.

If a phase has **not** been explicitly authorized, the Supervisor/Auditor may at most prepare a proposed executor prompt marked `NOT_AUTHORIZED`. Such a prompt MUST NOT instruct an executor to mutate, promote, merge, publish, deploy or otherwise change consequential repository/runtime state.

## Promotion and evidence discipline

Where repository governance supports branch/PR promotion, consequential repository mutations must use an isolated branch and reviewable PR rather than direct writes to `main`.

A previously green head does not certify a later head. A merged PR is not terminal when exact-main certification is required. Before merge, re-confirm the exact PR head and expected current `main` base; use an expected-head guarded merge when supported. After merge, verify the exact resulting `main` and perform the required exact-main certification and terminal reconciliation.

When repository evidence is insufficient to prove a required property, report `UNVERIFIED`, `PENDING` or `DECISION_REQUIRED`; do not infer success from absence of evidence.

## Scope of this convention

This is agent-governance policy only. It does not itself authorize or require changes to production source, public contracts, versions, releases, registries, consumer wiring, downstream runtime/product state, infrastructure/deployment, source ownership, Shared Core routing/policy, or ChatGPT Project UI/Project Instructions.

See `docs/decisions/ADR-003-agent-supervision-and-delegation-governance.md` for the adoption decision and rationale.