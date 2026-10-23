# 01 — Source and system audit
**Planning package:** LHW-ML-20261023 | **Checkpoint:** CP-1 | **Date:** 2026-10-23
**Classification:** PLANNING / NON-IMPLEMENTATION | **Status:** SOURCE-AUDITED, RUNTIME-UNVERIFIED
**Controlling repos:** Lakehouse Weather \`main@aea6bada042b34a8365c9e70e3a6a0f90304f3f0\` (tree \`a3a375a2235294b886703a9e698675be79e5831f\`); my-pa \`main@3d1593aa4dc2477395b47c97067338f8c46eff0b\` (tree \`fa7e416a83d67284b0801e5f59f04189d780bbee\`).
**Truth hierarchy:** authenticated runtime > current repository > accepted repository governance/ADRs > official upstream/hardware > reproducible tests > prior descriptions. Repository evidence below is verified as FILE CONTENT only; it does not establish deployment or hardware functionality. Planning is authorized; production database, credentials, schema execution and deployment are out of scope.

## Source census and exact as-found state
**Lakehouse Weather:** GitHub main has the original 2026-09-09 scaffold commit; no current open issues or PRs in repository API response at audit time; \`docs/status.md\` explicitly reports GATE-1-RF PENDING and downstream GATE-2 through GATE-6 BLOCKED. The repository tree contains ~74 tracked entries including five submodule gitlinks, not populated upstream source code. There is no repository-root \`AGENTS.md\` in the inspected tree. Only a minimal structural unittest, a shell-syntax/Compose validation script, and a wholly synthetic WH65B JSON fixture are present; no evidence of RF reception, field mapping, database integration, multi-location application, performance, recovery or deployed PWA.

| Path / source | Inspection and established result |
|---|---|
| \`README.md\`, \`ROADMAP.md\`, \`docs/ARCHITECTURE.md\`, \`docs/adr/0001-use-weewx-ecosystem.md\` | Accepted 2026-09-09 single-station conceptual choice: \`rtl_433 -> weewx-sdr -> WeeWX -> SQLite + Belchertown\`. Supersession by a new ADR is required for divergent implementation; do not silently delete ADR-0001. |
| \`compose.yaml\` | WeeWX container mounts \`/dev/bus/usb\`; nginx serves WeeWX static output on configurable 8088; optional Mosquitto and cloudflared profiles; no PostgreSQL or multi-location service. USB and WAN binding are not runtime-verified. |
| \`docker/weewx/Dockerfile\`, \`scripts/install-extensions.sh\` | Build rtl_433 at pinned commit but \`FROM felddy/weewx:5\` is a floating image tag; installation presumes independently populated submodules. No resulting image digest/build provenance supplied. |
| \`.gitmodules\`, \`UPSTREAMS.lock\`, \`vendor/\`, \`docs/upstreams/README.md\` | Five upstream gitlinks exist with commit pins; source isn't vendored into this repository tree. Licensing and version-upgrade obligations apply if copied/modified. |
| \`config/rtl_433/rtl_433.conf\`, \`config/weewx/*.example\` | RF target 915 MHz; station coordinates intentionally missing. Example \`FOWH65BPacket\` parser/mapping is explicitly unverified. Optional WH32B pressure is not detected. |
| \`scripts/gate1-rf-test.sh\`, \`scripts/synology/usb-device-info.sh\` | Five-minute RF diagnostic with >=3 WH65B packets and host/container USB probes. Default diagnostic image \`hertzg/rtl_433:master\` is floating despite \`UPSTREAMS.lock\`; at least three packets is insufficient by itself to prove sustained operation and restart recovery. |
| \`docs/runbooks/gate-1-rf.md\`, \`docs/runbooks/gate-2-sensor-map.md\`, \`docs/deployment/synology-ds923.md\` | Good stage boundaries, not executed evidence. Actual DSM, USB restrictions, RF hardware presence and decoding remain unknown. |
| \`tests/fixtures/wh65b.sample.json\`, \`tests/test_structure.py\`, \`.github/workflows/ci.yml\` | Synthetic example has \`rain_mm\`, \`uvi\`, \`light_lux\`; structural test checks paths only; CI does not test ingestion correctness or live RF. Never interpret fixture as received sensor data. |
| \`scripts/healthcheck.sh\`, \`scripts/backup.sh\`, \`config/nginx/default.conf\` | Health check reports Docker state and static nginx \`/healthz\`; backup tars WeeWX folder without a demonstrated live-consistent DB snapshot or recovery drill. |
| \`config/mosquitto/mosquitto.conf\`, \`docs/security.md\`, \`.env.example\` | Optional broker has \`allow_anonymous true\` (not WAN-published in the scaffold); planned tunnels/credentials exist only as templates. No real endpoints, tokens, coordinate values or physical NAS path proven. |
| \`scripts/bootstrap.sh\`, \`scripts/validate.sh\`, \`docs/publishing.md\` | Bootstrap and formatting/structure scripts are scaffolds; no deployed attestations. |
| \`patches/\`, \`runtime/\` | Placeholder patch and runtime paths exist; not evidence of completed customization or persistent observations. |

**my-pa:** Current repository inspected at named main SHA above. Governance \`AGENTS.md\` requires least-privilege, no unauthorized production mutation, minimal new services, explicit ownership and schema migrations; permanent Project exception to §8.3 orchestration topology applies, not to database safety. \`AI_OPERATING_MANUAL.md\`, \`CLAUDE.md\`, \`.ai/project-sources/00_AEOS_MASTER_INDEX.md\` are routers. \`docs/00_REPOSITORY_SOURCE_INDEX.md\`, \`docs/architecture/00_ARCHITECTURE_INDEX.md\` and ADR-002/008/011/012 provide controlling orientation. Some narrative sections of older runbooks and indexes name superseded historic heads; compare to current repository before carrying an identity.

| my-pa source | Confirmed repository assertion / planning implication |
|---|---|
| \`migrations/README.md\`, \`migrations/env.py\` | **Alembic owns every schema change to canonical \`my_pa\` database.** Online migrations require distinct \`MY_PA_MIGRATION_DATABASE_URL\`; application \`MY_PA_DATABASE_URL\` cannot substitute. Revisions run transaction-per-migration; ad hoc Lakehouse DDL is not an approved shortcut. |
| \`docs/architecture/00_ARCHITECTURE_INDEX.md\`, \`migrations/versions/20261019_6f1476b8da52_record_lineage_s3.py\` | Repository describes a *single* head \`6f1476b8da52\` and 121 migrations. This is repository contract, **not proof that the actual DB has been upgraded**. |
| \`src/my_pa/bootstrap/settings.py\` | \`MY_PA_DATABASE_URL\` required, \`postgresql+psycopg\` scheme; unknown \`MY_PA_\` settings fail startup. Lakehouse variables must not be injected into my-pa's env namespace. |
| \`src/my_pa/infrastructure/database/engine.py\` | my-pa engine uses bounded pool_size=5, max_overflow=0, pool_pre_ping, 30s default statement timeout. Adding a separate writer requires an independently constrained budget and admission gate. |
| \`ops/compose/postgres.yml\`, \`ops/postgres/README.md\` | **Local-development** example uses \`postgres:17.10\`, \`my_pa\`, and loopback :5433; docs explicitly forbid treating this as NAS/production topology. |
| \`docs/decisions/ADR-002-database-identity-and-compatibility-alias.md\` | Logical database \`my_pa\`; physical alias may differ and must be independently verified. No permission to assume a physical DB name/host for production. |
| \`docs/decisions/ADR-008-nas-runtime-topology.md\`, \`ops/nas/compose.example.yml\` | NAS-local PostgreSQL target with unpublished data plane, disabled/proof-gated Compose contract, approved app/proxy network boundaries. Neither actual NAS deployment nor active access may be inferred. |
| \`ops/runbooks/postgres-operations.md\`, \`ops/runbooks/postgres-backup-runtime-attestation.md\` | Historical operations evidence and strict scratch/backup discipline. Runbook's older revision counts cannot override current main. |
| \`src/my_pa/infrastructure/persistence/tables.py\`, \`docs/architecture/data-authority.md\` | Existing application tables are deliberately modeled and governed, not an invitation to let a separate app run its own migrations in \`public\` or \`knowledge\`. |
| \`ops/postgres/README.md\` | Record Event roles \`my_pa_owner\`, \`my_pa_migrator\`, \`my_pa_runtime\` are a specialized, operator-gated role split; reuse is not implied. |
| \`docs/decisions/ADR-011...\`, \`ADR-012...\` | Accepted my-pa auth and ingress decisions govern my-pa; they do not automatically confer a shared browser session, public hostname, tunnel or app role to Lakehouse. |

**Unable to verify at this checkpoint:** actual PostgreSQL version, \`alembic_version\` of running DB, privileges/current schema inventory, backup restore status, total connection headroom, DS923+ DSM build, \`/dev/bus/usb\` presence, installed dongle, antenna reception, WH65B/WH32B identifiers and software image digests. No database or NAS connection attempted.

## Official upstream evidence and comparison
Repository metadata and most recent commit obtained through GitHub repository/commit endpoints on 2026-10-23 (dates represent commit metadata, not formal release support).

| Upstream | Current default HEAD as observed | Existing Lakehouse pin | License reported by GitHub |
|---|---|---|---|
| \`merbanan/rtl_433\` | \`406f9a33550a2b6b3d0d8a8a486417ce5b3f13ab\` (2026-10-20) | \`3792adf1075acb7c6447f7c27df9920fd4f2d41a\` | GPL-2.0 metadata; inspect per-file license notices before distribution |
| \`matthewwall/weewx-sdr\` | \`e5f1f9915322fa6d1c25b4ff8e490b804cefeac1\` (2025-01-13) | same | GPL-3.0 |
| \`weewx/weewx\` | \`a5790be2d0d33da50440eb37e0a9e21499246920\` (2026-10-22) | \`felddy/weewx:5\` image tag, not a WeeWX source pin | GPL-3.0 |
| \`uajqq/weewx-belchertown-new\` | \`e3994950c6dd95a0bcc4f101f4ea087f3fc31a5c\` (2026-09-03) | same | GPL-3.0 |
| \`felddy/weewx-docker\` | \`037b9818adab132c03a2a889565f2718aafc2462\` (2026-10-22) | \`000186c66d1331c135f49bfd6fa28253464eefbf\` | MIT |
| \`hertzg/rtl_433_docker\` | \`8a849f4dd25a96c504dcd77da26b0a8c1dc27212\` (2026-10-11) | \`a3e2527a8bad99a794df5a3628c843497c3c16de\` | GPL-2.0 metadata |

Upstream code \`merbanan/rtl_433/src/devices/fineoffset.c\` describes WH65-family RF variants as A=868 MHz, B=915 MHz, C=433 MHz, approximately 16s WH65 transmissions, WH32B approx. 64s, WH65 sensor ID behavior on battery replacement, and WH32B pressure decoder. The actual installed sensor model and outputs require capture. **Do not claim WH65B itself provides reliable pressure**; WH32B or another measured provider is the proposed pressure source. Source: https://github.com/merbanan/rtl_433/blob/master/src/devices/fineoffset.c ; version pin validation still required.

Official WeeWX 5.5 database and binding references document SQLite and MySQL/MariaDB, not a supported stock PostgreSQL adapter. This creates a material compatibility gap with the required canonical my-pa database: https://weewx.com/docs/5.5/reference/weewx-options/data-bindings/ and https://weewx.com/docs/latest/reference/weewx-options/databases/. A third-party PostgreSQL adapter would require its own proof, maintenance owner and governance approval.

Official Nooelec SKU 100700 / Amazon ASIN B01GDN1T4S lists RTL2832U, R820T2/R860, 0.1–1750 MHz, SMA female, and three supplied antenna masts (one marked UHF; suitability for 915 MHz not demonstrated). Source: https://www.nooelec.com/store/nesdr-smart.html . No hardware possession/operation has been established.

NWS API: https://www.weather.gov/documentation/services-web-api (US forecasts, alerts, and station observations, rate-limited with a required identifiable client). Open-Meteo current free API has noncommercial usage limits and CC BY 4.0 attribution: https://open-meteo.com/en/terms ; distinguish model-derived current conditions from actual measured observations.

## Register — findings and evidence status
| ID | Status | Finding | Impact / next disposition |
|---|---|---|---|
| F-001 | VERIFIED repository | Scaffold single-station WeeWX/SQLite violates new canonical-store requirement | Reconsider ADR-0001 via proposed plan ADR; no implemented change |
| F-002 | VERIFIED upstream | WeeWX stock PostgreSQL backend not documented | Eliminate A absent separately proven/supported adapter |
| F-003 | VERIFIED repository | Existing CI validates syntax/paths, not RF, multi-source, persistence or API | Add contract, integration, failure and restore suites |
| F-004 | VERIFIED repository | Unpinned diagnostic image \`hertzg/rtl_433:master\` and mutable base image \`:5\` | Resolve image digests before runtime pilot |
| F-005 | VERIFIED repository | \`allow_anonymous true\` MQTT config exists | Omit broker in new minimal design; if ever enabled, require auth/isolation |
| F-006 | VERIFIED repository | No sensor hardware proof; synthetic fixture is not an RF capture | RF Gate-1 with controlled evidence |
| F-007 | VERIFIED my-pa policy | All schema changes to canonical my-pa through my-pa Alembic | Formal cross-repo migration ownership and approval gate |
| F-008 | UNRESOLVED runtime | Production PG alias/version/schema/head/roles/backups unknown | No DDL, SQL grant or activation until operator-authorized discovery |
| F-009 | VERIFIED upstream | rtl_433 recognizes WH65B and WH32B family code paths; exact installed fields unknown | Stage real RF captures and observed-field mapping |
| F-010 | PROPOSED | Multi-source provenance and forecast separation absent | Create explicit domain schema with acceptance tests |
| F-011 | VERIFIED repository | Backups are unverified WeeWX directory tar; no shared PostgreSQL recovery design | Reuse my-pa backup envelope, add weather restore verification |
| F-012 | UNRESOLVED deployment | No evidence of Synology USB permission, Tailscale tunnel or client reachability | Pre-activation discovery gate; no public port forwarding |
| F-013 | VERIFIED repo / DERIVED | Current fixed configuration cannot distinguish two sources/locations and device replacement | Typed source-device-assignment-period model |
| F-014 | VERIFIED upstream | Free Open-Meteo has noncommercial usage and CC BY attribution | Provider acceptance and usage/retention contract before enablement |
| F-015 | VERIFIED repo | my-pa's accepted NAS proxy/auth stack does not confer weather ingress/access | Independent least-privilege exposure and authentication gate |

## Checkpoint 1 outcome
As-found audit established. This checkpoint **does not** accept an architecture, evidence a runtime, or authorize changes to my-pa. Next: options/conflicts and proposed architecture decisions (CP-2); shared-database and domain design (CP-3); target/repository design (CP-4); acceptance/work packages and draft review PR (CP-5).
