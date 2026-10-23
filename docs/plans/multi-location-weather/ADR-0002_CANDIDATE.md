# ADR-0002 Candidate — Source-aware multi-location Lakehouse Weather using existing my-pa PostgreSQL
- **Status:** PROPOSED_FOR_INDEPENDENT_REVIEW — NOT ACCEPTED
- **Proposal ID:** LHW-ML-20261023-D-001
- **Date:** 2026-10-23
- **Controlling repository:** RMF112018/Lakehouse-Weather
- **Current accepted record to supersede only after approval:** `docs/adr/0001-use-weewx-ecosystem.md` (2026-09-09)
- **No software, database, runtime, role or external account implementation authority is granted by this candidate.**

## Context
Original Lakehouse Weather is an RF-first **single local station** scaffold using `rtl_433 -> weewx-sdr -> WeeWX 5 -> SQLite -> New Belchertown`. New requirements require an iPhone-first multi-location dashboard with **source-traceable measured observations and separate model forecasts**, and the **existing my-pa PostgreSQL database as the single canonical persistent store**. Official WeeWX database docs name SQLite and MySQL, no proven stock PostgreSQL adapter. my-pa migration policy requires its own Alembic authority for every schema change. Live hardware/DB identity remains UNKNOWN.

## Decision recommended for independent approval
Adopt Option C: use pinned `rtl_433` decoder in a restricted receiver container on NAS for local WS-2000/WH65B and optional WH32B; send versioned events over authenticated replay-safe internal HTTP to **one** bounded Python weather-app process. That process polls separately authorized NWS and optional Open-Meteo adapters for many other locations, stores weather-source/site/device-provenance-aware observations and distinctly typed model/forecast values in a proposed **`weather` schema in the already existing my-pa PostgreSQL physical database**, and serves a React/TypeScript/Vite read-only PWA via private HTTPS/Tailscale. No WeeWX SQLite archive, additional postgres instance, broker, Redis, Timescale or unsupported radio reception of remote stations.

**Database owner decision:** my-pa repository owns all DDL, Alembic revisions, grants/roles, backup policy and operational approval. Lakehouse owns weather domain logic and API but cannot migrate/write outside restricted approved weather grants. The schema is proposed, not already approved. Keep prior accepted ADR-0001 unchanged until independent review accepts its explicit supersession.

## Alternatives rejected conditionally
- A: WeeWX wired directly to PostgreSQL—unsupported stock backend plus station-centric multi-location schema.
- B: WeeWX local collector plus separate app—double archives/forwarding with operational ambiguity.
- D: hybrid reporting+DB—more processes and duplicate source truth absent measured benefit.
- E: put weather app inside my-pa runtime—excessive coupling and expansion of my-pa product/security blast radius.
Reopen any option upon substantive evidence, not simply least initial coding effort. See [02](02_ARCHITECTURE_OPTIONS.md) for criteria, [11](11_RISK_AND_DECISION_REGISTER.md) for risk.

## Consequences and gates
**Benefits:** minimal source-aware core, one canonical DB and backup, exact history/provenance, clear iPhone source labels, independent provider adapters. **Costs:** custom normalization/rain domain/UI logic, my-pa cross-repo migration governance, two weather images, RF compatibility and restricted UI ingress gates, pinned dependency maintenance.

**Approval criteria:** independent reviewer binds to exact planning HEAD, verifies all constraints and material blockers; my-pa DB owner/operator separately accepts design and implementation scope; real RF must pass GATE-RF; tested isolated migration and least-privilege grants pass GATE-DB; provider terms, backups, security and iPhone gates pass before any production request. Review PR may record `PLAN_APPROVED` only after a reviewer/operator issues that decision. This candidate must not be treated as active architecture in repository README/ROADMAP until approval.
