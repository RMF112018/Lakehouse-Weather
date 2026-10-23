# Multi-location Lakehouse Weather — Planning Package Index
**Plan ID:** LHW-ML-20261023 | **Revision:** 0.9 (planning PR candidate) | **Date:** 2026-10-23
**Disposition:** PROPOSED / INDEPENDENT_PLAN_REVIEW_REQUIRED / NO_IMPLEMENTATION_OR_DEPLOYMENT
**Scope:** implementation-ready plan for one NAS RF receiver (local Ambient WH65B + optional WH32B), many distinct API-sourced locations, shared existing my-pa PostgreSQL, source-aware iPhone dashboard. Source files from main remain unchanged.

## Start here
Read [00 Executive Summary](00_EXECUTIVE_SUMMARY.md) first, [02 Options](02_ARCHITECTURE_OPTIONS.md) and [ADR candidate](ADR-0002_CANDIDATE.md) for selection, [04 PostgreSQL](04_POSTGRESQL_INTEGRATION.md) for nondelegable database authority, [10 Work Packages](10_IMPLEMENTATION_WORK_PACKAGES.md) for execution, [09 Acceptance](09_VALIDATION_AND_ACCEPTANCE.md) and [11 Risks](11_RISK_AND_DECISION_REGISTER.md) for stopping criteria.

**Proposed architecture:** separately isolated `rtl_433` RF receiver -> authenticated weather-app ingestion/polling and source-aware API/PWA -> existing my-pa PostgreSQL database (proposed `weather` schema), with optional NWS observed station, NWS forecasts, conditional Open-Meteo model data for other locations. No independent weather DB, WeeWX/SQLite runtime, extra SDR remote stations or unrestricted public interfaces.

**Truth and scope:** GitHub `RMF112018/Lakehouse-Weather main@aea6bada042b34a8365c9e70e3a6a0f90304f3f0`, tree `a3a375a2235294b886703a9e698675be79e5831f`; `RMF112018/my-pa main@3d1593aa4dc2477395b47c97067338f8c46eff0b`, tree `fa7e416a83d67284b0801e5f59f04189d780bbee`. These are **October 23, 2026 planning snapshot identities**; current code/PG identity must be reverified before implementation. Evidence states `VERIFIED` repository/upstream documents, `DERIVED` analytic calculation, `PROPOSED` design target and `UNRESOLVED` runtime/approval gap.

## Full document register
| No. | File | Purpose / primary evidence |
|---|---|---|
| 00 | [Executive Summary](00_EXECUTIVE_SUMMARY.md) | selected proposal, rationale, critical gates, effort and next decision |
| 01 | [Source and System Audit](01_SOURCE_AND_SYSTEM_AUDIT.md) | source census, as-found commits and boundaries, upstream versions, F-001..F-015 |
| 02 | [Architecture Options](02_ARCHITECTURE_OPTIONS.md) | WeeWX A/B/C/D/E choices, rejection criteria, D-001..D-007 |
| 03 | [Target Architecture](03_TARGET_ARCHITECTURE.md) | component/process/networks, data flow, versioned APIs and failures |
| 04 | [PostgreSQL Integration](04_POSTGRESQL_INTEGRATION.md) | schema, roles, migration ownership, capacity, backup, unknown physical DB |
| 05 | [Weather Data Model](05_WEATHER_DATA_MODEL.md) | location/source/device, observation/model provenance, rain, DST, SC-01..SC-05 and I-01..I-12 |
| 06 | [Ingestion and Sources](06_INGESTION_AND_SOURCE_INTEGRATIONS.md) | actual RTL decoder code, RF gates, payload mapping, NWS/Open-Meteo, idempotency and outage |
| 07 | [Dashboard and Remote Access](07_DASHBOARD_AND_REMOTE_ACCESS.md) | iPhone PWA, source labeling, history, comparison, offline and private HTTPS |
| 08 | [Repository Change Plan](08_REPOSITORY_CHANGE_PLAN.md) | target file tree, existing file modification matrix, separate my-pa PR work |
| 09 | [Validation and Acceptance](09_VALIDATION_AND_ACCEPTANCE.md) | 27 ATs, gates, synthetic fixtures, negative and failure-injection tests |
| 10 | [Implementation Work Packages](10_IMPLEMENTATION_WORK_PACKAGES.md) | WP-001..WP-012, ordered dependencies/critical path/effort and detailed contracts |
| 11 | [Risk and Decision Register](11_RISK_AND_DECISION_REGISTER.md) | D-001..D-012, RSK-001..RSK-016, U-001..U-010, blockers and owners |
| 12 | [Operations and Lifecycle](12_OPERATIONS_AND_LIFECYCLE.md) | DB-wide recovery, NAS/private ingress, health, monitoring, upgrade/rollback and nondelegable gates |
| 13 | [Dependencies and BOM](13_DEPENDENCIES_AND_BOM.md) | hardware ownership vs conditional purchase, pinned upstream identities, licensing, budget assumptions |
| ADR | [Supersession Candidate](ADR-0002_CANDIDATE.md) | explicit nonaccepted replacement for original WeeWX ADR-0001, requires plan/operator approval |

## Checkpoint publication history
These SHAs are **GitHub planning-branch writes with readback for CP-1** and source content verification for later checkpoints; this index is not a CI/independent-review receipt.
| Checkpoint | GitHub commit(s) | Meaning |
|---|---|---|
| CP-1 | `12529dc602ed663493559694b99034cd7bf03cf0`, Markdown formatting correction `704f08bfd04b20f3e6eb93ba961f1171ee019580` | as-found repository/upstream facts; runtime unidentified |
| CP-2 | `cbd11b998654d3767470ca835c33620d30fe3542` | architecture options and decision/risk proposal |
| CP-3 | `86a1b584f2148a82559210bf1c7e20e6fb3a85a4` | schema governance and multi-location provenance domain |
| CP-4 | `0d9b4830080cb559adc1755f4edf32b37d982f83`, `f623f846985fcc90a51b27b0ba55d876bbe5bac2` | target architecture, ingest/provider adapters, UX, repo change plan |
| CP-5 (partial-to-final) | `432a673dcf89876058e4b7e4b897292889149c2c`, `ae037f31f94d821ea58511a4df2b0c1dc61e10b5`, `552c9b399014a768bf698b6ccb37dc0fb9270f68`, `60082211fc7aa54dd4647e5d5f80bfd548d5b625` | acceptance/WPs, operations, BOM, executive summary; final package identity belongs to PR HEAD, not self-referential here |

## Source authority and significant external references
1. Runtime authenticated evidence when actually available; then current GitHub/repository truth and repository `AGENTS.md`, migration and ADR decisions.
2. Historical Lakehouse scaffold + my-pa as-found source at pinned commits; no claims that repository definitions imply physical execution.
3. Third-party official technical sources: [rtl_433 decoder](https://github.com/merbanan/rtl_433/blob/406f9a33550a2b6b3d0d8a8a486417ce5b3f13ab/src/devices/fineoffset.c), [WeeWX database docs](https://weewx.com/docs/latest/reference/weewx-options/databases/), [Nooelec v5](https://www.nooelec.com/store/nesdr-smart.html), [NWS API](https://www.weather.gov/documentation/services-web-api), [Open-Meteo terms](https://open-meteo.com/en/terms), [Apple PWA web push](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers).
4. [Root Software Delivery Control Center source](https://drive.google.com/drive/folders/17fLunEr0ZGC_zsYCJn3x9v2I6gYuxKHZ) supports project-level governance but cannot override current repository or runtime truth.

## No-go and open approval boundary
This branch is **planning documentation only**. Approval by an independent planning reviewer is outstanding. my-pa migrations/role grants, live production DB, real sensor identifiers/geolocation, external provider secret enrollment, NAS runtime deployment, Cloudflare/Tailscale provisioning, purge/cleanup and merge **are not authorized** by these files. No passed physical RF, backup, production access, CI test or independent implementation review is asserted. Start actual implementation only after the explicit scope/repository/identity/gate decision described in [10](10_IMPLEMENTATION_WORK_PACKAGES.md).
