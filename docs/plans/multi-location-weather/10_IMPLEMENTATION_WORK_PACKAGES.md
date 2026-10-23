# 10 — Dependency-ordered implementation program
**LHW-ML-20261023 | CP-5 | PROPOSED / planning-only.**
A separate authorized local development agent should implement from this plan **only after independent plan review** and any required repository-specific operator gates. The Lakehouse planning branch does not authorize my-pa changes, production database connections, real provider secrets, or runtime deployment. Work packages are individually bounded, stable IDs **WP-001..WP-012**, not preapproved implementation tasks. Scope, evidence and tests map to [09](09_VALIDATION_AND_ACCEPTANCE.md). Risk IDs and decisions map to [11](11_RISK_AND_DECISION_REGISTER.md). Relative effort estimates are **engineering person-days** at an experienced developer baseline; illustrative ranges, not delivery commitments.

## 1. Work package dependency matrix and critical path
| WP | Phase / primary repo | Prereqs | Estimated effort | Gate/AT |
|---|---|---|---:|---|
| WP-001 | Authority and existing source audit / both read-only | none | **2–4d** | AT-024 |
| WP-002 | Architecture ADR, version/dependency admission / Lakehouse | WP-001, plan independent review | **3–5d** | AT-024 |
| WP-003 | Physical SDR RF feasibility / Lakehouse + authorized DS923+ | WP-001, receiver hardware present and non-mutating NAS approval | **2–6d** active + 24h observation | AT-001..AT-005 |
| WP-004 | Shared PG contract, scratch migration design & separately authorized implementation / **my-pa** | WP-001, WP-002 + my-pa DB owner/operator approval | **8–15d** | AT-011, AT-012, AT-015, AT-019 |
| WP-005 | Source-aware domain, quality, repository & API contract / Lakehouse | WP-002, WP-004 contract and disposable schema | **10–17d** | AT-006..AT-009, AT-013, AT-014, AT-021, AT-026 |
| WP-006 | RF decoder/receiver and replay / Lakehouse | WP-003, WP-005 DB+normalization contract | **8–14d** | AT-002..AT-010, AT-025, AT-027 |
| WP-007 | External NWS and conditional Open-Meteo adapters / Lakehouse | WP-005; provider terms approved | **6–10d** | AT-013, AT-016, AT-018, AT-025, AT-027 |
| WP-008 | Hourly/daily history and aggregate correctness / Lakehouse | WP-005, WP-006 or synthetic event fixtures, WP-007 | **5–9d** | AT-008, AT-014, AT-023 |
| WP-009 | Responsive read-only PWA, multi-location comparisons / Lakehouse | WP-005 API contract; WP-008 for summaries and charts | **10–18d** | AT-017, AT-018, AT-020, AT-021, AT-026 |
| WP-010 | Tailscale/private ingress, security and permission proof / Lakehouse + authorized NAS | WP-005, WP-009 interface; current NAS policies verified | **4–7d** | AT-020, AT-022 |
| WP-011 | Integration, performance, failure injection and independent review / Lakehouse + my-pa scratch | WP-004..WP-010 | **10–18d** | AT-001..AT-027 as applicable |
| WP-012 | Operations, backup, restore, lifecycle, staged handover / both governance; Lakehouse runtime docs | WP-004, WP-010, WP-011, operator recovery target and authorization | **5–9d** | AT-019, AT-023, AT-024, AT-027 |
**Revised provisional total:** **73–132 person-days** (previous 53–95d was arithmetically correct but optimistic for isolated migration/role constraints, replay, accessibility and integration) excluding elapsed hardware delivery, provider approval, operator decisions, actual production commissioning and schedule slack. Parallelism can reduce elapsed time but not total effort. 24h RF soak adds a wall-clock day, not a full engineer-day. The range is a **planning estimate only**. Avoid calendar promises without staffing, hardware and actual DB topology.

**Critical path:** WP-001 -> WP-002 -> **WP-004 my-pa schema authority** -> WP-005 -> WP-007/WP-006 -> WP-008 -> WP-009 -> WP-010 -> WP-011 -> WP-012. WP-003 -> WP-006 is a parallel physical bottleneck; if hardware is absent, WP-004 isolated design, WP-005 domain and WP-007 synthetic adapters can proceed after their gates without falsely passing RF. Hardware-dependent code should not be declared end-to-end accepted until Gate RF and WP-006 are complete. Provider terms approval is an independent stop before any real Open-Meteo source enrollment.

## 2. Executable package contracts
Each package below identifies exact repo, objective, inputs, dependencies, implementation method, deliverables, test, risk and **out-of-scope**. No package waives separate implementation/DB/production authorizations.

### WP-001 — Authority and environment census
- **Objective:** refresh both current repos/commit trees, governance, all Lakehouse source files, my-pa migration/model/backup policies and actual physical NAS/PG configuration **read-only only with operator consent**.
- **Repositories/components:** `RMF112018/Lakehouse-Weather` docs; `RMF112018/my-pa` inspected read-only; DSM/PG status collected via approved agent outside repo.
- **Inputs/dependencies:** CP-1 [01 audit](01_SOURCE_AND_SYSTEM_AUDIT.md); current GitHub auth; current `AGENTS.md` for my-pa; site hardware/DB admin availability. None prior.
- **Method/output:** source census with SHA of every controlling file, reconcile stale my-pa docs, capture redacted DSM version, source image digests, actual DB version, applied Alembic head, schema/role/grant inventory and existing workload/backup policy. Classify missing evidence as UNKNOWN.
- **Acceptance/tests:** AT-024, read-only queries/probes with explicit authorization, zero write, all conflicts logged. **Effort:** 2–4d. **Risks:** RSK-001, RSK-002. **Excludes:** SQL grants/migration/credentials, deployment and collection of private location unless approved.

### WP-002 — Architecture and dependency decision
- **Objective:** formally accept/revise Option C after independent review; preserve and explicitly supersede original WeeWX ADR before touching runtime design.
- **Repo:** Lakehouse `docs/adr/`, `README.md`, `ROADMAP.md`, `docs/ARCHITECTURE.md`, `UPSTREAMS.lock`, license inventory.
- **Inputs/deps:** WP-001, CP-2/3/4/5 review, accepted resource/security constraints, no blocked major design.
- **Method/output:** proposed ADR-0002 with rejections and reopen criteria; keep ADR-0001 provenance; file-level change/owner plan; pin decoder SHA and OCI image digest; record upstream license distribution obligations and actual support versions. Do not silently remove vendor submodules.
- **Acceptance/tests:** AT-024, no contradictory active ADR, all model/DB/source requirements mapped; architecture reviewer decision against exact SHA. **Effort:** 3–5d. **Risks:** RSK-009, RSK-014. **Excludes:** runtime migration, deployment, unrelated refactors or decommissioning old files without approval.

### WP-003 — SDR and sensor proof
- **Objective:** determine whether NAS USB and local sensor reception meet proof gates, without implementing application.
- **Repo/component:** Lakehouse `scripts/gate1-rf-test.sh`, `scripts/synology/usb-device-info.sh`, `docs/runbooks/gate-1-rf.md`, `tests/fixtures/rf/`; physical DS923+ with selected Nooelec if received.
- **Inputs/deps:** WP-001, installed real dongle+antenna and bounded read-only system access; pin older decoder and optional candidate newer build as test variants.
- **Method/output:** host enumerate; container device/open test; 5min WH65B sample; 24h soak; optional WH32B; image/tool info; antenna notes; capture rate and receiver/process restart evidence; sanitized fixture and private capture digests. Document DSM USB failure and lowest-cost Linux host fallback if necessary.
- **Acceptance/tests:** AT-001..AT-005; no guessed packet IDs, no unsupported pressure claim. **Effort:** 2–6 active days + 24h soak. **Risks:** RSK-002,003,016. **Excludes:** permanent deployment, public networking, new receiver purchases until diagnostics.

### WP-004 — Shared my-pa PostgreSQL, restricted role and migration gate
- **Objective:** prove shared-schema approach is allowed and safe; **only under a separately authorized my-pa change scope** implement the one additive migration/role contract in my-pa repo and disposable DB.
- **Repo:** `RMF112018/my-pa` `migrations/`, `ops/postgres/`, `tests/schema/`, `tests/database/`, its owning ADR/index; Lakehouse [04](04_POSTGRESQL_INTEGRATION.md) is contract, not migration code.
- **Inputs/deps:** WP-001, WP-002, true main/head, DB owner go decision and independently identified scratch instance. Before live SQL need separate explicit operator authorization, not supplied by this plan.
- **Method/output:** weather-only schema DDL matching [04 §7](04_POSTGRESQL_INTEGRATION.md) with immutable raw event metadata plus separate payload, source/assignment/provider stream and per-stream state, composite FK/half-open range/epoch/correction guards, operator-only `weather_admin_cli` NOINHERIT/SET ROLE and metadata audit, bounded nonce/quota state, migrations from empty+preceding head, pool limits and exact readback; verify no existing my-pa object change except approved permission metadata. Design backup/restore and reversible-by-forward-migration policy; no silent downgrade.
- **Acceptance/tests:** AT-011,012,015,019 on scratch; independent exact-head review; no app superuser rights. **Effort:** 8–15d. **Risks:** RSK-001,007,011. **Excludes:** production schema application, credential rotation, historical my-pa data refactor, independent Lakehouse migration history.

### WP-005 — Domain model, normalization, persistence and read API
- **Objective:** fully model locations, multiple sources/assignments, local station+sensor epochs, raw events, measured observations, modeled forecasts, corrections and quality; offer versioned source-safe query API.
- **Repo:** Lakehouse `src/lakehouse_weather/{domain,application,infrastructure,api}/`, `tests/{unit,contract,integration}`.
- **Inputs/deps:** WP-002 accepted ADR, WP-004 approved schema contract and disposable isolated DB; synthetic cases SC-01..SC-05.
- **Method/output:** closed metric enum + unit version; deterministic UUID/key strategy; time-range/cross-entity constraint consistency, source/stream identity, role-gated metadata transitions, transactional idempotence, source precedence, **on-read DERIVED rain projection** (never in measured observations), local-day DST, forecast separation; SQLAlchemy explicit schema refs; FastAPI GET schemas with cursor/freshness/error envelope. Fail closed on missing schema; no automatic DDL.
- **Acceptance/tests:** AT-006..AT-009, AT-013..AT-015, AT-021, AT-026 and invariant I-01..I-12. **Effort:** 10–17d. **Risks:** RSK-004,005,007,013. **Excludes:** RF hardware collection and live provider calls.

### WP-006 — Local SDR decoder, collector and replay
- **Objective:** deliver weather records from only one local physical WS-2000 installation through the NAS to canonical PG with stable provenance and bounded failure behavior.
- **Repo:** Lakehouse `docker/receiver/`, `src/lakehouse_weather/{ingestion/receiver.py,infrastructure/spool.py,api/internal_ingest_routes.py}`, `config/rtl_433/`, `scripts/`, tests.
- **Inputs/deps:** WP-003 RF proof; WP-005 normalization and transactional ACK; stable sensor IDs and fields; NAS service security constraints.
- **Method/output:** pinned `rtl_433` child/NDJSON reader, stable first-seen event UUID, strict model mapping (WH65B ≠ WS69 pressure), signed `rf-batch.v1` with fresh HMAC nonce per attempt, fsync+rename+directory-fsync durable journal, independently committed per-item digest-bound 200/207 ACK, terminal/conflict isolation, retry/backpressure and spool saturation/loss alert; never grant database to receiver.
- **Acceptance/tests:** AT-002..AT-010, AT-025, AT-027; fuzz input, restart between DB commit/ACK, spool full. **Effort:** 8–14d. **Risks:** RSK-002,003,004,008,010. **Excludes:** remote extra SDR stations, anonymous MQTT, private raw RF upload to public GitHub.

### WP-007 — Remote network-source adapters
- **Objective:** support independently located observations and forecast model series without conflating measured and modeled data.
- **Repo:** Lakehouse `src/lakehouse_weather/ingestion/providers/{nws.py,open_meteo.py,http_client.py}`, `application/provider_poll_loop.py`, `tests/fixtures/{nws,open_meteo}`.
- **Inputs/deps:** WP-005; operator-approved location coordinates/site selection, NWS user agent contact metadata, provider terms/attribution and any key entitlement; no assumed consumer coordinates.
- **Method/output:** bounded per-`provider_stream_id` HTTP GET with ETag/Retry-After/independent cursor, source/site-vs-forecast stream classification, independently authorized metadata admission, NWS shared observed station vs per-coordinate grid, optional Open-Meteo modeled Best Match `run_identity_status=UNKNOWN` with response-digest snapshot revisions/heartbeat only when unchanged, durable **effective weighted quota units** and per-stream stale status; 401 stops, 429 backs off.
- **Acceptance/tests:** AT-013,016,018,025,027, both measured remote and modeled fixture. **Effort:** 6–10d. **Risks:** RSK-005,006,010,015. **Excludes:** new commercial APIs, indefinite provider raw retention, public provider proxy or fake historical backfill.

### WP-008 — History, summaries and environmental calculations
- **Objective:** expose accurate hourly/daily/site-local summaries without silently manufacturing complete history.
- **Repo:** Lakehouse `application/summarize.py`, `domain/rain.py`, query code/optional aggregate table if benchmark justifies, `tests/golden/`.
- **Inputs/deps:** WP-005, normalized rainfall/temp/wind samples, WP-006 or synthetic local captures, WP-007 for remote metrics and source rules.
- **Method/output:** UTC queries with IANA local-day windows, missing/stale gaps, reset-aware **on-read derived rain** carrying two immutable counter observation IDs and `as_of_ingested_at`, wind direction circular mean, interval peak gust semantics, algorithm version/input evidence and optional rebuildable aggregate performance measurement. Only introduce stored aggregates/partitions after benchmark.
- **Acceptance/tests:** AT-008,014,023; high/low sum expected, DST fall-back repeated hour not double counted, gap completeness explicit. **Effort:** 5–9d. **Risks:** RSK-004,012,013. **Excludes:** scientific nowcasting, unvalidated pressure correction, automatic irreversible purges.

### WP-009 — iPhone-first multi-location dashboard
- **Objective:** deliver private, responsive one/two/multi-column UI with multiple locations/sources and measured vs forecast distinctions.
- **Repo:** Lakehouse `web/`, app static asset serving, `tests/e2e/`.
- **Inputs/deps:** WP-005 API contracts and WP-008 history/summary; synthetic provenance fixtures, UI accessibility acceptance.
- **Method/output:** React/TypeScript/Vite PWA, site picker, conditions/forecasts/physical observations vs explicitly DERIVED rain, source badges/timestamps, accessible comparisons, stale/partial/offline states; **default service-worker static assets only, private API no-store**, optional Home Screen install; no remote wipe guarantee. Bundle web static output in weather-app image; no public write UI.
- **Acceptance/tests:** AT-017,018,020,021,026; automated browser/VoiceOver manual iPhone proof. **Effort:** 10–18d. **Risks:** RSK-005,012. **Excludes:** push alerts, geofencing, public multiuser portal, arbitrary user-supplied geocoding.

### WP-010 — Private ingress, container hardening and security gate
- **Objective:** permit secure iPhone remote UI without exposing sensor, app write path or database.
- **Repo:** Lakehouse `compose.yaml`, `config/security/`, `docs/security.md`, private ingress operator configuration; my-pa existing proxy not mutated.
- **Inputs/deps:** WP-005/API path policy and WP-009 PWA, verified tailnet ACL/HTTPS and actual NAS network. Security reviewer admission.
- **Method/output:** loopback/private proxy allowlist, HTTPS via Tailscale Serve, no public ingress, weather app vs operator metadata-role isolation, nonroot images, egress restrictions, HMAC RF ingress with durable nonce replay proof, no-store private API and denied internal/admin routes, tests and minimal redacted logs.
- **Acceptance/tests:** AT-020,022, no DB port on WAN/LAN, authorized cellular iPhone access, blocked `/internal` and `/api` mutation, rotation/revocation procedure. **Effort:** 4–7d. **Risks:** RSK-008,009. **Excludes:** public Cloudflare activation, new DNS, MY-PA auth grant mutation, credential updates without approval.

### WP-011 — E2E reliability, load and independent exact-head review
- **Objective:** demonstrate full path on test/safe pilot, no regressions or unresolved high-risk findings before production decision.
- **Repo:** Lakehouse `tests/{integration,e2e,security,performance}`, CI; my-pa **scratch tests only**.
- **Inputs/deps:** WP-004..010, current repo exact head/tree, known NAS budgets, synthetic scenarios, physical capture when permitted.
- **Method/output:** event-flow mock/real RF readiness, provider outage, DB unavailable, 24h soak, recovery, duplicate retry, security port scan, iPhone usability, memory/WAL/disk/latency benchmarks, licensing inventory, SBOM, independent reviewer findings and corrective cycle.
- **Acceptance/tests:** AT-001..AT-027 as appropriate; failing/not-run clearly identified; exact-head review required after any corrective commit. **Effort:** 10–18d. **Risks:** all HIGH. **Excludes:** operator risk acceptance, live DB schema apply, unrestricted provider tests and production rollout.

### WP-012 — Operations, recovery and governed handover
- **Objective:** create durable runbooks, source status/alerts and backout procedures; prepare separate production authorization decision with no surprise mutations.
- **Repo:** Lakehouse `docs/runbooks/`, `docs/status.md`, `scripts/deploy-preflight.sh`, `scripts/backup-verify.sh`; my-pa existing backup runbooks authoritative and left unchanged unless independently authorized.
- **Inputs/deps:** WP-004 DB owner backup contract; WP-010 approved ingress; WP-011 independently reviewed test results; operator RPO/RTO, NAS image placement and retention decisions.
- **Method/output:** audit-ready manifest with images, SHAs, conf hashes, approved locations redacted, service identity, preflight/upgrade/rollback, DB recovery/restore-to-scratch, field failure handling, secret rotation owner, provider terms review and stale detection. If activation approval arrives later, stop for exact runtime target preflight and explicit activation authority.
- **Acceptance/tests:** AT-019,023,024,027; runbook tabletop+scratch restore & deployment rollback, no unverified PASS. **Effort:** 5–9d. **Risks:** RSK-007,008,010,011,013. **Excludes:** live recovery, production activation, destructive cleanup/purge, changes to my-pa production DB or credentials.

## 3. Resource/BOM and procurement gates
Existing WH65B/WS-2000 sensor installation and Synology DS923+ are reported as owned, not inspected; Nooelec receiver SKU 100700 candidate selected, purchase/delivery UNVERIFIED. Optional USB extension or 915-MHz antenna, or alternative Linux USB host, are contingent on WP-003 RF diagnosis; no speculative purchase. See [13 dependencies/BOM](13_DEPENDENCIES_AND_BOM.md).

## 4. Promotion and stop policy
- **Plan review pending.** No work package currently authorizes implementation; independent reviewer may request revisions.
- **Shared DB in my-pa**: only WP-004 separately authorized in its own repo can make migration code/role changes; that permission is distinct from applying to live DB. Migrations never run on production in this plan.
- **Hardware**: non-destructive host/USB inspection may need operator permission; no DSM configuration mutation or reboot assumed.
- **Production**: no deployment, public ingress, secrets, risk acceptance, cleanup or purge without exact target-specific operator approval.
- **PR**: planning PR may be opened against main, but merge remains operator-gated; review on exact head required; merge does not prove deployed hardware.
- **Discovered scope growth**: stop, record new risk/ADR/work item rather than silently implement.

## 5. Corrective implementation sequencing / effort sensitivity (CR-1)

The original 53–95d sum was mathematically correct but understated required design and testing. The table and individual WP estimates above now use an **independent sensitivity envelope of 73–132 experienced person-days**; this is a provisional engineering range, not observed throughput, staffing, quotation or calendar commitment. Includes expanded schema/role and payload lineage work, per-stream polling, crash-durable HMAC journal, inaccessible/historic sensor scenarios, accessible iPhone charts and negative cross-repo testing. Procurement/authorization waiting and >=24h RF soak add elapsed time outside active person-days. Hardware already delivered, admitted scratch DB and frozen contracts could reduce elapsed calendar/effort after actual evidence.

**Bounded dependencies:** WP-002 only converts accepted architectural decision/ADR after fresh external exact-head review; WP-003 real RF cannot start until hardware exists and bounded NAS approval; WP-004 any my-pa migration **code/isolated database** requires separate exact operator authorization in that repository. WP-005 synthetic domain/API may start only with accepted and independently reviewed schema contract; WP-006 depends on physical decoder proof, but its offline fixtures and protocol contracts can be tested without NAS only when independently authorized. WP-007 uses each provider stream's own cursor and operator-approved source enrollment; real provider calls are separately gated. WP-008 rain projections are on-read, so no unapproved unconditional aggregate table. WP-009 and WP-010 can test synthetic iPhone/security before any live ingress. WP-011 exact-head independently reviews implementation; WP-012 merely prepares recovery and never self-certifies an unexecuted restore.

**Correction ownership:** `LHW-RV-001` WP-003/006; `RV-002` WP-004/005/012; `RV-003` WP-004/005/007; `RV-004` WP-004/005/010; `RV-005` WP-004/005; `RV-006` WP-005/006/010/011; `RV-007` WP-005/008/009; `RV-008` WP-007; `RV-009` all WP effort assumptions; `RV-010` WP-009/010. Acceptance in [09 §7](09_VALIDATION_AND_ACCEPTANCE.md). No developer may expand scope or convert planning approval into live DB, receiver deployment or production authority.
