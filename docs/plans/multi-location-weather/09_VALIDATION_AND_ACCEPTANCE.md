# 09 — Verification gates, executable acceptance cases and negative tests
**LHW-ML-20261023 | Checkpoint CP-5 | PROPOSED.** These are future **acceptance criteria**, not passing test results. No SDR, NAS, iPhone or production PostgreSQL canary was executed during planning. Current GitHub validation is only source-file readback and static plan consistency. The accepted thresholds must be frozen before implementation testing and may be changed only by an operator-reviewed decision.

## 1. Gate sequence and test environment
| Gate | Prerequisites / environment | Required evidence | Blocking conditions |
|---|---|---|---|
| GATE-PLAN | Current main identity + plan docs + independent plan reviewer | reviewed exact plan commit, all material findings resolved or held, proposed ADR supersession accepted for implementation scope | no self-approved plan; unresolved architecture or DB cross-repo ownership |
| GATE-RF | actual receiver and Synology DSM, approved non-mutating hardware access | host/device inventory, 5min baseline + 24h soak packets, USB permissions, redacted decoder logs, restart observations | no stable RTL-SDR/WH65B packets, nonexistent device, insecure container privilege |
| GATE-DB | distinct **disposable PG target**, current approved my-pa revision/roles/backup policy, cross-repo authorization | migration isolated roundtrip from empty and preceding head, role denial, DB diff, performance/restore plan | unknown runtime alias/permissions, failed migration or unapproved live access |
| GATE-PROVIDER | approved provider+location registration and recorded terms | synthetic APIs 2xx/304/401/429/5xx tests, live canary only if authorized, NWS site identity | missing license/attribution, unreliable run/source identity, fabricated coordinates |
| GATE-DATA | synthetic RF/provider inputs, isolated PG | successful transaction, idempotence, model/source/device lineage, rain quality/DST test suite | leak of unregistered source, overwrite/cross-location errors |
| GATE-UI | self-contained synthetic backend, mobile Safari/Playwright | correct sources/types, missing/stale states, local day history and comparisons, accessible touch UI | modeled value displayed as measured, privacy leak, chart false data |
| GATE-SECURITY | approved tailnet/proxy and app roles | route/ACL/port scans, secret scans, auth denial, TLS/iPhone on cellular | unauthorized public exposure, unprotected RF ingress or DB privileges |
| GATE-OPS | approved NAS host, backup/restore, runtime rollback | 24h operations under load, bounded restarts, backup and scratch restore, resource quotas, operator runbooks | unknown RPO/RTO, unreliable restart, destructive rollback or no validated restore |
| GATE-REVIEW | exact implementation branch/HEAD/PR and CI | fresh **independent** reviewer who did not author implementation, exact-head tests + PR decision | newer code invalidates reviewed head; reviewer rejection |
| GATE-PRODUCTION | explicit operator authorization *after* all above | separately approved activation/run-time identity and rollback | any unapproved deployment, credential, role, migration or policy mutation |
A test that could not run due to missing hardware/permission/credentials is **NOT_RUN/BLOCKED**, never PASS. Operator may commission only after resolving no-go gates.

## 2. Atomic acceptance test register
**Classification:** Tests marked synthetic run without physical RF or private data; hardware/provider tests need operator-managed target. Each AT maps to one or more WPs; exact test filenames are proposed, not existing implementations.

| ID | Test type / WP | Pass assertion and failure coverage |
|---|---|---|
| **AT-001** | real hardware / WP-003 | DS923+ enumerates actual Nooelec VID/PID/serial, `rtl_test` claims dongle from restricted container with approved device mapping and releases device; capture exact DSM, driver/image digest. No privilege = FAIL, missing device = BLOCKED. |
| **AT-002** | RF capture / WP-003 | Pinned rtl_433 produces >=3 valid `Fineoffset-WH65B` events across >=5min at observed station ID; real source-to-model mapping and plausible environmental measurements; save private raw evidence and publish only synthetic/redacted fixtures. |
| **AT-003** | RF soak / WP-003, WP-006 | >=24h isolated capture with observed median sensor cadence, valid CRC/MIC rate, count and longest gap reported; **proposed** steady-state threshold >=95% expected decodes based on actual established cadence and no unexplained gaps >5min, subject to gate review; do not assume exactly 16s hardware. |
| **AT-004** | RF secondary / WP-003 | Decoder pin and actual packet model separated: `MODEL_WH65/Fineoffset-WH65B` has **no pressure output** in both inspected SHAs; `MODEL_WS69` optional pressure is different model; pressure may come only from truly observed/qualified `Fineoffset-WH32B` or other device. Missing sensor -> explicit null/unavailable. |
| **AT-005** | RF recovery / WP-003, WP-006 | Permission, container restart, dongle unplug/replug and separately authorized NAS restart recover decoder; new RF ID requires explicit new device identity epoch; two simultaneous sensor types do not collide. |
| **AT-006** | parser contract / WP-005, WP-006 | Synthetic RF parser normalizes true WH65B/WH32B model and units, distinct receiver-clock basis; reject invented WH65B pressure, invalid `mic`, unknown fields, wrong model; retain zero vs absent and exact decoder SHA. |
| **AT-007** | relational domain / WP-004, WP-005 | In disposable PG, SC-01..SC-04 insert lawful station+2 devices, two locations, two sources and shared NWS site stream; deny source/event/assignment/device cross-links, overlapping local assignments/epochs, invalid half-open event-time assignment, mismatched stream; concurrent conflicting metadata attempts serialize. |
| **AT-008** | rain algorithm / WP-005, WP-006, WP-008 | `rain_counter` only MEASURED; on-read DERIVED increments/rates reference **two** effective accepted counter UUIDs, source/device and `as_of_ingested_at`/algorithm version; reset, unknown rollover, out-of-order correction, first sample, gaps, cross-midnight and DST produce exact partial/NULL or zero as justified, never fabricated total or stored measured derivative. |
| **AT-009** | transport/DB retry / WP-005, WP-006 | Mixed <=100 event batch has one valid digest-bound outcome per item (`COMMITTED`/`DUPLICATE_COMMITTED`/`REJECTED_TERMINAL`/`CONFLICT_QUARANTINED`/`RETRYABLE`); 200 all committed/duplicate, 207 mixed, no false success. Event+metrics atomic per item, crash after commit/before response replay stays row-count invariant. |
| **AT-010** | security/quality / WP-005, WP-006 | Receiver filesystem journal fsync file+rename+directory before send; corrupt/torn/partial record, restart, permissions, disk full/80% warning and invalid sensor produce quarantine or gap alert without false ACK; auth failure halts, transient stays staged, terminal stops retry; neighboring RF not retained. |
| **AT-011** | isolated migration / WP-004 | my-pa-owned Alembic current single-head additive upgrade empty/prior-head on disposable PG; verify all selected composite FK/UNIQUE, lock/range/epoch/append-only/correction guards, nonce/poll/metadata audit objects, safe role ownership/search_path and no unapproved my-pa schema diff; failed migration URL refuses. |
| **AT-012** | database permissions / WP-004 | Scratch role matrix: `weather_app` inserts only accepted raw/observed/model rows, updates scoped stream state; `weather_admin_cli` authenticated NOINHERIT/SET ROLE can register/retire approved metadata **with same-transaction audit**, but cannot DDL or alter historical event/observation or other schemas; wrong-role/admin/retention DELETE denied; receiver has no DB route. |
| **AT-013** | forecast/source corrections / WP-005, WP-007 | Model forecast and measured endpoints never mix; model value must match source, provider stream and assignment. Open-Meteo Best Match run identity UNKNOWN; repeated 304/identical digest 200 heartbeat does not create new model run; changed digest creates new linked snapshot revision; provider corrections append immutable supersession. |
| **AT-014** | time & units / WP-005, WP-008 | UTC event vs ingest and site-local IANA day including DST/leap; wind circular mean, pressure basis and remote station geometry; on-read rain DERIVED identity/interval/cutoff and reproducible corrected ordering, never measured. |
| **AT-015** | shared DB integration / WP-004, WP-005 | fixed pool <=approved connection budget; concurrent batches, 30-day synthetic series, transaction timeout and LOCK contention injection do not exhaust my-pa connections or modify existing tables; benchmark plan recorded. |
| **AT-016** | provider fidelity / WP-007 | NWS qualified station/site attribution and distinct forecast grid; Open-Meteo conditional terms/admission/attribution, **effective weighted quota units** per provider entitlement across independent coordinate streams and retries, unknown weight fails closed; no real provider calls in ordinary CI. |
| **AT-017** | UI source semantics / WP-009 | UI visible `MEASURED_LOCAL` vs `MEASURED_REMOTE` vs `MODEL_*` vs `DERIVED`, source/time/site and null WH65B pressure, partial rain lineage/quality, stale/private responses no stored PWA API; accessibility labels include class and actual age. |
| **AT-018** | provider outage / WP-007, WP-009 | At least two destination-specific provider streams sharing one logical source: A 200 commits and watermark moves; B 429/503 fails and watermark does not move; B recovery replays safely. Exercise 304, schema drift, 401, Retry-After and per-stream freshness/alerts with unchanged history. |
| **AT-019** | backup/restore / WP-004, WP-012 | Full my-pa and weather-only **scratch restore** after simulated **separately authorized TEST-ONLY** 90-day payload expiry with 24-month observations: immutable event/digest/source FK remains, no cascade, absent payload explicitly flagged, original my-pa rows untouched; owner/role provisioning recovery separately proved. |
| **AT-020** | mobile acceptance / WP-009, WP-010 | Real iPhone Safari/cellular private HTTPS, Home Screen, small widths and VoiceOver; static-only service-worker precache, stale/offline timestamp. Revoke tailnet/ACL and verify new API requests denied while not claiming remote erasure of any previously cached private data; device evidence required. |
| **AT-021** | multi-location selection / WP-005, WP-009 | Two+ synthetic locations/providers, valid station source shared across assignments, model stream per coordinate and correct role-gated operator source/device retirement with transition audit; unauthorized/unknown location returns privacy-preserving 404. |
| **AT-022** | security / WP-010 | Unauthenticated WAN/tailnet peer blocked, `/internal` and DB never proxied; HMAC constant-time validation, duplicate/stale nonce rejection and valid fresh-signature same-event retry across restart; no secrets or responsive private API cache leaks; normal app cannot SET ROLE admin. |
| **AT-023** | operations/capacity / WP-008, WP-011, WP-012 | Synthetic scale includes 1/30/365d RF and provider stream rows, 90d optional payload vs 24mo metadata/observation, derived rain query cost, WAL/backup/read latency and storage. No deletion, prod performance claim or retention authorization absent operator gate; revised 73–132 person-day sensitivity is not benchmark. |
| **AT-024** | governance/ADR / WP-001, WP-002, WP-012 | exact repo base+tree, accepted ADR-0001 preserved with explicit supersession before implementation, current my-pa controlling head refreshed, all plan IDs/index links valid; no implementation/deploy/merge portrayed as approved. |
| **AT-025** | robust protocol / WP-006, WP-007 | Identical physical payload with distinct first-seen receiver event IDs is retained twice; same ID/digest duplicate is idempotent; changed digest isolated; mixed 207, 401/403/429/503/413, forged/expired signed request, fresh nonce retry, content type/size, post-commit lost response tested. |
| **AT-026** | API contracts / WP-005, WP-009 | `GET /api/v1` measured endpoints only physically observed rows; `/derived` returns separately typed computed rain and two source UUIDs, as-of and quality; bounded pagination/permissions/errors and private `Cache-Control: no-store` on geolocation/weather API. |
| **AT-027** | operational telemetry / WP-006, WP-007, WP-011, WP-012 | Healthy container but silent source or one failed provider stream exposes distinct receiver/stream stale statuses; spool backlog/corrupt journal and DB readiness visible, per-stream cursor never silently advances, logs/alerts redacted and recover after commit. |

## 3. Synthetic fixture test vectors (non-identifying)
| Fixture | Scenario / detailed expected result |
|---|---|
| `rf/wh65b_normal.jsonl` | 3 fake messages with stable RF id and distinct capture UUIDs, source/test site; fields differ as measured |
| `rf/wh32b_present_and_absent.jsonl` | indoor humidity/temp, conditional valid pressure, plus missing-pressure fallback |
| `rf/replay_same_payload_different_event.jsonl` | identical weather values at different reception events **both retained** |
| `rf/replay_same_id_conflicting_digest.jsonl` | 409 and no source-data mutation |
| `rf/rain_reset_rollover_gap.jsonl` | counter 10.0 -> 10.2 -> 0.1 -> 0.2, with correct unknown at reset |
| `rf/rain_midnight_dst.jsonl` | zone-local day split across fall-back and spring-forward |
| `nws/observation_quantity_si.json` | actual station ID and GeoJSON coordinate **synthetic**, quality control and proper unit; not display location |
| `nws/rate_limit_retry_after.json` | HTTP 429, Retry-After, same cursor on retry |
| `nws/forecast_grid_issue.json` | issued+valid intervals, no measured observation |
| `open_meteo/model_best_match.json` | modeled current & forecast, run identity UNKNOWN if absent, correct attribution |
| `database/permissions.sql` | restricted role denied DDL/TRUNCATE/cross-schema reads |
| `golden/locations_three_sources.json` | two sites, two sources on same site, physical replacement epoch |
| `web/offline_source_stale.json` | cached as-of displayed, no live badge |
Exact fixture bytes and test implementations are future WP outputs; none of these fixtures presently exists.

## 4. Full negative and failure-injection campaign
- **RF:** receiver no device, device busy, wrong tuner gain/frequency, unexpected model, low battery, RF ID collision, unsigned packet, corrupted JSON, decoder exit, device disconnect, clock jump, spool permission denied/disk full.
- **DB:** cannot authenticate with weather role, schema absent/head mismatch, DB connection refused after event staging, unexpected transaction serialization failure, schema-level privilege drift, duplicate concurrent replay, DB pool saturation, migration fork, unauthorized direct schema creation.
- **Provider:** 429/Retry-After and 503, error HTML instead of JSON, provider schema/key change, malformed unit string, invalid coordinates, out-of-order corrections, expired forecast, conflicting station measurements, unknown model-run identity, rate quota exceeded.
- **UI:** API offline, offline PWA cache older than TTL, stale measured data, unavailable pressure, reset daily rain, daylight saving repeated hour, unregistered location, unauthorized comparison ID, 2 sources conflicting, forecast as different measurement type, iPhone VoiceOver and 320px layout.
- **Ops:** partial backup, checksum mismatch, preflight missing secrets, wrong target migration URL, failed image upgrade, unauthorized profile activation, database slow query/WAL high, provider secrets in log, unapproved public ingress.

## 5. Reproducibility and proof artifacts
Every test run records repository/branch exact commit+tree, dependency/image digests, test variant, synthetic fixture version, PostgreSQL schema revision (isolated DB only), runner OS, actual command, exit status, assertion totals, errors, runtime and evidence path. Publish only aggregate identifiers/redacted evidence to public GitHub. Manual hardware verification includes DSM version, VID/PID, receiver build, frequencies/gain, capture duration, packet counts and redacted event digests. A reviewer must **read artifacts and inspect source**, not accept a self-reported PASS. Corrections that change head require re-validation and independent review of exact new head. Production acceptance is a distinct operator decision after all gates.

## 6. Traceability checks
All material D-001..D-012 in [11 risk/decision register](11_RISK_AND_DECISION_REGISTER.md) map to at least one WP and AT. All WPs in [10](10_IMPLEMENTATION_WORK_PACKAGES.md) have a measurable acceptance set above. Open unknowns U-001..U-010 are explicit blockers or conditioned gates, not invented evidence. Retention, QoS/freshness and NAS performance thresholds are design proposals until accepted; never silently promote to verified.

## 7. Corrective evidence, invariants and scenario crosswalk (CR-1; tests NOT_RUN)

All tests remain future gates. The plan-level assertion is the **test design**, not a passing result. `LHW-RV-001..007` require the following explicit negative coverage before a new plan reviewer may approve implementation-readiness:

| Invariant | Enforcement owner/operation | Decisive AT |
|---|---|---|
| I-01 source/event/assignment/time/canonical value | DB composite FKs, source-row locking guard, normalization | AT-007, AT-011, AT-014 |
| I-02 physical sensor device and raw lineage | event metadata FK, device/source station epoch guard, no cascading delete | AT-006, AT-007, AT-019 |
| I-03 measured/model/derived class separation | closed database types, read-only API/derived endpoint, UI source labels | AT-008, AT-013, AT-017, AT-026 |
| I-04 stable duplicate identity | unique first-seen UUID/digest, provider event+revision, per-event commit/ACK | AT-009, AT-025 |
| I-05 corrections append only | predecessor unique+source/metric guard, role UPDATE/DELETE refusal | AT-011, AT-013 |
| I-06 no historical reassignment | half-open immutable assignment and source station metadata epochs | AT-007, AT-012, AT-021 |
| I-07 missing is null, never fabricated zero | field mapping and typed API null reason; missing pressure null | AT-004, AT-006, AT-017 |
| I-08 no uncommitted watermark | provider `poll_state(stream_id)` same transaction as persisted product; spool exact ACK | AT-009, AT-018, AT-027 |
| I-09 rain reset/gap quality | on-read derived counter pair, null reason, DST/local-midnight completeness | AT-008, AT-014, AT-017 |
| I-10 DB DDL/runtime/admin isolation | weather_app vs CLI NOINHERIT/SET ROLE grant matrix and trigger transition audit | AT-011, AT-012, AT-022 |
| I-11 modeled never appears measured | qualified model stream/run/value constraints and API separation | AT-013, AT-017, AT-026 |
| I-12 append-only reconstructible selection | retained event digest, supersession, selection policy/as-of and algorithm version | AT-007, AT-013, AT-019, AT-026 |

**Synthetic scenarios:** SC-01 includes local WH65B + optional WH32B and rejects fabricated WH65B pressure; SC-02 two timezones and **two assignment-specific model streams** with independent state; SC-03 identical NWS measured-station stream legitimately provides separate observations to two assignments and conflicts with local source without dedup; SC-04 authorized old device epoch retirement/new device ID with historic FK and audit, denied wrong-role write; SC-05 A successful 200 while B gets 429/503 and later replays without cursor or quota corruption. Input aliases must map to synthetic UUID-form keys consistent with [04 §7](04_POSTGRESQL_INTEGRATION.md).

**RF outcome coverage:** AT-009/010/025 individually test (1) commit, (2) already committed duplicate, (3) terminal invalid, (4) conflicting identity/digest, (5) auth failure, (6) DB outage, (7) rate limiting, (8) crash/restart/torn spool, (9) spool full. A 207 response must identify every admitted member; incomplete response never authorizes deletion from the receiver journal. Test fresh signed nonce on legitimate event replay and reject reuse of old nonce across application restart.

**Retained unknowns:** real NAS USB, physical decoder pressure, live my-pa DB identity/applied head, provider terms and rate entitlement, actual iPhone/Tailscale ACL and RPO/RTO remain `UNRESOLVED` future gates—not fabricated failing tests. No migration or data deletion occurs as part of correction.
