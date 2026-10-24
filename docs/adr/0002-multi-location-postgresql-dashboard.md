# ADR-0002: Multi-location dashboard with the my-pa-owned PostgreSQL store

- Status: Accepted for nonproduction implementation by the 2026-10-23 operator objective; database admission and production activation remain unapproved.
- Supersedes: ADR-0001's SQLite archive, WeeWX presentation, and RF-before-all-application-work requirements. RF reception gates still apply to real sensor commissioning.
- Repository baseline: `aea6bada042b34a8365c9e70e3a6a0f90304f3f0`.
- Database-owner reference: `RMF112018/my-pa` at `3d1593aa4dc2477395b47c97067338f8c46eff0b`.

## Problem and decision

The accepted earlier plan replaces a failed WS-2000 console using an RTL-SDR, rtl_433, WeeWX, SQLite and New Belchertown. It has no proven RF deployment and contains scaffolding rather than a running archive. The new operator objective requires multiple stations at multiple locations and the existing my-pa PostgreSQL database. The operator confirms the console remains failed and selects the outdoor array via RTL-SDR.

Use one small Python HTTP application for observation ingestion, PostgreSQL queries, forecast retrieval and a same-origin static dashboard. Use no-build HTML/CSS/JavaScript for the iPhone interface. A deterministic in-memory demo proves the interface and domain behavior without contacting the shared database. It is explicitly synthetic and loses ingested data on restart. It is never a fallback when configured PostgreSQL fails.

Production persistence is a dedicated `weather` schema in the existing logical `my_pa` database, accessed through a dedicated least-privilege weather runtime role. The application neither provisions roles nor creates or migrates schemas at startup. Proposed DDL in this repository is design input to the my-pa owner's canonical Alembic change, not an independent migration authority. No second database, SQLite archive, queue, MQTT broker or new tunnel is needed for this slice.

Use rtl_433 JSON as the first implemented station adapter. Registry entries bind explicit decoder model and sensor ID to an internal station and location. Never discover or attach neighboring sensors automatically. The existing WH65B fixture supplies the synthetic mapping contract; hardware commissioning must still verify the actual array, frequency, sensor identity and timestamp behavior. Preserve the rain counter as a counter, with reset-aware interval derivation, rather than displaying it as today's rainfall.

Forecasts come from server-side Open-Meteo requests using registered coordinates. Requests are bounded, explicit and cached in the application store; unavailable or stale forecasts are visible. Coordinates leave the NAS when forecast refresh is enabled. Operator acceptance of that disclosure and provider terms is needed before real-location activation.

## Alternatives examined

| Option | Benefit | Reason not selected for this slice |
| --- | --- | --- |
| Original WeeWX + New Belchertown | Mature weather calculations and generated reports | Official WeeWX database support lists SQLite/MySQL. A PostgreSQL archive driver and multi-station presentation integration add maintenance and conflict with the required shared PostgreSQL boundary. |
| WeeWX plus a second export pipeline | Retains reporting ecosystem | Duplicates archive authority and processes before a demonstrated need. |
| Full React/Next.js application | Rich ecosystem and alignment with my-pa frontend tools | Weather does not yet share my-pa browser sessions. A second build/runtime dependency graph is unnecessary for this bounded interface. |
| rtl_433 directly into the application | Mature RF decoder, existing repository configuration | Selected. Real USB/RF commissioning remains hardware-dependent. |
| WS-2000 custom upload | Could avoid SDR when console works | Deferred pending working-console confirmation and exact protocol. Ambient's manual describes Wunderground or AmbientWeather.net custom protocols; native Ecowitt support must not be assumed. |

## Trade-offs and limits

This implementation owns a small amount of weather normalization, time handling and chart code. It does not claim WeeWX's mature climatology, calibration, rain-rate or daily-record coverage. Those features should be added only with explicit semantics and tests. Observation retention is indefinite by default; there is no automatic delete job. Capacity estimates and an owner-approved retention/backup policy precede long-term commissioning.

The dashboard is a separate application sharing database infrastructure, not my-pa application tables or identity. Local nonproduction access is loopback-only by default. Public routing, browser authentication/authorization, TLS, private receiver transport, owner migration, NAS networks and least-privilege grants require their own admission. A tunnel alone is not authentication. No my-pa ingress, passkey behavior, firewall, credentials or deployment manifest is changed here.

## Primary sources

- [WeeWX supported database types](https://weewx.com/docs/5.2/reference/weewx-options/database-types/)
- [rtl_433 Fine Offset decoder](https://github.com/merbanan/rtl_433/blob/master/src/devices/fineoffset.c)
- [Ambient WS-2000 manual](https://ambientweather.com/mwdownloads/download/link/id/1113)
- [Open-Meteo forecast API](https://open-meteo.com/en/docs) and [service terms](https://open-meteo.com/en/terms)

Upstream code was not copied or vendored into this application. Existing upstream pins and GPL-3.0-only project licensing remain intact.
