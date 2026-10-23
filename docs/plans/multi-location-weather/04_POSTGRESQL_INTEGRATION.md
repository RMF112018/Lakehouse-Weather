# 04 — my-pa PostgreSQL integration contract
**Package:** LHW-ML-20261023 | **CP-3** | **STATUS: PROPOSED / DB IMPLEMENTATION BLOCKED**
**Basis:** my-pa `main@3d1593aa4dc2477395b47c97067338f8c46eff0b`; repository migrations head `6f1476b8da52` (121 revisions **per current repository index**, not live attestation). See [01 audit](01_SOURCE_AND_SYSTEM_AUDIT.md), [05 domain](05_WEATHER_DATA_MODEL.md), [11 decisions](11_RISK_AND_DECISION_REGISTER.md).
**Hard stop:** this document is not SQL execution authority; actual runtime alias, server version, role/grant inventory, database connection string, applied Alembic revision, capacity and backup success are **UNRESOLVED**.

## 1. Canonical ownership and authorization gate
The **existing physical PostgreSQL cluster/database used by my-pa**, after independent authorized identity attestation, will hold weather data in a proposed isolated schema named **`weather`**. No second independent Postgres, SQLite WeeWX archive, Influx or TimescaleDB. Logical DB remains `my_pa`; actual physical name/endpoint may be a compatibility alias under my-pa ADR-002 and MUST NOT be guessed. The weather application owns the *semantics* and data contract for weather tables; **my-pa owns DDL migration application, server/database operational policies and authentication to the shared DB**.

Current my-pa sources: `migrations/README.md` explicitly "Alembic owns every schema change to canonical my_pa"; `migrations/env.py` requires separate `MY_PA_MIGRATION_DATABASE_URL`, keeps Alembic version in default schema, uses one transaction per revision, and refuses to fall back to runtime `MY_PA_DATABASE_URL`; `src/my_pa/bootstrap/settings.py` rejects unknown `MY_PA_*`; `src/my_pa/infrastructure/database/engine.py` has pool_size=5/max_overflow=0; `ops/compose/postgres.yml` is **development-only** (postgres:17.10), while `docs/decisions/ADR-008-nas-runtime-topology.md` and `ops/nas/compose.example.yml` are staged target not proven live.

**GATE-DB approval needs:** (a) operator-authorized non-mutating runtime census of target cluster, (b) joint Lakehouse/my-pa migration and role design review, (c) operator permission for separately scoped **my-pa repository change** in a new branch, (d) disposable-DB migration+grant+backup/restore tests and independent exact-head review, (e) separate permission to apply a migration to the selected actual database. A passed plan or GitHub review is not (e). Never run `alembic upgrade` against unverified endpoints; do not touch production during this assignment.

## 2. Objects and SQL contract (proposed, not deployed)
Schema `weather` should be created via **one additive, forward-safe my-pa Alembic revision on whatever is then current single head**, with per-revision transaction. A version head recorded here is historical review basis, not a future revision parent. Migration code must qualify `weather.` tables/functions explicitly, avoid altering existing schemas/functions/roles, use idempotent existence checks *only where compatible with Alembic ownership*, and handle re-running on scratch deterministically. Never use `Base.metadata.create_all` on shared database.

| Table | Ownership, core columns and constraints |
|---|---|
| `weather.locations` | `location_id uuid PK`; display label, coordinate pair (both null or both present), elevation m nullable, validated IANA zone, privacy class, active, created/updated UTC. No guessed coordinates. |
| `weather.station_installations` | `station_id uuid PK`, local site label, created/retired timestamps. A logical local installation independent of hardware replacements or moves. |
| `weather.sources` | `source_id uuid PK`, provider code, `source_kind` closed vocabulary, external identifier, `station_id nullable FK`, capabilities, attribution/license profile, active, credential **reference only**, created/retired UTC. Natural `(provider_code,external_identifier)` uniqueness only when provider contract makes IDs stable. |
| `weather.devices` | `device_id uuid PK`, `station_id FK`, model/decoder family, observed RF identifier and identity epoch, effective_from/effective_to, status, battery marker. Device records immutable for measurement lineage after retirement. |
| `weather.source_assignments` | `assignment_id uuid PK`, `source_id FK`, `location_id FK`, `effective_from/effective_to`, preferred rank, actual sensor/provider-site coordinates where available, assignment method. Historical rows never silently overwritten. Reject intervals with `effective_to<=effective_from`. |
| `weather.raw_events` | `event_id uuid PK`, `source_id FK`, `device_id nullable FK`, `receiver_event_key` or provider event key, source_time nullable, received_at, ingested_at, decoder/adapter version, content digest, immutable SHA-256 metadata and correction lineage; JSONB content is stored separately in `raw_event_payloads`, not this long-lived row. Unique logical event fingerprint with explicit correction version. |
| `weather.raw_event_payloads` | `event_id uuid PRIMARY KEY/FK` to immutable `raw_events` (`ON DELETE RESTRICT`), sanitized JSONB payload, payload digest and storage time. Independent short-horizon retention may remove only this row under future operator authorization, never the referenced event identity. |
| `weather.provider_streams` | `stream_id uuid PK`, immutable `source_id`, optional `assignment_id` (required for per-coordinate forecasts/model), product kind, qualified site/coordinate basis, canonical request fingerprint and unique `stream_key_digest`; immutable association to provider and source. |
| `weather.observations` | `observation_id uuid PK`, `event_id FK`, `assignment_id FK`, `source_id FK` (must match event+assignment), `device_id nullable`, metric code, `observed_at timestamptz`, `observed_at_basis`, `ingested_at`, `value_canonical numeric`, `unit_code`, validation status and reason, `supersedes_observation_id nullable FK`, normalization version; unique `(event_id,assignment_id,metric_code,normalization_version)`. Physical measurements **only**. |
| `weather.model_runs` | `model_run_id uuid PK`, `stream_id/source_id` matching composite FK, product kind `forecast/model_analysis`, provider model version, true issue/init time when provided, fetched_at, external run identity or `run_identity_status=UNKNOWN` retrieval snapshot SHA/revision and raw metadata link. |
| `weather.model_values` | `model_value_id uuid PK`, qualified `model_run_id/stream_id/source_id` FK and `(assignment_id,source_id)` composite FK, half-open validity, canonical unit/value, optional uncertainty, quality, model kind and linked supersession revision; cannot appear in measured `observations`. |
| `weather.poll_state` | `stream_id PK FK` to `provider_streams`, last attempt/success/watermark, next permissible attempt, consecutive failure count, last failure category, optimistic version. Only this and bounded quota/nonce operational state may be updated by application role. |
| `weather.provider_quota_usage` | Per admitted provider/entitlement/UTC window, conservatively reserved effective quota units (not only raw GET count), durable across streams and restarts. |
| `weather.transport_nonces` | Unique receiver identity/nonce, timestamp and expiry for request HMAC anti-replay; event replay identities remain independent and stable across re-signing. |
| `weather.metadata_transitions` | Append-only operator request/actor/reason, entity kind/ID and before/after digest; written atomically with permitted metadata registration or one-time retirement. |
| `weather.aggregates` (conditional) | Computed hourly/daily aggregates by location, time interval, metric, selected source/algorithm/version, completeness and contributing sample/cutoff evidence. Purely derived rebuildable performance cache after benchmark, never physical measured observation; rainfall increments/rates are computed on read in MVP. |

**Naming/type rules:** PostgreSQL `timestamptz` UTC instants, no local timestamps as stored authority; range checks for coordinates, nonnegative physically bounded humidity/rain values, measured site vs display coordinate distinction; metrics normalized to **SI units** (temperature degC, speed m/s, distance mm, pressure hPa, direction deg, irradiance W/m², illuminance lux); no double/float conversion in persisted decimals without documented scale. For ephemeral sensor/broker timing, preserve original string/time basis in raw event. Missing metric => no observation/null API; never invent zero.

**Illustrative constraints to require in migration review** (pseudocode, NOT ready-to-run migration):
~~~sql
CHECK (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180);
CHECK ((latitude IS NULL) = (longitude IS NULL));
CHECK (effective_to IS NULL OR effective_to > effective_from);
UNIQUE (event_id, assignment_id, metric_code, normalization_version);
-- source_id/assignment_id/device_id cross-consistency requires
-- composite FK or BEFORE INSERT trigger plus negative tests;
-- enforce append-only using restrictive GRANTs and triggers.
~~~
Use real CHECK names (63-byte-safe); test constraint violations in isolated PostgreSQL. Define a migration-compatible naming convention and SQLAlchemy metadata isolated to `weather` with `search_path` explicitly constrained; app credentials cannot DDL or run migrations. If deployment identity uses database schemas containing tenant partitioning in my-pa, keep all weather tables outside those policies unless approved, and never join private my-pa records by implicit principal.

## 3. Role and network design (proposed)
- `weather_owner`: **NOLOGIN**, DDL ownership via explicitly authorized role management, not supplied to services.
- `weather_migrator`: **NOLOGIN** or isolated authorization role, used only by authenticated my-pa migration operator; never included in weather-app env.
- `weather_app`: restricted LOGIN identity (exact name/credentials subject to operator policy) with `USAGE weather`, scoped `SELECT` and `INSERT` into raw event metadata, optional payload, measured observations, model snapshots and authentication nonces; `UPDATE` only bounded per-stream poll state and approved quota ledgers. **No metadata registration/retirement**, historic row rewrite, `TRUNCATE`, `DELETE`, DDL, `BYPASSRLS` or cross-schema privileges.
- `weather_admin` (NOLOGIN/NOINHERIT) via separately credentialed operator `weather_admin_cli` (LOGIN NOINHERIT; explicit `SET ROLE`) is proposed for CLI-only controlled metadata INSERT/one-time retirement with audit. The runtime `weather_app` is not a member; no DDL or cross-schema rights.
- `weather_retention_executor` is an uncommissioned, operator-only future payload-expiry role. **No retention deletion grants or actions are authorized here.**
- `weather_reader`: optional restricted SELECT if a future separate read-only UI service is introduced; initial combined service can use weather_app but **never expose SQL or direct browser DB access**.
- Receiver has **no database credential** and no direct network route to PostgreSQL. It can only send authenticated packets to the internal app endpoint, through a firewall/Compose network rule.
- Existing my-pa service roles, owner/grants, default search_path and migration credentials must remain untouched. No inherited `my_pa` superuser or historical `my_pa_runtime` role for weather writes.

**Migration authority split:** Lakehouse authors fixture specifications/data contract; my-pa repo owns actual SQL Alembic revision and governed role-provisioning scripts. If migration review forbids externally owned tables in the shared physical database, the exact exception requires a **new accepted my-pa ADR**; the request's DB requirement does not itself supersede that policy.

## 4. Isolation, idempotency and operational limits
Proposed initial weather-app DB pool: `pool_size <= 2`, `max_overflow=0`, 5–10 second statement timeout for ordinary ingestion/read queries, 2s connect timeout, bounded batch size <=100 events or <=500 observation rows, one producer instance; these are **proposed budgets** and MUST be revised against measured PG `max_connections`, observed my-pa resource usage and test benchmarks. Use INSERT ... ON CONFLICT for event identity and sample idempotency; **never** use blind REPLACE/DELETE. Source event and dependent observations enter same transaction. Provider pagination/watermarks advance in same or safely replayable unit of work. If DB responds overloaded/timeout, back off with jitter, keep bounded receiver spool and reflect stale state; never spin retry loops.

Indexes: unique raw `(source_id,provider_event_key,revision)` or receiver UUID; `observations(assignment_id,metric_code,observed_at DESC)`; `model_values(assignment_id,valid_start DESC,metric_code)`; `raw_events(received_at)`; `source_assignments(source_id,effective_from)`; `poll_state(next_permitted_at)`. Test actual queries with `EXPLAIN (ANALYZE, BUFFERS)` in scratch populated with synthetic time-series. Partition monthly only if measured retention/delete performance justifies it; partition design and unique keys are interdependent and must be re-reviewed before any migration claiming global uniqueness.

**Volume planning example (not an observed workload):** 1 WH65B packet every ~16s yields about 5,400 packets/day. At 8 metrics each, unthrottled normalized storage can approach ~43,200 metric rows/day (~15.8M/year) *before* remote locations. PostgreSQL indexes/WAL substantially increase on-disk bytes; measure with synthetic inserts, not a fixed GB promise. **FK-compatible example, not approved retention:** keep immutable `raw_events` identity/digest at least as long as referenced observation/model records (e.g. >=24 months); only separately stored `raw_event_payloads` may qualify for optional 90-day payload expiry under future operator authorization. Fine-grain observations may be retained 12–24 months and derived caches longer if approved; **no automated purge** without separately operator-approved retention schedule and a tested weather-only backup/restore/delete workflow.

## 5. Backup, migration validation and reversibility
The shared physical DB is backed up under my-pa's existing approved consistent `pg_dump` / operator attestation path, not the old `scripts/backup.sh` WeeWX tar. Verify weather tables appear in whole-DB dump; restore **to a new disposable DB** including both my-pa and weather; test weather-only logical recovery and cross-schema nonmutation. Required protections: backup taken before any authorized schema migration, verified checksum/list, explicit target, same snapshot consistency, no unsupported destructive downgrades, documented migration rollback decision. Weather-only maintenance may use `pg_dump --schema=weather` as **supplemental** backup but may not replace the canonical DB backup. Do not independently restore partial weather into live my-pa without operator approval.

**Tests AT-011/AT-012/AT-015/AT-019/AT-023:** single-head migration from empty and preceding revision; existing my-pa schema diff zero except approved `weather` objects; wrong-role `CREATE/DROP/TRUNCATE/UPDATE` denied; app pool peak <=admitted; restart/replay idempotency; missing migration URL refuses; full and weather-only scratch restore checksums; heavy ingest concurrency and timeout protect my-pa; retention blocked without approval.

## 6. DB no-go checklist
- No authenticated existing database/target identity.
- No accepted design by the my-pa DB owner or approved schema change.
- Live Alembic head differs from authenticated migration basis without reconciliation.
- App requires superuser or grants beyond `weather`.
- No reproducible empty-to-head and populated-from-prior-head isolated migration proof.
- Backup/restore attestation missing; WAL/disk/connection headroom not measured.
- Deployment requires PostgreSQL TCP port exposed to browser/WAN.
- Any migration modifies my-pa-owned legacy tables, principal grants, knowledge schemas or user data.
Each is independently blocking; no implication that approval of this document waives a gate.

## 7. Correction CR-1 — binding planning contract (not executable DDL)

The decisions below resolve `LHW-RV-002/003/004/005/007`. All actual DDL, owner/role provisioning and constraint definitions belong to separately authorized **my-pa** Alembic work. Nothing in this correction creates a schema or grants access.

### 7.1 Data identity and referential constraints

| Invariant | Required enforcement in my-pa migration design | Negative proof |
|---|---|---|
| Long-lived event lineage | `raw_events(event_id,source_id)` UNIQUE and immutable; `raw_event_payloads(event_id)` FK `ON DELETE RESTRICT`; observations reference immutable event metadata `ON DELETE RESTRICT`. No historical FK uses CASCADE or SET NULL. | Deleting payload leaves source/digest/observation join intact; deleting referenced event is denied |
| Same-source observations | `observations(event_id,source_id)` FK to `raw_events(event_id,source_id)` and `(assignment_id,source_id)` FK to `source_assignments(assignment_id,source_id)`; both parent pairs UNIQUE. | Reject event/assignment from another source |
| Local device/site | Source and device have station FKs; BEFORE INSERT guard locks and checks `devices.station_id = sources.station_id`, valid epoch for event observed time; physical local reading requires `device_id`. | Reject wrong station, retired device or missing required device |
| Assignment validity | UTC half-open `[effective_from,effective_to)` with check `to > from`; metadata transaction locks `sources` row before overlap query, prevents overlapping same source/location and *any* simultaneous locations for local ambient source; externally measured site source may share locations. | Concurrent local cross-location assignment conflict rejected; shared NWS station succeeds |
| Physical device epochs | Stable `device_id`, immutable station/model/RF identity and effective start; guarded nonoverlap per `(station_id,model,rf_sensor_id)` via station row lock. | Duplicate overlapping epoch refused, retired history remains |
| Independently polled product | `provider_streams(stream_id,source_id)` UNIQUE, unique immutable request/site digest, optional `(assignment_id,source_id)` composite FK to assignments; coordinate/model/forecast stream must bind its assignment, shared upstream measured station stream may omit it. | Two sites' forecast cursors cannot alias; same upstream NWS observation stream can serve both |
| Stream-specific polling | `poll_state(stream_id)` PK/FK; cursor and watermark change in the same successful per-stream write transaction; `provider_quota_usage` per entitlement UTC period is reserved atomically across all streams. | A succeeds, B fails, B later replays without missing its records |
| Receiver/provider idempotency | Unique `(receiver_identity,receiver_event_id)` and `(stream_id,provider_event_key,revision)` when present; reused identity with different SHA-256 is conflict, not an update. | Same event retry count invariant, changed digest blocked |
| Model and forecast lineage | `model_runs(stream_id,source_id)` composite FK to streams, unique `(model_run_id,stream_id,source_id)`; model values reference that run and matching `(assignment_id,source_id)`; per-coordinate product must match run stream assignment; valid end after start. | Cross-site and cross-source forecast values refused |
| Append-only corrections | `observations.supersedes_observation_id` self-FK RESTRICT and partial UNIQUE predecessor; insert guard enforces same source/assignment/device/metric and strictly later revision; accepted observations never UPDATE/DELETE. Equivalent source/run/interval restrictions for model corrections. | Second successor, cross-source correction and deleted history refused |
| Governed metadata | Admin-only field/transition grants and BEFORE UPDATE retirement/immutability guard, with same-transaction append-only `metadata_transitions` record. | Unlogged transition and non-operator writes refused |

Do not treat client-side validators as the sole protection of these invariants. Concurrency/range checks must run in the database with parent-row locking; test transaction races and failure rollback in disposable PostgreSQL. Reconcile the concrete migration and index/lock plan to then-current my-pa head before a separately authorized implementation.

### 7.2 Metadata privileges and governed transitions

`weather_app` may SELECT registered weather metadata and INSERT immutable raw metadata/payload/physical observations/model snapshots, plus bounded updates to per-stream poll/quota operational state. It may not create/retire sources, stations, devices, assignments or provider streams; neither it nor the receiver holds DDL or other my-pa schema rights. The operator-only `weather_admin_cli` receives distinct credentials from an approved operator mechanism; it may `SET ROLE weather_admin` only after authenticated authorization. The `weather_admin` NOLOGIN role has narrow INSERT grants on `locations`, `station_installations`, `sources`, `devices`, `source_assignments` and `provider_streams`, and column-limited UPDATE to display labels, status/retirement dates and permitted preference fields. Guard triggers refuse edits to historical foreign keys, source identities, station/coordinate/timezone/effective starts or completed retirement intervals; a coordinate/timezone relocation creates a **new location identity** until a separately designed location-history model is approved. Every permitted transition atomically records actor, request ID, reason and before/after hash in `metadata_transitions`. No public admin HTTP endpoint. my-pa DB owner must separately review NOINHERIT/SET ROLE grants, secret lifecycle, trigger ownership and safe `search_path`.

### 7.3 Provenance-preserving illustrative retention

A **90-day payload / 24-month observation** example is feasible because immutable `raw_events` metadata remains for >=24 months, and only optional `raw_event_payloads` bytes can be removed *after* an independently authorized operator retention action. Historical joins preserve event ID, SHA-256 digest, decoder version, source, device, measurement and ingestion times; deleted payload means original bytes can no longer be re-normalized, so do not claim byte-perfect replay after expiry. The physical event metadata and all referenced observations stay nondeletable under normal grants. Before any future retention action, require licensing/privacy classification, full consistent my-pa backup, scratch-only authorized payload-expiry simulation, FK verification and before/after restore/digest evidence. **No purge, grants, credentials, DDL or live SQL are permitted under this plan.**

### 7.4 Derived rainfall projection

Select deterministic **on-read** computation. Only cumulative `rain_counter` is a physically measured observation. Derived `rain_increment`, `rain_rate` and local-day totals never enter `observations`; API computations select current effective accepted predecessor/current counters within the same device/source epoch, with observation IDs, UTC interval, local IANA zone, DST/midnight/gap/reset quality, algorithm version and `as_of_ingested_at` cutoff. NULL+reason denotes unknown, not zero. A future stored `aggregates` table is only a rebuildable cache after benchmark/independent contract review.

**Traceability:** `LHW-RV-002/003/004/005/007` → `D-001/004/007/008/009` → `WP-004/005/007/008/012` → `AT-007/008/011/012/013/014/018/019/021/023`. All proofs are future isolated tests.
