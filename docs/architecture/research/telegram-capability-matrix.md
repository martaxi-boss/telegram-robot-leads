# Telegram Capability & Permission Matrix

Status: **DRAFT**  
Started: 2026-09-07  
Related issue: #3

## Purpose

Separate capabilities that require an authenticated user/MTProto session from capabilities supported directly through bot/admin invite workflows. This prevents the final architecture from assuming that the legacy user-account model is required for every responsibility.

## Primary sources

- Bot API: https://core.telegram.org/bots/api
- Invite links: https://core.telegram.org/api/invites
- `messages.exportChatInvite`: https://core.telegram.org/method/messages.exportChatInvite
- `channels.inviteToChannel`: https://core.telegram.org/method/channels.inviteToChannel
- Telethon session guidance: https://docs.telethon.dev/en/stable/concepts/sessions.html
- Telethon RPC/FloodWait guidance: https://docs.telethon.dev/en/stable/concepts/errors.html

## Capability matrix — initial findings

| Capability | Bot API / bot admin | MTProto user | Evidence / constraint | Architecture status |
|---|---|---|---|---|
| Create chat invite link | Yes, bot must be admin with appropriate rights | Yes | Bot API `createChatInviteLink`; MTProto `messages.exportChatInvite` is available to users and bots | SUPPORTED BY BOTH |
| Create invite link requiring admin approval | Yes | Yes | Bot API `creates_join_request`; MTProto `request_needed` | SUPPORTED BY BOTH |
| Receive join-request event | Yes, with `can_invite_users` admin right | Yes for user admins via MTProto updates | Bot API `chat_join_request`; Telegram invite docs | SUPPORTED BY BOTH |
| Approve join request | Yes, bot admin + `can_invite_users` | Yes for admin user via MTProto | Bot API `approveChatJoinRequest`; MTProto `messages.hideChatJoinRequest` | SUPPORTED BY BOTH |
| Decline join request | Yes, bot admin + `can_invite_users` | Yes for admin user via MTProto | Bot API `declineChatJoinRequest`; MTProto `messages.hideChatJoinRequest` | SUPPORTED BY BOTH |
| Directly add arbitrary users to channel/supergroup | Not via `channels.inviteToChannel` as a bot | Yes, subject to admin/privacy/contact/platform restrictions | Official method explicitly says only users can use it | USER-ONLY AND HIGH-RISK |
| Durable user-account authorization session | Not applicable in same form; bot token auth | Yes | Telethon `.session` includes authorization key and cached entities | USER-SESSION SECRET |
| Bot-token based admin automation | Yes | Not applicable | Bot API HTTPS token model | CANDIDATE FOR ADMIN WORKFLOWS |

## Finding TCM-001 — Opt-in join-request architecture is technically viable

Telegram officially supports invite links where a user **chooses to request membership**, and administrators/bots can then approve or decline the request.

This does not prove that it is the correct business model, but it demonstrates that direct unsolicited `inviteToChannel` is not the only technical path for controlled membership acquisition.

**Architecture consequence:**

At least one final architecture alternative must model an opt-in acquisition flow using:

1. project-owned invite link;
2. user-initiated join request;
3. policy/qualification step;
4. bot/admin approval or rejection;
5. auditable membership outcome.

Status: **HIGH-CONFIDENCE ALTERNATIVE REQUIREMENT**

## Finding TCM-002 — Direct member addition is a distinct, user-only capability

Telegram documents `channels.inviteToChannel` as **user-only**. The documented error surface includes:

- admin-required/forbidden errors;
- privacy restrictions;
- non-mutual-contact restrictions;
- invalid/deleted/banned user conditions;
- channel/user-capacity conditions;
- generic member-add failure.

**Architecture consequence:**

Direct member addition should not be bundled into a generic 'Telegram adapter' without a separate policy boundary. If retained at all, it is a distinct action class with stricter authorization, risk controls, and platform-policy review.

Status: **HIGH CONFIDENCE**

## Finding TCM-003 — A bot can own and manage its own invite links

Telegram's Bot API notes that administrators generate their own invite links and a bot should generate its own links to manage them reliably.

Potential benefit:

- clear attribution of join source;
- controlled revocation/rotation;
- expiry and usage policy;
- join-request mode;
- less dependence on user-account session credentials for membership intake.

This requires further product research on acquisition channels and attribution.

## Finding TCM-004 — Join requests expose limited contact window/data

The Bot API `ChatJoinRequest` includes the requesting user and the invite link used. It also provides a temporary private-chat identifier with a limited window for contact before the request is processed, subject to Telegram's documented conditions.

**Data/privacy consequence:**

An opt-in join-request design may provide stronger provenance than the legacy third-party scraping model because the system can record:

- which project-owned invite link was used;
- when the user requested to join;
- what policy decision was made.

The exact fields retained still require data-minimization and retention decisions.

## Finding TCM-005 — Exact generic Telegram limits are not a stable architecture constant

Telethon documentation explicitly notes that exact limits vary and are not comprehensively known; `FloodWaitError` provides Telegram's required wait duration for a particular condition.

**Architecture consequence:**

- do not encode an assumed universal 'safe number of requests' as platform truth;
- distinguish business quotas from Telegram-generated wait/permission signals;
- stop/deny when safety state is unavailable;
- treat repeated platform enforcement signals as account health/policy events, not as input to evasion logic.

## Finding TCM-006 — Session files contain more than a simple login flag

Telethon documents that its default SQLite session stores the authorization key and can cache entities including chats/users and potentially phone information.

**Security/privacy consequence:**

- `.session` files are credentials plus cached metadata;
- access should be restricted to the specific worker/service identity that needs them;
- copying session files into generic backup or diagnostic bundles needs explicit review;
- consider whether entity caching should be disabled if not required by the accepted design.

## Architecture alternatives that must now be compared

### Alternative family A — Bot-led opt-in membership workflow

Potential responsibilities:

- bot creates project invite links;
- users initiate join requests;
- bot receives join request;
- policy engine approves/rejects or queues for human review;
- DB records provenance and decision;
- user-account sessions used only if a separate accepted capability truly requires them.

### Alternative family B — Hybrid bot + limited user-session adapter

Potential responsibilities:

- bot handles intake, membership requests, administration and observability-friendly events;
- user session handles only narrowly justified MTProto/user-only functions;
- each user-only action class is separately authorized and bounded.

### Alternative family C — Legacy-style user-account centric model

Potential responsibilities:

- user sessions perform discovery and direct member addition.

This alternative remains in the comparison to preserve analytical fairness, but it carries the highest current platform/privacy/security risk and must demonstrate a legitimate, sustainable requirement before selection.

## Next research tasks

- Determine whether the actual business funnel can route acquisition traffic through project-owned invite links.
- Map group/supergroup/channel differences relevant to the target community.
- Research bot webhook/polling deployment choices only after product requirements are known.
- Determine whether any accepted feature truly requires third-party member scraping.
- Determine whether any accepted feature truly requires direct user-account member addition.
- Build account-health state model for user sessions if they remain in any architecture candidate.
