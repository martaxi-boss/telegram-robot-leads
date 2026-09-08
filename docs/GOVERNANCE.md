# Documentation & Knowledge Governance v1

Status: **Adopted**
Adopted: 2026-09-08
Decision: `ADR-001`

## Purpose

Prevent loss of project knowledge across long sessions, implementation phases and future maintenance while keeping the current source of truth easy to find.

## Operating model

The project uses:

**Docs-as-Code + arc42-lite + C4 + ADR + Research/Evidence/Experiment records + PROJECT-STATE + Checkpoints + GitHub Issues/Projects.**

## Four knowledge classes

### 1. Current authoritative knowledge
Answers: **What is true now?**

Examples: `PROJECT-STATE.md`, accepted requirements, current architecture, current deployment, current interfaces and current risks.

### 2. Durable historical/evidential knowledge
Answers: **How and why did we get here?**

Examples: research, evidence, completed experiments, PoCs, accepted/superseded ADRs, major checkpoints and future incident reviews.

### 3. Transient coordination
Answers: **What work are we doing next?**

Examples: GitHub Issues, Projects, PR discussion and temporary tasks. These may link to durable records but must not be the only location of a material decision or finding.

### 4. Derived/generated material
Rendered diagrams, indexes and exports are secondary when an authoritative source model exists.

## Stable identifiers

Use sequential IDs for important records:

- `REQ-xxx` — requirement
- `RQ-xxx` — research question
- `EV-xxx` — evidence/source
- `EXP-xxx` — experiment or PoC
- `ADR-xxx` — decision
- `RISK-xxx` — risk

Do not reuse retired identifiers.

## Traceability

Material decisions should be traceable where applicable:

`REQ -> RQ -> EV/EXP -> ADR -> architecture -> Issue/PR -> verification`

A record should link to upstream/downstream artifacts rather than duplicate their content.

## Status lifecycles

- Research: `Draft -> In Progress -> Validated -> Closed/Superseded`
- ADR: `Proposed -> Accepted -> Superseded/Deprecated`
- Requirement: `Draft -> Accepted -> Implemented -> Verified/Superseded`
- Risk: `Open -> Mitigating -> Accepted/Closed`
- Experiment: `Planned -> Running -> Passed/Failed/Inconclusive`

## Historical vs living records

### Preserve history
Do not silently rewrite the historical conclusion of:

- accepted ADRs;
- completed experiment results;
- evidence materially used for a decision;
- validated research conclusions;
- future production incident/postmortem records.

If the world changes, create/link a newer record and mark the older one superseded where appropriate.

### Maintain continuously
Keep these current:

- `PROJECT-STATE.md`;
- active requirements;
- current architecture views;
- roadmap and exit criteria;
- open questions;
- risk register;
- operational runbooks.

Git history preserves their evolution.

## Research promotion rule

A chat conclusion is not automatically a project fact.

Typical promotion path:

`Question -> Research -> Evidence/Experiment -> Validated conclusion -> Proposed decision -> Accepted ADR -> Architecture/Implementation`

Not every research item needs an ADR. ADRs are for decisions that are architecturally, operationally, security-wise or economically material and difficult/costly to reverse.

## Documentation update triggers

Update durable documentation when any of these occurs:

- requirement added, changed or removed;
- material architectural choice made or reversed;
- external API/provider contract materially changes;
- PoC changes confidence in an assumption;
- security boundary or credential-handling model changes;
- deployment/infrastructure model changes;
- data/persistence model changes materially;
- production incident creates reusable operational knowledge;
- decision becomes superseded.

## Pull request rule

Once implementation work starts, a material code/architecture change is not complete until the relevant living documentation is updated in the same change or an explicitly linked follow-up is justified.

## C4 / architecture depth

Use C4 Context + Container as the default visual depth. Add Component views only for complex/high-risk areas. Code-level diagrams are exceptional and must justify their maintenance cost.

Use arc42 concepts selectively for coverage (goals, context, constraints, runtime, deployment, quality, risks, decisions) rather than filling a large template mechanically.

## Checkpoint rule

Create/update a checkpoint at major milestones, before a long-session handoff, or whenever losing the current conversation would materially slow recovery.

A checkpoint records:

- phase and objective;
- completed work;
- research/evidence produced;
- accepted decisions;
- open decisions/questions;
- risks;
- repository/code state;
- next actions;
- exact resume point.

A new session should recover primarily from `PROJECT-STATE.md`, the latest checkpoint, active ADRs and relevant research/evidence.

## Documentation quality rules

- Preserve high-value knowledge, not every utterance.
- Prefer links over duplication.
- Separate fact, assumption, recommendation and decision.
- Record confidence when evidence is incomplete.
- Cite primary/official sources where possible.
- Date time-sensitive evidence and record access date.
- Do not place secrets, tokens, credentials or private customer data in documentation.
- Mark stale/superseded content explicitly rather than deleting useful history.
- Keep `PROJECT-STATE.md` concise enough to read first in every new session.

## Review cadence

Governance itself should be reviewed when it creates friction, fails to preserve important context, or when the project enters a materially different operational phase. Changes to this governance require a new/superseding ADR.