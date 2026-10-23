# 11 — Risks, decisions, findings, open dependencies
**Package:** LHW-ML-20261023 | **Checkpoint CP-2** | **Status:** PROPOSED. This register never substitutes for operator approval, my-pa governance, RF evidence or runtime verification.

## Decision register
| ID | Decision | Rationale/status | Work packages | Acceptance |
|---|---|---|---|---|
| D-001 | Lakehouse weather app, my-pa PostgreSQL canonical | PROPOSED; my-pa schema authority is a hard gate | WP-002, WP-004, WP-005 | AT-011, AT-012, AT-015 |
| D-002 | Use pinned rtl_433 only; no WeeWX/MQTT at runtime | PROPOSED; avoids unsupported PG backend and duplicate archive | WP-002, WP-003, WP-006 | AT-001, AT-006 |
| D-003 | Separate RF receiver sidecar from API/ingester | PROPOSED; USB credential/DB privilege isolation | WP-006, WP-010 | AT-009, AT-022 |
| D-004 | Separate observation, modeled and forecast semantics | PROPOSED; prevents false source claims | WP-005, WP-007, WP-009 | AT-013, AT-017 |
| D-005 | NWS + conditional Open-Meteo, no broad provider framework | PROPOSED; smallest coverage set with known published APIs | WP-007 | AT-016, AT-018 |
| D-006 | Private Tailscale access first, authenticated public optional | PROPOSED; narrow attack surface | WP-010 | AT-020, AT-022 |
| D-007 | Rainfall algorithm preserves raw counters and incomplete periods | PROPOSED; no invented deltas on reset or gap | WP-005, WP-006, WP-008 | AT-008, AT-014 |
| D-008 | my-pa Alembic-only weather schema DDL; dedicated restricted roles | PROPOSED; migration ownership; no direct app DDL | WP-004 | AT-011, AT-012 |
| D-009 | Non-destructive retention policy with budget before purge | PROPOSED; may initially accumulate data; deletion operator gated | WP-008, WP-012 | AT-019, AT-023 |
| D-010 | Mobile static PWA with single API, not WeeWX skin | PROPOSED; multi-location source-aware UX | WP-009 | AT-017, AT-020 |
| D-011 | Original ADR-0001 remains historical until approved supersession | PROPOSED; no silent governance rewriting | WP-002 | AT-024 |
| D-012 | First **implementation** package must be WP-003 RF capability proof if hardware present; otherwise WP-004 disposable DB compatibility contract | PROPOSED conditional sequencing; zero live changes | WP-003, WP-004 | AT-001, AT-011 |

## Risk register
| ID | Priority | Risk / evidence class | Mitigation / pass condition | Owner / state |
|---|---|---|---|---|
| RSK-001 | CRITICAL | Shared my-pa DB schema/role changes can damage existing application; VERIFIABLE only in scratch | my-pa-authored Alembic revision, exact tested head, DDL and grants review, disposable full upgrade/backup restoration, separate operator DB approval | DB owner; OPEN |
| RSK-002 | HIGH | DS923+ DSM USB device access unknown; UNRESOLVED | Gate-1 host enumerate/container claims/5-minute capture, 24h soak, restart; alternate Linux USB host if NAS unsupported | Operator/local agent; OPEN |
| RSK-003 | HIGH | RF ID changes on WH65B battery replacement and optional WH32B may be absent; VERIFIED upstream / runtime UNRESOLVED | explicit device identity epochs; capture registration and historical continuity | Local agent; OPEN |
| RSK-004 | HIGH | rain_mm cumulative reset/rollover, bad timestamp or duplicates corrupt totals; DERIVED | synthetic replay, threshold, reset state, stale/partial marking; parity samples | Weather engineer; OPEN |
| RSK-005 | HIGH | API/provider modeled values mislabeled as observations; DERIVED | typed records, source badges, test golden fixtures, explicit site location | Weather engineer; OPEN |
| RSK-006 | HIGH | Provider licensing/attribution or commercial use restrictions; VERIFIED terms, use classification UNRESOLVED | approved provider profile with license and usage purpose, explicit UI attribution, cap/admission tests | Operator; OPEN |
| RSK-007 | HIGH | my-pa DB connection exhaustion/WAL/storage pressure; runtime UNRESOLVED | pool<=2 for weather app initially, batch sizes<=100, write timeout, backoff, budget measurements and hard fail-closed admission | DB owner; OPEN |
| RSK-008 | HIGH | Public web or internal RF endpoint exposed inadvertently; UNRESOLVED | tailnet-only proxy, route allowlist, separate ingress secret, port scans and auth negatives | Security reviewer; OPEN |
| RSK-009 | MEDIUM | Unpinned Docker tags or upstream changes cause parser drift/supply-chain failures; VERIFIED | digest pins, versioned sample output regression, SBOM and upgrade test | Maintainer; OPEN |
| RSK-010 | MEDIUM | Data loss during DB/provider outage or NAS restart; DERIVED | replay-safe bounded spool, retry with Retry-After, cut-over watermarks, soak & failure injection | Maintainer; OPEN |
| RSK-011 | MEDIUM | Backup includes my-pa but weather data restore may be incomplete/slow; runtime UNRESOLVED | full consistent DB restore to scratch and weather-only logical extract rehearsal, RPO/RTO defined | DB owner; OPEN |
| RSK-012 | MEDIUM | Static PWA cached values displayed as live; DERIVED | explicit capture/ingestion freshness, last sync, stale banners, offline labels | UI engineer; OPEN |
| RSK-013 | MEDIUM | High-frequency RF records consume excess shared DB resources; DERIVED | benchmark measured 16s packet workload, storage budgets, partitioning only if justified | DB owner; OPEN |
| RSK-014 | MEDIUM | Existing ADR-0001 accepted and proposed new design conflicts; VERIFIED | prospective replacement ADR explicit status and approved review, leave original intact | Operator; OPEN |
| RSK-015 | MEDIUM | Other-location NWS station may be geographically distant; VERIFIED API semantics | separate station point, source-location assignment and distance; no false locality claim | Weather engineer; OPEN |
| RSK-016 | LOW | A pressure metric is assumed from WH65B without physical evidence; VERIFIED upstream field distinction | null on no sensor; record WH32B as separate device if observed | Local agent; OPEN |

## Blocking decisions / unknowns
| ID | Exact question | Gate |
|---|---|---|
| U-001 | Which physical my-pa DB instance, role, PostgreSQL server version and actually applied `alembic_version` will be target? | GATE-DB before any SQL |
| U-002 | Will my-pa maintain the new `weather` schema and grant new restricted LOGIN roles under existing Alembic/role management? | GATE-DB and separate migration operator authorization |
| U-003 | What remaining max_connections, disk, WAL, backup retention, RPO/RTO and concurrent workloads are available? | GATE-PERF |
| U-004 | DS923+ DSM version, USB passthrough policy, SDR kit arrival, WH65B & WH32B installed IDs/fields? | GATE-RF |
| U-005 | Exact chosen additional locations, IANA zones, privacy classes, source preferences? | GATE-CONFIG; no fabricated addresses/coordinates |
| U-006 | Can Open-Meteo free non-commercial terms cover this exact personal deployment and chosen historical retention? | GATE-PROVIDER |
| U-007 | Which tailnet/HTTPS endpoint, ACL and browser-auth assumptions are actually available? | GATE-SECURITY |
| U-008 | Are weather-specific retention/deletion policies approved? | GATE-RETENTION; no default destructive purge |
| U-009 | What numeric freshness thresholds and aggregate accuracy/error budgets should operator accept? | GATE-ACCEPTANCE; defaults in plan are proposed |
| U-010 | Does current pinned decoder parse real outdoor & indoor packets with stable measurement names? | GATE-RF |

### Approval boundaries
This entire register is **design proposal**. User's request authorizes planning files and a review PR only. It does **not** approve migration implementation, DB role provisioning, access to personal coordinates, connection to live my-pa, NAS deployment, credential/tunnel changes, retention purges, or architectural risk acceptance. Any approved corrective changes affecting my-pa must be separately scoped in **that repository** and independently reviewed against exact identity.

## Finding -> decision -> work -> acceptance crosswalk
Every repository/upstream finding F-001..F-015 originated in [01](01_SOURCE_AND_SYSTEM_AUDIT.md). This provides a stable **PROPOSED mitigation trace**, not independent validation that a fix exists.
| Finding | Decision/constraint | WP | Test/gate |
|---|---|---|---|
| F-001 | D-001, D-002, D-011 | WP-002, WP-004, WP-005 | AT-011, AT-024 |
| F-002 | D-002, D-011 | WP-002 | AT-024 |
| F-003 | D-003 | WP-011 | AT-026, AT-027 |
| F-004 | D-002 | WP-002, WP-003 | AT-001, AT-024 |
| F-005 | D-002, D-006 | WP-010 | AT-022 |
| F-006 | D-002, D-012 | WP-003 | AT-001, AT-002, AT-003 |
| F-007 | D-001, D-008 | WP-004 | AT-011, AT-012 |
| F-008 | D-008 | WP-001, WP-004 | AT-011, AT-015 |
| F-009 | D-002, D-007 | WP-003, WP-006 | AT-002, AT-004, AT-006 |
| F-010 | D-004, D-010 | WP-005, WP-007, WP-009 | AT-013, AT-017 |
| F-011 | D-009 | WP-004, WP-012 | AT-019 |
| F-012 | D-006 | WP-003, WP-010 | AT-001, AT-022 |
| F-013 | D-004 | WP-005, WP-009 | AT-007, AT-021 |
| F-014 | D-005 | WP-007 | AT-016 |
| F-015 | D-006 | WP-010 | AT-022 |

**Traceability audit:** D-001..D-012 have WP and AT targets in the decision table; WP-001..WP-012 have exact prerequisites and acceptance in [10](10_IMPLEMENTATION_WORK_PACKAGES.md); AT-001..AT-027 have methods and pass/fail in [09](09_VALIDATION_AND_ACCEPTANCE.md). Acceptance does not imply an approved authorization or executed test.
