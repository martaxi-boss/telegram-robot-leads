# Decision Log

This is a chronological index. Full architectural decisions belong in ADRs.

| Date | ID | Decision | Status | Record |
|---|---|---|---|---|
| 2026-09-07 | D-001 | Use a research-first Architecture Discovery Program before final implementation | ACCEPTED | `adr/001-architecture-discovery-before-final-implementation.md` |
| 2026-09-07 | D-002 | Use GitHub as the authoritative engineering memory for research, decisions, experiments and implementation history | ACCEPTED | `adr/001-architecture-discovery-before-final-implementation.md` |
| 2026-09-07 | D-003 | Treat the current `main` implementation as a legacy baseline, not as the final architecture specification | ACCEPTED | `ROADMAP.md`, baseline audit |
| 2026-09-07 | D-004 | Do not optimize mechanisms intended to evade Telegram anti-abuse controls; first determine a sustainable operating model | ACCEPTED CONSTRAINT | Telegram research |
| 2026-09-07 | D-005 | Final production integration must not rely on Telegram's published/sample Android API credentials | PROPOSED — high-confidence platform constraint | Telegram research |
| 2026-09-07 | D-006 | Safety/quota authorization should fail closed when required durable state is unavailable | PROPOSED — architecture requirement | Baseline audit / requirements |
| 2026-09-08 | D-007 | Use the developer PC as the default environment for discovery/PoCs; introduce a staging VPS only for tests that materially require production-like Linux/network/runtime behaviour | ACCEPTED | `TESTING-STRATEGY.md` |

## Rules

- `ACCEPTED`: approved and binding until superseded.
- `PROPOSED`: strong candidate, pending the relevant architecture gate/ADR.
- `REJECTED`: evaluated and intentionally not selected.
- `SUPERSEDED`: replaced by another decision; history remains.

New material decisions must be added here when made. Do not rewrite history to make earlier uncertainty disappear.
