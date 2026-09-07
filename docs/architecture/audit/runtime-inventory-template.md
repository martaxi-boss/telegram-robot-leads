# Runtime Inventory Template

Status: **PENDING LIVE HOST IDENTIFICATION**  
Related issues: #6, #7, #8

## Purpose

Collect the facts required to understand the current production/VPS runtime without copying secrets, private keys, Telegram session contents, API hashes, bot tokens, passwords, or full phone numbers into GitHub.

## Host identity

- Provider: TBD
- Region/datacenter: TBD
- OS/distribution: TBD
- Kernel: TBD
- systemd version: TBD
- Hostname: record only if not sensitive / operationally useful

## Application process

- Process supervisor: PM2 (repository assumption; verify live)
- PM2 version: TBD
- Application process user/group: **TBD — important**
- Working directory: repository says `/root/TELEGRAM-IPTVPN`; verify live
- Startup persistence mechanism: TBD
- Restart policy: TBD
- Number of worker processes: TBD
- Current release/commit deployed: TBD

## Python/runtime

- Python version: TBD
- Virtualenv path: TBD
- Installed Telethon version: TBD
- Installed aiosqlite version: TBD
- Installed langdetect version: TBD
- Installed python-dotenv version: TBD

Record versions only; do not record environment-variable values.

## Sensitive runtime files

For each file class, record **existence, owner/group, permission mode, size, and backup policy only**.

Do not record content.

| File class | Exists | Owner/group | Mode | Backup? | Notes |
|---|---|---|---|---|---|
| `.env` | TBD | TBD | TBD | TBD | No values in Git |
| `accounts.json` | TBD | TBD | TBD | TBD | No phone numbers/content in Git |
| `*.session` | TBD | TBD | TBD | TBD | Treat as critical credentials |
| `users.db` | TBD | TBD | TBD | TBD | Personal/operational data |
| logs | TBD | TBD | TBD | TBD | Check PII/secrets exposure |

## Database

- SQLite file location: TBD
- File size: TBD
- WAL/SHM files present: TBD
- SQLite version: TBD
- Integrity check result: TBD
- Backup mechanism: TBD
- Backup frequency: TBD
- Last successful backup: TBD
- Last tested restore: TBD

Do not upload/copy the live DB into GitHub.

## Storage/resources

- Filesystem type: TBD
- Disk total/free: TBD
- Application directory size: TBD
- DB growth rate if measurable: TBD
- Log growth/rotation: TBD
- Memory usage representative range: TBD
- CPU usage representative range: TBD

## Network exposure

- Inbound listening services/ports: TBD
- Publicly exposed application port: TBD / likely none; verify
- SSH exposure model: TBD
- Host firewall: TBD
- Provider firewall/security group: TBD

Do not record passwords, keys, or confidential allowlists in Git.

## Telegram runtime health

Record aggregate/boolean state only unless an identifier is necessary and non-sensitive:

- Number of configured accounts: TBD
- Number of authorized sessions: TBD
- Number disabled/restricted: TBD
- Target community resolves: TBD
- Required admin permissions present: TBD
- Last successful low-risk API health check: TBD

Do not record session strings, phone numbers, API hashes, or authentication codes.

## Operations

- How deployment is performed today: TBD
- Who/what can deploy: TBD
- How rollback is performed: TBD
- How emergency stop is performed: TBD
- How Telegram session revocation is handled: TBD
- How DB restore is handled: TBD
- Monitoring/alerts: TBD

## Exit criteria

Runtime inventory is complete enough to:

1. verify whether the application actually runs as root;
2. understand recovery/backup gaps;
3. measure whether SQLite/current host resources are constraints;
4. compare PM2, systemd and Docker Compose fairly;
5. design migration without risking current production state.
