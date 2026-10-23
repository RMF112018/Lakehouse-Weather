# ADR-0003: Additive NAS runtime, owner-bound weather storage and forecast isolation

- Status: Authorized for implementation on 2026-10-23; execution must bind to reviewed source and recorded runtime evidence.
- Extends: ADR-0002. The operator explicitly authorized all remaining work except physical RF verification, including the live weather schema/roles, NAS services and protected `/weather/` activation.

## Runtime and access

Use a pinned Gunicorn WSGI runtime with two bounded synchronous workers for the dashboard. The standard-library server remains a local development/testing entry point. Health and dependency readiness are separate; neither claims RF commissioning. Secrets are mounted as specific read-only files, with no browser disclosure, broad environment dumps or request/payload logging.

The intended public origin is `https://www.bobby-fetting.me/weather/`, routed through the existing tunnel. The selected access boundary is a dedicated dashboard password with durable opaque remembered sessions capped at 60 days from initial authentication. Passwords are entered only through a hidden operator-terminal setup command and stored as salted scrypt hashes. Session tokens are stored hashed; explicit rotation preserves the original absolute deadline, and logout revokes server-side authority. Exact-origin checks, CSRF validation and shared database-backed rate/KDF limits protect mutations. No public account bootstrap exists. Existing my-pa passkeys cannot authenticate the `www` host implicitly because their cookie is host-scoped to `pa`. A dedicated password meets the requested independent 60-day remembered session without a cross-host authentication bridge or OAuth password flow.

Dashboard ingress accepts only the explicitly listed GET assets and read APIs. Bare `/weather` redirects relatively to `/weather/`. Health/readiness, machine ingestion and unlisted paths stay private. No host port or new tunnel process is needed. Existing my-pa services and their network attachments remain unchanged.

## Database ownership and migration history

The authenticated live my-pa owner chain is older than the source checkout's current head. Upgrading unrelated owner migrations or falsely stamping that chain would widen this objective. Apply only the exact reviewed additive weather DDL, transactionally, through the positively bound PostgreSQL container's local owner socket. Verify the schema's exact frozen catalog shape and retain the existing owner Alembic revision unchanged. A future canonical owner revision may adopt only that exact shape after the owner's normal chain reaches it. Source adoption is not represented as a live owner-chain upgrade.

The dashboard receives a dedicated non-owner, non-inheriting runtime login with the required weather relation privileges. A second login for forecasts has only weather schema usage and forecast-cache SELECT/INSERT/UPDATE. Provisioning audits effective privileges across unrelated application relations and executable security-definer functions. An existing PUBLIC grant that widens either role's authority blocks activation; this change does not repair canonical grants by weakening another boundary.

Fresh role passwords are generated inside the operator program and written exclusively to protected mounted input files. The program does not print them or read existing credentials. An ambiguous transaction/transport outcome retains the protected files for reconciliation and never blindly retries credential creation.

## Forecast worker and egress

The existing data-plane and browser-origin networks are internal. Scheduled provider requests therefore have a current, concrete need for a separate egress path. Use a second process from the same immutable image, hourly, nonoverlapping, with a bounded child timeout. It receives only the forecast-role credential and configured registry, with no ingest token or observation access.

Only this forecast service joins a new weather-owned egress bridge; the dashboard and existing PostgreSQL/proxy services do not. The application uses a fixed HTTPS provider endpoint and refuses redirects. This is an application destination bound, not a layer-three firewall allowlist. Provider failures preserve existing cache and visible freshness. Scheduling metadata must be observable without response bodies or coordinates in logs.

Precise operator-supplied coordinates are private deployment configuration, outside source control and output bundles. Provider disclosure was explicitly authorized for forecasts. Source examples remain generic. The station remains disabled for ingestion and shows no measurements until its real sensor identity and reception can be verified after hardware arrives.

## Recovery and scope

Back up only the weather schema through the existing owner service; never copy canonical personal-data schemas for this task. Restore rehearsal targets a separate disposable fixture. On failure, disable the weather route and stop only weather services. Keep the additive schema/roles for safe reconciliation; do not drop them as an automatic rollback.

Deployment readiness requires independent exact-head review, isolated database and packaged runtime tests, action-time target identity checks, effective privilege proofs, access enforcement and unchanged my-pa health. Neither authorization nor application readiness constitutes physical RF evidence.
