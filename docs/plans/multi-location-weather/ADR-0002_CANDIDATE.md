# ADR-0002 Candidate — Source-aware multi-location Lakehouse Weather using existing my-pa PostgreSQL
- **Status:** CR-2_CORRECTED_PROPOSAL_FOR_FRESH_INDEPENDENT_NEW_HEAD_REVIEW — NOT ACCEPTED
- **Proposal ID:** LHW-ML-20261023-D-001
- **Date:** 2026-10-23
- **Controlling repository:** RMF112018/Lakehouse-Weather
- **Current accepted record to supersede only after approval:** `docs/adr/0001-use-weewx-ecosystem.md` (2026-09-09)
- **No software, database, runtime, role or external account implementation authority is granted by this candidate.**

## Context
Original Lakehouse Weather is an RF-first **single local station** scaffold using `rtl_433 -> weewx-sdr -> WeeWX 5 -> SQLite -> New Belchertown`. New requirements require an iPhone-first multi-location dashboard with **source-traceable measured observations and separate model forecasts**, and the **existing my-pa PostgreSQL database as the single canonical persistent store**. Official WeeWX database docs name SQLite and MySQL, no proven stock PostgreSQL adapter. my-pa migration policy requires its own Alembic authority for every schema change. Live hardware/DB identity remains UNKNOWN.

## Decision recommended for independent approval
Adopt Option C: use pinned `rtl_433` decoder in a restricted receiver container on NAS for local WS-2000/WH65B and optional WH32B; send versioned events over authenticated replay-safe internal HTTP to **one** bounded Python weather-app process. That process polls separately authorized NWS and optional Open-Meteo adapters for many other locations, stores weather-source/site/device-provenance-aware observations and distinctly typed model/forecast values in a proposed **`weather` schema in the already existing my-pa PostgreSQL physical database**, and serves a React/TypeScript/Vite read-only PWA via private HTTPS/Tailscale. No WeeWX SQLite archive, additional postgres instance, broker, Redis, Timescale or unsupported radio reception of remote stations.

**Database owner decision:** my-pa repository owns all DDL, Alembic revisions, grants/roles, backup policy and operational approval; this includes composite FK/time-epoch guards and a distinct operator-only weather metadata CLI role with append-only transition audit, never shared weather-app DDL. Lakehouse owns weather domain logic and API but cannot migrate/write outside restricted approved weather grants. The schema is proposed, not already approved. Keep prior accepted ADR-0001 unchanged until independent review accepts its explicit supersession.

## Alternatives rejected conditionally
- A: WeeWX wired directly to PostgreSQL—unsupported stock backend plus station-centric multi-location schema.
- B: WeeWX local collector plus separate app—double archives/forwarding with operational ambiguity.
- D: hybrid reporting+DB—more processes and duplicate source truth absent measured benefit.
- E: put weather app inside my-pa runtime—excessive coupling and expansion of my-pa product/security blast radius.
Reopen any option upon substantive evidence, not simply least initial coding effort. See [02](02_ARCHITECTURE_OPTIONS.md) for criteria, [11](11_RISK_AND_DECISION_REGISTER.md) for risk.

## Consequences and gates
**Benefits:** minimal source-aware core, one canonical DB and backup, exact history/provenance, clear iPhone source labels, independent provider adapters. **Costs:** custom normalization/rain domain/UI logic, my-pa cross-repo migration governance, two weather images, RF compatibility and restricted UI ingress gates, pinned dependency maintenance.

**Approval criteria:** independent reviewer binds to exact planning HEAD, verifies all constraints and material blockers; my-pa DB owner/operator separately accepts design and implementation scope; real RF must pass GATE-RF; tested isolated migration and least-privilege grants pass GATE-DB; provider terms, backups, security and iPhone gates pass before any production request. Review PR may record `PLAN_APPROVED` only after a reviewer/operator issues that decision. This candidate must not be treated as active architecture in repository README/ROADMAP until approval.

## Corrective decision CR-1 — Required prior independent findings

The independent review `LHW-INDEPENDENT-PLAN-REVIEW-20261023-001` returned `PLAN_REVISION_REQUIRED` at prior HEAD `78a33161e38dce7adb2476e74488f18ccd6ad01f`/tree `782327104e71ef144410285eafc534e75c3470b6`. This ADR is still **PROPOSED, not accepted**. Corrected Option C requires: (1) no WH65B decoder-pressure assumption—conditional outdoor pressure is separate `MODEL_WS69`, and WH32B requires capture proof; (2) referenced immutable raw-event identity/digest surviving separately governed payload expiry; (3) `provider_stream_id`/independent cursors per coordinate product and shared station feed only when truly identical; (4) operator-only metadata administration via a restricted audited role, not normal app grants; (5) composite FKs and concurrency-safe assignment/epoch/revision guards; (6) `rf-batch.v1` fsynced spool, fresh HMAC nonce per attempt and digest-bound per-item 200/207 ACK; (7) on-read DERIVED rainfall from paired physically measured counters, not measured observation storage. Open-Meteo uses snapshot identity UNKNOWN if no proven single run, quota effective units and operator terms gate. Sensitive PWA response caching defaults off and is not remotely erased by ACL revocation. Provisional delivery estimate becomes 73–132 person-days, not a commitment.

The binding proposed details are [03](03_TARGET_ARCHITECTURE.md), [04 §7](04_POSTGRESQL_INTEGRATION.md), [05 §11](05_WEATHER_DATA_MODEL.md), [06](06_INGESTION_AND_SOURCE_INTEGRATIONS.md), [09](09_VALIDATION_AND_ACCEPTANCE.md), [10](10_IMPLEMENTATION_WORK_PACKAGES.md) and [11](11_RISK_AND_DECISION_REGISTER.md). Acceptance requires a **fresh reviewer who did not author this corrective revision** at the new HEAD/tree. No application code, my-pa SQL, NAS/SDR, credentials, provider activation, merge, data deletion or production action is authorized by this candidate.


## CR-2 — Additional contract precision, not an accepted amendment

The next independent report `LHW-CR1-INDEPENDENT-REREVIEW-20261023-001` found `PLAN_REVISION_REQUIRED` at the then-current CR-1 HEAD `e048d5de85afc8d275ea258a3db8aeb45b67f360` / tree `76b7ca604ab1f3e325b7853f4be14c2fb97b533f`. This CR-2 proposal keeps **Option C** but requires the following before any new plan approval:

1. One `rf-batch.v1` policy: 200 only all commit/identical duplicate; 207 for every fully processed batch with terminal/conflict/retryable including homogeneous all-negative; pre-admission-only whole batch errors; durable terminal receipt.
2. DB-enforced observation ↔ raw-event **same physical device** identity even when two sensor devices share station/source; provider null-device cases require explicit DB guard. Model runs require non-cascading event/source/stream-checked raw metadata FK surviving any separately authorized payload-only expiry.
3. Immutable upstream provider product identity across moving absolute forecast windows; separate immutable full raw-response SHA-256 and versioned semantic model SHA-256. Stitched Best Match has `run_identity_status=UNKNOWN` and nullable true `issued_at` unless verified.
4. HMAC replay nonce commits before member processing, rejects duplicate/restart replay, and has a bounded operator-only operational expiry distinct from unapproved weather retention. No weather runtime DELETE privilege.
5. Offline cold-start weather is unavailable under static-only PWA caching; an already-open page can show its in-memory last reading with OFFLINE/as-of stamp. Tests retain two measured observation IDs for derived rain.

These are design contracts for separately authorized future my-pa and Lakehouse implementation, **not** SQL, permission, runtime or production approval. Accepted `docs/adr/0001-use-weewx-ecosystem.md` is untouched until an authorized supersession decision, and this candidate is not self-approved.
