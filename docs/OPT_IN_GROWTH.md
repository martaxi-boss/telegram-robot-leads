# Telegram Leads: read-only health and opt-in growth tools

These tools preserve the existing Telethon/SQLite baseline and **do not deploy, restart,
modify, or enable the legacy direct-add worker**. They provide a safe way to diagnose
the existing VPS and prepare legitimate, voluntary entry to the Telegram group.

## 1. Diagnose the existing VPS (read-only)

From the repository checkout on the VPS, using the Python interpreter with access
to the project files:

\`\`\`bash
python3 scripts/lead_health.py
\`\`\`

The output is JSON with:

- PM2 process state for \`TELEGRAM-IPTVPN\`, but **PM2 online is not an end-to-end pass**;
- current configuration *candidates* and their sources (selected nonsecret keys only);
- credentials **presence only** (never the token, hash, account phones, or session contents);
- counts of Telegram session files, accounts (if readable), and safe file modes;
- read-only SQLite candidate count and latest daily accounting aggregates.

The diagnostic DOES NOT sign into Telegram, verify that an account session is
authorized, or verify that joining/admission actually works. It cannot prove the
state of a separate external vault. For the exact effective runtime state, confirm
the running PM2 version and loaded \`.env\`; a stale deployment can differ from GitHub.

## 2. Bot API voluntary admission via named invite links

The official Telegram Bot API supports \`createChatInviteLink\` with
\`creates_join_request=true\`. A person who **chooses** to follow that link applies
to the group; an administrator handles the request. It **does not** add people
without consent or message scraped contacts.

References:

- https://core.telegram.org/bots/api#createchatinvitelink
- https://core.telegram.org/bots/api#getchatmember

Prerequisites:

1. Have a separate bot authorized by the group owner and added as admin to the
   intended group with \`can_invite_users\` (create links and process join requests).
2. Configure \`TELEGRAM_GROWTH_BOT_TOKEN\` securely in the local \`.env\` or in
   the process environment, with \`TARGET_GROUP=@iptvpncode\` (or intended group).
   **Do not store real tokens in Git, messages, or logs.** The token is distinct
   from the legacy Telethon \`TELEGRAM_API_HASH\`.
3. Validate that the bot token, target chat, and admin rights actually work:

   \`\`\`bash
   python3 scripts/optin_join_links.py --check
   \`\`\`

4. Only after the check succeeds, create a **named** voluntary admission link:

   \`\`\`bash
   python3 scripts/optin_join_links.py --create-link site
   \`\`\`

The link is returned by Telegram and may be shared in places where promotion is
allowed: your website, channels and collaborations. The name lets an administrator
distinguish campaigns in Telegram. This script does not yet persist analytics or
auto-approve join requests. Avoid running it with another bot's token without
verifying ownership and permissions.

## Deployment boundaries

- No Telegram credentials are available to local unit tests or GitHub Actions.
- This branch introduces *only* opt-in and read-only tools; it does not replace
  \`main.py\` nor touch the PM2 deployment.
- Credential storage, VPS backups, process health and platform permissions must
  be validated on the real VPS before any production release.
- No automation can guarantee zero Telegram rate limits, policy enforcement,
  restrictions or bans.
- Existing risks (historical \`users.db\` in Git, fail-open daily accounting,
  duplicate state sources, missing opt-out/retention) remain unresolved by these
  helpers and require separate recovery-first remediation.

## Tests

\`\`\`bash
python3 -m unittest discover -s tests -v
python3 -m py_compile main.py scripts/lead_health.py scripts/optin_join_links.py
\`\`\`
