# Architecture Discovery Program

## Purpose

This directory is the authoritative engineering memory for `telegram-iptvpn`.

The project will not jump directly from the current monolithic implementation to a proposed rewrite. The architecture must be derived from verified product requirements, Telegram platform constraints, security/privacy requirements, reliability tests, infrastructure trade-offs, and proof-of-concept evidence.

## Source-of-truth rules

GitHub is the project record. Important information must not exist only in chat, terminal history, a VPS, or one person's memory.

Record the following in this repository:

- product requirements and assumptions;
- research questions and source links;
- measurements and experiment results;
- current-state audits;
- security and privacy findings;
- architecture alternatives and comparison matrices;
- ADRs (Architecture Decision Records);
- rejected approaches and reasons;
- migration plans and rollback plans;
- production-readiness evidence;
- post-implementation changes to architecture.

## Document lifecycle

Documents should use one of these states where relevant:

- `DRAFT` — incomplete and actively being researched;
- `PROPOSED` — sufficiently complete for review, not yet approved;
- `ACCEPTED` — approved decision or requirement;
- `SUPERSEDED` — replaced by a newer record;
- `REJECTED` — explicitly evaluated and not selected.

## Architecture gates

A phase may progress only when its exit criteria are recorded and satisfied.

The final architecture is not approved until:

1. product requirements are explicit;
2. Telegram platform and policy research is complete enough to constrain the design;
3. data/privacy requirements are defined;
4. failure modes and recovery objectives are defined;
5. infrastructure alternatives are compared;
6. critical assumptions are tested in PoCs;
7. security threats and controls are documented;
8. an architecture decision matrix is completed;
9. the final architecture ADR is accepted.

## Directory map

```text
docs/architecture/
├── README.md
├── ROADMAP.md
├── REQUIREMENTS.md
├── DECISION-LOG.md
├── WORKLOG.md
├── audit/
├── research/
└── adr/
```

## Working principles

- Understand the current system before changing it.
- Verify assumptions with evidence.
- Measure before optimizing.
- Prefer root-cause fixes over behavioural patches.
- Reuse proven components before adding new infrastructure.
- Compare alternatives explicitly.
- Design recovery before destructive changes.
- Validate changes before declaring a phase complete.
- Prefer fail-closed controls for actions that can create account, policy, privacy, or rate-limit risk.

## Change discipline

Architecture-discovery changes should normally be made on branches and reviewed through pull requests. The current private repository plan does not presently provide enforceable private-repository rulesets/branch protection through the available GitHub tier, so this process is documented and must be followed operationally until enforcement is available.
