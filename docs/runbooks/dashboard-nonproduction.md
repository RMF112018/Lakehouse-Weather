# Nonproduction dashboard and commissioning boundary

## Local demonstration

Run from the repository root with Python 3.11 or newer. No packages, database, network provider or hardware are required for demo mode:

```sh
python3 -m weather serve --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. Demo locations, stations, forecasts and observations are synthetic. The registry does not identify real homes or sensors. The default process does not connect to PostgreSQL or fetch a live forecast. Stop it with Ctrl-C; this does not remove retained data because demo state is memory-only.

The optional `compose.dashboard.yaml` is an inert nonproduction container candidate with a loopback port, non-root process, read-only filesystem, no host devices and no database service. Building it downloads a base image and is a separately authorized dependency operation. The image includes the exact tested psycopg 3.3.6 dependency. `compose.dashboard-postgres.example.yaml` is an inert opt-in overlay requiring an explicit isolated database URL, ingest token and read-only registry mount; it grants no live network or database authority. The original `compose.yaml`, RF scripts and WeeWX configuration are legacy reference and hardware-evaluation paths; they do not launch the new PostgreSQL dashboard.

## Database owner handoff

1. Review the proposed `migrations/` DDL and the observation/forecast contracts with the my-pa owner. Incorporate the accepted schema change into my-pa's canonical Alembic chain. Never run the proposal against an unverified endpoint.
2. In a verified disposable local PostgreSQL target only, validate migration-from-empty, duplicate rejection, out-of-order observations, station isolation and persistent restart behavior. Synthetic tests are a prerequisite, not evidence of NAS database compatibility.
3. Owner provisions an independent weather runtime login with `CONNECT` on logical `my_pa`, `USAGE` on `weather`, and only the explicit weather relations' required read/write privileges. No superuser, schema ownership, role membership, my-pa application-table access or schema-creation authority. The owner migration identity remains separate. Do not reuse `MY_PA_DATABASE_URL` or the historical my-pa owner login.
4. Owner approves backups, restore rehearsal, capacity and retention. Observation retention has no implicit deletion policy. Include the new schema in the existing PostgreSQL backup ownership model.
5. Supply a dedicated server-only connection URL through the operator's approved secret mechanism. Do not put URLs/tokens into browser code, compose source, CLI arguments, tickets or reports. The application must explicitly opt into nonproduction PostgreSQL use; this is not production admission.

No database migration, owner provisioning, shared-database read, or grant is performed by this repository's normal application startup.

## First real station: Ambient WS-2000 / WH65B

The operator confirms the console failed. Use the existing outdoor array through an RTL-SDR; console custom upload is not part of this slice.

Use the retained RF runbook to prove Synology USB enumeration and reliable rtl_433 decoding. Bind an observed model plus sensor ID in the registry; the fixture's `111` is synthetic, not a discovered device. Set decoder time explicitly to UTC ISO output. Validate temperature, wind, pressure, rain counter/reset behavior, units, clock and packet cadence against physical readings. Never map all devices heard over RF.

The receiver posts normalized JSON to the private ingest endpoint using the configured server-only ingest token. Keep receiver ingress private on a separately reviewed local network; never add it to the public dashboard route allowlist. Do not send an ingest token over an untrusted plaintext network. A proper receiver service, SDR USB identity, restart/backpressure policy and reconnect commissioning remain hardware work.

## Forecast commissioning

Forecast refresh is explicit, server-side and bounded. Open-Meteo receives the configured geographic coordinates. Before enabling real locations, approve that disclosure, confirm the current terms cover the intended use, and size a refresh cadence within provider limits. Do not confuse forecasts with observed station measurements. Show provider attribution and freshness; retain the last forecast on provider failure and show unavailable/stale state.

## Synology and Cloudflare proposal

The requested host is the existing Synology NAS accessible as `ssh bf-nas`. The manager performed only a bounded platform check: Linux x86_64 with Python available. This is not database, Docker, USB, network or deployment readiness evidence.

The operator confirmed the exact public route: `https://www.bobby-fetting.me/weather/`. Redirect bare `/weather` to `/weather/`, then strip `/weather` before forwarding dashboard requests to the private weather origin. Relative assets/API paths support that proxy contract. The route has not been configured or activated. Do not create DNS, reuse tunnel credentials or change routing without separate authorization.

Reuse the existing tunnel only after the owning deployment procedure approves an exact new dashboard route and origin network. Do not add a parallel cloudflared service or attach weather directly to my-pa's database plane without reviewed network ownership. Do not expose ingest, database, SDR or my-pa internal routes. Choose and verify browser access protection explicitly; my-pa passkeys and Cloudflare Access are not inherited automatically.

Before activation: pinned image/dependency identity, production-grade HTTP serving and request limits, approved browser access policy, dedicated database role and owner migration, NAS storage/backup/restore, isolated network path, real RF health, TLS origin, iPhone HTTPS checks and rollback must all be proven. This implementation is a functional nonproduction slice, not an approved live package.
