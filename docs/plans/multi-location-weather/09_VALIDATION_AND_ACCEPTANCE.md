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
| **AT-004** | RF secondary / WP-003 | WH32B/WH25-family capture identifies exact model and pressure availability **if present**; if absent, explicitly conclude pressure `UNAVAILABLE`; conditional WH65B pressure field only if verified. No invented 0 reading. |
| **AT-005** | RF recovery / WP-003, WP-006 | Permission, container restart, dongle unplug/replug and separately authorized NAS restart recover decoder; new RF ID requires explicit new device identity epoch; two simultaneous sensor types do not collide. |
| **AT-006** | parser contract / WP-005, WP-006 | Synthetic WH65B/WH32B JSON cases normalize metric code/unit precision/receive-time provenance exactly; malformed JSON, invalid CRC indicator, unexpected model or unknown field fail closed; zero and null distinct. |
| **AT-007** | relational domain / WP-004, WP-005 | 1 station with 2 physical devices and 1 location; 1 other location with provider; 2 competing sources for 1 location. FK/time/assignment and source-site identity enforced; no cross-source dedup. |
| **AT-008** | rain algorithm / WP-005, WP-006, WP-008 | Ordered sample, exact equal counter, first sample, negative reset, later rollover without verified modulus, implausible jump, midnight crossing, multi-day gap, station replacement and DST. Unknown increment becomes `NULL`+quality state; no negative/artificial rainfall. |
| **AT-009** | transport/DB retry / WP-005, WP-006 | At-least-once duplicate receiver ID with same hash yields same row counts; conflicting same ID/different hash rejected; write+ACK atomic; after receiver crash before ACK replay does not duplicate observations. |
| **AT-010** | security/quality / WP-005, WP-006 | Unknown RF sensor/site, packet-size overflow, invalid unit/value and clock >accepted drift quarantined; no auto-registration, no unreviewed raw neighbor RF persistence; spool saturation explicitly logs data-loss/gap risk. |
| **AT-011** | isolated migration / WP-004 | my-pa-owned Alembic revision upgrades empty->current, prior-head->new head in **disposable** database, schema objects correctly named/qualified, no new head fork; rollback has documented safe contract, and migration URL guard refuses unknown/production. |
| **AT-012** | database permissions / WP-004 | weather app can SELECT/INSERT weather permitted rows; cannot ALTER/CREATE/DROP/TRUNCATE/DELETE, read/write existing `knowledge`, `observability`, `sources` etc; receiver cannot directly connect to DB. No unexpected schema diff outside `weather`/approved grants. |
| **AT-013** | forecast/source corrections / WP-005, WP-007 | measured observations returned only on measured endpoints; provider corrected reading appends supersession; model issue/revision events preserved, stitched Best Match marked run-identity unknown; exact schema snapshot golden tests. |
| **AT-014** | time & units / WP-005, WP-008 | UTC event-time vs ingestion time, strict unit validation, site-local daily buckets across DST and leap days, wind direction circular mean, pressure basis preserved, source timezone/geometry never inferred from NAS/default env. |
| **AT-015** | shared DB integration / WP-004, WP-005 | fixed pool <=approved connection budget; concurrent batches, 30-day synthetic series, transaction timeout and LOCK contention injection do not exhaust my-pa connections or modify existing tables; benchmark plan recorded. |
| **AT-016** | provider fidelity / WP-007 | NWS user-agent/site attribution, station observations vs forecast grid classification, per-site time metadata and missing station values; Open-Meteo terms gate/attribution, quota and run-identity limitation; no real provider calls in routine CI. |
| **AT-017** | UI source semantics / WP-009 | every metric/forecast displays source class and timestamp, missing pressure unavailable, rainfall partial, modeled current separate, comparisons source-distinct and accessibility labels unambiguous on iPhone. |
| **AT-018** | provider outage / WP-007, WP-009 | NWS 304, 429+Retry-After, 503, timeout, 401, schema drift, bad JSON and recovery; last committed history untouched, watermarks do not skip, retries bounded and UI stale visible. |
| **AT-019** | backup/restore / WP-004, WP-012 | consistent full my-pa dump includes `weather`, fresh checksum/list and successful restore into **new scratch DB**, row counts/digests/source links match, existing my-pa records untouched. Test weather-only logical extraction as supplemental. |
| **AT-020** | mobile acceptance / WP-009, WP-010 | iPhone Safari over approved remote HTTPS on cellular, Home Screen launch, 320–430px widths, VoiceOver/source labels, landscape, offline cache age, no mixed content. Untested device = BLOCKED, not mocked PASS. |
| **AT-021** | multi-location selection / WP-005, WP-009 | 2+ synthetic site timezones + 2 providers at one site; location picker, up to 4-site comparison, source filters, readable unit-normalized aligned time axis; 404 for unauthorized/unknown sites. |
| **AT-022** | security / WP-010 | unauthorized WAN/tailnet peer blocked, ingress denies `/internal`, broker, metrics/admin and DB routes; secrets absent from git/logs; no public port forward; HTTPS and ACL smoke, source token replay rejected. |
| **AT-023** | operations/capacity / WP-008, WP-011, WP-012 | ingestion/forecast/poll resource use measured on NAS or representative host, bounds/alert thresholds and storage growth projections written; retention purge prohibited until operator decision; rollback exercised on scratch/approved pilot. |
| **AT-024** | governance/ADR / WP-001, WP-002, WP-012 | exact repo base+tree, accepted ADR-0001 preserved with explicit supersession before implementation, current my-pa controlling head refreshed, all plan IDs/index links valid; no implementation/deploy/merge portrayed as approved. |
| **AT-025** | robust protocol / WP-006, WP-007 | synthetic sensor packet repeated with identical JSON on two genuine receive IDs is retained as two events, plus tampered HMAC/nonce/bad version denied; provider API content-type/size limit enforced. |
| **AT-026** | API contracts / WP-005, WP-009 | `GET /api/v1` schema v1 stable, page/window upper bounds enforced, permission-filtered cursor, source/time/units present, error states 400/401/403/404/409/422/429/503, no modeled-as-measured cross-leak. |
| **AT-027** | operational telemetry / WP-006, WP-007, WP-011, WP-012 | container healthy but sensor silent reports receiver/process alive **and** source STALE separately; DB unavailable triggers readiness failure, poll lag metric, bounded logs without PII/credentials, alert recovers after commit. |

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
