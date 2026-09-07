# Research — Data, Privacy & Governance

Status: **DRAFT**  
Started: 2026-09-07  
Research phase: 2 / 4

## Objective

Determine what data the product actually needs, what the legal/policy constraints are, and what technical controls must exist before a final data model is selected.

This is an engineering/privacy risk analysis, not a substitute for qualified legal advice.

## Primary sources

- GDPR consolidated text, EUR-Lex: https://eur-lex.europa.eu/eli/reg/2016/679/2016-05-04/eng
- GDPR Article 6, EUR-Lex: https://eur-lex.europa.eu/eli/reg/2016/679/art_6/par_1
- Telegram API Terms of Service: https://core.telegram.org/api/terms
- Telegram Terms of Service: https://telegram.org/tos/eu

## Current legacy data inventory

The existing code/schema may store or derive:

- Telegram `user_id`;
- Telegram username;
- inferred region (`pt_es` / `europe`);
- processing/action status;
- account/session that processed a candidate;
- timestamps;
- event details;
- source-discovery context in logs, though provenance is not modeled cleanly in the candidate table;
- Telegram session/authentication state in local `.session` files;
- account phone numbers in local configuration where used.

The original Git history also contained a `users.db` file that was later removed from the working tree but remains in historical objects until history sanitization is performed.

## Finding DP-001 — Data minimization must shape the schema

GDPR Article 5 includes purpose limitation, data minimization, storage limitation, accuracy, integrity/confidentiality, and accountability principles.

**Architectural consequence:**

A field should not exist merely because it is convenient to scrape or derive. Each personal-data field should have:

- defined purpose;
- source/provenance;
- retention period;
- deletion behaviour;
- access policy;
- accuracy/confidence considerations where derived.

Status: **HIGH CONFIDENCE**

## Finding DP-002 — Lawful basis is a product requirement, not a database afterthought

GDPR Article 6 requires a lawful basis for processing personal data. Which basis applies depends on the actual product purpose and operating model.

**Architectural consequence:**

The final system must not assume that public visibility of a Telegram username automatically authorizes any downstream collection/use. Product requirements and legal/compliance review must establish the basis and notices/rights handling appropriate to the chosen workflow.

Status: **REQUIRES QUALIFIED LEGAL/COMPLIANCE CONFIRMATION**

## Finding DP-003 — Provenance is missing from the legacy candidate model

The legacy `users` table identifies a user but does not provide a normalized record of every source community/discovery event that led to collection.

If candidate ingestion remains in scope, provenance should be considered explicitly.

Potential model to research:

```text
candidate
  id
  telegram_user_id
  username_current
  created_at

candidate_source
  candidate_id
  source_type
  source_identifier
  observed_at
  collection_method
  project_id
  evidence/confidence
```

This is a **schema hypothesis**, not an approved model.

Benefits:

- explainability;
- retention by source/purpose;
- debugging;
- deduplication without losing origin;
- deletion/suppression enforcement;
- auditability.

## Finding DP-004 — Derived region currently has weak accuracy guarantees

The legacy application infers region from names/usernames and language detection. This can be inaccurate, especially for short strings and multilingual communities.

Questions:

- Is region actually required?
- What business decision depends on it?
- Can region come from an explicit project/source attribute instead of profiling a person?
- If inference remains necessary, what confidence and correction mechanism is required?

Interim recommendation: **do not treat inferred region as verified personal location.**

## Finding DP-005 — Suppression must be durable

If a user/candidate must no longer be processed, deletion alone may be insufficient: future discovery can reinsert the same Telegram user ID.

Potential requirement:

- a minimal suppression record keyed by stable Telegram identity, with a reason/category and timestamp;
- ingestion must check suppression before creating an actionable candidate;
- retention/legal implications of the suppression record itself must be defined.

Status: **PROPOSED FOR RESEARCH**

## Finding DP-006 — Secrets and operational personal data require different handling

Telegram `.session` files, API credentials, and account phone numbers are authentication/secrets material. Candidate identifiers and action events are operational data.

They should not share identical storage/access/backup policies.

Research separate classes:

1. application secrets;
2. Telegram session credentials;
3. project configuration;
4. candidate/user data;
5. immutable-ish audit events;
6. aggregate metrics;
7. backups.

## Finding DP-007 — Retention must be explicit

The legacy system does not define a deletion TTL for candidates/events.

Required decisions:

- how long an unprocessed candidate is useful;
- how long final action outcomes are retained;
- whether aggregate metrics can replace identifiable events after a period;
- how backup retention interacts with deletion;
- whether logs contain usernames/user IDs and how long logs are retained.

## Historical Git-data remediation

The initial Git commit included `users.db`. Planned handling:

1. create/verify recoverable repository backup before rewrite;
2. record affected blob/commit identifiers;
3. determine repository-access population during exposure window where possible;
4. rewrite repository history to remove the database;
5. expire/remove reachable refs as appropriate;
6. validate by searching rewritten history;
7. document completion and residual risk.

No history rewrite should occur until the recovery procedure is approved.

## Candidate data-governance requirements

The following are proposed for evaluation:

- `DG-001`: every candidate-processing purpose is explicit;
- `DG-002`: collect only fields needed for approved purposes;
- `DG-003`: record provenance where candidate ingestion remains in scope;
- `DG-004`: configurable retention policies;
- `DG-005`: suppression/deletion workflows;
- `DG-006`: project-level isolation if multi-project architecture is selected;
- `DG-007`: secrets/session credentials isolated from candidate data;
- `DG-008`: backups inherit data classification and retention requirements;
- `DG-009`: operator access is least-privilege and auditable;
- `DG-010`: logs avoid unnecessary personal data.

## Open research/legal questions

- What exact business purpose(s) apply to collected Telegram identifiers?
- Which lawful basis applies to each processing purpose?
- What notice/transparency obligations apply?
- What rights-request process is required?
- Is a DPIA or other formal assessment appropriate given the chosen scale/behaviour?
- Which entity acts as data controller/processor in the final business model?
- Are inferred profile attributes needed at all?

## Architecture impact

The datastore decision cannot be made only from throughput. It must also support:

- deletion and retention;
- provenance;
- suppression;
- access control model;
- backup/restore;
- auditability;
- safe migrations;
- project isolation if required.
