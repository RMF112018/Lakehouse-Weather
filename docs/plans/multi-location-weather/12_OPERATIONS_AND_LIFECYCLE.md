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
**Receiver:** exactly one image with pinned `rtl_433` version, specific approved USB device mapping, read-only config, bounded encrypted/protected local replay spool and rotating logs. Nonroot where USB permission allows; never fall back to `--privileged` without separate security review. Only outbound private authenticated RF-event requests to weather-app, no direct Postgres access. Monitor process, USB disconnect and restart attempts with backoff.

**Weather-app:** exactly one service/ASGI worker and one provider polling owner; Python REST API + static built PWA, limited egress to NWS/Open-Meteo HTTPS, weather-only SQL role, tiny pool (initial proposed <=2, max_overflow=0), bounded batches and timeouts. Enforce no automatic schema creation or migration on startup. Credential references resolved from owner-only mounts or approved secrets manager. No direct WAN port publishing.

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
| browser state | offline cache older than fetch timestamp; no live API | show cached-as-of, never "live" for stale data |
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
- Missing pressure: label unavailable; WH32B/conditional WH65 pressure requires capture provenance.
- Negative rain jump: mark unknown reset/rollover, do not insert fabricated rainfall.
- Provider outage: respect Retry-After, stop advancing cursor, show stale and resume idempotently.
- DB overload: throttle weather workload before compromising my-pa; DB operator authorizes tuning.
- Public route leak/credential exposure: stop external ingress, preserve redacted evidence, obtain separate credential action authority.
- Restore failure: fail readiness and withhold commissioning, don't mark recovered.

## 7. Retention, operations calendar and handover
**Proposed, not authorized for deletion:** raw input 30–90 days, high-resolution observations 12–24 months, longer daily summaries; implement no purge until operator approves measured disk/WAL budget, provider retention restrictions and weather-only recovery test. Daily freshness/backup/quota/spool review, weekly dependency/unknown RF trends, monthly scratch restore or approved frequency, quarterly risk/retention and access review.

Handover records actual host/DB identities, current images and source commits, provider/site registrations stored privately, schema/role grants, backup retention+restore, RPO/RTO, license/attribution, sensor replacement steps, confirmed iPhone access, alert recipients, blocked risks and exact operator-only next action. All live evidence remains NOT_VERIFIED until direct runtime tests are performed. For full acceptance identifiers see [09](09_VALIDATION_AND_ACCEPTANCE.md); risk owners [11](11_RISK_AND_DECISION_REGISTER.md).

## 8. Exact traceability
D-006/D-008/D-009/D-012; WP-004/WP-010/WP-011/WP-012; AT-011/AT-012/AT-019/AT-022/AT-023/AT-024/AT-027. All thresholds and backup effects remain PROPOSED until exact-environment evidence and operator approval.
