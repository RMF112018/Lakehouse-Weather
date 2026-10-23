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
| Operator-only CLI | register sources/locations/stations/devices/assignments/streams and close epochs via separately authorized `weather_admin_cli` → `SET ROLE weather_admin` transition | no public HTTP write API, normal `weather_app` cannot configure sources, no DDL/live role authority | auditable weather-only metadata registration |

**Proposed application stack:** Python 3.12+ (select exact supported image digest during WP-002) + FastAPI/Pydantic/SQLAlchemy/psycopg + one Uvicorn worker; sync SQL transactions inside explicitly bounded task executor; app startup creates exactly one provider polling task (fixed single replica). Use Python standard async/time primitives for scheduling initially; no APScheduler/Celery/Redis. Frontend: **React + TypeScript + Vite static PWA**, bundled into the app's static assets, no separate frontend container and no server-side rendering. Reasoning: component-driven responsive charts with small build/runtime footprint and familiar test tooling. Add only one chart library after a small proof of historical time-series correctness; inspect licenses. These are implementation selections **proposed**, subject to architecture/plan review, not installed packages.

## 3. Routing and boundaries
Proposed internal networks: `weather-ingest` (receiver --> weather-app internal POST only), `weather-data` (weather-app --> already authorized my-pa PostgreSQL host/internal bridge), `weather-edge` (private proxy --> weather-app API/static; outbound provider HTTPS separately allowed). Do not attach receiver to DB network. If existing my-pa Postgres is on separate bridge, do **not** assume container DNS name; require a reviewed network attachment or restricted service endpoint and verify it does not inadvertently expose existing my-pa. Weather-app binds container only, not NAS public interfaces. LAN/WAN `0.0.0.0:port` publishing forbidden until explicitly security-reviewed; private proxy is the only network-visible endpoint. No direct UI calls to `api.weather.gov`, Open-Meteo, or PostgreSQL; backend owns provider credentials, caching and rate limits.

**Auth:** operator-controlled tailnet identity + private ingress access checks for MVP. Network identity is not a general-purpose user principal; if a broader network or public origin is ever admitted, add application-session authentication and CSRF/authorization review before it is opened. `/internal/rf-events` requires HMAC or equivalent strong token bound to receiver with constant-time verifier, timestamp/nonce and replay dedup; endpoint blocked at proxy, denied by browser and not reverse-proxied at public ingress. HTTPS on loopback/private ingress; assess encryption for cross-host data plane if required. Read API response uses private-cache headers where precise data included; service worker does not persist secrets.

## 4. Named interfaces (proposed version `v1`)
**Receiver --> app:** internal `POST /internal/rf-events`, signed `rf-batch.v1` JSON with immutable first-seen `event_id`/payload digest, durably staged before send. Max 32 KiB/item, <=100 items/512 KiB batch, 5s timeout (proposed). One committed-or-rolled-back DB transaction per member; a complete digest-bound `rf-batch-result.v1` uses HTTP **200 only for all COMMITTED/DUPLICATE_COMMITTED**, or **207 for any terminal, conflict or retryable member**, including homogeneous all-negative outcomes. Whole-batch 400/413/401/403/429/503 are permitted only before any member is processed; no blanket 409/422 for event-level errors. See §10. Unknown RF sources are quarantined with redacted diagnostic, never automatically enrolled. Members carry `schema_version,event_id,receiver_boot_id,receive_utc,decoder_name,decoder_git_sha,decoder_model,rf_sensor_id,payload,sha256`; original ID/digest are retained on retry.

**Provider adapter --> app:** `fetch(provider_stream_context, stream_cursor, limit)` returns `ProviderResult` with immutable `stream_id`, `source_ref`, optional assignment, provider site, fetched/issue/valid times, source kind, canonical digest, charged effective quota units and normalized *candidate* values. No provider is trusted to update DB directly. Source registration whitelist and license/attribution registry block unadmitted providers. Provider polls scheduled from `poll_state(stream_id)` with independent per-stream backoff/304/ETag and provider-wide weighted quota; network clients limited to fixed known hosts and TLS certificate verification; timeout 10s, bounded response bytes. Never include API tokens in logs or test fixtures.

**Persistence:** `insert_raw_event_metadata_payload_and_metrics(...)` uses one atomic transaction **per member**; only committed/duplicate members receive success ACK. Separate `insert_model_snapshot_and_values(...)` writes per immutable provider **stream** and advances that stream's cursor only in the same successful transaction. Metrics include `source_assignment_id`, `device_id`, `observed_at_basis` and UTC `ingested_at`. All writes require my-pa-approved `weather_app` role; row-level schema grants and explicit `weather` schema qualification. No my-pa ORM migration ownership transfer.

## 5. Read-only public-facing API contract (illustrative v1)
All resources require private authorized session/transport and are returned with bounded pagination/intervals. API errors are machine-readable `{code,message,request_id}`, avoid locations/credentials in diagnostic messages.
| Path | Query / limits | Essential fields and invariant |
|---|---|---|
| `GET /api/v1/locations` | active-only default, page<=50 | `location_id,name,timezone,available_source_kinds,default`; coordinates omitted from list unless explicit permission |
| `GET /api/v1/locations/{location_id}/current` | selected metrics; max 50 | per-metric `value,unit,source_id,device_id?,observation_type,observed_at,ingested_at,quality,freshness,provider_site_ref`; missing metric `null` with reason |
| `GET /api/v1/locations/{location_id}/observations` | `metric,start,end,source_id?,page_token?`; window<=31d, page<=1000 | array of source-distinct **measured** observations only; no modeled values |
| `GET /api/v1/locations/{location_id}/forecasts` | `metric?,start,end,provider?` | `run_id,run_identity_status,issued_at? (nullable when true issuance unknown),fetched_at,valid_from,valid_to,provider,model,forecast_value`; distinguish model-analysis/current output |
| `GET /api/v1/locations/{location_id}/comparison` | up to 4 source IDs or up to 4 locations, matching metric/time | chronological per-source series, units aligned; never auto-average conflicting sources |
| `GET /api/v1/locations/{location_id}/summary` | local date / time zone, <=366 days range | high/low, **DERIVED-on-read** rainfall total and completeness, supporting measured counter IDs, cutoff, algorithm version |
| `GET /api/v1/locations/{location_id}/derived` | metric/time window and `as_of_ingested_at`, bounded | `kind: DERIVED`, predecessor/current counter IDs, source/device, interval, nullable rate/increment, reset/gap/DST quality, algorithm version; **not measured observations** |
| `GET /api/v1/health/sources` | private authorized read-only surface only | accepted sample freshness, **per-stream** last poll/backoff/cursor, decoder and spool status, stale reason; no CLI/admin mutation |
| `GET /health/live`, `GET /health/ready` | network-restricted | readiness requires DB permission and migration compatibility; no private object metadata returned |
| `GET /api/v1/sources` | internal/private only | source ID/type, provider attribution, station metadata, status; no secret refs |

**Error contracts:** 400 invalid metric/time/range, 401/403 no authority, 404 unknown or invisible location (same shape), 409 stale cursor/conflict, 422 invalid time-zone/parameter, 429 rate limited, 503 DB/provenance unavailable; never substitute modeled values for missing observation endpoint. Cursor must encode stable `(observed_at,observation_id)` and role/scope binding; no offset-only unbounded scans.

### Example semantic response (SYNTHETIC ONLY)
~~~json
{
  "location_id": "00000000-0000-4000-8000-000000000101",
  "observation_type": "MEASURED",
  "metrics": [{
    "metric": "air_temperature",
    "value": 24.8,
    "unit": "degC",
    "source_id": "00000000-0000-4000-8000-000000000201",
    "device_id": "00000000-0000-4000-8000-000000000301",
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
3. External polling task obtains admitted **provider stream** configuration and per-stream cursor, reserves provider-wide weighted quota, writes measured station observations or per-location model snapshots. One NWS measured-station stream may back many valid assignments; every coordinate-specific forecast/model request has a separate stream and cursor. 429/503 -> bounded backoff for only that stream, no optimistic watermark.
4. Read queries choose preferred qualified measurement per metric, return explicit source site/time, and label model forecast separately; UI detects stale values using source-specific expected interval.
5. DB unreachable -> app readiness fails, receiver replays bounded spool; provider task halts advances; Private API returns 503 or last-known data **only if reachable**; default browser/API `Cache-Control: no-store`, static-asset-only service worker; no sensitive response caching or implied remote wipe of previously stored data.
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

## 9. Terminal/permanent rejection handling and traceability clarification
A permanently invalid **member** (unregistered sensor, impossible metric, member schema/value failure) receives a digest-bound `REJECTED_TERMINAL` outcome in a trusted HTTP **207** batch reply, including when all members are terminal. A conflicting reused `event_id`/digest receives per-member `CONFLICT_QUARANTINED` in **207**, never blanket HTTP 409. Both cease ordinary retry only after the receiver durably preserves a verified redacted terminal/quarantine receipt; neither counts as an accepted weather observation. A malformed/oversized **outer** envelope is refused by whole-batch 400/413 before any member transaction. Auth failures halt forwarding; pre-processing 429/503, timeouts, member `RETRYABLE` and untrusted/incomplete acknowledgements preserve unacknowledged journal entries for a fresh signed attempt.

Traceability: D-001/D-002/D-003/D-004/D-006/D-008/D-010; WP-004/WP-005/WP-006/WP-007/WP-009/WP-010; AT-006/AT-009/AT-012/AT-013/AT-017/AT-022/AT-025/AT-026/AT-027. The API example above uses reserved **synthetic UUID-form** identifiers satisfying the proposed schema shape; no actual site or device identity is included.

## 10. Binding RF transport, spool and provider-stream contract (CR-1; PROPOSED only)

### 10.1 Signed batch and result envelopes
**Whole-batch versus member atomicity:** A whole-batch non-207 error is legal only before any member processing starts. After any event member is processed, finish the admitted batch with one explicit outcome per member, even if later members fail, and return 200/207 by the rule below. Receiver deletion needs a trusted matching `request_id`, `event_id` and original digest; an incomplete response cannot clear unverified entries.

Request `rf-batch.v1` is an HMAC-authenticated JSON object `{schema_version,request_id,receiver_identity,items:[...]}`. Each member has immutable `event_id` (first-seen UUID), `receiver_boot_id`, sequence, `receive_utc`, decoder model/SHA, candidate RF ID, sanitized payload and `payload_sha256`. The receiver signs HTTP method+path+UTC request timestamp+**new random nonce**+body SHA-256 with a receiver-only secret. Constant-time verifier checks bounded clock skew, registered receiver and durable `weather.transport_nonces` uniqueness within a short admitted window. A legitimate resend preserves original `event_id`/payload/digest but **uses a fresh request timestamp, nonce and signature**. A duplicate signed nonce is an auth failure, not a duplicate event. If nonce persistence cannot be checked because the DB is down, return 503 and commit no event.
**Fresh-nonce admission lifecycle (v1 design budget):** Require server-clock skew no greater than ±120 seconds and a distinct random signed nonce per transport attempt. After verification of HMAC, receiver identity, request method/path and body SHA-256, the app must **commit** a uniquely constrained `(receiver_identity,nonce)` row to PostgreSQL before any member transaction. Parallel/restarted nonce reuse is HTTP 403 with no event processing; unavailable nonce storage is HTTP 503 before any member processing. Keep each admitted nonce for **at least 300 seconds from server admission**, covering the full 240-second possible signed-timestamp validity span plus 60-second margin. Reject admission if server clock integrity cannot be established. A legitimate retry uses a new timestamp/nonce/signature but the **same first-seen event ID and payload digest**. Expiration after the replay window is a separately authorized, bounded **operator-only operational nonce maintenance** action; the weather runtime has no DELETE/TRUNCATE or canonical retention authority. Test simultaneous duplicate nonce, crash/restart, expiry-window edges, clock rollback, full nonce table and DB outage.

Result `rf-batch-result.v1` is `{schema_version,request_id,results:[{event_id,payload_sha256,outcome,reason_code?}],retry_after_seconds?}`. A fully processed response binds every admitted member's exact original ID/digest. Outcomes: `COMMITTED` (atomic event+accepted metrics committed); `DUPLICATE_COMMITTED` (identical already committed ID/digest, row-count invariant); `REJECTED_TERMINAL` (permanent invalidity, no accepted observation); `CONFLICT_QUARANTINED` (reused ID/different digest, no overwrite); `RETRYABLE` (member write rolled back). **HTTP 200** applies exclusively to all committed/duplicates; **HTTP 207** to *every* complete batch with one or more terminal/conflict/retryable members, including all-terminal, all-conflict, all-retryable and mixed outcomes. HTTP 400/413 outer envelope/size, 401/403 auth/nonce, 429/503 pre-processing backpressure/DB outage are whole-batch refusals only if **zero** members processed. No blanket member 409/422. Incomplete, timed-out or unverifiable reply leaves all unverified items pending. Successful weather ACK is **only** committed/duplicate; terminal/conflict is a trusted receipt to retire/quarantine from retries, never weather success.

### 10.2 Nine-case receiver transition matrix

| Condition | Response | Required receiver action |
|---|---|---|
| Newly committed event | member `COMMITTED` after DB commit | Verify ID/digest, mark ACKED and durably delete pending journal file |
| Already committed same event ID/digest | member `DUPLICATE_COMMITTED` | Delete staged copy; no new observation |
| Permanent invalid member | member `REJECTED_TERMINAL` (HTTP 207 when mixed) | Stop retry, redacted terminal receipt; no observation ACK |
| Conflicting ID/digest | member `CONFLICT_QUARANTINED` | Isolate, alert operator, no overwrite/automatic reuse |
| Authentication/clock/nonce failure | HTTP 401/403 | Halt forwarding; preserve approved staged data for operator remediation; no silent bypass |
| Database outage or transient failed member | HTTP 503/timeout or member `RETRYABLE` | Retain immutable event; bounded backoff and **fresh HMAC attempt** |
| Rate limiting/backpressure | HTTP 429 or member `RETRYABLE` | Keep staged; honor Retry-After; monitor spool age |
| Receiver crash/restart, lost response | no trustworthy final result | Scan/validate journal and replay surviving IDs with new HMAC; torn entries quarantined with explicit data-gap uncertainty |
| Spool full or no durable write | cannot safely forward this capture | Stop/limit intake, critical gap/loss alert; no false accepted ACK or silent rotation |

### 10.3 Durable filesystem spool (noncanonical buffer, no second DB)
For any terminal/conflict outcome, durably journal the exact authenticated redacted receipt/quarantine state (file fsync and directory fsync) **before** removing an associated pending event. Do not leave permanently rejected items in a busy retry loop, and do not delete on an unauthenticated or partial 207.

For each accepted RF packet, allocate first-seen UUID/receive time once and write a versioned length+digest record to `pending/<uuid>.tmp`; `fsync` file, atomic rename to `pending/<uuid>.event`, then `fsync` directory **before** HTTP send. `IN_FLIGHT` is volatile, `CAPTURED_DURABLE` is a verified pending file, `ACKED` is an exact valid member ACK followed by unlink and directory fsync. If ACK was committed but local removal fails, subsequent replay yields `DUPLICATE_COMMITTED` without duplication. Crash after received packet but before file sync can lose data and **must not** be described as lossless. Startup scans validate record version, length and digest; torn/corrupt records quarantine with visible gap alert instead of silently dropping. Terminal/conflict moves to controlled redacted quarantine with privacy-approved payload handling. Bound disk usage and age; warn at 80%, critical on exhaustion. Validate actual NAS rename/fsync behavior and restart/power failure in WP-006; if semantics unsupported, block deploy or use separately assessed receiver-host fallback.

### 10.4 Provider product identity and PWA privacy

`source_id` is the qualified logical provider/site origin. `stream_id` is the unique immutable *upstream polling product*, not the specific resolved UTC HTTP window. The versioned `stream_key_digest` binds provider, entitlement, product, source, coordinate assignment or identical shared measured station, fixed site/grid geometry, model/variables/units, and **relative horizon/window policy**. Exclude current poll time, resolved absolute start/end, fetch timestamp, ETag, response body/digest and request-specific parameters from stream identity; actual request windows and results belong to poll/retrieval evidence. An operator-governed material change in product/geography/model/relative horizon creates a **new** stream, whereas rolling a window never creates a new cursor. Each coordinate-specific NWS grid forecast or Open-Meteo model has its own `poll_state(stream_id)`; a genuinely identical measured NWS station product can serve multiple qualified assignments. Every model retrieval snapshot preserves its *full raw response SHA-256* in immutable event metadata and a separate versioned **semantic-product SHA-256** of normalized provider/model, metric, units, validity intervals, values, qualifying issue time when real, and relevant model metadata; exclude volatile HTTP/transport timestamps and `generationtime_ms`. 304 or semantically identical 200 updates heartbeat only; changed semantic content appends new retrieval revision and advances only that stream after commit. For Best Match, `run_identity_status=UNKNOWN` and `issued_at=null` unless true issuance is independently verified; never fabricate issue time. Provider-wide quota reserves **effective weighted units** before each actual request. Open-Meteo remains license-gated; only audited operator CLI administers streams.

Default private weather API replies must set `Cache-Control: no-store`; service worker caches versioned static assets **only**, not history, location coordinates or authenticated API bodies. ACL/tailnet revocation denies subsequent network fetches but cannot guarantee remote erasure of previously retained data. Test stale/offline display without claiming network revocation wipes device storage.

**Review crosswalk:** `LHW-RV-003/004/006/008/010` → `D-003/005/006/008` → `WP-004/005/006/007/009/010` → `AT-007/009/010/012/013/016/018/020/022/025/027`. All test and live prerequisites remain unexecuted.
