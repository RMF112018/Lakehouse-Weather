# Weather persistence: owner-controlled adoption

Weather uses the existing physical database **my_pa**, owned by **my_pa**. The
application never creates databases, schemas or roles. Historical observations
have no automatic expiry. No live migration is implied by these files.

The frozen `001_weather_schema.PROPOSAL.sql` remains the reviewable additive DDL.
Its SHA-256 is `5f2214e45d42184fad13b10d4246dfb2ce6b901c76190ecbc922c78291c8fd28`.
The local my-pa canonical Alembic revision `a91b7d3c8e20` follows
`6f1476b8da52`: it creates an absent schema or adopts only the exact frozen
catalog. It refuses downgrade; retiring history needs a separate owner decision.
It changes no existing my-pa domain tables or grants.

The deployed owner chain may be older than this checkout. **Do not upgrade
unrelated my-pa migrations or stamp a false Alembic head.** The separately
reviewed owner adapter applies only weather DDL and leaves the existing owner
revision unchanged. A later canonical upgrade validates and adopts that exact
schema. Shape validation compares columns/types/nullability/defaults,
constraints/PK/FK/check expressions, index definitions, relation membership,
owner identity, and absence of application triggers, RLS or functions.

`scripts/database/nas_owner_apply.py` (relative to the repository root) needs only Python standard library and
Docker CLI on the NAS. It runs `psql -X` over the existing PostgreSQL container's
Unix socket as my_pa. Explicit arguments bind the Docker executable, container
name and immutable 64-digit container ID, physical database/owner, expected
Alembic revision, and reviewed DDL digest. The default is a dry run with no
Docker connection. `--verify-only` checks shape and effective runtime privileges
without changing state. `--apply` additionally requires two explicit new absolute
secret destinations (`--secret-file` and `--forecast-secret-file`), private
executor-owned 0700 parents, and runtime DNS host.
Optional `--secret-owner-uid` transfers the new file to the application UID when
executed as root. It writes a raw single-line PostgreSQL URL to an exclusive
0400 file; it never prints or reads that secret. Existing files/roles cause a
refusal, preventing accidental credential rotation. On uncertain SQL transport
failure preserve the protected file and reconcile commit outcome before retrying.
No automatic cleanup, role deletion, or database recreation runs on failure.

Both roles are LOGIN, NOINHERIT, non-owner, non-superuser, with no role or
database creation, replication or RLS bypass. The `weather_runtime` role gets
weather schema USAGE,
SELECT/INSERT/UPDATE on locations, stations and forecast_cache, and SELECT/INSERT
on observations. DELETE, TRUNCATE, DDL and observation UPDATE are denied. The
separate `weather_forecast` role gets only schema USAGE and SELECT/INSERT/UPDATE
on forecast_cache, with no observation/registry table access. The owner adapter
audits effective privileges including PUBLIC grants, memberships,
all non-system application tables (including column grants)/sequences, database/schema CREATE, ownership,
and accessible application SECURITY DEFINER functions. Unexpected inherited or
PUBLIC authority aborts the transaction; canonical grants are never weakened.

The psycopg single-runtime developer alternatives `schema_apply.py` and
`weather_role.py` use an explicit owner socket target. They are fixture tools,
not the dual-role NAS commissioning path. Use `nas_owner_apply.py` for that path.
All owner paths require separately authorized exact targets. A successful dry
run proves argument binding only, never deployment readiness.

## Synthetic verification

Use `WEATHER_SYNTHETIC_PG=127.0.0.1:55439 python -m unittest discover -s tests -p
 test_database_readiness.py -v` only with the expressly disposable worker-owned
fixture described by that suite. It accepts no arbitrary DSN. Integration checks
cover strict existing-schema adoption, absent-schema creation, row preservation,
role grants, forbidden writes/DDL, PUBLIC authority and SECURITY DEFINER leakage,
and schema drift. Static tests run without a database.

A separate programmatic Alembic proof executed all **122** canonical upgrades
from empty on isolated PostgreSQL **17.10**, without loading Alembic configuration
or connecting to deployed data. Direct weather predecessor/adoption and empty
schema upgrades passed. A synthetic weather-only pg_dump/restore into a second
**disposable** database reproduced the exact catalog and persisted row. These
fixtures provide evidence, not another persistent weather database.

## Backup and recovery boundary

Before any authorized shared-database operation the owner must confirm its
existing whole-my-pa backup and recovery procedure. A weather-only supplement
can use container-socket `pg_dump -n weather --no-owner --no-privileges` into an
owner-protected backup destination; backups may contain personal location data.
Include registry configuration separately under its existing protection. Never
capture credentials or container environment in migration receipts.

Restore first to a separately authorized isolated target using matching
PostgreSQL tooling; verify the frozen catalog and per-station observation
counts/time bounds, then reapply reviewed role grants. A schema-only dump does
not preserve role passwords or PUBLIC privilege posture. Do not restore over
live my-pa, drop canonical schemas, or assume a weather-only restore rolls back
other database state. Stop writers and obtain explicit owner authorization for
any live restore/cutover. Retain the existing owner Alembic marker until canonical
adoption; receipts should record exact source hashes, container identity,
unchanged owner revision, schema/privilege verification and synthetic checks,
never connection URLs or generated passwords.
