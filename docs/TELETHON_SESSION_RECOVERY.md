# Telegram Robot Leads — Telethon recovery and voluntary group joining

## Scope and evidence (2026-10-18)

This is **only** `martaxi-boss/telegram-robot-leads`. Historical
`TELEGRAM-IPTVPN` labels refer to this same old leads project, not to any
other IPTV posting bot or the Project Leader/Codex Supervisor.

- The protected canonical vault is `/root/project-secrets/telegram-robot-leads/`,
  with `.env`, `accounts.json` and **two** protected Telethon `.session`
  files. The legacy old vault directory is absent.
- [Live read-only two-account Telegram test](https://github.com/martaxi-boss/VPS/actions/runs/39166864689)
  authenticated **both** stored accounts. Each connected, returned a valid
  Telegram identity, and its actual phone matched `accounts.json`; no phone
  values or auth keys were reported.
- A direct open using the dependency selected during that test failed with
  `ValueError` **before network connection** for both original session files.
  Explicitly reading `dc_id, server_address, port, auth_key` read-only from
  SQLite, then passing a Telethon `MemorySession` succeeded for both. This
  makes no assumption about the old session schema's exact additional columns.
- That is **not** evidence that the legacy `main.py` adder can safely start.
  Read-only VPS audit #39160115127 found no running legacy Leads process.
  The currently tracked PM2 `ecosystem.config.js` is the new canonical runtime configuration; the **historical** config and process must not be started.
- The BotFather token of the unrelated `iptvpn_bot` and the Project Leader
  Telegram Supervisor are **out of scope**. No bot token is needed to verify
  these two Telegram user sessions.

## New code: `scripts/telethon_sessions.py`

The new module is inert unless executed. It never imports the old `main.py`,
runs an adder/scraper, copies credentials into the repository, or initiates new
logins. Secrets, phone numbers and session keys never appear in the JSON report.

It requires a protected owner-only vault and reads the existing `.env`,
`accounts.json` and SQLite sessions. It refuses missing/unsafe files,
symlinks, ambiguous session identifiers, unexpected account counts and invalid
DC/authorization key records. SQLite sessions are opened with
`mode=ro&immutable=1` and the Telethon client uses a memory-only session, so
it cannot upgrade or write the original session SQLite database.

### Read-only inventory, without network or extra Python dependencies

```bash
python3 scripts/telethon_sessions.py \
  --vault /root/project-secrets/telegram-robot-leads
```

### Real online test of BOTH existing accounts, without external effects

Use a trusted Python environment where the project's Telethon dependency is
already installed. The global Python on the VPS did **not** have Telethon
installed during the 2026-10-18 audit; don't assume this command can use it.

```bash
python3 scripts/telethon_sessions.py \
  --vault /root/project-secrets/telegram-robot-leads --online
```

Run as the vault-owning user. Verifies one account at a time using only
`connect`, `is_user_authorized` and `get_me`; compares the phone with the
protected account configuration without printing either value. No new login,
message, member addition, group scraping or update polling is performed.
Online calls can still receive network/API errors, which are reported by
**type only** without revealing private values.

These checks do not start a 24/7 process or certify the old mass-add runtime. The current production entrypoint is `scripts/safe_runtime.py`, guarded by the new policy and separate deployment checks.

## Operator-only option: voluntary join-request link, NO BotFather

A Telegram account with group administrator permissions can request a
voluntary approval-required link using the official MTProto
`messages.exportChatInvite` method. It is *not* equivalent to adding another
group's members without their permission; individuals have to choose to
request access.

[Official Telegram API method](https://core.telegram.org/method/messages.exportChatInvite)

```bash
python3 scripts/telethon_sessions.py \
  --vault /root/project-secrets/telegram-robot-leads \
  --create-link "campaign_name" --confirm-link-creation
```

Only this explicit operator command creates one link; `--online` and default
offline health have no membership-changing effects. Link creation requires
**application-owned** Telegram API ID/hash, the first account's valid
authorization and group admin privileges. It deliberately refuses the
published Android fallback that appears in some legacy configurations.
Telegram enforces the group administration permission. A failed or ambiguous
creation response is **never automatically retried**; check existing invite
links with Telegram first.

Share a link only in places where voluntary promotion is permitted. The
existing public `@iptvpncode` group can also be joined by interested people
through its published Telegram group address, without creating a new link.

## Legacy behavior: not production approved

The unmodified legacy `main.py` obtains members from other groups and calls
`InviteToChannelRequest`, which attempts **direct group addition**, even
though the method's name includes the word "invite". It is not merely sending
an invite link. It includes "human-like" pauses, scraping and retries after
`PeerFlood`. Those are not sufficient protection against Telegram reports
or restrictions. Telegram explicitly warns against unwanted group additions:
[Telegram FAQ on spam](https://telegram.org/faq_spam).

**Do not start or re-enable the direct-add / unrelated-group harvesting paths
for production.** The original `main.py` has unresolved fail-open accounting,
unknown-outcome retry, redundant SQLite/JSON state, personal-data provenance,
retention and consent controls. These have *not* been certified or repaired by
the session read-only tool.

Existing Bot API join metrics remain optional and **inactive**; their separate
BotFather token is not a requirement of the working Telethon accounts or the
new operator-only opt-in link.

## Production gates still not passed

1. Establish dedicated application-owned API credentials. A publicly reused
   Android client API ID/hash is not a safe production configuration; see the
   [Telegram API Terms](https://core.telegram.org/api/terms).
2. Confirm user consent and permissible data origin and retention; stop on
   rate-limit or abuse warnings instead of shifting work to another account.
3. Design a durable fail-closed datastore and unknown-outcome handling for
   **any** future user-affecting workflow.
4. Certify restore of private sessions and databases, dependency/runtime
   compatibility, process supervision and safe restart in the canonical vault.
5. Perform an explicitly authorized, consent-based live end-to-end join test.

No merge of this documentation or its associated diagnostics restarts the VPS.
