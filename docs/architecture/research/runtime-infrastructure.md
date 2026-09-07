# Research — Runtime, Infrastructure & Deployment

Status: **DRAFT**  
Started: 2026-09-07  
Related issue: #7

## Objective

Compare deployment models before selecting infrastructure. The correct solution is the simplest model that satisfies verified requirements for reliability, security, recovery, concurrency, and operations.

## Current observed baseline

Repository configuration assumes:

- PM2 process management;
- Python interpreter from a local virtual environment;
- application path `/root/TELEGRAM-IPTVPN`;
- local `.env`, Telethon session files, SQLite DB and logs.

The path strongly suggests a root-owned deployment layout, but the actual process user has **not yet been verified**. Runtime inventory is still required.

A local workstation inspection found no SSH alias/config identifying the project VPS automatically, so no remote runtime assumptions will be recorded as facts until the deployment host is identified and inspected safely.

## Primary sources

Docker:

- Production Compose guidance: https://docs.docker.com/compose/how-tos/production/
- Compose services/restart/read-only: https://docs.docker.com/reference/compose-file/services/
- Compose secrets: https://docs.docker.com/compose/how-tos/use-secrets/
- Docker volumes and backup/restore: https://docs.docker.com/engine/storage/volumes/

systemd / Linux service hardening:

- systemd documentation: https://www.freedesktop.org/software/systemd/man/

PM2:

- Existing repository configuration remains the primary evidence for current PM2 usage; official PM2 deployment/operations documentation will be added during the deeper operational comparison.

## Option family RI-A — Native VPS + systemd

### Hypothesis

Best fit if the final system is one Linux host, one application deployment, local SQLite or remote managed DB, and operational simplicity is the highest priority.

### Advantages

- minimal runtime layers;
- native Linux service lifecycle;
- straightforward dedicated service user;
- direct filesystem permissions for `.session` files;
- easy integration with journald and host monitoring;
- no container image/volume lifecycle to manage.

### Risks/trade-offs

- application environment reproducibility must be engineered explicitly;
- host package/Python drift if deployments are not disciplined;
- local filesystem layout matters;
- rollback needs a defined artifact/release approach;
- host-level dependency isolation is weaker than containers.

### Security opportunities

Systemd can support service-level sandbox/hardening controls such as no-new-privileges and restricted filesystem visibility depending on host/systemd version.

### Evidence required

- actual host OS/systemd version;
- deploy frequency;
- number of app services;
- whether a local SQLite DB remains acceptable.

## Option family RI-B — Single VPS + Docker Compose

### Hypothesis

Best fit if reproducible application packaging and clear service/data boundaries justify modest container complexity while still operating on one server.

### Advantages

- repeatable image/environment;
- explicit service definition;
- production-specific Compose overrides;
- restart policies;
- per-service secret grants;
- named volumes for persistent data;
- easier staging/prod parity at application level;
- natural path if adding PostgreSQL as a separate service during PoC/staging.

### Risks/trade-offs

- additional container/runtime operational layer;
- Telethon `.session` persistence and permissions must be designed deliberately;
- Docker restart can make a broken app repeatedly restart without being healthy;
- volume backups are not automatically solved just because a volume exists;
- host compromise still compromises containers/secrets unless additional controls exist.

### Source observations

Docker documentation states:

- Compose supports restart policies;
- startup ordering is not the same as readiness unless health conditions are configured;
- secrets can be granted per service and mounted as files;
- volumes persist outside container lifecycle and can be backed up/restored.

### Evidence required

- whether image reproducibility materially improves current operations;
- whether the team is comfortable operating Docker on the VPS;
- session/DB volume backup/restore PoC;
- health-check design.

## Option family RI-C — Containerized app + managed PostgreSQL

### Hypothesis

Best fit if final requirements show multiple workers/projects, central relational state, stronger DB operations, or a likely need to move application hosts independently from data.

### Advantages

- database lifecycle separated from app host;
- PostgreSQL concurrency and queue patterns available;
- managed backup/high-availability options depending on provider;
- easier future horizontal worker expansion;
- potentially clearer project/data access controls.

### Risks/trade-offs

- recurring database/service cost;
- network dependency for every authoritative state decision;
- credentials/TLS/connection pooling required;
- more failure modes;
- may be overengineering for two accounts on one host.

### Evidence required

- verified concurrency/scale;
- RTO/RPO;
- project count;
- database growth/retention;
- managed DB cost comparison;
- network-outage fail-closed behaviour.

## Option family RI-D — Managed application platform

### Hypothesis

Potential fit only if the platform can safely support persistent Telegram session credentials, long-running workers, required network behaviour, and the chosen database model without awkward workarounds.

### Questions

- Is filesystem persistence stable enough for user sessions, or must sessions live in a separate secure store?
- Are long-running background workers first-class?
- Are outbound Telegram connections supported predictably?
- What are restart/deploy semantics?
- Can production disable/kill controls be implemented cleanly?
- What does it cost at the required uptime?

No provider is selected or preferred at this stage.

## PM2 legacy assessment — preliminary

PM2 currently works as a process supervisor, but the architecture should not keep it merely because it exists.

Questions for the final comparison:

- Does PM2 provide a material benefit for a Python-only service compared with systemd?
- Does it obscure the actual service user/environment?
- How are startup persistence, log rotation and deployment handled today?
- Is PM2 state itself part of disaster recovery?

PM2 may remain viable, but must compete with systemd/Compose on operational evidence.

## Common requirements regardless of runtime

The following should not depend on which runtime wins:

1. non-root application identity;
2. explicit production/staging configuration;
3. no secrets in source control;
4. controlled session credential storage;
5. health model beyond process liveness;
6. bounded restart behaviour;
7. auditable release identifier/commit;
8. rollback procedure;
9. backup and tested restore;
10. disk/storage monitoring;
11. production kill switch independent from ordinary queue activity;
12. dependency/environment reproducibility.

## Runtime inventory required

Before scoring options, collect from the actual current VPS:

- provider/region (if operationally relevant);
- OS/version;
- systemd version;
- current PM2 version and startup config;
- process user/group;
- Python and dependency versions;
- directory ownership/modes;
- disk/filesystem layout and free space;
- firewall/listening ports;
- backup/snapshot configuration;
- reboot behaviour;
- log rotation/retention;
- current resource consumption over representative periods.

Do not commit passwords, private keys, session contents, phone numbers, API hashes or tokens while collecting this inventory.

## Decision matrix inputs

Each runtime option will be scored for:

- reliability;
- security/least privilege;
- recovery simplicity;
- reproducibility;
- operational complexity;
- cost;
- observability;
- scaling headroom;
- developer workflow;
- migration/rollback risk.

## Current conclusion

No runtime is selected.

For a small single-host product, native systemd or Docker Compose are the leading simplicity candidates. Managed PostgreSQL/container architecture becomes stronger only if scale/data/recovery requirements justify it. The legacy PM2 approach remains a candidate until actual runtime operations are inventoried and compared.
