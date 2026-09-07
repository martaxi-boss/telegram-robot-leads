# Legacy Current Behaviour Model

Status: **BASELINE DESCRIPTION — NOT REQUIREMENTS**  
Source: `main.py` at baseline HEAD `5a9623d191c5d2294cbc29b7af68194613bf5302`

## Purpose of this document

Record what the legacy application currently does so that future migration can distinguish:

- behaviour that must be preserved;
- behaviour that should be redesigned;
- behaviour that was accidental/dead code;
- behaviour that must be removed for security/platform/privacy reasons.

Nothing here is automatically an accepted product requirement.

## Startup

1. Load `.env` from the script directory when `python-dotenv` is available.
2. Resolve Telegram API credentials from environment or JSON file, with a legacy published-Android credential fallback.
3. Load account definitions from `TELEGRAM_ACCOUNTS_JSON` or `accounts.json`.
4. Validate account phone/session availability.
5. Configure regions/account mapping and operational flags.
6. Initialize SQLite tables/migrations.
7. Warn if disk free space is below configured threshold.
8. Start one async worker per configured Telegram account, staggered by account index.

## Account/session model

- Each account has a configured `session` name.
- Telethon creates/uses `<session>.session` in the application directory.
- Worker connects first, then checks if the session is already authorized.
- If not authorized, worker attempts interactive-style start using configured phone number and a timeout.
- Worker records session-ready or session-start failures in event metrics.
- Workers are isolated through `adder_worker_guarded` so one uncaught worker error does not automatically terminate other account tasks.

## Regional model

Legacy regions:

- `pt_es`
- `europe`

Default multi-account model maps first account to PT+ES and second/remaining accounts to Europe unless overridden.

Region classification uses:

- accented-character heuristics;
- `langdetect` on names/text;
- fallback assumptions for legacy pending rows.

Important: source groups can trigger relaxed name filtering, which may assign the scraper account's region without strong per-user evidence.

## Discovery

The legacy discovery engine:

1. starts with configured/embedded priority Telegram group usernames;
2. searches Telegram for hard-coded IPTV/streaming keywords by region using `contacts.SearchRequest`;
3. collects matching megagroups with usernames;
4. deduplicates discovered groups.

Embedded themes include IPTV, M3U, streaming, Stremio, CCCam and country/language variations.

## Source-group extraction

For each selected source group:

1. optionally retrieve and exclude group admins/owner;
2. iterate participants;
3. reject bots/deleted users/users without username;
4. apply recent-activity heuristic;
5. optionally apply regional name/language filtering;
6. insert unseen users into SQLite with status `pending` and a region.

`TELEGRAM_SCRAPE_MAX_PER_GROUP` currently limits successful new insertions rather than necessarily limiting total participants examined.

## Queue model

Primary table: `users`.

Important fields:

- `user_id` primary key;
- `username`;
- `status`;
- `added_by`;
- `timestamp`;
- later-added `region`.

Queue claim behaviour:

- starts `BEGIN IMMEDIATE`;
- requeues stale `processing` rows;
- claims one `pending` row through `UPDATE ... RETURNING`;
- with region split, account claims only its region;
- otherwise can partition by `ABS(user_id) % ACCOUNT_COUNT`;
- ordering is newest-first by default or random if configured.

## Secondary JSON state

`estado_bot.json` maintains an additional per-user status store protected by an asyncio lock for writes.

The DB and JSON state can therefore represent overlapping state, creating two sources of truth.

## Daily quota model

Configuration includes:

- minimum/maximum daily target per account;
- global project daily cap;
- per-account fair cap with slack;
- persisted daily successful-action count;
- randomized target per account/day loop.

In multi-account mode, target bounds may be reduced to fit the project cap.

Important reliability note: some quota/metric reads return zero on exception, which can fail open.

## Scheduling / timing model

The legacy runtime includes configurable/randomized timing intended to imitate human usage:

- wake/bed windows in Europe/Lisbon;
- weekend variation;
- start-of-day jitter;
- pre-action hesitation;
- distraction pauses;
- lunch pauses;
- variable pause between successful actions;
- evening slowdown;
- multi-account login staggering.

`TELEGRAM_ACTIVE_MODE` reduces several waits and disables some pauses.

This timing model is recorded for behavioural completeness but is **not approved as a final architecture requirement**.

## Target membership action

The worker resolves `TARGET_GROUP` and, when invitation actions are enabled:

1. claims a pending user;
2. checks secondary JSON state;
3. resolves username to Telegram entity;
4. rechecks project/account caps;
5. calls `InviteToChannelRequest(target_channel, [peer])` under a process-wide async lock;
6. records success/failure state and metrics;
7. waits according to the timing model.

Official Telegram documentation identifies the underlying `channels.inviteToChannel` method as user-only and subject to admin/privacy/contact and platform constraints.

## Error/result model

Final statuses include variants such as:

- `added`;
- `privacy_restricted`;
- `not_mutual`;
- `unresolvable`;
- `no_username`;
- `not_addable`;
- `too_many_channels`;
- `user_restricted`;
- `bot_not_addable`;
- `error`.

Transient/retry handling includes:

- `FloodWaitError`: requeue then sleep at least a minimum;
- `PeerFloodError`: adaptive wait and possible scrape while waiting;
- generic rate-limit text detection: requeue and long wait;
- target permission failures: stop that worker path to avoid consuming queue items.

## PeerFlood behaviour

The legacy design intentionally retries after PeerFlood with increasing waits and contains comments indicating the worker should not stop the day solely due to PeerFlood.

There is also a configured `TELEGRAM_PEERFLOOD_DAILY_MAX` value whose documented intent is not consistently reflected in the actual worker path.

This contradiction is a migration/research item, not something to preserve blindly.

## Scrape-when-empty behaviour

When the queue is empty:

1. record queue-empty metrics/event;
2. wait `QUEUE_EMPTY_WAIT_SEC`;
3. if the account is eligible to scrape, run discovery/extraction;
4. continue attempting the daily target.

PeerFlood waiting can also trigger scraping to refill the queue.

## Daily completion behaviour

Worker may stop/sleep for the day when:

- randomized daily target reached;
- account fair quota reached;
- project cap reached and account has reached its fair share.

Some project-cap logic periodically wakes an under-utilized account even when the global cap is already reached, based on the legacy goal of balancing account contribution.

## Persistence schema

### `users`

Queue/candidate state.

### `adder_events`

Event/audit-style records containing session, type, detail, optional username/user ID and JSON extras.

### `adder_daily`

Daily metrics per account/session including target, successes, error counters, scrape metrics and pause counters.

## Logging

- Python logging to stdout/stderr and rotating `telethon_adder.log`.
- Log size/count configurable.
- Some event details contain usernames/user IDs.

## Deployment baseline

`ecosystem.config.js` configures PM2 with:

- app name `TELEGRAM-IPTVPN`;
- working directory `/root/TELEGRAM-IPTVPN`;
- `.venv/bin/python` interpreter;
- selected environment overrides.

Helper scripts also hard-code `/root/TELEGRAM-IPTVPN`.

## Behaviour classification backlog

Each behaviour above must eventually receive one classification:

- `PRESERVE` — accepted requirement;
- `REDESIGN` — requirement remains but implementation changes;
- `REMOVE` — should not exist in final product;
- `RESEARCH` — decision requires evidence;
- `LEGACY/DEAD` — no longer required.

That classification will be performed during Product Requirements and Telegram policy research, not inferred from the fact that code currently exists.
