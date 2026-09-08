# ADR-001 — Adopt continuous documentation & knowledge governance

Status: **Accepted**
Date: 2026-09-08
Scope: Project engineering/process governance; does **not** freeze application architecture.

## Context

Telegram-IPTVPN is expected to pass through extended discovery, architecture research, PoCs, implementation and operations, with significant work occurring across long AI/human sessions. Relying on chat history or retrospective reconstruction would risk losing evidence, assumptions, rejected alternatives and the rationale behind architectural choices.

## Decision

Adopt **Docs-as-Code + arc42-lite + C4 + ADR + Research/Evidence/Experiment records + PROJECT-STATE + Checkpoints + GitHub Issues/Projects** as the project knowledge-governance model.

The model is continuous across the system lifecycle rather than a documentation phase performed once before implementation.

## Supporting research

- `../research/documentation-governance.md`

## Key consequences

### Positive

- research and decision rationale remain recoverable;
- current truth is distinguishable from historical context;
- new sessions/contributors can recover state without depending on chat history;
- architectural changes can be traced to requirements/evidence;
- production/operational knowledge can evolve in the same repository.

### Costs

- documentation has an ongoing maintenance cost;
- templates/IDs require discipline;
- stale living documents can become dangerous if update triggers are ignored.

## Guardrails

- Do not document every conversation verbatim.
- Keep `PROJECT-STATE.md` concise.
- Preserve historical evidence and accepted ADRs.
- Use C4/arc42 selectively rather than producing unnecessary detail.
- Implementation architecture remains under research until a later Architecture Baseline is explicitly approved.