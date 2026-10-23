# 08 — Lakehouse Weather repository change plan and boundary with my-pa
**LHW-ML-20261023 | CP-4 | PROPOSED / NOT EXECUTED.**
Repository baseline: `RMF112018/Lakehouse-Weather main@aea6bada042b34a8365c9e70e3a6a0f90304f3f0`. my-pa baseline: `RMF112018/my-pa main@3d1593aa4dc2477395b47c97067338f8c46eff0b`. Before actual development refresh both SHAs, read governance and bind plan review to exact base. Do not combine Lakehouse planning PR with my-pa implementation. Existing architectural ADR-0001 remains accepted historical until an approved explicit superseding ADR.

## 1. Target proposed file tree (implementation phase ONLY)
~~~text
Lakehouse-Weather/
  AGENTS.md                              # proposed repository-local task boundaries, if needed
  README.md                              # updated user/operator guide
  ROADMAP.md                             # amended dependency order; current goals preserved historically
  compose.yaml                          # service topology; no DB or USB outside permitted planes
  .env.example                          # non-secret LAKEHOUSE_* keys, no my-pa app env pollution
  pyproject.toml                        # small Python app/collector dependency set + test/dev extras
  uv.lock (or approved reproducible lock)
  package.json                          # workspace frontend build; exact lock package-lock.json
  src/lakehouse_weather/
    __init__.py
    config.py                           # strict settings; no secret logging
    types.py                            # source classes / typed names
    application/
      weather_service.py                # bounded use cases for writes/reads
      provider_poll_loop.py             # one process owner, per-stream backoff/weighted quota
      freshness.py
      summarize.py
    domain/
      location.py
      source.py
      station.py
      observation.py
      model.py
      rain.py
      quality.py
      source_selection.py
      units.py
    infrastructure/
      db.py                             # weather-only least-privilege connection
      repositories.py                   # explicit weather schema, atomic upsert
      clock.py                          # injectable UTC time
      spool.py                          # durable file journal: fsync + rename, replay
    ingestion/
      receiver.py                        # line capture, first-seen IDs, backpressure
      decoder_mapping.py
      normalized_events.py
      providers/
        nws.py
        open_meteo.py
        http_client.py                  # SSL, cache headers, Retry-After, quotas
    api/
      app.py                            # FastAPI route composition
      read_routes.py
      internal_ingest_routes.py
      schemas_v1.py
      errors.py
    cli/
      main.py                           # weather_admin_cli/SET ROLE audited registration
  web/
    src/
      api/typedClient.ts
      features/
        locations/
        current/
        history/
        forecast/
        compare/
        health/
      components/                       # accessible cards, source badges, navigation
      styles/tokens.css
      App.tsx
    public/manifest.webmanifest
    public/icons/                       # project-owned assets only
    index.html
    vite.config.ts
    package.json
    package-lock.json
    tsconfig.json
    tests/
      components/
      e2e/
  docker/
    receiver/Dockerfile                 # pinned rtl_433, minimal runtime, no DB drivers
    weather-app/Dockerfile              # pinned Python app+static web assets, nonroot
    scripts/                             # entrypoint only when justified
  config/
    rtl_433/rtl_433.conf                 # versioned diagnostic/prod model config
    weather/weather.example.yaml        # locations/sources template with no real sites
    security/proxy.example.yaml         # reference allowlist, no endpoints guessed
  tests/
    fixtures/
      rf/                               # synthetic and sanitized authenticated RF samples
      nws/                              # synthetic valid/error responses
      open_meteo/
      database/                         # fixture schema and seeded fake IDs only
      golden/                           # timezones, rain resets, source replacements
    unit/
    contract/
    integration/
    security/
    e2e/
    performance/
  scripts/
    gate1-rf-test.sh                     # preserved RF diagnostic, pin image
    validate.sh
    bootstrap.sh
    run-local-synthetic.sh               # no real DB credentials
    validate-compose.sh
    verify-source-fixtures.sh
    check-dependency-pins.sh
    deploy-preflight.sh                  # dry-run / no implicit activation
    backup-verify.sh                     # delegates canonical backup to my-pa operator
    synology/usb-device-info.sh
  docs/
    plans/multi-location-weather/        # this planning package, readme/index and ADR candidate
    adr/0001-use-weewx-ecosystem.md      # preserved history, explicit supersession notice only after review
    adr/0002-multi-location-weather.md   # PROPOSED -> operator/plan-gate ACCEPTED
    runbooks/gate-1-rf.md
    runbooks/gate-2-sensor-map.md
    deployment/synology-ds923.md
    runbooks/source-replay.md
    runbooks/provider-outage.md
    runbooks/postgres-compatibility.md
    runbooks/recovery.md
    runbooks/update-rollback.md
    security.md
    status.md
    upstreams/README.md
  .github/workflows/
    ci.yml
    dependency-review.yml               # only if repo policy/permissions support
    specialized-rf.yml                   # manual hardware gate, no public secrets
  vendor/rtl_433                         # retained pinned source; evaluate vendoring strategy
  vendor/...                             # historic refs retained until approved retirement
  UPSTREAMS.lock                         # versions, licenses, provenance and digest map
  patches/                               # preserve until explicitly reviewed cleanups
  runtime/                               # ignored runtime state: spool, logs, never sample credentials
~~~
File paths and dependency choices are target design, not an instruction to generate all directories regardless of need. Stage increments by work package; do not create stub code solely to match tree. Keep Python package rooted `src/`, frontend rooted `web/`, and all tests synthetic.

## 2. Existing Lakehouse files: modify / retain / retire proposal
| Existing path | Plan action and purpose | Gate |
|---|---|---|
| `README.md` | **MODIFY** after ADR approval: describe two-container PG-backed target and current unverified status; preserve link to original scaffold | WP-002 |
| `ROADMAP.md` | **MODIFY**: replace WeeWX-specific downstream gate route with RF + my-pa DB + source-aware app + UI integration stages, mark historical roadmap | WP-002 |
| `docs/ARCHITECTURE.md` | **MODIFY** only after new ADR accepted; reference target architecture and no independent SQLite archive | WP-002 |
| `docs/adr/0001-use-weewx-ecosystem.md` | **RETAIN** unchanged while plan under review; then add explicit supersession note, not delete accepted record | WP-002 |
| `compose.yaml` | **REPLACE CONTENT** with receiver/weather-app private network topology after authority; remove running WeeWX/Mosquitto/Cloudflared services by approved measured plan, not during planning | WP-006, WP-010 |
| `docker/weewx/Dockerfile` | **RETAIN as historical** until post-ADR cleanup; replace production build path with `docker/receiver` and `docker/weather-app` | WP-002, WP-006 |
| `config/weewx/` | **RETAIN as historical** until approved retirement; real collector source maps use `ingestion/decoder_mapping.py`/fixtures | WP-006 |
| `config/rtl_433/rtl_433.conf`, `scripts/gate1-rf-test.sh`, `scripts/synology/usb-device-info.sh` | **REUSE/MODIFY**; preserve RF acceptance, pin image/digest, add latency, soak and device reconnect evidence | WP-003, WP-006 |
| `.env.example` | **MODIFY** safe placeholders only for weather app, source IDs, private paths, DB secret injection references; no real coords or credentials | WP-002 |
| `UPSTREAMS.lock`, `.gitmodules`, `vendor/` | **RETAIN initially** with documented usage/why redundant; version/digest pin decoder and audit license; retire unused upstream only after approved cleanup | WP-002, WP-012 |
| `scripts/bootstrap.sh` | **MODIFY** to avoid auto-initializing no-longer-needed submodules or writing executable config without RF/DB gates | WP-002 |
| `scripts/install-extensions.sh`, `scripts/repoint-forks.sh`, `patches/*` | **RETAIN legacy** until review, then deprecate/delete through independently approved cleanup scope; no silent destructive action | WP-012 |
| `scripts/backup.sh`, `scripts/healthcheck.sh` | **MODIFY** for governed my-pa DB backups and actual ingestion freshness readiness; no more ad hoc SQLite tar claims | WP-011, WP-012 |
| `config/nginx/default.conf`, `config/cloudflare/*`, `config/mosquitto/*` | **REVIEW** security; do not enable anonymous broker or unreviewed public tunnel; only private ingress policy in MVP | WP-010 |
| `tests/test_structure.py`, `tests/fixtures/wh65b.sample.json` | **RETAIN** provenance, clearly synthetic; new strict contract fixtures and suites; avoid real RF metadata publication | WP-006, WP-011 |
| `.github/workflows/ci.yml` | **MODIFY** for changed Python/TypeScript unit/contract/security and isolated PG; never live my-pa nor NAS in public CI | WP-011 |
| `docs/runbooks/*`, `docs/deployment/*`, `docs/security.md`, `docs/status.md` | **UPDATE** only after decision; distinguish planned, test-isolated, pilot, production; preserve failed gate evidence | WP-002, WP-012 |
| `docs/publishing.md`, `LICENSE`, `.gitignore` | **REVIEW** license and privacy; GPLv2-or-later rtl_433 vs GPL-3-only project integration; keep unmodified license policy pending legal/maintainer assessment; ignore only sensitive runtime, not evidence manifests | WP-002, WP-012 |

## 3. my-pa repository ownership (separate work product, not part of this planning PR)
**No my-pa source modification is authorized by Lakehouse PR.** After operator approves the DB interface, separately scope `RMF112018/my-pa` branch and PR:
- `migrations/versions/<new_rev>_weather_schema.py`: a separately authorized additive revision on **then current** Alembic head using [04 §7](04_POSTGRESQL_INTEGRATION.md): event metadata+separate raw payload, provider streams, per-stream state, quota/nonce/metadata-audit tables, composite source/assignment/device/forecast integrity, retirement guards and indexes; never hand-edit legacy target SQL.
- `ops/postgres/provision_weather_roles.py` (or approved role provisioning mechanism): owner/migrator/app scope, distinct authenticated `weather_admin_cli` NOINHERIT LOGIN and `weather_admin` NOLOGIN with audited metadata-only DML, future **uncommissioned** retention role; operator-gated apply/readback.
- `tests/schema/test_weather_schema_migration.py`, `tests/database/test_weather_permissions.py`, `tests/database/test_weather_isolation.py`: isolated database, zero unintended schema changes; migration from preceding head, negative grants and backup/restore.
- `docs/decisions/ADR-016-or-next-weather-schema.md` **only if** my-pa owning ADR index demands it; no invented next ADR number.
- `docs/00_REPOSITORY_SOURCE_INDEX.md`, nearest DB/migration owning index and runbooks updated under my-pa governance.
**Owner:** my-pa repository DB maintainer/operator, not Lakehouse weather-app service. The schema and role can use approved SQLAlchemy expressions in Lakehouse at runtime but must not create DDL there. No new `MY_PA_*` weather settings unless my-pa approves; Lakehouse should use `LAKEHOUSE_*`.

## 4. CI/CD package boundaries
**CI (unprivileged):** ruff/format/typecheck, pytest pure unit+contract, synthetic adapter/replay fixtures, DB test in disposable PostgreSQL with compatible test migration basis, TypeScript typecheck, Vitest/Playwright browser mobile tests, Compose config static lint, secret scanning and SBOM/license checks. No real NAS mounts, provider credentials, RF packet captures, private source locations or live DB ports.
**Specialized manual gates:** controlled SDR on actual NAS; provider quota/license checks with approved public test geography; restore verification on scratch only; measured database performance; iPhone over private ingress; security pen test. CI statuses reflect what ran; hardware-unavailable marked **NOT_RUN**, never PASS.

**Build:** pin Python/Node versions and all container images by digest, `rtl_433` commit SHA, record package/OCI digest and SBOM; build multi-stage React static files into Python app image and restrict runtime to non-root. Do not publish secrets in image layers, build args or Actions logs. GPL obligations reviewed for bundled images and distribution of modified components.

## 5. File/order staging and proof
WP-002 ADR/README/roadmap only after plan review; WP-003 independent RF test first when hardware present; WP-004 my-pa DB schema contract separate; WP-005 domain algorithms and synthetic persistence, WP-006 receiver ingestion, WP-007 provider adapters, WP-008 aggregates, WP-009 dashboard, WP-010 ingress, WP-011 E2E and independent exact-head review, WP-012 runbooks and readiness. Hardware-independent work may proceed on synthetic fixtures **after plan approval**, but no actual schema/migration and no deployments without separate authorization. See [10_IMPLEMENTATION_WORK_PACKAGES.md](10_IMPLEMENTATION_WORK_PACKAGES.md).

## 6. Explicit exclusions
No public secrets or household geolocation, no my-pa refactor, no other provider RF reception, no new PostgreSQL instance, no cross-DB migration, no change to live roles, no WAN exposure, no destructive legacy cleanup until separately approved. Create/revise only planning documents in this PR. Proposed future deletion of legacy WeeWX files is intentionally blocked by a separate cleanup authorization.

## 7. CR-1 correction ownership and test mapping

**Present authorization covers only corrected Markdown in this existing planning directory.** Future file ownership below is an implementation proposal, not permission to create code, migrations or credentials.

| Finding | Future owning implementation paths | Test criterion |
|---|---|---|
| RV-001 | `ingestion/decoder_mapping.py`; RF fixtures | Actual WH65B vs WS69/WH32B decoder AT-004/006 |
| RV-002 | `infrastructure/repositories.py`; my-pa Alembic `raw_events` metadata/`raw_event_payloads` | FK RESTRICT, 90d/24mo example scratch restore AT-019/023 |
| RV-003 | `provider_poll_loop.py`, NWS/Open-Meteo adapters; my-pa `provider_streams`, `poll_state(stream_id)` | independently succeeding/failing destination streams AT-016/018 |
| RV-004 | `cli/main.py`; my-pa admin role provisioner and metadata audit | operator allowed / normal application denied AT-012/021 |
| RV-005 | weather domain tests; my-pa composite FK/epoch/range/chain triggers | isolated cross-source/time/epoch negatives AT-007/011/013 |
| RV-006 | `receiver.py`, `spool.py`, `internal_ingest_routes.py`; nonce register | mixed 207, HMAC re-sign, durable journal/crash AT-009/010/025 |
| RV-007 | `domain/rain.py`, `application/summarize.py`, `/derived` read API | on-read computed rain with paired IDs/cutoff AT-008/014/017 |
| RV-008/009/010 | provider quotas, WP effort, private frontend cache policy | AT-013/016/020/023 |

Refined contracts: [03](03_TARGET_ARCHITECTURE.md), [04](04_POSTGRESQL_INTEGRATION.md), [05](05_WEATHER_DATA_MODEL.md), [06](06_INGESTION_AND_SOURCE_INTEGRATIONS.md), [09](09_VALIDATION_AND_ACCEPTANCE.md). All my-pa code, scratch DB actions and production changes require separate explicit operator authorization.


## 8. CR-2 — Detailed future file ownership, documentary only

This plan revision adds **no** application/role/DDL/config changes. It refines the separately gated future file responsibilities already described in §1–§7:

- `src/lakehouse_weather/ingestion/receiver.py`, `infrastructure/spool.py`, `api/internal_ingest_routes.py` (WP-005/006/010) implement **one** all-member 200 / any-non-success 207 contract, whole-batch errors only before member processing, fresh signed nonce on retry, durable exact terminal receipt, and nonce-ledger admission only through weather-app's scoped DB role (RR2-001/005).
- my-pa-owned `migrations/versions/<new_rev>_weather_schema.py` and operator-scoped role provisioning (WP-004) must bind local physical observation to the **same device on its raw event**; remote null-device cases require DB-owned source-kind guard; model runs require matching `(event_id,source_id,stream_id)` FK to immutable raw event metadata with ON DELETE RESTRICT; nonce expiry authority is operator-only (RR2-002/003/005).
- `src/lakehouse_weather/ingestion/providers/{nws.py,open_meteo.py}`, `application/provider_poll_loop.py` and persistence/domain code (WP-005/007) freeze stream identity across absolute rolling windows, distinct raw/semantic hashes, nullable true model issuance, model source/stream FKs, and quota accounting (RR2-003/004).
- `web/` / `application/summarize.py` (WP-008/009) show no durable offline weather API cache, label on-read rainfall with **two measured observation UUIDs**, and show null true run issue time where unavailable (RR2-007/008).

All test additions to `tests/` are future WP outputs listed in [09](09_VALIDATION_AND_ACCEPTANCE.md); no fixture has been created by CR-2. Original source files remain untouched pending explicit implementation authorization. A separate independent reviewer must inspect any resulting exact new HEAD before an ADR or implementation decision.
