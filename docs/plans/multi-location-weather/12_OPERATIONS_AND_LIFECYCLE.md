# 12 — Operations, recovery, security and lifecycle
**Package:** LHW-ML-20261023 | **Checkpoint:** CP-5 | **State:** PROPOSED — NOT DEPLOYED
**Authority:** my-pa `AGENTS.md`, `migrations/README.md`, ADR-008, `ops/nas/`, and `ops/runbooks/postgres-backup-runtime-attestation.md` govern the existing DB. Read [03](03_TARGET_ARCHITECTURE.md), [04](04_POSTGRESQL_INTEGRATION.md), [09](09_VALIDATION_AND_ACCEPTANCE.md).

## 1. Lifecycle and gate controls
| State | Required evidence / transition |
|---|---|
| PLANNED (current) | documents on planning branch, independent plan review pending |
| RF_PROVEN | host USB enumeration, valid WH65B decode, 24h soak and restart evidence |
| DB_CONTRACT_PROVEN | separately authorized my-pa DDL/role work in *disposable* PG; permitted migration head, role negatives and recovery design |
| SYNTHETIC_INTEGRATION_PASS | full contracts, source-aware API and frontend under isolated tests |
| PILOT_ELIGIBLE | exact-head independent review, approved NAS nonproduction target, security and restore checks |
| PRODUCTION_ACTIVATION_APPROVED | explicit operator approval of named target, images, roles, migrations, secrets, ingress and rollback |
| OPERATING_VERIFIED | measured end-to-end RF/provider flow, last accepted timestamps, backup/restore, iPhone cellular HTTPS after authorized activation |
Neither publication, commit, PR, merge, CI success, nor existence of a planning package implies live activation. No model accepts operational risk.

## 2. Read-only preflight specification
1. Reauthenticate Lakehouse exact branch HEAD+tree, approved source SHA, image OCI digests, my-pa main HEAD and approved migration revision. Reject drift.
2. Operator-controlled redacted NAS inspection: DSM version, CPU/RAM/storage/free space, actual USB VID:PID/serial and kernel driver, Container Manager permissions, system clock, remote access availability, private storage root and backup status. Do not assume the scaffold path `/volume1/docker/lakehouse-weather` or that the Nooelec kit was delivered.
3. Operator-controlled target DB discovery: verified physical cluster/db identity, server version, applied Alembic revision, current roles/schema, connection budget, WAL and backup/restore receipts. Distinguish `MY_PA_MIGRATION_DATABASE_URL` from `MY_PA_DATABASE_URL`; never print either secret. Reject any migration whose identity/authority is ambiguous.
4. Verify receiver container has USB access **but no database or provider secret**, app has restricted `weather` role but **no USB device**, static PWA/browser has neither credential, and existing my-pa services retain existing scope. Check no Docker socket, uncontrolled privileged flag, host network or public DB publishing.
5. Verify private proxy/Tailscale ACL: only read-only browser routes exposed and all internal/administrative RF routes denied; no Cloudflare until separately approved. Verify HTTPS on real iPhone cellular path, not localhost screenshot.
6. Confirm NWS station identities and per-source provider usage terms; Open-Meteo free usage remains noncommercial with attribution; locations/coordinates remain private and operator-approved.
7. Preflight scripts are **dry-run by default** and cannot execute Docker start/stop, role provisioning, migrations, backup deletion, or secret mutation. Produce redacted refusal reasons, not secret-bearing Compose output.

## 3. Container responsibilities and hardening
**Receiver:** Exactly one image with pinned `rtl_433`, approved USB device, protected fsynced file+atomic-rename+directory-fsync journal; stable first-seen event UUID/digest and fresh HMAC request timestamp/nonce on every signed retry. Per-member authenticated 200/207 outcomes and a durable terminal/conflict receipt precede unlink; outage/restart/unknown RF/full spool each has explicit gap/alert policy, never silent loss. No SQL credentials, sensitive RF data retention, or unapproved privileged USB grants. Receiver requires outbound-only internal ingest reachability and backoff on failures.

**Weather-app:** One bounded weather app/ASGI worker and one provider polling owner; independently committed per-`stream_id` watermarks, stable relative-horizon product identity across rolling absolute HTTP windows and model semantic-digest revisions; provider-entitlement-wide weighted quota; restricted weather SQL role, small measured pool, no schema creation/DDL or mutation of configuration metadata. HMAC verifier atomically commits unique nonce before member processing (±120s skew, >=300s nonce retention, restart-safe); nonce expiry operator-owned only. API/static PWA with private `no-store` weather replies and static-only precache; no USB or WAN port exposure.

**my-pa PostgreSQL:** the physically existing operator-verified instance is *the* canonical DB, including weather data in the proposed isolated schema. DB owner executes any accepted migration/role work. Lakehouse Compose must not launch another Postgres. Protect private application schemas and preserve my-pa's backup/restore contract.

**Ingress:** MVP Tailscale private HTTPS only; proxy GET/asset allowlist; deny /internal, admin/metrics, any SQL route, and unauthorized mutation. Cloudflare + Access only as a separately scoped security/identity project, with no reuse of my-pa's hostname, credentials or public tunnel.

## 4. Health signals and response policies
| Signal | Proposed warning and evidence | Safe response |
|---|---|---|
| decoder process alive vs actual sensor packet | heartbeat separate from last accepted WH65B/WH32B; warn WH65B after >2min only until cadence observed | diagnose device/antenna/parser; do not auto-enroll new RF IDs |
| spool backlog/age | >80% capacity or exceeds approved outage window; full is critical | pause/backpressure with **explicit gap alert**, no silent overwrite |
| PostgreSQL availability/role/head | schema mismatch, permission denied, high latency/pool saturation | 503 readiness, pause writes/backoff, protect my-pa |
| provider availability | NWS 429/503/Retry-After or Open-Meteo quota/terms error; last success separate from last observation | honor backoff and quota; preserve last accepted history as stale |
| data quality | counter reset, implausible reading, unexpected sensor ID, checksum drift | reject/quarantine with sanitized reason; retain append-only raw lineage if permitted |
| browser state | disconnected already-open tab may show in-memory last reading stamped OFFLINE; fresh offline cold start has static shell and **no cached weather response** | show weather unavailable until reconnect, never invent saved offline history or live status |
| backup freshness | absent/invalid governed PostgreSQL receipt or failed scratch restore | block migration/commissioning; do not report recoverable |
| disk/WAL/load | measured resource thresholds against my-pa budget | slow weather writes first; owner-approved DB tuning only |
Log opaque source IDs, statuses, event digests and timing; **never log** household coordinates/addresses, neighbor RF packet contents, connection URLs, tokens, provider bodies, email contacts or credentials. Default no third-party telemetry. Define log retention and monitor owner before launch. Liveness and source freshness must never be conflated.

## 5. Backup and recovery procedures — design only
1. Canonical my-pa DB owner performs a PostgreSQL-consistent complete DB backup including proposed `weather` schema; retain protected dump, checksum and attestation according to my-pa operator standard. An old WeeWX SQLite folder tar is not sufficient.
2. Rehearse full dump restoration **to a newly created disposable PG database only**; verify schema/roles, version compatibility, row counts, raw-event digests, source-to-device lineage, daily rain quality, and actual GET query behavior. Never restore into a live my-pa instance under this plan.
3. Weather-only logical export is optional supplemental evidence, not a stand-alone replacement for shared DB-wide backup. Test constraints and dependencies in scratch.
4. Define operator-approved RPO/RTO after measuring backup/restore. A collector spool reduces short outage loss but cannot restore RF transmissions missed during power-off or guarantee database recovery.
5. After authorized recovery, bring up existing my-pa DB first, verify head and privileges, then weather-app, then replay safe receiver buffers and provider watermarks. Unknown observation periods remain recorded as missing, not reconstructed.
6. Reject corrupt checksums, unknown source database identity, half-applied migration, privilege overreach or unverified backup. Never use `alembic downgrade base`, `down --volumes`, `DROP SCHEMA CASCADE` or blind credential reset as rollback.

## 6. Release and rollback
**Before release:** one accepted plan, accepted superseding ADR, no blocking findings, verified package SHA/tree, pinned source and image digests, SBOM/license check, synthetic tests, real RF gate, current my-pa migration contract, private ingress and exact-head independent reviewer. **Before production:** a second explicit operator approval with named environment, post-change rollback target, backup and DB/proxy permissions.

**Roll forward:** only on the authorized target after preflight; schema migration applied via my-pa operator's approved mechanism; receiver/app container with no public ports; confirmed grant isolation and source liveness; private proxy enabled only after data and security proof. **Roll back:** operator may stop weather-specific services and restore prior compatible images, preserve raw events/spool/history, use a forward-safe repair migration if needed, and never silently downgrade/delete existing my-pa objects. Every changed source or image triggers relevant regression tests and exact-head review.

**Incident matrix:**
- No packets: inspect hardware/USB/decoder/known ID/spool in order; don't infer new sensor identity.
- Missing pressure: label unavailable; WH32B or independently classified WS69 pressure requires real capture; the inspected WH65B branch never emits pressure.
- Negative rain jump: mark unknown reset/rollover, do not insert fabricated rainfall.
- Provider outage: respect Retry-After, stop advancing cursor, show stale and resume idempotently.
- DB overload: throttle weather workload before compromising my-pa; DB operator authorizes tuning.
- Public route leak/credential exposure: stop external ingress, preserve redacted evidence, obtain separate credential action authority.
- Restore failure: fail readiness and withhold commissioning, don't mark recovered.

## 7. Retention, operations calendar and handover
**Proposed, no deletion authority:** immutable event metadata/digests retained as long as referenced measurements (example >=24 months), optional raw JSONB payload separately stored and potentially expired after 90 days only under future authorized policy; observations 12–24 months and derived summary cache longer only if approved; implement no purge until operator approves measured disk/WAL budget, provider retention restrictions and weather-only recovery test. Daily freshness/backup/quota/spool review, weekly dependency/unknown RF trends, monthly scratch restore or approved frequency, quarterly risk/retention and access review.

Handover records actual host/DB identities, current images and source commits, provider/site registrations stored privately, schema/role grants, backup retention+restore, RPO/RTO, license/attribution, sensor replacement steps, confirmed iPhone access, alert recipients, blocked risks and exact operator-only next action. All live evidence remains NOT_VERIFIED until direct runtime tests are performed. For full acceptance identifiers see [09](09_VALIDATION_AND_ACCEPTANCE.md); risk owners [11](11_RISK_AND_DECISION_REGISTER.md).

## 8. Exact traceability
D-006/D-008/D-009/D-012; WP-004/WP-010/WP-011/WP-012; AT-011/AT-012/AT-019/AT-022/AT-023/AT-024/AT-027. All thresholds and backup effects remain PROPOSED until exact-environment evidence and operator approval.

## CR-1 — Corrected recovery, provenance, private cache and operating bounds
**CR-2 operational ownership:** Nonce replay admission is security-operational state, *not* canonical weather history. Each signed request admits at most one durable `(receiver_identity,nonce)` within ±120s server clock skew before members; retain for >=300s after admission with monitored size/index. Neither `weather_app` nor admin/source registration receives nonce or weather-row DELETE/TRUNCATE. A future separately authorized operator-only nonce maintenance path may delete **only expired nonce rows** after the complete replay horizon, with dry-run/volume/clock checks and scratch proof; this is not weather-data purge approval. An untrusted clock or unavailable nonce ledger fails closed before processing any member. Full/raw response digests and normalized semantic model digests remain distinct in backup evidence. Model run→raw event metadata/source/stream FK survives optional payload-only test expiry.

The canonical weather record has immutable `raw_events` metadata/digests, with optional JSONB bytes only in `raw_event_payloads`. A proposed 90-day payload horizon and 24-month measured-observation horizon can coexist because observation and model lineage FKs refer to immutable event metadata with `ON DELETE RESTRICT`, not expiring JSONB; no payload expiry is approved by this plan. Backup/restore AT-019 must use a fresh disposable full my-pa snapshot after a **synthetic operator-authorized scratch-only** payload-expiry example and prove old records, event SHA, source/device/assignment links, role metadata and missing expired bytes; backup may not recreate external secret/credential state without separate owner evidence.

Receiver journal acceptance requires fsynced staging before send, exact per-item committed ACK, mixed batch 207 processing and new nonce/HMAC per attempt without changing first-seen event ID. Process crash, DB outage, spool full, torn file and auth refusal each have separate health and gap evidence. Stream-specific provider cursor failures never change a different site's watermark. Operator-only metadata registration uses approved `weather_admin_cli` and auditable `SET ROLE weather_admin` under my-pa DB gate, **not** normal app permissions.

Private PWA/API defaults: `Cache-Control: no-store` for location/history/weather data and static-only service-worker precache; tailnet/ACL revocation blocks future network access but is not remote device data erasure. Any future offline weather cache requires separate operator privacy approval. Real NAS/USB, backup, DB head, performance, cloud network and iPhone remain unverified. This resolves planning contracts `LHW-RV-002/003/004/006/010` for fresh independent review only, with tests in [09](09_VALIDATION_AND_ACCEPTANCE.md).
