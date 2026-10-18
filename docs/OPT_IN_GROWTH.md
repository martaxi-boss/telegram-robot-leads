# Telegram Robot Leads: read-only health and opt-in growth tools

## Project identity (Owner-confirmed 2026-10-18)

**Telegram Robot Leads** is the current official name of the existing project
`martaxi-boss/telegram-robot-leads`. **TELEGRAM-IPTVPN was its former
operational label, not a different project or a VPN service.** Do not create a
second instance or a second set of Telegram accounts when seeing that old name.

The separate `martaxi-boss/iptvpn-bot` project remains a different application,
with independent credentials and processes.

**Verified operational rename (2026-10-18):** the same project's credential
directory was moved on the existing VPS `vps-32bea5b6` from the old
`/root/project-secrets/TELEGRAM-IPTVPN/` location to its **current, canonical**
`/root/project-secrets/telegram-robot-leads/` location. The same five protected
files were preserved, including the existing `.env`, `accounts.json`, and two
Telegram `.session` files. The old directory is now absent, and the separate
`/root/project-secrets/iptvpn_bot/` vault remains untouched.

Evidence: [guarded atomic rename, GitHub Actions #39158397322](https://github.com/martaxi-boss/VPS/actions/runs/39158397322)
and [independent read-only postflight #39158539431](https://github.com/martaxi-boss/VPS/actions/runs/39158539431).
These runs checked only path, file and permission metadata; no credentials were
exposed, no processes restarted, and no Telegram API login was attempted.

Some legacy source/configuration files still refer to the historical
`TELEGRAM-IPTVPN` PM2 process name or `/root/TELEGRAM-IPTVPN` runtime
checkout. Those are **historical references, not the vault location**.
No such runtime checkout or running Telegram Leads worker was observed on
this VPS as of the 2026-10-18 audit. Do not start an old archived PM2 configuration. The tracked `ecosystem.config.js` now describes the canonical `telegram-robot-leads` worker, which still requires independent deployment readiness checks. Safe opt-in metrics files were independently
staged (but **not started**) at `/opt/telegram-leads-optin/`; their runtime
credentials and Telegram bot administrator permissions remain a separate
activation check. Do not mistake Telethon API ID/hash for a BotFather bot token.


### Verified live readiness (2026-10-18)

The live [read-only SSH audit](https://github.com/martaxi-boss/VPS/actions/runs/39160115127)
found the protected canonical vault, four staged opt-in modules and their
provenance file, an active/enabled offsite-backup timer with a recent recorded
success, and **no running Telegram Robot Leads or metrics worker**. The separate
`iptvpn_bot` was **running**. Its existing bot token authenticated successfully,
and it had group administrator and invitation permissions; **it is not an
available dedicated metrics token**. Do not start a second `getUpdates` poller
using it. Nothing in that audit consumed Telegram updates or logged secrets.

The safe metrics modules are staged at `/opt/telegram-leads-optin/`.
They have no runtime token installed; the existing protected
`/root/project-secrets/telegram-robot-leads/.env` supplies Telethon API
credentials and the target group, **not a dedicated BotFather metrics token**.
Real join-event tracking therefore remains inactive. Creating another worker
must not be confused with renaming the existing project.

#### Read-only status, and credentials in their existing vault

```bash
# Run directly from the current repository checkout (or staging scripts).
bash scripts/telegram-robot-leads-status.sh

# Explicit external credentials path: no token is copied into /opt.
# This check is expected to BLOCK until a genuinely dedicated token exists.
python3 /opt/telegram-leads-optin/scripts/growth_tracker.py \
  --check --root /opt/telegram-leads-optin \
  --env-file /root/project-secrets/telegram-robot-leads/.env
```

`--env-file` is supported by both `growth_tracker.py` and
`optin_join_links.py`. It requires an absolute, canonical path pointing to an
owner-only regular credentials file under an owner-only directory. Symlinks
and world/group-readable credentials are rejected. Values are loaded privately
from the original vault at execution time, **never passed as command arguments,
logged or copied**. `--stats` does not require credentials and now opens an
existing metrics SQLite database **read-only**, without creating a new one.

The legacy `scripts/telegram-iptvpn-status.sh` filename remains as a
compatibility alias for the safe canonical status command; it no longer opens
a missing `users.db` for writing or prints lines from account logs. Canonical
`ecosystem.config.js` now **inactive legacy configuration**, not the
current vault path or a safe production start command.

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
- Offline `--stats` queries existing metrics SQLite data using a read-only
  connection and does not initialize or modify the database.
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


## 4. Recovery, bot isolation and optional PM2 supervisor

The official Bot API `getUpdates` transport may temporarily fail. The
continuous `--run` mode now retries **only read-only polling** after temporary
network failures and HTTP 500/502/503/504 responses. Delays are bounded
(2, 4, 8, 16, 32, 60 seconds); after six unsuccessful retries the process exits
with an error. A successful poll resets the retry count. Credential errors,
another poller's HTTP 409, and Telegram HTTP 429 restrictions are terminal:
do not bypass these errors or run several consumers on one bot token.

A potentially ambiguous **link-creation write is never retried** automatically.
When Telegram may have created a link but local registration failed, inspect
the real group invite links before taking further action.

Both `optin_join_links.py` and `growth_tracker.py` require the same explicit
`TELEGRAM_GROWTH_BOT_DEDICATED=1` declaration and reject a token visibly
shared with an existing bot. They verify the target is a group or supergroup,
not a broadcast channel. The declaration is **not** proof of exclusive ownership
on another machine.

The repo contains the **inert** file
`ecosystem.growth.example.config.js` for the existing PM2 installation.
It is not included in the legacy `ecosystem.config.js`, has no token or
automatic launch, and cannot start by a GitHub merge alone. Only after the
real VPS checkout has been backed up, the bot token independently checked,
the account permissions verified and the Python preflight passed should an
operator consider starting the metrics worker. Example manual commands:

```bash
python3 scripts/growth_tracker.py --check
# Only when preflight passed AND the dedicated bot is confirmed:
pm2 start ecosystem.growth.example.config.js --only TELEGRAM-LEADS-METRICS
pm2 status TELEGRAM-LEADS-METRICS
python3 scripts/growth_tracker.py --stats
```

The PM2 template uses the existing checkout's `.venv/bin/python`; it must
exist on the VPS. **Do not run** the example while another poller/webhook uses
that bot, while session/backup posture is unknown, or in a shared unattended
GitHub Actions runner. A passing source-code test suite does not certify
Telegram connectivity, bot permissions, actual joins or VPS uptime.
