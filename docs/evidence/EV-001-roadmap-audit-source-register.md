# EV-001 — Roadmap Audit Source Register

Status: **Validated**
Date: 2026-09-11
Topic: Evidence used by `docs/research/roadmap-deep-audit-2026-09-11.md`

## Repository evidence

### EV-001-A — Current repository tree

Source: GitHub current `main` tree at audit time.

Finding:

- executable/runtime surface is concentrated in `main.py`, `ecosystem.config.js`, `requirements.txt`, `.env.example`, helper scripts;
- no `.github/workflows` exists;
- governance documentation exists under `docs/`;
- no independent IPTV/VPN/payment/customer provisioning modules are present.

Confidence: **High**.

### EV-001-B — Current legacy implementation

Source: `main.py`, blob `068714174f2ab95bef79a87330e7296b485cb49e`.

Findings include:

- Telethon user-account sessions;
- SQLite/WAL queue/state;
- group discovery and participant ingestion;
- direct `InviteToChannelRequest` action;
- broad DB exception paths that return zero or suppress audit/metric write failures;
- overlapping SQLite + `estado_bot.json` state;
- region inference via names/langdetect;
- extensive human-like timing/retry behavior;
- import-time account/API configuration;
- project-specific target/search configuration.

Confidence: **High**.

### EV-001-C — Runtime configuration drift

Sources: `.env.example` and `ecosystem.config.js`.

Finding: `.env.example` documents `MAX_ADDS_PROJECT_PER_DAY=70`; PM2 injects `100` and forces dotenv override, demonstrating multiple competing configuration layers.

Confidence: **High**.

### EV-001-D — Historical database exposure

Source: commit `56c4996400e46e43666dfb947679ab1efdaab180` and its parent.

Finding: `users.db` was removed from the current tree and added to `.gitignore`, but remains in repository history.

Confidence: **High**.

### EV-001-E — Main branch control state

Source: GitHub branch metadata on 2026-09-11.

Finding: `main` is not protected and required status checks are not enabled.

Confidence: **High**.

### EV-001-F — Existing discovery program

Sources: `architecture-discovery` branch, issues #1–#10, draft PR #11.

Finding:

- substantial research already exists and remains valuable;
- PR #11 is draft, 23 commits / 19 changed files at audit time;
- it is currently non-mergeable with the newer `main` governance baseline;
- product scope issue #2 remains open.

Confidence: **High**.

## External primary evidence

### EV-001-G — Telegram API application / API ID guidance

Source: https://core.telegram.org/api/obtaining_api_id
Accessed: 2026-09-11

Relevant findings:

- third-party clients must obtain their own `api_id`;
- API libraries are monitored to prevent abuse;
- flooding/spamming can result in bans;
- sample API ID included with open-source code is limited and not suitable for released production applications.

Confidence: **High — official Telegram documentation**.

### EV-001-H — Telegram API Terms of Service

Source: https://core.telegram.org/api/terms
Accessed: 2026-09-11

Relevant findings:

- developers must protect privacy/security;
- own `api_id` is required;
- actions on behalf of users without their knowledge/consent are prohibited by the API terms.

Confidence: **High — official Telegram documentation**.

### EV-001-I — Telegram direct member-add capability

Source: https://core.telegram.org/method/channels.inviteToChannel
Accessed: 2026-09-11

Finding: `channels.inviteToChannel` is documented as user-only.

Confidence: **High — official Telegram documentation**.

### EV-001-J — Telegram Bot API opt-in capabilities

Source: https://core.telegram.org/bots/api
Accessed: 2026-09-11

Findings:

- bots with appropriate admin rights can create invite links;
- invite links may require join requests;
- bots can receive and approve/decline join requests with required permissions;
- join request payload can include the invite link used;
- current Bot API also exposes subscription invite links for channel membership, which may be relevant only if paid Telegram membership is an accepted product requirement.

Confidence: **High — official Telegram documentation**.

### EV-001-K — Telethon session-file security

Source: https://docs.telethon.dev/en/stable/concepts/sessions.html and stable session API documentation
Accessed: 2026-09-11

Findings:

- session files include authorization material sufficient to log in without resending a code;
- default SQLite sessions cache Telegram entity information;
- session files/strings must be protected as credentials and revoked if compromised.

Confidence: **High — Telethon documentation**.

### EV-001-L — SQLite WAL constraints

Sources:
- https://www.sqlite.org/wal.html
- https://www.sqlite.org/whentouse.html
Accessed: 2026-09-11

Findings:

- WAL supports concurrent readers and a writer but only one writer at a time;
- WAL participants must be on the same host; WAL is not a multi-host network-filesystem design;
- SQLite is appropriate for local/single-server workloads with modest writer concurrency;
- client/server databases are more appropriate when many concurrent writers or multi-host access is required;
- `synchronous=NORMAL` in WAL mode trades power-loss durability for performance.

Confidence: **High — SQLite project documentation**.

### EV-001-M — PostgreSQL queue concurrency primitive

Source: PostgreSQL documentation for `SELECT ... FOR UPDATE ... SKIP LOCKED`.
Accessed: 2026-09-11

Finding: PostgreSQL explicitly documents `SKIP LOCKED` as useful to avoid lock contention with multiple consumers of a queue-like table.

Confidence: **High — PostgreSQL documentation**.

### EV-001-N — Data protection by design/default

Source: European Data Protection Board, Guidelines 4/2019 on Article 25 Data Protection by Design and by Default, final version.
Accessed: 2026-09-11

Finding: privacy/data-protection requirements should be designed into systems rather than retrofitted after implementation.

Confidence: **High — EDPB guidance**.

## Evidence limitations

The audit did **not** verify:

- current live VPS configuration or filesystem contents;
- current production `.env` values;
- active Telegram account restrictions/permissions;
- business/legal entitlement for any IPTV/VPN content/service;
- selected payment/provider contracts;
- actual production workload metrics;
- current workstation package state after 2026-09-08.

These remain explicit research/experiment inputs and must not be inferred from repository source code.
