# 13 — Dependencies, hardware BOM, licensing and implementation compatibility
**LHW-ML-20261023 | CP-5 | PROPOSED.** Costs are observed manufacturer listings, not orders, quotations, commitments or proof of hardware arrival. Source pin/metadata snapshot 2026-10-23; revalidate at execution.

## 1. Physical inventory and bill of materials
| Item | Evidenced state | Quantity & requirements | Purchase/cost disposition |
|---|---|---|---|
| Existing Ambient WS-2000, outdoor WH65/WH65B Osprey-class transmitter | **USER-REPORTED OWNED**, console failed, physical on-air condition/model unverified | one single local station; assumed US 915 MHz pending actual capture | reuse, no new station |
| Optional Ambient/Fine Offset WH32B indoor sensor | **MAY EXIST**, not identified or decoded | one optional co-located indoor/pressure device, separate device ID | no purchase before RF proof |
| Synology DS923+ NAS | **USER-REPORTED OWNED**, DSM/Container Manager/USB path/current PG topology unverified | one current NAS for receiver/app and existing separately managed my-pa PostgreSQL | use only after hardware/runtime acceptance |
| Nooelec NESDR SMArt v5 **Bundle**, SKU 100700, ASIN B01GDN1T4S | **PLANNED/SELECTED** per user; order, delivery and actual PCB revision unknown | one RTL2832U, R820T2/R860, female SMA and included antenna/cable kit; vendor spec 0.1–1750 MHz | vendor US$54.95 observed on 2026-10-23, **not paid or delivery proof**; do not reorder if already procured |
| Included antenna base + 2 m RG58 + three masts | Included **if SKU 100700 authentic bundle delivered** (telescopic, 433 MHz fixed, UHF fixed) | initially use suitable mast with frequency/gain measurement; 433 MHz mast should not be assumed optimal at 915 MHz | included, conditional RF acceptance |
| Short shielded USB extension | optional, if placement/fit/noise diagnostics justify | one | **CONDITIONAL**, no unsupported price |
| Dedicated tuned 915 MHz antenna | optional if measured 24h receive quality inadequate | one suitable SMA/ground plane, verify connector and placement | **CONDITIONAL after Gate-RF**, quote later |
| Alternate small Linux USB host (receiver only) | fallback if Synology DSM cannot stably expose RTL-SDR | one host + authenticated relay to NAS, **not another weather station** | **CONDITIONAL**, cost unknown |
| UPS/NAS RAM or disk expansion | dependent on existing installed resources and RPO/storage measurements | not specified | no automatic procurement |
Official hardware: https://www.nooelec.com/store/nesdr-smart.html ; https://support.nooelec.com/hc/en-us/articles/10470422657047-NESDR-SMArt-v5-FAQ ; https://www.nooelec.com/datasheets/100700 . Advertised frequency coverage establishes theoretical tuning, not usable USB passthrough or reception through installed antenna.

## 2. Third-party upstream pins, maintenance and license
| Upstream / purpose | Current Lakehouse pin and verified GitHub upstream HEAD | Licence / recommendation |
|---|---|---|
| `merbanan/rtl_433` — **required** weather RF decoder | Lakehouse `3792adf1075acb7c6447f7c27df9920fd4f2d41a`; upstream master `406f9a33550a2b6b3d0d8a8a486417ce5b3f13ab` 2026-10-20 | GitHub GPL-2.0 metadata, `src/devices/fineoffset.c` header GPLv2-or-later; pin exact SHA and capture field regression before bump |
| `matthewwall/weewx-sdr` — original WeeWX driver | Lakehouse `e5f1f9915322fa6d1c25b4ff8e490b804cefeac1`; current master same 2025-01-13 | GPL-3.0, **historical only** for Option C; don't fork |
| `weewx/weewx` — original station/archives | Lakehouse Docker baseline `felddy/weewx:5` mutable; WeeWX master `a5790be2d0d33da50440eb37e0a9e21499246920` 2026-10-22 | GPL-3.0; stock documented archives SQLite/MySQL, not approved PG backend; **historical only** |
| `uajqq/weewx-belchertown-new` — old UI skin | Lakehouse `e3994950c6dd95a0bcc4f101f4ea087f3fc31a5c`; current master same 2026-09-03 | GPL-3.0, not source-aware multi-location system; **historical only** |
| `felddy/weewx-docker` — old Docker base | Lakehouse `000186c66d1331c135f49bfd6fa28253464eefbf`; upstream `037b9818adab132c03a2a889565f2718aafc2462` 2026-10-22 | MIT, not initial production runtime |
| `hertzg/rtl_433_docker` — initial RF diagnostic image | Lakehouse `a3e2527a8bad99a794df5a3628c843497c3c16de`; upstream `8a849f4dd25a96c504dcd77da26b0a8c1dc27212` 2026-10-11 | GitHub GPL-2.0 metadata; script currently floats `:master`, pin OCI digest for test reproducibility |
Upstream URLs and gitlinks are in original `UPSTREAMS.lock` and `.gitmodules`, see [01_SOURCE_AND_SYSTEM_AUDIT.md](01_SOURCE_AND_SYSTEM_AUDIT.md). Keep submodules/patch records until accepted superseding ADR and separately approved cleanup. Commit hashes are *source identities*, not proof of package security or support. Inspect upstream license headers and redistribution of linked/copied vs independently executed binaries; retain copyright notices and source references. Current Lakehouse integration is GPL-3.0-only; don't assume metadata SPDX alone settles packaging/distribution obligations.

## 3. Proposed software bill of materials
| Component | Proposed role | Version/authority and runtime limits |
|---|---|---|
| Python | weather service and receiver line-forwarder | >=3.12 candidate; choose exact image architecture and patch **at WP-002**, lock dependencies; not yet installed |
| FastAPI + Pydantic | strict input validation and versioned GET/internal ingestion routes | choose mutually supported pinned versions; single Uvicorn process; no public swagger route by default |
| SQLAlchemy + psycopg 3 | restricted PG transactions and read queries | own small pool (proposed <=2; 0 overflow), explicit `weather` schema, **no Alembic in Lakehouse** |
| Existing my-pa PostgreSQL | **only canonical weather persistence** | actual server+instance UNKNOWN; my-pa local-dev Compose references `postgres:17.10` but is not live attestation |
| my-pa Alembic | only DDL owner | existing repository 121 revisions at `6f1476b8da52` **per index**, inspect then-current head before new migration |
| React + TypeScript + Vite | private iPhone-first static PWA inside weather-app image | pin Node/build versions with lock; no extra Next.js frontend server, no SSR |
| Charting library | historical trends | choose after proof of accessible time-series charts, license and bundle-size comparison; not preselected |
| Tailscale Serve / HTTPS | private remote iPhone browser access | configuration, ACL and endpoint UNKNOWN; avoid public port forwarding |
| Cloudflare Tunnel/Access | optional future public edge | **NOT MVP**; separate operator approval and application auth, no reuse of my-pa credentials |
| NWS / NOAA API | US station measurements, forecasts and optional alerts | no charge under current API terms, user-agent required, reasonable undisclosed rate limits; station observations only about 7 days available |
| Open-Meteo forecast API | global fallback and model-derived series | free only for noncommercial use: **<10k/day, <5k/hour, <600/min**; CC BY 4.0 attribution; issued run identity may be unavailable under Best Match; eligibility decision U-006 |
| Docker/Container Manager | service isolation | actual DSM image/runtime platform to verify, all images pinned by digest |
Provider primary sources: https://www.weather.gov/documentation/services-web-api , https://open-meteo.com/en/terms , https://open-meteo.com/en/pricing , https://open-meteo.com/en/docs/model-updates . Client push alerts are deferred and must meet Apple's iOS Home Screen/permission requirements.

## 4. Capacity and recurring cost model (DERIVED, not live measurement)
WH65B nominal 16-second broadcast interval is decoder-era expectation: `86400/16 = 5400` candidate packet events/day; if 8 metric fields each then `43200` rows/day and `~15.8M` rows/year. This **does not establish observed RF cadence, retention necessity, compressed bytes, WAL or backup size**. WH32B/remote providers add variable volume. Required isolated test: populate synthetic 1d/30d/365d weather rows and indexes; measure `pg_total_relation_size`, WAL bytes, CPU/RAM, concurrent my-pa p95 latency, backup/restore time, and exact selected source count. Only then set retention, aggregate partition choice, NAS disk headroom and image memory limits. No unbounded cache, Redis, Timescale, Influx or separate Postgres.

Additional recurring expense for baseline is unknown. Existing devices are user-reported, Tailscale plan entitlement unverified, Open-Meteo noncommercial may be free if eligible, NWS has no charge, optional domain/Cloudflare and hardware depend on operator selection. **Do not authorize purchases** from this BOM.

## 5. Dependency readiness gates
- U-001..U-003: physical DB identity, role/migration owner, connection/WAL/backup allowance.
- U-004, U-010: Nooelec kit/WH65B/WH32B present and actual DSM RF decode; postpone antenna/host purchase until Gate-RF diagnostic.
- U-005: chosen locations and real coordinates/timezones, supplied by operator in protected runtime config only.
- U-006: Open-Meteo commercial/noncommercial classification, actual call/retention and attribution requirements.
- U-007: verified private HTTPS/Tailscale/ACL path; no assumed hostname.
- U-008..U-009: approved retention/RPO/RTO and freshness/performance thresholds.
- WP-002: exact package versions, OCI digest pins, ABI/architecture compatibility and SBOM/license review prior to any deployment build.

## 6. Traceability
D-002/D-005/D-009; WP-002/WP-003/WP-004/WP-007/WP-011/WP-012; AT-001/AT-003/AT-015/AT-016/AT-023/AT-024. Costs are external vendor observations, not purchase authorization or completed asset inventory.
