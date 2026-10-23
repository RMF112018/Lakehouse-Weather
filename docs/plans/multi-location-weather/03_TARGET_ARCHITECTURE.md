# 03 — Target architecture, component boundaries, topology and contracts
**LHW-ML-20261023 | Checkpoint CP-4 | 2026-10-23 | PROPOSED — no implementation or production authority.**
Controlling decisions: [02](02_ARCHITECTURE_OPTIONS.md), [11](11_RISK_AND_DECISION_REGISTER.md); DB contract [04](04_POSTGRESQL_INTEGRATION.md); domain contract [05](05_WEATHER_DATA_MODEL.md). Exact Lakehouse repository base: `aea6bada042b34a8365c9e70e3a6a0f90304f3f0`.

## 1. Proposed component diagram
~~~text
 LOCAL WEATHER INSTALLATION             EXTERNAL LOCATIONS / SOURCES
 WH65B outside + WH32B optional         Configured location A/B/C ...
            | 915-MHz RF                         | secure outbound HTTPS
            v                                    v
 NOOELEC RTL2832U SDR <- USB -> NAS  [NWS station observations + grid forecasts]
            |                        [Open-Meteo models: conditional fallback]
            v                                    |
 +--------------------------+           +-------------------------+
 | receiver container       |           | weather-app container   |
 | rtl_433 pinned build     |  private  | adapter poll loop       |
 | versioned NDJSON parser  +---POST--->+ normalize/quality/queue |
 | bounded durable replay   | authenticated| DB bounded pool       |
 | spool / restart health   |           | versioned REST API      |
 | no PostgreSQL credentials|           | static iPhone PWA       |
 +--------------------------+           +-----+-------------------+
                                            |
                                 private Docker data-plane
                                            v
                                Existing MY-PA PostgreSQL cluster
                                same physical database / weather
                                restricted weather role, no SQL
                                access to other my-pa schemas
                                            ^
                                            |
                           HTTPS private browser ingress
                 iPhone Safari/PWA <-> Tailscale Serve/proxy
                            (proxy is private; no direct WAN)
~~~
This is a target, not evidence the NAS hosts any of these processes. Weather collector and web service MAY run on the same NAS but are deliberately isolated in separate containers: USB+decoder has no database authority; the weather-app does not receive USB access. Both use one repository; no independent event bus, background queue service, second relational database, search engine or cache. The receiver's bounded disk replay spool is a **transient at-least-once transport buffer**, not the authoritative weather store.

## 2. Responsibility assignment and justification
| Process/component | Specific responsibility | Authority boundary | Why necessary |
|---|---|---|---|
| `receiver` container | configure SDR, invoke pinned `rtl_433`, read JSON lines, wrap each accepted packet in an immutable receive envelope, bounded persist/replay/ack | USB passthrough; no DB key; outbound only to weather-app internal endpoint; no WAN | Hardware isolation and crash replay; only service that requires USB |
| `weather-app` container | validate and authenticate RF envelopes; normalize observations and forecasts; call approved provider APIs on a bounded schedule; transactional writes; query/API; static PWA | Separate weather-only DB role; restricted provider secrets; no USB; no generic my-pa API/session authority | One source-aware application for all locations and 1 canonical DB |
| Existing my-pa PostgreSQL | durable weather schema and shared physical backup, WAL and capacity | controlled DDL via my-pa Alembic and approved role provisioner only | Mandatory existing canonical DB |
| Verified Tailscale HTTPS ingress | authenticate private device/network peer and present weather app HTTPS | only UI and read-only `/api/v1` routes; internal ingest route denied | iPhone remote access; no router port forward |
| Optional Cloudflare | later optional separately authorized edge with application auth | not selected for MVP; must be separate from my-pa tunnel and secrets | Conditional, not required |
| Operator CLI | register/edit location and source assignments, rotate credentials through approved secret mechanism, run probes | no public HTTP write API, no direct database DDL | Small admin surface; testable and auditable |

**Proposed application stack:** Python 3.12+ (select exact supported image digest during WP-002) + FastAPI/Pydantic/SQLAlchemy/psycopg + one Uvicorn worker; sync SQL transactions inside explicitly bounded task executor; app startup creates exactly one provider polling task (fixed single replica). Use Python standard async/time primitives for scheduling initially; no APScheduler/Celery/Redis. Frontend: **React + TypeScript + Vite static PWA**, bundled into the app's static assets, no separate frontend container and no server-side rendering. Reasoning: component-driven responsive charts with small build/runtime footprint and familiar test tooling. Add only one chart library after a small proof of historical time-series correctness; inspect licenses. These are implementation selections **proposed**, subject to architecture/plan review, not installed packages.

## 3. Routing and boundaries
Proposed internal networks: `weather-ingest` (receiver --> weather-app internal POST only), `weather-data` (weather-app --> already authorized my-pa PostgreSQL host/internal bridge), `weather-edge` (private proxy --> weather-app API/static; outbound provider HTTPS separately allowed). Do not attach receiver to DB network. If existing my-pa Postgres is on separate bridge, do **not** assume container DNS name; require a reviewed network attachment or restricted service endpoint and verify it does not inadvertently expose existing my-pa. Weather-app binds container only, not NAS public interfaces. LAN/WAN `0.0.0.0:port` publishing forbidden until explicitly security-reviewed; private proxy is the only network-visible endpoint. No direct UI calls to `api.weather.gov`, Open-Meteo, or PostgreSQL; backend owns provider credentials, caching and rate limits.

**Auth:** operator-controlled tailnet identity + private ingress access checks for MVP. Network identity is not a general-purpose user principal; if a broader network or public origin is ever admitted, add application-session authentication and CSRF/authorization review before it is opened. `/internal/rf-events` requires HMAC or equivalent strong token bound to receiver with constant-time verifier, timestamp/nonce and replay dedup; endpoint blocked at proxy, denied by browser and not reverse-proxied at public ingress. HTTPS on loopback/private ingress; assess encryption for cross-host data plane if required. Read API response uses private-cache headers where precise data included; service worker does not persist secrets.

## 4. Named interfaces (proposed version `v1`)
**Receiver --> app:** internal `POST /internal/rf-events`, JSON object, at-least-once, `event_id` sender UUID with stable replay identity. Maximum envelope 32 KiB (proposed, test against real decoder payloads), batch <=100 envelopes and 512 KiB total (proposed), bounded request timeout 5s; 200/201 acknowledged only **after DB commit**, 409 if reused `event_id` has a conflicting content digest, 400 malformed, 401/403 unauthorized, 422 unexpected sensor schema, 429 backpressure, 503 DB outage. Quarantine unknown RF source and emit sanitized diagnostic; do not dynamically register an unknown station. Persist source/device context on receiving side when registered. Include `schema_version`, `event_id`, `receiver_boot_id`, `receive_utc`, `decoder_name`, `decoder_git_sha`, `decoder_model`, `rf_sensor_id`, `payload`, `sha256`. Monotonic event sequence within boot recommended; clocks across restarts explicitly reconciled.

**Provider adapter --> app:** `fetch(context, cursor, limit)` returns `ProviderResult` with `source_ref`, `provider_site_ref`, fetched/issue/valid times, source kind, raw response digest, rate-limit hints and normalized *candidate* values. No provider is trusted to update DB directly. Source registration whitelist and license/attribution registry block unadmitted providers. Provider polls scheduled from `poll_state` with backoff and 304/ETag handling; network clients limited to fixed known hosts and TLS certificate verification; timeout 10s, bounded response bytes. Never include API tokens in logs or test fixtures.

**Persistence:** `insert_raw_event_and_metrics(...)` one atomic transaction; conflict on duplicate version does not advance watermark; correction is appended revision with supersession. Separate `insert_model_run_and_values(...)`. Metrics include `source_assignment_id`, `device_id`, `observed_at_basis` and UTC `ingested_at`. All writes require my-pa-approved `weather_app` role; row-level schema grants and explicit `weather` schema qualification. No my-pa ORM migration ownership transfer.

## 5. Read-only public-facing API contract (illustrative v1)
All resources require private authorized session/transport and are returned with bounded pagination/intervals. API errors are machine-readable `{code,message,request_id}`, avoid locations/credentials in diagnostic messages.
| Path | Query / limits | Essential fields and invariant |
|---|---|---|
| `GET /api/v1/locations` | active-only default, page<=50 | `location_id,name,timezone,available_source_kinds,default`; coordinates omitted from list unless explicit permission |
| `GET /api/v1/locations/{location_id}/current` | selected metrics; max 50 | per-metric `value,unit,source_id,device_id?,observation_type,observed_at,ingested_at,quality,freshness,provider_site_ref`; missing metric `null` with reason |
| `GET /api/v1/locations/{location_id}/observations` | `metric,start,end,source_id?,page_token?`; window<=31d, page<=1000 | array of source-distinct **measured** observations only; no modeled values |
| `GET /api/v1/locations/{location_id}/forecasts` | `metric?,start,end,provider?` | `run_id,issued_at,valid_from,valid_to,provider,model,forecast_value`; distinguish model-analysis/current output |
| `GET /api/v1/locations/{location_id}/comparison` | up to 4 source IDs or up to 4 locations, matching metric/time | chronological per-source series, units aligned; never auto-average conflicting sources |
| `GET /api/v1/locations/{location_id}/summary` | local date / time zone, <=366 days range | high/low, rainfall total and `completeness`, source provenance, algorithm version |
| `GET /api/v1/health/sources` | private admin session only | last good sample, last poll, decoder state, stale reason, weather-app status |
| `GET /health/live`, `GET /health/ready` | network-restricted | readiness requires DB permission and migration compatibility; no private object metadata returned |
| `GET /api/v1/sources` | internal/private only | source ID/type, provider attribution, station metadata, status; no secret refs |

**Error contracts:** 400 invalid metric/time/range, 401/403 no authority, 404 unknown or invisible location (same shape), 409 stale cursor/conflict, 422 invalid time-zone/parameter, 429 rate limited, 503 DB/provenance unavailable; never substitute modeled values for missing observation endpoint. Cursor must encode stable `(observed_at,observation_id)` and role/scope binding; no offset-only unbounded scans.

### Example semantic response (SYNTHETIC ONLY)
~~~json
{
  "location_id": "loc_test_1",
  "observation_type": "MEASURED",
  "metrics": [{
    "metric": "air_temperature",
    "value": 24.8,
    "unit": "degC",
    "source_id": "src_test_wh65b",
    "device_id": "dev_test_epoch1",
    "observed_at": "2026-10-23T12:00:00Z",
    "ingested_at": "2026-10-23T12:00:01Z",
    "quality": "ACCEPTED",
    "freshness": "FRESH"
  }, {
    "metric": "barometric_pressure",
    "value": null,
    "unit": "hPa",
    "source_id": null,
    "quality": "UNAVAILABLE",
    "reason": "SENSOR_NOT_OBSERVED"
  }]
}
~~~

## 6. Data flow and failure containment
1. Receiver starts by verifying accessible SDR only; `rtl_433` emits decoded packets for local installation; receiver timestamps, wraps and durably stages each before request. Unknown IDs still tracked as a count with redacted metadata, not adopted as official site.
2. App authenticates envelope, enforces model/id registration and schema version, determines time-bounded assignment, checks units/ranges, writes raw+metric rows transactionally, acknowledges committed IDs. Source windows update when committed, not after network acceptance.
3. External polling task obtains admitted source configuration, respects update cadences and provider limits, writes measured NWS site observations or separately typed model runs. 429/503 -> exponential backoff bounded, no optimistic watermark.
4. Read queries choose preferred qualified measurement per metric, return explicit source site/time, and label model forecast separately; UI detects stale values using source-specific expected interval.
5. DB unreachable -> app readiness fails, receiver replays bounded spool; provider task halts advances; API shows last previously cached data as cached/stale if cache exists, never fictitious live.
6. Persistent spool full -> stop/limit capture or rotate under **explicit data-loss alert**, with dropped-count and oldest/latest timestamps; no silent drop. Do not claim gapless ingestion if SDR itself was offline.
7. Restart/USB reconnection -> stable receiver boot identity, decoder process supervised, retry with backoff, replay; container/network failure injection and no duplicates verified.

## 7. Throughput, HA and maintenance constraints
- Initially **exactly one** receiver and **exactly one** weather-app task owner/ASGI worker. No multiworker Uvicorn startup; duplicate poll loops are unacceptable without a DB lease. If high availability later desired, require explicit leadership and failover design.
- Initial proposed DB cap: pool <=2, overflow=0, batch <=100 events/500 metrics, transaction bounded, appropriate indexes and expected packet volume benchmark. These are default test targets, not confirmed safe production limits.
- Provider refresh cadence: NWS dictated by cache headers/observed station update; Open-Meteo based on published model update, not arbitrary minute polling; enforce calls/day and budget. Force refresh cannot circumvent rate limit.
- Version and pin base images by immutable digest plus recorded upstream SHA; record decoder `rtl_433 -V`/build fingerprint alongside sample.
- CI validates parser fixtures, schema mismatch rejection, API snapshots, UI tests and Compose static config; specialized USB/NAS/real-provider tests run in separately approved runtime proof gates, never in ordinary public CI.
- Recovery RPO/RTO is an operator input; not an invented promise. Shared DB restores owned by my-pa operator and must include `weather` schema.

## 8. Unapproved future capabilities
Multi-user geolocation, commercial/public API, paid provider integrations, long-term raw IQ recording, autonomous station selection, new field sensors, MQTT, generalized event queues, second DB, weather alert rules, remote sensor RF reception, public weather profile pages, iOS push and home automation are deferred. See [07 Dashboard](07_DASHBOARD_AND_REMOTE_ACCESS.md) and [12 Operations](12_OPERATIONS_AND_LIFECYCLE.md). Every new process/port, broad external exposure or data retention is a separate architecture/safety review.
