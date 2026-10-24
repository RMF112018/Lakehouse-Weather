# 02 — Architecture alternatives and independent challenge
**Package:** LHW-ML-20261023 | **Checkpoint CP-2** | **2026-10-23** | **Decision state:** PROPOSED; independent plan review and operator gate outstanding.
Source baseline and verified facts: [01_SOURCE_AND_SYSTEM_AUDIT.md](01_SOURCE_AND_SYSTEM_AUDIT.md).

## Nonnegotiable criteria
1. Existing my-pa PostgreSQL is the **only canonical weather record database**. No WeeWX SQLite/MySQL or new Postgres/Influx/TimescaleDB system of record.
2. One NAS-connected SDR receives **only the local WS-2000/WH65B installation**, and optional WH32B is part of that installation. Every other location relies on independently approved network providers.
3. Each weather record carries location, logical source, physical device where applicable, measurement/event time, ingest time, unit, quality, immutable raw lineage reference where applicable and an explicit distinction of observed / modeled / forecast.
4. No modification of my-pa application or DB permissions/schema without my-pa-owned migration review and separately authorized execution.
5. Mobile private iPhone access; no public DB ports, unauthenticated write broker, extra database or speculative service.

## Evaluation
Rating key: **Good** meets requirements with maintainable interfaces; **Conditional** needs unverified adaptation; **Poor** directly conflicts or creates long-lived complexity. Ratings are engineering judgment (**DERIVED**) informed by verified upstream/repo interfaces, not benchmark measurements.

| Option | PostgreSQL & governance fit | Multiple locations / provenance | Operational footprint | Reuse / delivery risk | Verdict |
|---|---|---|---|---|---|
| **A**: Extend WeeWX directly onto my-pa PostgreSQL; one or many WeeWX instances | **Poor**: WeeWX's stock documented storage adapters are SQLite and MySQL/MariaDB; unknown third-party PostgreSQL driver and migration collision | **Poor**: station/interval archive schema does not natively supply time-bounded provider and device identity or forecast lifecycle | **Poor** if scaled to locations: instances, competing schema owners | Reuses archive/reporting but demands undocumented backend and extensive adaptation | **REJECT pending credible supported PostgreSQL adapter, multi-source evidence, and governance agreement** |
| **B**: WeeWX for local SDR, normalized forwarder to weather app, my-pa PostgreSQL canonical | **Conditional**: needs reliable forwarding and separate ingest idempotency; WeeWX normally owns a duplicate archive | **Good** once the receiving app exists; WeeWX only solves local portion | **Poor/Conditional**: extra image, station configuration, SQLite secondary archive, reports and forwarding bridge | Reuses sensor map / weather calculations; however duplicate persistence and two error pathways | **REJECT for MVP; preserve only as RF/prototype fallback subject to proof it can run without durable duplicate archive** |
| **C**: Pinned `rtl_433` decoder + dedicated local collector relay + single weather application (provider polling, normalization, API, static PWA) + my-pa PostgreSQL `weather` schema | **Good conditional on my-pa migration/role authorization** | **Good**: explicit source/device/assignment history and forecast table from inception | **Good**: two weather containers, existing DB, no broker or second archive | Small but material custom code for normalization/time series and mobile UI; avoids WeeWX database lock-in | **PREFERRED for planned implementation** |
| **D**: Hybrid retained WeeWX reports/calculations alongside direct PostgreSQL ingest | **Conditional**: data replicas/exports require reconciliation | **Good** only with separate weather app | **Poor**: two pipelines, more operational cost | Existing reports may be useful but duplicate authority is difficult to prove | **DEFER unless metric-quality benchmark demonstrates indispensable missing capability** |
| **E**: Extend my-pa gateway/frontend with weather capabilities in same processes | **Good** for physical DB but strongly coupling to my-pa code/migrations | **Good** if engineered | **Conditional**: avoids weather API but imports USB/provider polling into a governance-sensitive application | High blast radius and independent release friction; auth/repository scope expansion | **REJECT initial design; reconsider only under a joint product architecture approval** |

### Decision D-001 — Storage and application ownership (PROPOSED)
Use **Option C** subject to **GATE-DB**. Keep code, API, UI, external weather pollers and RF normalization in **Lakehouse Weather**. All schema changes, role provisioning changes and migration sequencing for the existing DB belong to **my-pa** and its authorized owners. No Lakehouse migration command against the live shared database.

### Decision D-002 — Only required upstream at runtime (PROPOSED)
Use rtl_433 as a separate, pinned, provenance-preserving executable. Do not use WeeWX, weewx-sdr, New Belchertown, Mosquitto, an Influx/Timescale instance, Redis, or Celery in initial production. Retain existing submodule pins and ADR-0001 as **historical evidence** until a separately reviewed dependency retirement plan, without silent deletion. A new proposed ADR must explicitly supersede ADR-0001 for the implemented path after approval.

### Decision D-003 — Two weather containers, one shared DB (PROPOSED)
**receiver**: restricted device-owning container running `rtl_433 -f 915M -M time:utc -F json` and a small bounded line-forwarder over an internal Docker bridge, with no database credential. Receiver authenticates to private `POST /internal/rf-events` with a mounted ingest secret. Whitelist models/IDs; do not treat JSON fields as trusted. Make connection failures explicit and preserve bounded local transient spool for replay; never call spool a canonical database.
**weather-app**: one Lakehouse-owned Python process containing normalizers, approved-provider polling schedules, data access, read-only /api/v1 endpoints, and serving versioned static PWA. It has a **restricted** application DB credential but no USB device. Schedule/polling ownership assumes exactly one running app instance; expanding replica count requires a leader/lease design. Private tailnet-only iPhone access through a verified proxy and Tailscale Serve; a Cloudflare-origin route requires a separate ingress and authentication decision. No publicly exposed POST or database endpoint.
Resource obligations and interfaces: [03_TARGET_ARCHITECTURE.md](03_TARGET_ARCHITECTURE.md).

### Decision D-004 — Data types never conflated (PROPOSED)
Weather sample data types: **measured observation** (RF physical sensor or actual provider station measurement), **modeled current/historical analysis** (e.g., Open-Meteo model estimates), **forecast** (future prediction with issue time and validity interval), **derived aggregate** (audited computed summary). No extrapolated forecast can fill a measured reading without visible type/source labeling; missing remains `null`, not zero.

### Decision D-005 — Provider minimization (PROPOSED)
MVP provider set: (1) local WH65B via rtl_433 if hardware passes Gate 1; (2) **NWS** for US observed stations, forecasts, warnings where available; (3) **Open-Meteo** only for approved noncommercial modeled forecasts/global location fallback. NWS observation site may differ from the selected display location: record station identity/coordinates and distance, do not claim a nearby station measured exactly at the destination. Open-Meteo `current` and historical model products are never labeled locally measured. Check provider terms, attribution, rate limits and source metadata at adapter enablement. Alternatives (Tomorrow.io etc.) require material capability/cost case, not speculative registration.

### Decision D-006 — Auth and external access (PROPOSED)
First expose **read-only** UI through private Tailscale/HTTPS, with verified ACLs. Browser clients have no database credentials and cannot invoke internal ingestion endpoints. Keep admin/source registration private via operator CLI initially. Cloudflare Tunnel + Access (if chosen for Lakehouse) needs its *own* trust and origin policy; my-pa's public tunnel/hostname, auth and credentials are **not inherited**.

### Decision D-007 — No unvalidated meteorology (PROPOSED)
Retain original RF counters and quality flags. Rain period totals derive only from verified monotonic counter segments. Source changes, gaps, negative deltas, reset and rollover require distinct handling. Pressure absent from outdoor array until independently observed WH32B or another qualified sensor. Wind averages use defined sample duration and arithmetic/circular statistics as appropriate. Maintain formula version and source links.

## Upstream capabilities and challenge evidence
- Official WeeWX database bindings: https://weewx.com/docs/5.5/reference/weewx-options/data-bindings/ ; https://weewx.com/docs/latest/reference/weewx-options/databases/
- rtl_433 WH65B and WH32B code: https://github.com/merbanan/rtl_433/blob/master/src/devices/fineoffset.c
- weewx-sdr: https://github.com/matthewwall/weewx-sdr (weewx station driver, `sensor_map`, invokes rtl_433; no general multi-source PostgreSQL application)
- New Belchertown: https://github.com/uajqq/weewx-belchertown-new (WeeWX skin, not independently confirmed to provide a native multi-provider/multi-location API)
- NWS official API: https://www.weather.gov/documentation/services-web-api
- Open-Meteo license and limits: https://open-meteo.com/en/terms

## Rejection reconsideration thresholds
A or B can reopen only upon a working PostgreSQL-backend/service demonstration, independent schema ownership approval, contract tests for location/source history and forecast separation, bounded duplicate-storage analysis and measured lower lifecycle cost than C. D can reopen only if instrumented derived-metric parity proves reusable WeeWX outputs materially reduce correctness risk without introducing a competing canonical archive. No alternative is approved for deployment by this plan alone.

## CR-1 — Independent review corrections do not alter the option selection

Option **C** remains the preferred architecture after the adverse plan review `LHW-INDEPENDENT-PLAN-REVIEW-20261023-001` (`PLAN_REVISION_REQUIRED` at previous HEAD `78a33161e38dce7adb2476e74488f18ccd6ad01f`). This is **not** a new accepted ADR or implementation approval. It is a revised *design contract*: decoder `MODEL_WH65` cannot emit `MODEL_WS69` pressure in either inspected SHA; immutable raw metadata and expiring payload bytes must coexist with long-lived observation FKs; each coordinate-specific forecast/model stream gets independent cursor; separate auditable `weather_admin_cli` controls metadata; composite integrity guards protect assignment/device/source history; `rf-batch.v1` uses fsynced spool/per-member ACK with new nonce on retry; derived rainfall stays outside physical observation storage. See [03](03_TARGET_ARCHITECTURE.md), [04 §7](04_POSTGRESQL_INTEGRATION.md), [05 §11](05_WEATHER_DATA_MODEL.md), [06](06_INGESTION_AND_SOURCE_INTEGRATIONS.md), [09](09_VALIDATION_AND_ACCEPTANCE.md) and [11](11_RISK_AND_DECISION_REGISTER.md). Open-Meteo remains gated and PWA weather-API caching defaults to off. Alternative A/B/D/E decisions stay deferred or rejected on the current facts; independent exact-head re-review remains required.
