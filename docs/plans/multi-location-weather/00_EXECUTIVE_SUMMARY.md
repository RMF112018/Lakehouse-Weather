# 00 — Executive summary: multi-location Lakehouse Weather
**Plan ID:** LHW-ML-20261023 | **Version:** 1.2 CR-3 NF-001/NF-002 DOCUMENTARY CORRECTIVE CANDIDATE | **Date:** 2026-10-23
**Disposition:** CR-3_TWO_MATERIAL_DESIGN_CORRECTIONS_PROPOSED / FRESH_INDEPENDENT_EXACT_HEAD_REVIEW_REQUIRED / NO_IMPLEMENTATION_AUTHORITY / PRODUCTION_BLOCKED
**Authority:** Planning-only. No weather service, database migration, credential, NAS configuration or production deployment has been changed.
**Controlling identities:** `RMF112018/Lakehouse-Weather main@aea6bada042b34a8365c9e70e3a6a0f90304f3f0` (tree `a3a375a2235294b886703a9e698675be79e5831f`); `RMF112018/my-pa main@3d1593aa4dc2477395b47c97067338f8c46eff0b` (tree `fa7e416a83d67284b0801e5f59f04189d780bbee`), observed 2026-10-23. Revalidate at implementation gate.

## 1. Recommendation
**Select Option C**, subject to independent design review, explicit my-pa database/migration ownership approval, actual SDR and security proof:

```text
Local WS-2000 WH65B (+ optional WH32B) -> 915 MHz -> Nooelec RTL-SDR
  -> pinned rtl_433 in NAS-isolated receiver container
  -> TLS 1.3 mTLS private RF ingest + independently server-signed ACK -> weather-app (Python API+poller)
External registered locations -> NWS measured site observations & forecasts
                              -> optional Open-Meteo MODELED data
  -> common source-aware normalization/quality/provenance service
  -> existing my-pa PostgreSQL physical database, proposed weather schema
  -> versioned read-only API + static React/TypeScript/Vite iPhone PWA
  -> private authenticated/Tailscale HTTPS ingress -> iPhone
```

**Only the one local WS-2000 installation sends RF to NAS-attached SDR.** Other geographic locations use independently registered and authorized web providers. WH65B outdoor array and potential WH32B indoor/pressure sensor belong to the same station installation but retain separate physical device identities. Real sensor and coordinate values remain unverified and must never be guessed.

**Rationale:** The existing WeeWX 5 + weewx-sdr + New Belchertown + SQLite scaffold is designed for a single local weather archive and does not provide a supported, verified direct PostgreSQL/forecast/multi-source data architecture. WeeWX official database documentation describes SQLite/MySQL, not stock PostgreSQL. Keeping it as a second archive creates two truths and a second operational lifecycle. Direct `rtl_433` decoding preserves the proven RF ecosystem while allowing a small, explicit domain for source identity, API forecasts, corrections and many locations. Two weather containers are justified to isolate USB and DB credentials. No MQTT, Redis, new PostgreSQL, InfluxDB, TimescaleDB, separate dashboard server or speculative provider framework.

## 2. Major differences from current scaffold
| Today (repository-level verified) | Recommended future (PROPOSED) |
|---|---|
| WeeWX + SQLite records, generated New Belchertown skin | dedicated source-aware Python service + my-pa PostgreSQL `weather` tables + versioned React/Vite PWA |
| A single outdoor station and optional indoor sensor | same local installation plus multiple independently registered remote geographic locations |
| Single-station data fields and sample WH65B fixture | immutable raw event metadata/digests plus separately controlled payload bytes, per-location provider streams/cursors, logical sources and time-valid assignments, device epochs, typed measured vs modeled vs DERIVED records and quality/revisions |
| Optional anonymous internal Mosquitto and floating diagnostic/base image tags | no broker; digest/SHA-pinned decoder, strict private internal authenticated RF forwarding |
| Status says RF pending and downstream blocked | same status remains pending until real NAS/USB/receiver tests; no claim of implemented ingestion |
| Ad hoc archive tar/HTTP liveness only | my-pa-owned consistent PG backup/restore, weather provenance, source freshness, replay/failure telemetry and mobile validation |

## 3. Ownership boundary
The **existing my-pa PostgreSQL database** remains mandatory canonical persistence. Proposed schema `weather` is not an approved DDL change. my-pa repository owns **every new schema migration and role provisioning change** under its current Alembic/DB policy, in separately authorized my-pa work; actual target DB identity and applied migration head have not been verified. Lakehouse owns RF decoder integration, weather application code, external provider adapters, non-schema read/write ORM, PWA, tests and weather-specific operations. The receiver holds no SQL credentials; weather-app receives restricted `weather` privileges, never `my_pa` superuser or cross-schema access.

**Nondelegable stops:** no production DB connection/migration, source API secret enrollment, NAS deployment, public ingress, credential mutation, destructive cleanup, record purge, merge, risk acceptance or production activation without applicable explicit operator authority. A planning PR is a request for review, not an implementation authorization.

## 4. Multi-location/source rules
One station installation may include WH65B outdoor + conditional WH32B indoor sensor. A location may have several preferred or competing sources; one logical provider may serve many locations through time-bounded assignments. A source retains its own provider-site geography, observation timestamp, ingestion timestamp, original raw event digest, device if physical, unit/quality, correction link and attribution. Station relocation and RF ID/battery replacement append history rather than rewrite it. NWS site observations are **measured remotely at the station** (not necessarily at destination); Open-Meteo current and historical weather values are **model estimates**, not physical sensor observations; forecasts have issue and valid times in separate tables.

Rainfall derives from verified cumulative counter deltas and flags resets, rollovers and incomplete local-day intervals; no fabricated zero or undocumented precision. Time values persist as UTC instants with real location IANA timezone for daily boundaries and DST. UI displays source class, freshness, unavailable sensors, quality/completeness and conflicts.

## 5. Proposed execution sequence and effort
**WP-001** current source and runtime audit → **WP-002** independent plan/ADR approval → parallel **WP-003** hardware RF proof (if dongle present) and **WP-004** separately approved my-pa disposable DB/schema contract → **WP-005** domain/API/persistence → **WP-006** single local RF ingest and **WP-007** remote provider adapters → **WP-008** source-aware historical calculations → **WP-009** iPhone PWA → **WP-010** tailnet/private ingress → **WP-011** integration/independent exact-head review → **WP-012** backup/restore, runbooks and handover.

Revised planning sensitivity **73–132 experienced engineering person-days** (original 53–95 was an optimistic but correctly summed estimate) (not schedule or cost commitment), with parallel execution possible after gates. RF soak adds >=24 elapsed hours. Steps independent of hardware include my-pa authorization/documentary schema design, synthetic domain/test fixtures and NWS/Open-Meteo contract tests; none permit claiming live RF success. [10](10_IMPLEMENTATION_WORK_PACKAGES.md) gives per-WP repository, prerequisites, deliverables, risks, exclusions and effort; [09](09_VALIDATION_AND_ACCEPTANCE.md) provides 27 acceptance tests.

## 6. Material open decisions / no-go gates
| ID / risk | Open item | Required proof |
|---|---|---|
| U-001..003 / RSK-001,007 | actual DB version/physical alias, applied Alembic head, grants and connection/WAL/backup capacity | my-pa operator-approved runtime attestation and reviewed scratch migration/role/restore proof |
| U-004/U-010 / RSK-002,003 | Nooelec kit arrived? DSM USB passthrough, installed WH65B/WH32B IDs, pressure and reception quality | hardware Gate-1, 24h soak and restart tests |
| U-005 / RSK-015 | actual additional user locations, zones, privacy/source preferences | protected operator config; synthetic placeholders until supplied |
| U-006 / RSK-006 | Open-Meteo noncommercial/attribution quota and data retention eligibility | approved source registration; provider terms and license evidence |
| U-007 / RSK-008 | tailnet/HTTPS/ACL topology | live iPhone cellular test, proxy/port/auth negatives |
| U-008..009 / RSK-004,011,013 | retention, RPO/RTO, freshness/packet capture rate and storage resource budgets | operator-approved measured thresholds, non-destructive scratch restore/performance benchmarks |
No gate is recorded as passed without actual evidence at the correct identity. No unapproved purchasing based solely on this plan.

## 7. Recommended next action
**Immediate:** submit this *planning-only* PR for independent review and obtain an explicit architecture/ADR and my-pa DB ownership decision. **First technical work package after independently approved corrected plan and exact operator authority: WP-003 — local RF/USB acceptance**, provided the selected Nooelec kit is physically available and bounded NAS inspection is authorized. If it is absent, pursue the **documentary/scratch design-only portion of WP-004** in parallel after exact my-pa authorization; never infer RF Gate PASS.

## 8. Package status and navigation
- 01 Source / as-found system audit and 15 finding classifications
- 02 Architecture alternatives and option C proposal
- 03 Proposed two-container target topology, API and data flow
- 04 Existing my-pa PostgreSQL authorization, migration/role and backup contract
- 05 Source-aware multi-location observation and forecast data model with five synthetic scenarios
- 06 RF hardware, provider interfaces and normalization/replay requirements
- 07 iPhone dashboard/PWA and private ingress design
- 08 File-specific repository modification and my-pa boundary plan
- 09 Gates, 27 future acceptance tests and failure injection
- 10 Twelve implementation WPs, effort and critical path
- 11 Decision, risk, finding and unknown registers
- 12 Operations, continuity, recovery and nondelegable production gates
- 13 Dependencies, licensing, bill of materials, sizing assumptions
See [README](README.md) for index, checkpoint commits, package coverage and authoritative external links. This is **not independently approved** and does **not** demonstrate physical or production operation.

## 9. Corrective review candidate — CR-1 (not self-approved)

The independent review `LHW-INDEPENDENT-PLAN-REVIEW-20261023-001` concluded `PLAN_REVISION_REQUIRED` against old HEAD `78a33161e38dce7adb2476e74488f18ccd6ad01f` and tree `782327104e71ef144410285eafc534e75c3470b6`. This revision repairs seven MAJOR design contracts and three MINOR refinements **on planning Markdown only**. Exact new corrective HEAD/tree are established by GitHub after commit; the previous review verdict does not automatically apply to the revised HEAD.

- **Decoder:** inspected `Fineoffset-WH65B` cannot report the optional `MODEL_WS69` pressure field; separate actual WH32B/other qualified sensor only.
- **Provenance:** immutable raw-event metadata/digest outlives referencing measurements, optional raw payloads separate; 90-day payload/24-month observation is a possible future operator-gated policy with no purge now.
- **Sources/privilege:** independent provider streams/cursors per coordinate, shared measured NWS station where appropriate; restricted app vs separately authorized auditable metadata-admin CLI; SQL composite integrity and half-open station epochs.
- **Transport/meteorology:** durable fsynced first-seen packet journal, signed fresh-nonce attempts and per-member exact 200/207 ACK; rainfall increments/rates/totals DERIVED on read with two measured input IDs and correction-aware quality.
- **Refinements:** Open-Meteo Best Match model-run `UNKNOWN` and effective weighted quota, 73–132d provisional effort, static-only offline PWA cache and no false remote wipe guarantee.

Controlling corrective design: [03 transport](03_TARGET_ARCHITECTURE.md), [04 schema §7](04_POSTGRESQL_INTEGRATION.md), [05 domain §11](05_WEATHER_DATA_MODEL.md), [06 provider/RF](06_INGESTION_AND_SOURCE_INTEGRATIONS.md), [09 acceptance §7](09_VALIDATION_AND_ACCEPTANCE.md), [10 WPs](10_IMPLEMENTATION_WORK_PACKAGES.md) and [11 finding crosswalk](11_RISK_AND_DECISION_REGISTER.md). **A fresh independent reviewer must issue a new `PLAN_APPROVED`, `PLAN_REVISION_REQUIRED` or `PLAN_BLOCKED` against the actual revised HEAD/tree.** All other migration, hardware, credentials, provider, NAS, merge, deployment, production and risk gates remain closed.


## 10. CR-2 plan corrections — not independently accepted

A fresh independent rereview `LHW-CR1-INDEPENDENT-REREVIEW-20261023-001` concluded `PLAN_REVISION_REQUIRED` at **the preceding** CR-1 HEAD `e048d5de85afc8d275ea258a3db8aeb45b67f360` / tree `76b7ca604ab1f3e325b7853f4be14c2fb97b533f`. This operator-authorized **documentation-only CR-2** proposes corrections for four residual MAJOR contracts (batch HTTP member status, same-event physical device FK, mandatory model-to-raw-event provenance, stable provider-stream/semantic snapshot equality) and four mandatory MINOR refinements (nonce lifecycle, payload-retention wording, offline/SC-05 consistency, PR identity/API acceptance text). See [11 §CR-2](11_RISK_AND_DECISION_REGISTER.md), [03](03_TARGET_ARCHITECTURE.md), [04](04_POSTGRESQL_INTEGRATION.md), [05](05_WEATHER_DATA_MODEL.md), [06](06_INGESTION_AND_SOURCE_INTEGRATIONS.md), [09](09_VALIDATION_AND_ACCEPTANCE.md). **No reviewer has yet approved this new corrective HEAD/tree.** Option C remains a proposal; historical accepted ADR-0001 and all my-pa/operator physical/runtime no-go gates remain unchanged.

## 11. CR-3 bounded response to independent CR-2 review (NOT APPROVED)

Independent `LHW-CR2-INDEPENDENT-PLAN-REVIEW-20261023-001` issued **PLAN_REVISION_REQUIRED** against previous PR #1 HEAD `d0739f9e4ceba5ee45e8ba8ab8891cb68c994e23` / tree `45d2ead414320e275cb97d31f819f7a944f55e47`. The mechanical census had passed, but two NEW MAJOR design defects remained. This operator-authorized **documentation-only CR-3** corrects just those contracts and their acceptance/ownership crosswalk; it does not amend actual PostgreSQL or receiver code.

- **NF-001 PostgreSQL provenance:** every coordinate `FORECAST_MODEL` stream, model run and model value carries a **non-null immutable source/stream/assignment/class** with matching database composite foreign keys. A lawful same-source assignment B cannot receive model values fetched for A. Shared physical `MEASURED_STATION` NWS stream has NULL owner assignment and may only support correctly attributed physical measured observations, not model rows. See [04 §8](04_POSTGRESQL_INTEGRATION.md), [05 §12](05_WEATHER_DATA_MODEL.md) and [09 §8](09_VALIDATION_AND_ACCEPTANCE.md).
- **NF-002 authenticated RF ACK:** **mandatory mTLS 1.3 even on the Docker bridge** (dedicated validated internal CA/server SAN and registered receiver client identity), and separately keyed HMAC-SHA256 `rf-ack-mac.v1` over **the current signed request attempt, exact status and complete response**. A forged matching 200/207 or replay from an older send must not retire the only staged record; correct terminal receipt is separately fsynced. Remote Linux fallback must meet the same controls. See [03 §11](03_TARGET_ARCHITECTURE.md), [06 §10](06_INGESTION_AND_SOURCE_INTEGRATIONS.md), [12 §9](12_OPERATIONS_AND_LIFECYCLE.md) and [09 §8](09_VALIDATION_AND_ACCEPTANCE.md).

**Remains proposed:** retain Option C, all original F/D/RSK/U/WP/AT/SC/I stable identifiers and preliminary 73–132 engineer-day estimate; no tests run, no independent new-head review concluded, no accepted superseding ADR. Cross-repo my-pa migration authority, RF hardware, credentials, provider permissions, private iPhone, backup/retention, merge and production decisions remain separate operator gates. A new independent reviewer must bind an explicit `PLAN_APPROVED`, `PLAN_REVISION_REQUIRED` or `PLAN_BLOCKED` to the actual Git successor **HEAD/tree**; this correction does not self-approve.
