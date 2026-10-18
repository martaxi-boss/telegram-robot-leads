# Telegram Leads: read-only health and opt-in growth tools

These tools preserve the existing Telethon/SQLite baseline and **do not deploy, restart,
modify, or enable the legacy direct-add worker**. They provide a safe way to diagnose
the existing VPS and prepare legitimate, voluntary entry to the Telegram group.

## 1. Diagnose the existing VPS (read-only)

From the repository checkout on the VPS, using the Python interpreter with access
to the project files:

```bash
python3 scripts/lead_health.py
```

The output is JSON with:

- PM2 process state for `TELEGRAM-IPTVPN`, but **PM2 online is not an end-to-end pass**;
- current configuration *candidates* and their sources (selected nonsecret keys only);
- credentials **presence only** (never the token, hash, account phones, or session contents);
- counts of Telegram session files, accounts (if readable), and safe file modes;
- read-only SQLite candidate count and latest daily accounting aggregates.

The diagnostic DOES NOT sign into Telegram, verify that an account session is
authorized, or verify that joining/admission actually works. It cannot prove the
state of a separate external vault. For the exact effective runtime state, confirm
the running PM2 version and loaded `.env`; a stale deployment can differ from GitHub.

## 2. Bot API voluntary admission via named invite links

The official Telegram Bot API supports `createChatInviteLink` with
`creates_join_request=true`. A person who **chooses** to follow that link applies
to the group; an administrator handles the request. It **does not** add people
without consent or message scraped contacts.

References:

- https://core.telegram.org/bots/api#createchatinvitelink
- https://core.telegram.org/bots/api#getchatmember

Prerequisites:

1. Have a separate bot authorized by the group owner and added as admin to the
   intended group with `can_invite_users` (create links and process join requests).
2. Configure `TELEGRAM_GROWTH_BOT_TOKEN` securely in the local `.env` or in
   the process environment, with `TARGET_GROUP=@iptvpncode` (or intended group).
   **Do not store real tokens in Git, messages, or logs.** The token is distinct
   from the legacy Telethon `TELEGRAM_API_HASH`.
3. Validate that the bot token, target chat, and admin rights actually work:

   ```bash
   python3 scripts/optin_join_links.py --check
   ```

4. Only after the check succeeds, create a **named** voluntary admission link:

   ```bash
   python3 scripts/optin_join_links.py --create-link site
   ```

The link is returned by Telegram and may be shared in places where promotion is
allowed: your website, channels and collaborations. The name lets an administrator
distinguish campaigns in Telegram. This script does not yet persist analytics or
auto-approve join requests. Avoid running it with another bot's token without
verifying ownership and permissions.

## Deployment boundaries

- No Telegram credentials are available to local unit tests or GitHub Actions.
- This branch introduces *only* opt-in and read-only tools; it does not replace
  `main.py` nor touch the PM2 deployment.
- Credential storage, VPS backups, process health and platform permissions must
  be validated on the real VPS before any production release.
- No automation can guarantee zero Telegram rate limits, policy enforcement,
  restrictions or bans.
- Existing risks (historical `users.db` in Git, fail-open daily accounting,
  duplicate state sources, missing opt-out/retention) remain unresolved by these
  helpers and require separate recovery-first remediation.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile main.py scripts/lead_health.py scripts/optin_join_links.py
```


## 3. Track confirmed joins by campaign (independent of legacy Telethon)

The tracker from this branch is **not deployed automatically**. Its only Telegram
operations are `getMe`, `getChatMember`, `getChat`, `getWebhookInfo`
and `getUpdates`. It neither sends messages nor invites/approves users.

The group administrator must use a **dedicated BotFather bot token**, one not
used by `iptvpn_bot` or by any other polling/webhook application. The Bot API
does not allow `getUpdates` while a webhook is configured, and competing
pollers can consume updates belonging to the other application.

Config in a private `.env` on the VPS (or the equivalent protected environment):

```dotenv
TARGET_GROUP=@iptvpncode
TELEGRAM_GROWTH_BOT_TOKEN=<store privately; never commit or paste into chat>
TELEGRAM_GROWTH_BOT_DEDICATED=1
```

`TELEGRAM_GROWTH_BOT_DEDICATED=1` is an assertion of exclusive ownership;
do **not** set it unless the token is genuinely dedicated. The code cannot
discover pollers running on other servers. **Every online operation, including
`--check`, now fails closed** without that confirmation. A token also fails
preflight if identical to `TELEGRAM_BOT_TOKEN`, `BOT_TOKEN`, or
`IPTVPN_BOT_TOKEN` in the local configuration. This is a collision check,
not proof of exclusivity.

`--check` validates Bot API access, administrator rights, absence of a webhook,
the **group/supergroup** destination type and safe local storage file modes.
It does not create files or consume Telegram updates. The status
`admin_and_local_storage_verified` does **not** prove event delivery or
exclusive ownership of the bot. If blocked, investigate the cause rather
than bypassing the check.

The bot requires admin privileges
for the intended group and the `Invite users` right.

Run in this order on a controlled, backed-up host:

```bash
python3 scripts/growth_tracker.py --check
python3 scripts/optin_join_links.py --create-link website
python3 scripts/growth_tracker.py --once
python3 scripts/growth_tracker.py --stats
# Only after an operator verifies the dedicated token and the first results:
python3 scripts/growth_tracker.py --run
```

`--once` and `--run` **consume Bot API updates** and update local state;
they are not read-only Telegram history viewers. Run only one poller per bot.
The tracker deliberately does not delete webhooks or drop pending updates.

### What it counts

- **requested**: a voluntary join request received by Telegram for this group;
- **joined**: a member-status transition from outside the group into the group;
- **left**: a transition from membership to non-membership;
- **unattributed**: a membership event not identifiable to a registered campaign.

Links created with `optin_join_links.py` are registered locally against
the canonical numeric group ID. If Telegram omits the link from the member
update, a prior recorded join request can supply the campaign attribution.
A Telegram member event is still required to count an actual join.

These are **events**, not unique people, total current members, guaranteed
advertising conversions, or evidence of how many users saw a link. Telegram
may not deliver events older than 24 hours if the bot was offline, so missing
events cannot be reconstructed from this local tracker. The bot must explicitly
subscribe to both `chat_member` and `chat_join_request` update types.

### Storage, privacy and recovery

- `growth_metrics.sqlite3` is created with owner-only permissions (0600).
- It stores campaign names, SHA-256 link digests, group IDs, Telegram update
  identifiers and event categories; no raw usernames, phone numbers, private
  invite URLs or session contents are stored.
- Pending requests are joined across events using a keyed digest derived
  from the dedicated bot token and expire after **30 days**.
- Event records are kept for **90 days**; the stats query reports that window.
- Per-batch SQLite transactions advance the Telegram polling offset only after
  recording the corresponding events. Crashes before commit lead to safe replay
  rather than silent loss from premature acknowledgement.
- Bot token rotation changes keyed member digests, so pending-request
  attribution may temporarily become **unattributed**.
- Back up the local SQLite database consistently before production changes;
  restoring an old copy can produce different metrics because Telegram retains
  pending updates for a limited period. No credential values should be copied
  into logs or GitHub.

Use the current group's native Telegram admin controls to review and approve
the voluntary requests. This tool deliberately does not auto-approve or
send messages to people who have not opted in.
