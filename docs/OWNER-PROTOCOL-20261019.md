# Telegram Robot Leads - owner protocol and implementation status (2026-10-19)

> **Registo histórico datado, não especificação operacional vigente.**
> Em 31-10-2026, a regra antiga de **um grupo por conta/dia** foi
> substituída pelo funcionamento documentado em [BOOTSTRAP.md](BOOTSTRAP.md):
> sem máximo fixo de adesões a grupos por dia, duas contas podem estar no
> mesmo grupo, histórico por (conta, grupo). O restante conteúdo mantém o
> contexto original de 19-10-2026 e não deve ser usado isoladamente para
> configurar ou reinstalar o robô.


## Intent and protected assets

Keep one Telegram Robot Leads project. Preserve both existing private user accounts,
phone numbers, Telethon session files, and VPS vault. Do not combine this bot with
the unrelated IPTV bot or the Project Leader Telegram Supervisor. A hygiene pass
must never replace or delete functioning functionality without a documented,
tested migration. Git history is recovery evidence, not a second active runtime.

## Owner's requested operational sequence

1. Find publicly accessible groups in the same market/niche.
2. Each of the two accounts may join at most one new group per calendar day.
3. After entering an eligible group, assess observable group/user metadata;
   exclude owners, administrators, deleted/bot accounts, and accounts without
   a visible public @username. Reject duplicate users across groups and accounts.
4. Keep a durable central queue shared by both accounts, even across restarts
   and day changes. A person found in multiple groups is one person, not multiple
   additions. Where available, deduplicate by stable Telegram numeric user ID
   rather than mutable @username.
5. Owner's ceiling: at most ten successful additions per account per day,
   twenty across both. The target is *not* mandatory. Additions should take
   place within 08:00-22:00 in Europe/Lisbon. Avoid bursts. Stop immediately
   on platform anti-abuse or account restrictions, and never evade restrictions
   by moving a refused action to the other account.
6. Report account joined group, successful authorized addition, already a member,
   rejected/privacy-restricted, duplicate, and account/Telegram hard stop.
7. Use past operation outcomes to measure performance; do not assume
   statistical estimates (such as 90% eligibility) are a validated AI model.

## Essential distinction between requested discovery and allowed actions

Public @username, ordinary group membership, and lack of an observable privacy
restriction do not establish that a third party opted in to the owner's target
group. Telegram does not provide a reliable universal preflight to determine
all privacy restrictions. Do not infer permission or circumvent restrictions.

Automated direct additions are supported **only** for users who actually
authorized joining the owner's group. The live safe runtime accepts a private
operator-controlled approved_users.txt queue with APPROVED/CONSENTED markers;
these markers must reflect genuine authorization, not merely operator
classification. Discovery of relevant public groups and operator-authorized
joins may be developed without scraping third-party member lists into
an unsolicited-admission engine.

## Actual state after PR #26 and current corrections

- Two existing sessions: separately verified online, untouched.
- Existing group allowlist: operator selected, not automatic discovery.
- Account join limits: one each daily; assignment now uses available capacity.
- Authorized direct additions: ten *successful* adds per account per day,
  maximum twenty project-wide; global single-instance execution lock.
- Account/member denial: known privacy denial is recorded; FloodWait/PeerFlood
  hard-stop account with durable state.
- Authorized member queue: approved_users.txt remains the input. Persisted
  username completion history plus a cross-account stable numeric ID journal
  (new); legacy unknown pending attempts require reconciliation.
- Time: new 08:00-22:00 Europe/Lisbon guard for member additions; a fixed
  ten-minute minimum interval remains a safety bound, not a disguise.
- Existing saved user outcomes or old users.db: **not yet recovered/verified**;
  do not invent migration success or erase backups.
- Source-group participant enumeration, admin filtering during discovery,
  autonomous third-party candidate queue, and inferred privacy preselection:
  **not present** in current safe runtime.
- Telegram notifications for each successful group/member action:
  **not yet wired into the safe runtime**.
- Production status: installation on VPS is currently staged but not running;
  new source changes require verified deployment and operational prerequisites.
  Never declare the robot running based on green offline CI.

## Acceptance checks

- Both account sessions remain unchanged and can be checked read-only.
- Day/account counters, global counters, and 08:00-22:00 window have tests.
- New group assignment does not use the same exhausted account twice.
- The same authorized Telegram user ID found via a new username cannot be
  added twice across accounts. Ambiguous outcomes cannot be replayed.
- Historical status mappings survive the midnight rollover and restarts.
- A hard platform restriction stops operations rather than retrying evasively.
- No production/third-party Telegram effects before live safety validation.
