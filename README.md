# Lakehouse Weather

A self-hosted, mobile-friendly dashboard for multiple stations across multiple locations. The first real station is the existing Ambient WS-2000 / WH65B outdoor array, received through rtl_433 and an RTL-SDR; the console has failed. Persistent weather storage belongs in the existing my-pa-owned PostgreSQL database.

## Try the nonproduction dashboard

```sh
python3 -m weather serve --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. Python 3.11+ is sufficient. Demo needs no package installation, database, hardware or external API. It includes synthetic locations, multiple stations, current conditions, history, forecasts and visible stale/battery states. Data and forecasts are marked demo; in-memory behavior does not prove PostgreSQL persistence.

The dashboard offers location/station selection, units, observation charts, forecast attribution and freshness. The backend validates configured RF sensor identities, normalizes units/timestamps, deduplicates samples, derives interval rain from cumulative counters and caches forecasts.

## Validation

```sh
python3 -m unittest discover -s tests -v
```

PostgreSQL integration is separately opt-in against a verified disposable target. Missing dependencies/database are not silently counted as persistence validation. See `migrations/` and [the nonproduction runbook](docs/runbooks/dashboard-nonproduction.md) before enabling database mode.

## Architecture and ownership

One Python application serves a same-origin, no-build HTML/CSS/JavaScript interface. A dedicated weather runtime uses only `weather` relations in the existing logical `my_pa` PostgreSQL database. The application never creates a database, applies schema changes or reuses my-pa owner credentials. Open-Meteo refresh is server-side and explicit; demo forecasts are synthetic.

Local default binds loopback. NAS hosting, authentication, owner-managed Alembic migration, a dedicated role, live RF commissioning and existing Cloudflare routing remain controlled operations. The requested public route is `https://www.bobby-fetting.me/weather/`; no route has been activated. Browser assets/API calls are relative to support a reviewed prefix-stripping proxy.

The new objective supersedes the earlier SQLite/WeeWX-only and RF-before-all-application-work plan. [ADR-0002](docs/adr/0002-multi-location-postgresql-dashboard.md) explains alternatives. [Architecture](docs/ARCHITECTURE.md) defines the boundary.

| Path | Purpose |
| --- | --- |
| `weather/` | Application, normalization, stores, forecast integration |
| `web/` | Responsive browser interface |
| `migrations/` | Inert weather DDL proposal for my-pa owner review |
| `config/stations.example.json` | Registry template; coordinates and sensor ID require replacement |
| `compose.dashboard.yaml` | Nonproduction container candidate; demo default, optional explicit PostgreSQL overlay, no database or tunnel |
| `compose.yaml`, `docker/weewx/`, RF runbooks | Preserved hardware/WeeWX scaffold; not the new dashboard launcher |

The container candidate has not been deployed. Its Python base is digest-pinned and PostgreSQL dependency versions are exact; NAS admission still needs image/platform and dependency review. Existing `make up`, backup and health scripts target the legacy WeeWX scaffold; they are not PostgreSQL operational procedures.

## License

Integration code remains GPL-3.0-only. Existing upstream pins/provenance are retained in `UPSTREAMS.lock` and `docs/upstreams/README.md`. No upstream source is vendored into the new application.
