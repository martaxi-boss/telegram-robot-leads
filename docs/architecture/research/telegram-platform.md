# Research — Telegram Platform & Operating Model

Status: **DRAFT**  
Started: 2026-09-07  
Research phase: 2 / 3

## Research objective

Determine which Telegram integration and community-growth workflows are technically sustainable and compatible with Telegram platform rules before final architecture is selected.

This document records evidence. It does not yet approve a final operating model.

## Primary sources

1. Telegram — Creating your Telegram Application  
   https://core.telegram.org/api/obtaining_api_id
2. Telegram — API Terms of Service  
   https://core.telegram.org/api/terms
3. Telegram — Bot API  
   https://core.telegram.org/bots/api
4. Telegram — User Authorization  
   https://core.telegram.org/api/auth
5. Telegram — Terms of Service  
   https://telegram.org/tos/eu

Primary-source preference: official Telegram documentation should be used before blog/community interpretations for architecture decisions.

## Finding TP-001 — Project-owned API credentials are required for a production design

Telegram documents a process for obtaining an `api_id` and `api_hash` through `my.telegram.org` for a developer's own application.

Telegram also documents that the sample API ID included with its open-source code is server-limited and is not suitable for applications released to end users; it is intended for testing/sample use.

**Architectural consequence:**

- production must use Alaska Digital/project-owned API credentials;
- the legacy published Android API credential fallback must not be part of the approved production architecture;
- ownership, recovery, and rotation procedures for API credentials must be documented.

Status: **HIGH CONFIDENCE**

## Finding TP-002 — Telegram explicitly treats flooding/spamming as an enforcement risk

Telegram's API documentation states that API client libraries are monitored for abuse and warns that using the API for flooding/spamming can lead to bans. Telegram's general Terms of Service also prohibit sending spam/scams.

**Architectural consequence:**

- PeerFlood/FloodWait and similar signals must be treated as safety/platform-policy feedback;
- the final architecture must not be designed to disguise or bypass enforcement mechanisms;
- 'human-like' randomisation is not an acceptable architectural substitute for a sustainable operating model;
- research must prioritize opt-in/community-admin-supported mechanisms where possible.

Status: **HIGH CONFIDENCE**

## Finding TP-003 — User authorization is security-sensitive state

Telegram documents that after authorization, the authorization key is associated with the user and subsequent API operations execute as that user's identity.

**Architectural consequence:**

Telethon `.session` files/auth keys must be treated as high-value authentication secrets, not ordinary cache files.

Required controls to research:

- dedicated service identity;
- least-privilege filesystem access;
- session inventory;
- session revocation process;
- recovery when a session is invalidated;
- encrypted backup policy, or a decision not to back sessions up;
- separation from source code and application logs.

Status: **HIGH CONFIDENCE**

## Finding TP-004 — Bot API and MTProto/user-account responsibilities must be evaluated separately

The Bot API offers a supported bot integration surface with its own authorization and group-management capabilities. The legacy implementation is entirely based on authenticated user accounts through Telethon/MTProto.

It is premature to assume that all future responsibilities require user-account sessions.

**Research requirement:** build a capability matrix for each desired product function:

| Capability | Bot API | User/MTProto | Human admin | Decision |
|---|---|---|---|---|
| Community configuration | TBD | TBD | TBD | OPEN |
| Join/invite workflow | TBD | TBD | TBD | OPEN |
| Membership requests | TBD | TBD | TBD | OPEN |
| Analytics/events | TBD | TBD | TBD | OPEN |
| Source discovery | TBD | TBD | TBD | OPEN |
| Candidate ingestion | TBD | TBD | TBD | OPEN |
| Administrative actions | TBD | TBD | TBD | OPEN |

Status: **OPEN RESEARCH**

## Finding TP-005 — Current legacy design is action-centric; final design should be policy-centric

The legacy system makes the worker decide timing/retry behaviour directly. The architecture should instead separate:

1. capability (what Telegram API can technically do);
2. policy (what the product is allowed to do);
3. authorization (whether this action is allowed now);
4. execution (perform action);
5. durable result/reconciliation.

Candidate conceptual boundary:

```text
Request / Candidate
       |
       v
Policy + Eligibility
       |
       v
Action Authorization ----> DENY / REQUIRE HUMAN REVIEW
       |
       v
Telegram Adapter
       |
       v
Result + Audit + Reconciliation
```

This is a **design hypothesis**, not yet an accepted ADR.

## Research questions for next pass

### Telegram capabilities

- Which target-community workflows can be implemented with invite links/join requests rather than direct member addition?
- Which Bot API updates expose join-request lifecycle and what admin permissions are required?
- Which member-management operations are available to bots vs authenticated users?
- Are there material differences between groups, supergroups, and channels for the required product model?

### Account/session operations

- What are the recovery semantics for revoked/banned/logged-out sessions?
- What must be stored to identify session ownership without exposing phone numbers unnecessarily?
- Can account health be tested with low-risk calls?
- What isolation boundary is appropriate between multiple accounts?

### Rate limits / reliability

- Which limits are explicitly documented?
- Which API errors must be interpreted as stop/disable signals rather than retryable transient failures?
- What safe backoff policy can be specified without attempting to circumvent Telegram controls?

### Product implications

- Can the business objective be achieved through explicit opt-in acquisition instead of unsolicited member-add actions?
- Does Alaska Digital need a generalized Telegram operations platform, or is a smaller project-specific system sufficient?

## Interim architecture constraints

Until this research is complete:

- do not optimize anti-abuse-evasion behaviour;
- do not increase automated invitation volume;
- do not treat current quota numbers as product requirements;
- do not assume user accounts must implement every function;
- do not approve a queue/datastore architecture based solely on the current scraper/adder flow.

## Next evidence to collect

1. Telegram join-request and invite-link API capabilities.
2. Bot API member-management permission matrix.
3. MTProto/user-account permission and error model relevant to target workflows.
4. Telethon session lifecycle/security guidance.
5. Real current runtime observations from the VPS, without exposing secrets in Git.
