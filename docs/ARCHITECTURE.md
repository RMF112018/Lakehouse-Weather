# Architecture

The 2026-10-23 operator objective admits a multi-location nonproduction application using the existing my-pa PostgreSQL store. [ADR-0002](adr/0002-multi-location-postgresql-dashboard.md) supersedes conflicting SQLite/WeeWX and RF-before-application provisions. Original RF commissioning evidence remains pending.

```text
Approved RF sources -> pinned network-none rtl_433 -> local stdin collector
                                                    | allowlist + fsynced journal
                                                    v committed PostgreSQL insert
                                         |
                                  weather application
                                   /       |       \
                       weather-only PG   HTTP UI   Open-Meteo
                       schema in my_pa    / API    explicit refresh
                                           |
                                    mobile / desktop
```

One process serves the static UI and bounded API. No frontend build process, broker, queue, separate archive database or tunnel service is required. Its simple HTTP server is nonproduction; production serving and origin limits require admission.

Locations own IANA timezones and forecast coordinates. Stations belong to one location, with stable identifiers independent of receiver identity. Observations use UTC time plus station identity for deduplication. An explicit decoder model/sensor-ID pair maps to exactly one station; adjacent RF sensors are not auto-attached. History/current readings are station-specific, and late arrivals never replace newer conditions. Cumulative rain remains distinct from derived intervals.

Synthetic mode has an in-memory store, never claims persistence or measured weather, and is never a fallback when PostgreSQL fails. PostgreSQL mode requires explicit nonproduction opt-in and a dedicated role. Configuration and ingest credentials stay server-side. Browser traffic is same-origin; no browser parameter selects forecast hosts or database endpoints.

Database schema/role provisioning, migrations, backup and restore stay owned by my-pa. SQL here is an inert proposal for the owner's canonical Alembic chain. There is no automatic deletion policy.

Forecasts carry source, retrieval time and availability. Explicit refresh sends registry coordinates to fixed Open-Meteo endpoints, uses bounded requests and preserves old cache on failure. Synthetic forecasts are marked demo. Retention and restart durability require isolated PostgreSQL tests before deployment.

The operator confirms the failed WS-2000 console. RF reception through an RTL-SDR is the first real station path. Synology USB mapping, actual cadence, sensor identity, clock and calibration remain commissioning gates. Console custom upload is not implemented.

The target public path is `https://www.bobby-fetting.me/weather/` through the existing Cloudflare tunnel. Redirect bare `/weather` to `/weather/`, then strip that prefix before forwarding only dashboard routes. Keep machine ingest private. No existing my-pa passkey or Cloudflare Access protection is inherited automatically; choose browser access protection explicitly. No DNS, tunnel, firewall, database or deployment change is performed here.

The operational NAS RF path uses the protected local collector rather than the optional HTTP forwarding command. Exact source profiles gate admission before persistence, and a bounded fsynced journal replays after ambiguous delivery. Exact duplicates commit safely; changed collisions stop capture and retain evidence. A root-owned, hash-bound one-minute scheduler supervises the weather-only launcher with process locks and bounded metadata. See [RF operations](runbooks/rf-operations.md) for commissioning, USB/image bindings, private backups and recovery limits. The receiver image digest identifies the decoder build; it does not authenticate a transmitter.
