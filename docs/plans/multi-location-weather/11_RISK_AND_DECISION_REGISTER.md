# 11 — Risks, decisions, findings, open dependencies
**Package:** LHW-ML-20261023 | **Checkpoint CP-2 / CR-2** | **Status:** CR-3 NF-001/NF-002 BOUNDED DOCUMENTARY CORRECTION CANDIDATE / FRESH INDEPENDENT EXACT-HEAD REVIEW REQUIRED. Original review at `78a33161e38dce7adb2476e74488f18ccd6ad01f`; CR-1 rereview `LHW-CR1-INDEPENDENT-REREVIEW-20261023-001` found `PLAN_REVISION_REQUIRED` at `e048d5de85afc8d275ea258a3db8aeb45b67f360` / `76b7ca604ab1f3e325b7853f4be14c2fb97b533f`. This register neither self-approves CR-2 nor creates operator/my-pa/live authority.

## Decision register
| ID | Decision | Rationale/status | Work packages | Acceptance |
|---|---|---|---|---|
| D-001 | Lakehouse weather app, my-pa PostgreSQL canonical | PROPOSED; my-pa schema authority is a hard gate | WP-002, WP-004, WP-005 | AT-011, AT-012, AT-015 |
| D-002 | Use pinned rtl_433 only; no WeeWX/MQTT at runtime | PROPOSED; avoids unsupported PG backend and duplicate archive | WP-002, WP-003, WP-006 | AT-001, AT-006 |
| D-003 | Separate RF receiver sidecar from API/ingester | PROPOSED; USB/DB isolation and receiver may unlink ONLY after genuine weather-app `rf-ack-mac.v1` authenticated mTLS 200/207 matching current send attempt | WP-005, WP-006, WP-010 | AT-009, AT-010, AT-022, AT-025 |
| D-004 | Separate observation, modeled and forecast semantics | PROPOSED; model stream/run/value geographic assignment equality enforced in DB by non-null composite FK; shared measured station is a distinct class | WP-004, WP-005, WP-007, WP-009 | AT-011, AT-013, AT-016, AT-021 |
| D-005 | NWS + conditional Open-Meteo, no broad provider framework | PROPOSED; smallest coverage set with known published APIs | WP-007 | AT-016, AT-018 |
| D-006 | Private Tailscale browser access; **separately authenticated RF ingress** | PROPOSED; protected receiver link uses dedicated mTLS TLS 1.3 server SAN+client cert plus independent ACK MAC on same-host and cross-host | WP-006, WP-010 | AT-009, AT-020, AT-022, AT-025 |
| D-007 | Physical rain counter plus on-read DERIVED interval/rate with source-pair lineage | PROPOSED; no invented deltas on reset or gap | WP-005, WP-006, WP-008 | AT-008, AT-014 |
| D-008 | my-pa Alembic-only weather schema DDL; dedicated restricted roles | PROPOSED; DB-owned `FORECAST_MODEL` nonnull stream/assignment/class composite FKs plus measured station exception; separate migration permission | WP-004 | AT-011, AT-012, AT-013 |
| D-009 | Long-lived event metadata and separately expiring raw payload with operator-gated retention | PROPOSED; may initially accumulate data; deletion operator gated | WP-008, WP-012 | AT-019, AT-023 |
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
| RSK-005 | HIGH | API/provider modeled values may be wrongly attributed to another same-source destination despite individually valid source FKs; NF-001 confirmed planning gap | `FORECAST_MODEL` stream/run/value assignment equality mandatory nonnull composite FKs, measured-station kind isolation and A/B scratch negative | DB/domain/provider owners; OPEN / CR-3 proposed correction |
| RSK-006 | HIGH | Provider licensing/attribution or commercial use restrictions; VERIFIED terms, use classification UNRESOLVED | approved provider profile with license and usage purpose, explicit UI attribution, cap/admission tests | Operator; OPEN |
| RSK-007 | HIGH | my-pa DB connection exhaustion/WAL/storage pressure; runtime UNRESOLVED | pool<=2 for weather app initially, batch sizes<=100, write timeout, backoff, budget measurements and hard fail-closed admission | DB owner; OPEN |
| RSK-008 | HIGH | Public/internal ingress exposure or forged 200/207 could retire uncommitted receiver journal data; NF-002 confirmed planning gap | nonpublic mTLS receiver listener, validated service SAN/client cert plus distinct-key server ACK MAC and forged-reply negatives | Security owner; OPEN / CR-3 proposed correction |
| RSK-009 | MEDIUM | Unpinned Docker tags or upstream changes cause parser drift/supply-chain failures; VERIFIED | digest pins, versioned sample output regression, SBOM and upgrade test | Maintainer; OPEN |
| RSK-010 | MEDIUM | Data loss during DB/provider outage or NAS restart; DERIVED | replay-safe bounded spool, retry with Retry-After, cut-over watermarks, soak & failure injection | Maintainer; OPEN |
| RSK-011 | MEDIUM | Backup includes my-pa but weather data restore may be incomplete/slow; runtime UNRESOLVED | full consistent DB restore to scratch and weather-only logical extract rehearsal, RPO/RTO defined | DB owner; OPEN |
| RSK-012 | MEDIUM | Static PWA cached values displayed as live; DERIVED | explicit capture/ingestion freshness, last sync, stale banners, offline labels | UI engineer; OPEN |
| RSK-013 | MEDIUM | High-frequency RF records consume excess shared DB resources; DERIVED | benchmark measured 16s packet workload, storage budgets, partitioning only if justified | DB owner; OPEN |
| RSK-014 | MEDIUM | Existing ADR-0001 accepted and proposed new design conflicts; VERIFIED | prospective replacement ADR explicit status and approved review, leave original intact | Operator; OPEN |
| RSK-015 | MEDIUM | Other-location NWS station may be geographically distant; VERIFIED API semantics | separate station point, source-location assignment and distance; no false locality claim | Weather engineer; OPEN |
| RSK-016 | LOW | VERIFIED decoder distinction: `MODEL_WH65` lacks the conditional pressure; `MODEL_WS69` branch differs. Real installed pressure remains unknown | null on no sensor; record WH32B as separate device if observed | Local agent; OPEN |

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

## CR-1 — Original independent findings and correction crosswalk

Source report: `LHW-INDEPENDENT-PLAN-REVIEW-20261023-001`, previous HEAD `78a33161e38dce7adb2476e74488f18ccd6ad01f`. Proposed corrections are **not** independently approved; original F/D/RSK/U/WP/AT/SC IDs are preserved.

| Finding | Plan-level correction | WPs | ATs | Current disposition |
|---|---|---|---|---|
| LHW-RV-001 MAJOR | Pinned/newer WH65B pressure **absent**, WS69/WH32B distinct | WP-003/006 | AT-004/006/017 | CORRECTED_IN_PLAN; hardware unknown |
| LHW-RV-002 MAJOR | Immutable event metadata and separate optional payload, FK RESTRICT; 90d payload/24mo measurements feasible only after future retention approval | WP-004/005/012 | AT-007/019/023 | CORRECTED_IN_PLAN; no purge authorized |
| LHW-RV-003 MAJOR | Per-`stream_id` cursor for each coordinate product; NWS station stream shared only when upstream identical; weighted provider quota | WP-004/005/007 | AT-013/016/018 | CORRECTED_IN_PLAN; provider not active |
| LHW-RV-004 MAJOR | Operator-only NOINHERIT metadata CLI/role, auditable controlled registration/retirement; app has no metadata admin | WP-004/005 | AT-012/021 | CORRECTED_IN_PLAN; roles not provisioned |
| LHW-RV-005 MAJOR | Composite source/event/assignment/run FKs, station/range/epoch guards and correction-chain immutability | WP-004/005 | AT-007/011/013 | CORRECTED_IN_PLAN; scratch tests future |
| LHW-RV-006 MAJOR | `rf-batch.v1` per-item commit/207 outcomes, signed fresh HMAC nonce retry and fsynced journal | WP-005/006/010/011 | AT-009/010/022/025/027 | CORRECTED_IN_PLAN; no receiver implemented |
| LHW-RV-007 MAJOR | Rain increments/rates/day sums computed on read as DERIVED with paired observation IDs, never MEASURED | WP-005/008/009 | AT-008/014/017/026 | CORRECTED_IN_PLAN; computation untested |
| LHW-RV-008 MINOR | Best Match snapshot SHA/revision/UNKNOWN run, effective quota units, license gate | WP-007 | AT-013/016/018 | CORRECTED_IN_PLAN; U-006 open |
| LHW-RV-009 MINOR | Re-estimate **73–132 person-days**, provisional and excludes gate waiting | WP-001..012 | AT-023/024 | CORRECTED_IN_PLAN; estimate unmeasured |
| LHW-RV-010 MINOR | Static-only PWA cache, API no-store; tailnet revocation cannot erase existing local data | WP-009/010 | AT-017/020/022 | CORRECTED_IN_PLAN; device proof future |

Binding details: [03 transport](03_TARGET_ARCHITECTURE.md), [04 PostgreSQL §7](04_POSTGRESQL_INTEGRATION.md), [05 source/weather model](05_WEATHER_DATA_MODEL.md), [06 RF/providers](06_INGESTION_AND_SOURCE_INTEGRATIONS.md), [09 acceptance §7](09_VALIDATION_AND_ACCEPTANCE.md), [10 WPs](10_IMPLEMENTATION_WORK_PACKAGES.md). Each correction is a proposed design, **not** implementation evidence. Original risks RSK-001..RSK-016 and unknowns U-001..U-010 remain open to future gates; fresh independent plan review is required at the new HEAD/tree. No application code, database, NAS, credentials, public ingress, merge, deployment, deletion or risk acceptance is authorized.


## CR-2 — Independent rereview residuals and corrective ownership (NOT SELF-APPROVED)

**Source:** `LHW-CR1-INDEPENDENT-REREVIEW-20261023-001`, disposition `PLAN_REVISION_REQUIRED` against **previous** corrected commit `e048d5de85afc8d275ea258a3db8aeb45b67f360` and tree `76b7ca604ab1f3e325b7853f4be14c2fb97b533f`. The review was adversarial to CR-1 and surfaced new `RR2-001..008`. The following table records **corrective specifications proposed in this CR-2 planning revision**, not an independent closure determination. Preserve all original F/D/RSK/U/WP/AT/SC/I identities.

| Review finding | Severity | CR-2 binding correction | Decision / risk | Future WP and executable AT |
|---|---|---|---|---|
| RR2-001 | MAJOR | One `rf-batch.v1` status law: 200 iff all committed/duplicates; 207 for any complete batch with terminal/conflict/retryable (including homogeneous all-negative); whole-batch 400/413/401/403/429/503 before any member, no blanket 409; durable exact terminal receipt | D-003/008, RSK-008/010 | WP-005/006/010/011 → AT-009/010/022/025/027 |
| RR2-002 | MAJOR | DB-source-kind physical observation same-event same-device FK; null-safe remote guard; same-station WH65B/WH32B negative and deterministic retirement locks | D-001/004/008, RSK-001/003/005 | WP-004/005 → AT-007/011/014; SC-01/04, I-01/02/05/06 |
| RR2-003 | MAJOR | Every model run links by source/stream-checked RESTRICT composite FK to immutable raw provider retrieval event metadata; payload-only expiry preserves model provenance | D-001/004/009, RSK-001/011 | WP-004/005/007/012 → AT-011/013/019, I-04/11/12 |
| RR2-004 | MAJOR | Stream key immutable across rolling absolute poll windows; separate versioned semantic digest from full raw digest; no false Best Match issue timestamp | D-004/005/008, RSK-005/006/010/015 | WP-004/005/007 → AT-013/016/018/027, SC-02/05 |
| RR2-005 | MINOR mandatory | Atomic unique nonce admission before members; ±120s freshness, >=300s persistence; authorized operational-only expiry, not app DELETE/weather purge | D-003/006/008, RSK-001/007/008 | WP-004/006/010/012 → AT-010/011/022/023/025 |
| RR2-006 | MINOR mandatory | Replace old “raw-event 30–90d” claim with optional short-lived payload bytes; metadata lives while referenced | D-009, RSK-011/013 | WP-004/005/012 → AT-019/023 |
| RR2-007 | MINOR mandatory | Fresh offline cold start has no weather data; already-open tab may show OFFLINE in-memory as-of; SC-05 dual independent stream recovery | D-005/006/010, RSK-010/012 | WP-007/009/010 → AT-017/018/020/022 |
| RR2-008 | MINOR mandatory | PR body updated to final commit/tree and 73–132 provisional days only **after** corrected commit; AT-026 uses predecessor/current observation UUIDs | D-007/011, RSK-014 | WP-002/005/009 → AT-024/026 |

**Gate:** A reviewer who did not write or control CR-2 must reauthenticate the *new* Git commit/tree, read all affected cross-layer documents and actual diff, verify numerical registers/relative links and challenge every RR2 item. CR-1 cannot be retroactively approved, and this table cannot approve its author. All original physical RF, my-pa database ownership/roles/migration, Open-Meteo licensing, iPhone/private ingress, backup/restore, deployment, merge, destructive and risk gates remain closed.

## CR-3 — Independent CR-2 report and two blocking design corrections (NOT APPROVED)

**Review identity:** `LHW-CR2-INDEPENDENT-PLAN-REVIEW-20261023-001`, disposition **PLAN_REVISION_REQUIRED**, exact reviewed PR #1 HEAD `d0739f9e4ceba5ee45e8ba8ab8891cb68c994e23` / tree `45d2ead414320e275cb97d31f819f7a944f55e47`. This documentation-only proposal addresses exactly `LHW-CR2-NF-001` and `LHW-CR2-NF-002`. Neither is independently closed until a **different reviewer** authenticates the successor Git HEAD/tree and challenges the full repaired contracts. RR2-004 and original `LHW-RV-003/005/006` remain **PARTIAL_PENDING_REVIEW** due to those specific loopholes; other original and RR2 documentary adjudications remain unchanged and never imply implementation passed.

| Finding | Independent severity | Proposed binding solution | Owning WP / acceptance | Status |
|---|---|---|---|---|
| LHW-CR2-NF-001 | MAJOR | `FORECAST_MODEL` product streams require immutable nonnull assignment and class; `model_runs` and `model_values` must have all nonnull `(stream_id,source_id,assignment_id,stream_class)` keys and matching composite FKs to stream and run. Source/assignment FKs alone are insufficient. `MEASURED_STATION` NULL owner exception applies **only to measured observations**, never modeled rows. Qualify at issue/retrieval and never rebind on future validity. Reject same-source valid A/B cross-assignment rA/sA→B. | my-pa WP-004, Lakehouse WP-005/007; AT-011/013/016/021, SC-02/05, I-01/06/11/12 | CORRECTED_IN_PLAN / INDEPENDENT_REREVIEW_PENDING; no DB work |
| LHW-CR2-NF-002 | MAJOR | Mandatory dedicated **TLS 1.3 mTLS** endpoint, exact pinned/approved CA and server SAN and receiver certificate for co-host and cross-host; **distinct server ACK HMAC** (`rf-ack-mac.v1`) covering original current request ID/nonce/body digest, server and receiver identity, HTTP status and complete reply. Verify both before accepted/terminal journal unlink. Matching echoed IDs without real server authenticity, forged 200/207, stale old receipt, wrong key/cert/clock or plaintext always leave staged bytes intact. | Lakehouse WP-005/006/010 and independent WP-011; AT-009/010/022/025/027, I-04/08/10 | CORRECTED_IN_PLAN / INDEPENDENT_REREVIEW_PENDING; no key/network work |

**Normative documents and objective follow-through:** [04 §8](04_POSTGRESQL_INTEGRATION.md) and [05 §12](05_WEATHER_DATA_MODEL.md) fix geography; [03 §11](03_TARGET_ARCHITECTURE.md), [06 §10](06_INGESTION_AND_SOURCE_INTEGRATIONS.md) and [12](12_OPERATIONS_AND_LIFECYCLE.md) fix receipt trust; [09 §8](09_VALIDATION_AND_ACCEPTANCE.md), [10 §6](10_IMPLEMENTATION_WORK_PACKAGES.md) own future negative tests, effort and blockers. Option C stays proposed; previous accepted ADR-0001 remains operative. Preserve all stable F/D/RSK/U/WP/AT/SC/I identifiers and the provisional 73–132 person-day estimate. Live hardware, database, migrations, credentials, provider activation, iPhone, merge, deployment, production, cleanup, retention and operator risk acceptance remain unauthorized.

**Handoff:** fresh independent **exact corrected-head/tree plan review** required. No reviewer result or test PASS is asserted by the correction author.
