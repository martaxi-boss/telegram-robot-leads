# Risk Register

Updated: 2026-09-08

| ID | Risk | Probability | Impact | Status | Mitigation / next action |
|---|---|---|---|---|---|
| RISK-001 | Knowledge/decision context is lost across long sessions or project phases | Medium | High | Mitigating | Governance v1, `PROJECT-STATE.md`, ADRs and checkpoints adopted |
| RISK-002 | Existing implementation is mistaken for the final target architecture before investigation completes | Medium | High | Open | Treat current code as evidence/reference until Architecture Baseline approval |
| RISK-003 | Documentation becomes excessive, duplicated or stale | Medium | Medium | Mitigating | Just-enough-docs rule, authority separation, links over duplication, update triggers |
| RISK-004 | Assumptions about external IPTV/VPN/payment/provider behavior are accepted without empirical validation | Medium | High | Open | Create explicit RQs, EVs and EXPs before material integration decisions |
| RISK-005 | Security/credential handling weaknesses are inherited from prototype/current code | Unknown | Critical | Open | Dedicated security audit/research and threat model before production baseline |

Risk statuses: `Open`, `Mitigating`, `Accepted`, `Closed`.

Add new risks with stable sequential IDs; do not reuse IDs.