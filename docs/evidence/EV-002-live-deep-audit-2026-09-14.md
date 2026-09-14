# EV-002 — Live deep audit — 2026-09-14

Status: **Validated evidence snapshot**
Date: 2026-09-14
Scope: GitHub repository truth, DigitalOcean account/droplet posture, live VPS runtime, deployment drift, access/security posture, persistence/backup, process topology, configuration handling and governance alignment.

## Safety / evidence handling

This record intentionally excludes secret values, Telegram phone numbers, API hashes, tokens, session contents, customer/user data and authentication material. It records presence, location, ownership, mode, topology and risk only.

## Canonical repository evidence

- Accessible repository: `martaxi-boss/telegram-iptvpn`.
- Repository is private and the connected GitHub principal has admin/maintain/push/pull/triage permissions.
- Default branch: `main`.
- Live GitHub `main` at audit time: `9f7e3760666e65abd661f38a488d005c552e5009`.
- `main` branch protection is disabled; required status checks are off.
- No workflow runs were associated with the audited `main` head.
- Root governance entrypoint is present at `AGENTS.md`.
- Governance drift detected: `AGENTS.md` identifies the repository-level entrypoint as `Alaska-Digital/telegram-iptvpn`, while the live audited repository is `martaxi-boss/telegram-iptvpn`.
- Project state says Architecture Baseline is not frozen and G1 Product Definition remains the next decision gate.
- Dependencies remain range-based rather than locked (`telethon>=1.41.0`, `aiosqlite>=0.20.0`, `langdetect>=1.0.9`, `python-dotenv>=1.0.0`).
- `ecosystem.config.js` hard-codes `/root/TELEGRAM-IPTVPN` and sets production-oriented PM2 environment overrides, including a project daily cap value that differs from `.env.example`.
- Current risk register already covers fail-open DB behavior, ambiguous external-action outcomes, historical DB exposure, session credential compromise, configuration drift, missing CI/branch protection, backup uncertainty and live-runtime uncertainty.

## DigitalOcean account / droplet evidence

- DigitalOcean account is active.
- One active droplet was visible in the connected account at audit time.
- Droplet ID: `570619582`.
- Name: `ubuntu-s-1vcpu-1gb-lon1`.
- Region: `lon1` (London 1).
- Size: Basic `s-1vcpu-1gb` — 1 vCPU, 1 GiB RAM, 25 GiB local disk.
- Ubuntu 24.04 LTS base image lineage; the specific original image entry is now marked retired in the DigitalOcean catalog.
- Private networking is enabled.
- DigitalOcean API reported no registered account SSH keys.
- Droplet metadata showed no backup IDs and no snapshot IDs.
- User image/snapshot listing was empty.
- DigitalOcean backup policy endpoint returned no enabled policy details beyond the droplet ID.

Conclusion: no evidence of an enabled DigitalOcean backup/snapshot recovery path was found.

## Live VPS runtime evidence

The authorized remote device corresponding to the droplet was online and directly inspected read-only.

### Host

- Ubuntu 24.04.3 LTS.
- Kernel: 6.8.0-117-generic.
- Architecture: x86-64 / KVM.
- Audit commands ran as `root`.
- Host uptime at capture: about 116 days.
- Root filesystem: ~24 GiB, ~15 GiB used, ~8.8 GiB available (~63% used).
- RAM: ~961 MiB total, with swap configured at 4 GiB.

### Process topology

PM2 had at least two online application processes:

1. `TELEGRAM-IPTVPN` — `/root/TELEGRAM-IPTVPN/.venv/bin/python /root/TELEGRAM-IPTVPN/main.py`.
2. `iptvpn_bot` — separate Python process under `/root/iptvpn_bot`.

Other live services include PostgreSQL 16 and Nginx. Therefore this droplet is not isolated to the Telegram-IPTVPN workload.

### Network exposure

Observed listeners included:

- SSH on TCP 22 on IPv4 and IPv6.
- Nginx on TCP 80/443 on IPv4 and IPv6.
- PostgreSQL bound to loopback only on 5432.

UFW is active with default inbound deny and outbound allow, but has broad explicit allows for:

- 22/tcp (SSH),
- 80/443 (Nginx),
- 7860/tcp,
- 7861/tcp,
- 8000/tcp,
- duplicate explicit 443/tcp rule.

The 7860/7861/8000 rules are annotated for other projects/services, confirming shared-host blast radius.

### SSH posture

Effective `sshd -T` values at audit time:

- `permitrootlogin yes`
- `passwordauthentication yes`
- `pubkeyauthentication yes`
- `maxauthtries 6`

This is a material security weakness for an internet-facing host: root remote login and password authentication are both effectively enabled.

### Application filesystem / credential posture

Within `/root/TELEGRAM-IPTVPN` the following sensitive/runtime artifacts were present:

- `.env` — mode 0600, owner root:root.
- `accounts.json` — mode 0600, owner root:root.
- two Telethon `.session` files — mode 0600, owner root:root.
- `users.db` — mode 0644, owner root:root.
- `estado_bot.json` — mode 0644, owner root:root.
- `telethon_adder.log` — mode 0644, owner root:root.

Secret-bearing files `.env`, `accounts.json` and Telethon session files have restrictive owner-only modes, which is good. However the SQLite database, durable JSON state and operational log are world-readable on the host and may contain operational/personal data.

### Production-state activity

- `users.db` had a modification timestamp on 2026-09-14, confirming active runtime persistence.
- `estado_bot.json` was also modified on 2026-09-14.
- `main.py` timestamp on the VPS was 2026-05-29.

This confirms the live system still uses overlapping SQLite + JSON durable state in production.

## Critical deployment drift

The Git checkout in `/root/TELEGRAM-IPTVPN` reported:

- branch: `main`
- remote: `https://github.com/martaxi-boss/telegram-iptvpn.git`
- local HEAD: `5a9623d` (`Add or update .env.example with required variables`)
- only the early commits `5a9623d`, `56c4996`, `1862998` were visible in the local checkout history.

The authoritative GitHub `main` at audit time was `9f7e3760666e65abd661f38a488d005c552e5009`.

Therefore the live VPS checkout is materially stale relative to current repository `main`. Production source/runtime truth and repository governance truth are not synchronized.

No deployment mechanism was identified that certifies an exact GitHub commit and promotes it reproducibly to the VPS.

## Secret-management / “DigitalOcean vault” finding

The connected DigitalOcean capability available to this audit exposes droplets, account metadata, SSH keys, images/snapshots/backups and lifecycle operations, but exposes **no DigitalOcean secret-vault / secret-store API**. Therefore no claim is made that phone numbers, Telegram tokens, API credentials or session secrets were migrated into a DigitalOcean vault.

Current live secret storage is filesystem-based under `/root/TELEGRAM-IPTVPN` (`.env`, `accounts.json`, Telethon session files). Values were not printed or copied into GitHub.

State: **DECISION_REQUIRED** for the target secret-management mechanism and migration plan.

## Severity-ranked findings

### Critical

1. **Internet-facing SSH permits root login and password authentication.**
2. **No verified DigitalOcean backup/snapshot recovery path for the live droplet.**
3. **Production checkout is stale versus authoritative GitHub `main`; no exact-commit deployment certification.**
4. **Live application runs as root.**
5. **Telegram user-session credentials remain host-local high-value credentials; lifecycle/revocation/recovery is not formalized.**
6. **SQLite + `estado_bot.json` continue as overlapping durable state sources in production.**

### High

7. Shared droplet hosts multiple unrelated application/services, increasing blast radius and complicating changes/recovery.
8. `users.db`, `estado_bot.json` and application log are mode 0644 and may expose operational/personal data to other local principals.
9. No branch protection and no required CI/status checks on authoritative GitHub `main`.
10. Dependency graph is not reproducibly locked.
11. Production configuration has precedence/value drift (`.env.example`, PM2 overrides and code defaults).
12. Deployment path hard-codes `/root/TELEGRAM-IPTVPN` and root-owned runtime.
13. Firewall contains legacy/shared-project exposure (7860, 7861, 8000) and duplicate 443 allowance.
14. Repository governance identifier drift (`Alaska-Digital/...` vs live `martaxi-boss/...`).

### Medium

15. Original DigitalOcean image lineage is retired in catalog; rebuild should use a current supported image and reproducible bootstrap.
16. Single small droplet has limited isolation/headroom and currently uses swap; scaling decisions remain blocked on product/capacity requirements.
17. No evidence of host-level fail2ban deployment was found in the initial command set.

## Positive controls observed

- UFW is enabled with default inbound deny.
- PostgreSQL is loopback-bound rather than internet-exposed.
- `.env`, `accounts.json` and Telethon session files are mode 0600.
- Repository `.gitignore` excludes `.env`, `*.session`, `accounts.json`, logs/state and `users.db` going forward.
- Governance explicitly forbids committing secrets/customer data and requires roadmap-first authorization.
- Current project documentation already recognizes many of the core architectural/security risks; this audit closes the previously unverified live-runtime portion for the observed snapshot.

## Recommended supervisory gates

No production mutation is authorized by this evidence record alone.

Recommended ordered remediation/decision program:

1. **G0A — Access hardening decision:** define non-root administrative access, SSH key policy, password-auth disablement, emergency access and rollback.
2. **G0B — Backup/recovery decision:** define RPO/RTO and establish/verify droplet + application-consistent backup and restore experiment.
3. **G0C — Secret-management decision:** select target vault/secret store, classify Telegram sessions separately from normal key/value secrets, define rotation/revocation and migration.
4. **G0D — Deployment provenance decision:** establish exact Git SHA deployment, immutable/reproducible build/bootstrap, rollback and live-vs-repo drift detection.
5. **G0E — Host isolation decision:** decide whether Telegram-IPTVPN remains on a shared droplet or moves to an isolated workload boundary.
6. Continue the existing **G1 Product Definition Gate** before freezing application architecture.

## Supervisor state

- Repository truth: **VERIFIED for snapshot**.
- DigitalOcean droplet inventory: **VERIFIED for snapshot**.
- Live process/network/filesystem posture: **VERIFIED for observed commands**.
- Secret values: **NOT COLLECTED / intentionally excluded**.
- DigitalOcean vault migration: **NOT PERFORMED / capability not exposed; DECISION_REQUIRED**.
- Backup restore viability: **UNVERIFIED**.
- Exact production behavior and Telegram-side action correctness: **UNVERIFIED**.
- Architecture Baseline v1.0: **PENDING**.
