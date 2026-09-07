# telegram-iptvpn

Private Alaska Digital project currently under **Architecture Discovery**.

The current implementation is treated as a **legacy operational baseline**, not as the approved final architecture. No major refactor or scaling decision should be made until the discovery program has completed its research, proofs of concept, and architecture decision gates.

## Current status

- Discovery branch: `architecture-discovery`
- Baseline branch: `main`
- Final architecture: **NOT YET APPROVED**
- Production-readiness status: **requires hardening and architecture review**

## Engineering record

All research, decisions, rejected alternatives, risks, experiments, and implementation history must be recorded in GitHub.

Primary documentation:

- `docs/architecture/README.md` — governance and documentation map
- `docs/architecture/ROADMAP.md` — phased discovery and implementation roadmap
- `docs/architecture/REQUIREMENTS.md` — product and engineering requirements register
- `docs/architecture/DECISION-LOG.md` — chronological decision register
- `docs/architecture/WORKLOG.md` — chronological engineering/research work log
- `docs/architecture/audit/2026-09-07-baseline-audit.md` — initial repository audit
- `docs/architecture/research/` — research evidence and findings
- `docs/architecture/adr/` — Architecture Decision Records

## Governance rule

A design choice is not considered an architectural decision until it has:

1. a stated problem/context;
2. alternatives considered;
3. evidence or experiment results;
4. security/privacy/operations impact;
5. documented trade-offs;
6. an ADR with an explicit status.

The purpose of this process is to preserve institutional memory: future maintainers should be able to determine **what was built, why it was built that way, what was rejected, and what evidence supported each decision**.
