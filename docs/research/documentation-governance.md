# Research — Project Documentation & Knowledge Governance

Status: Recommended model / not an architecture decision
Date: 2026-09-08
Project: Telegram-IPTVPN

## Question

How should the project preserve research, evidence, architectural reasoning, decisions and current-state documentation so that knowledge is not lost across long ChatGPT sessions, development phases, implementation, production and later maintenance?

## Executive finding

Documentation should not be treated as a one-time deliverable before implementation. The project should define the documentation system early, during discovery, and then maintain it continuously as part of the engineering workflow.

The recommended model combines:

- Docs-as-Code: versioned Markdown stored with the repository.
- arc42 concepts for architecture coverage and continuous architecture work.
- C4 for system/context/container/deployment views, adding component/code detail only when useful.
- Architecture Decision Records (ADRs) for durable decision history.
- Research and Evidence records for pre-decision investigation.
- Experiment/PoC records for empirical validation.
- A small living PROJECT-STATE document as the current source of truth.
- GitHub Issues/Projects for transient work tracking rather than durable architectural knowledge.
- Periodic checkpoints for reliable handoff between long AI/human work sessions.

## Key principle

Preserve history, but do not give every historical artifact equal authority.

The repository should distinguish:

1. Historical/evidential knowledge — research, sources, experiments, superseded decisions.
2. Living/current knowledge — project state, active requirements, current architecture, current risks.
3. Work tracking — issues, tasks, implementation backlog.
4. Generated/derived material — rendered diagrams or generated indexes, which are not the authoritative source when a source model exists.

## Why this should exist before final project structuring

The documentation governance model should be established before the final architecture and implementation structure because otherwise early investigation is scattered across chats, temporary notes and code comments. Once architecture decisions start being made, reconstructing their context retrospectively becomes unreliable.

However, only the governance rules and initial templates should be defined up front. The actual documentation must remain incremental and evolve with the project.

## Why it must continue throughout the project

Architecture is not static. Requirements, external APIs, deployment constraints, security assumptions, providers and operational knowledge can change. Therefore:

- accepted ADRs are preserved and superseded rather than rewritten;
- current architecture documentation is updated when implementation changes it;
- experiments and PoCs remain historical evidence;
- risks and assumptions are reviewed continuously;
- implementation PRs should update relevant documentation when behavior or architecture changes;
- production introduces new durable knowledge such as runbooks, incident reviews, backup/restore procedures and operational constraints.

## Recommended artifact lifecycle

Idea / Question
→ Research Question (RQ)
→ Evidence (EV) and/or Experiment (EXP)
→ Analysis / Comparison
→ Proposed Decision
→ ADR
→ Architecture Baseline
→ Implementation
→ Verification
→ Operational Knowledge
→ Evolution / Superseding ADR when needed

## Recommended authority model

### Authoritative current state

Living documents that answer: “What is true now?”

- `docs/PROJECT-STATE.md`
- active requirements
- current architecture views
- current deployment model
- current risk register
- current interface/contracts documentation

### Durable historical record

Documents that answer: “How and why did we get here?”

- research records
- evidence records
- experiments/PoCs
- ADRs, including superseded ADRs
- major project checkpoints
- incident/postmortem records once operational

### Transient coordination

Artifacts that answer: “What are we doing next?”

- GitHub Issues
- GitHub Projects
- PR discussions
- temporary implementation tasks

They may link to durable documentation but should not become the only place where an architectural decision or critical finding exists.

## Recommended repository model

```text
docs/
├── PROJECT-STATE.md
├── project/
│   ├── vision.md
│   ├── scope.md
│   ├── context.md
│   ├── glossary.md
│   └── constraints.md
├── requirements/
│   ├── functional.md
│   ├── quality.md
│   ├── security.md
│   ├── operational.md
│   └── assumptions.md
├── research/
│   ├── README.md
│   └── <topic>.md
├── evidence/
│   ├── sources.md
│   ├── experiments/
│   └── poc-results/
├── decisions/
│   ├── README.md
│   └── ADR-xxx-<decision>.md
├── architecture/
│   ├── overview.md
│   ├── context.md
│   ├── containers.md
│   ├── runtime.md
│   ├── deployment.md
│   ├── data-model.md
│   ├── integrations.md
│   ├── security.md
│   └── diagrams/
├── risks/
│   └── risk-register.md
├── roadmap/
│   ├── roadmap.md
│   └── exit-criteria.md
├── checkpoints/
│   └── YYYY-MM-DD-<checkpoint>.md
└── operations/
    ├── runbooks/
    ├── backup-restore.md
    ├── monitoring.md
    └── incidents/
```

Not every directory needs to be populated immediately. The structure should grow when the corresponding knowledge exists.

## Artifact IDs and traceability

Use stable identifiers for important artifacts:

- `REQ-xxx` — requirement
- `RQ-xxx` — research question
- `EV-xxx` — evidence/source
- `EXP-xxx` — experiment or PoC
- `ADR-xxx` — architecture decision
- `RISK-xxx` — risk

Relationships should be explicit. Example:

`REQ-014` → `RQ-006` → `EV-021`, `EXP-004` → `ADR-009` → implementation PR → verification test.

This makes the reasoning chain discoverable by humans and AI without inferring it from prose.

## Status model

Suggested statuses depend on artifact type.

Research: Draft → In Progress → Validated → Closed / Superseded

ADR: Proposed → Accepted → Superseded / Deprecated

Requirement: Draft → Accepted → Implemented → Verified / Superseded

Risk: Open → Mitigating → Accepted / Closed

Experiment: Planned → Running → Passed / Failed / Inconclusive

## What should be immutable vs living

### Preserve as historical records

- accepted ADR content;
- completed experiment results;
- evidence/source records relevant to a decision;
- major research conclusions after validation;
- production incident/postmortem records.

If circumstances change, link a newer artifact instead of silently rewriting history.

### Maintain as living documents

- `PROJECT-STATE.md`;
- current architecture diagrams/views;
- current requirements;
- roadmap;
- open questions;
- risk register;
- operational runbooks.

Git history preserves their evolution.

## ChatGPT/session continuity

Chat conversations are a working environment, not the project source of truth.

At meaningful milestones or before a conversation handoff, create/update a checkpoint containing:

- current phase;
- objective;
- work completed;
- research completed;
- accepted decisions;
- open decisions/questions;
- risks;
- repository/code state;
- next actions;
- exact resume point.

A new session should be able to reconstruct the project primarily from `PROJECT-STATE.md`, the latest checkpoint, active ADRs and the relevant research/evidence documents.

## Phase-by-phase documentation behavior

### Discovery / current phase

Create project context, research records, evidence, assumptions, open questions and risk records. Avoid freezing the final architecture prematurely.

### Architecture definition

Promote validated research into requirements, ADRs and C4/architecture views. Produce an explicit architecture baseline before implementation is treated as final.

### Prototype / PoC

Record experiments, environments, procedures, observations and results. Use the results to validate or supersede proposed decisions.

### MVP implementation

Link issues and PRs to requirements/ADRs. Update living architecture documentation in the same engineering change when architecture or behavior changes.

### Hardening / pre-production

Add threat model, deployment, backup/restore, observability, failure modes, security and operational runbooks.

### Production and evolution

Maintain architecture as-built, operational procedures, incidents, migrations and new/superseding ADRs. Documentation governance continues for the lifetime of the system.

## Documentation update triggers

A documentation update should be considered mandatory when any of the following occurs:

- a requirement is added, changed or removed;
- a material architectural choice is made;
- an external provider/API contract changes;
- a PoC changes confidence in an assumption;
- a security boundary or credential-handling model changes;
- a deployment/infrastructure model changes;
- a data model or persistence strategy changes materially;
- a production incident reveals new operational knowledge;
- a decision is reversed or superseded.

## GitHub workflow recommendation

Use GitHub Issues/Projects to track work and investigation tasks, and Markdown in the repository for durable knowledge. For significant documentation/architecture changes, use pull requests so rationale and review history remain attached to the change. As the project matures, branch protection, required reviews/checks and CODEOWNERS can protect the source of truth.

Documentation should be kept close to code and evolve with code, rather than being a separate end-of-project exercise.

## Avoiding documentation overload

Do not document everything at maximal detail.

Apply these rules:

- document high-value/high-impact knowledge;
- prefer links over duplicated explanations;
- use C4 Context + Container as default visual architecture depth;
- add Component/Code diagrams only where complexity or risk justifies them;
- keep `PROJECT-STATE.md` short;
- keep ADRs focused on one decision;
- store raw conversation transcripts only if needed for audit, and never treat them as authoritative;
- periodically mark stale or superseded artifacts explicitly rather than deleting history.

## Recommended hybrid for Telegram-IPTVPN

The strongest fit for this project is:

**Docs-as-Code + arc42-lite + C4 + ADR + Research/Evidence/Experiment records + PROJECT-STATE + Checkpoints + GitHub Issues/Projects.**

This balances traceability with maintenance cost and is suitable for an AI-assisted project where conversation context may be temporary while Git is persistent.

## References

- arc42 method: https://arc42.org/method/
- arc42 sections/examples: https://examples.arc42.org/sections/
- C4 model: https://c4model.com/
- C4 diagrams: https://c4model.com/diagrams
- C4 tooling / diagrams-as-code considerations: https://c4model.com/tooling
- Martin Fowler, Architecture Decision Record (2026): https://martinfowler.com/bliki/ArchitectureDecisionRecord.html
- GitHub Docs, content design principles: https://docs.github.com/en/contributing/writing-for-github-docs/content-design-principles
- GitHub Docs, planning and tracking work: https://docs.github.com/en/issues/tracking-your-work-with-issues/learning-about-issues/planning-and-tracking-work-for-your-team-or-project
- GitHub Docs, managing/standardizing pull requests: https://docs.github.com/en/pull-requests/reference/managing-and-standardizing-pull-requests

## Decision status

This document is research and a recommended governance model. It does **not** freeze the Telegram-IPTVPN application architecture. Adoption of the documentation governance model can be made before application architecture decisions because its purpose is to preserve and trace those decisions.