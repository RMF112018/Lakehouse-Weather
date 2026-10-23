# Weather schema proposal — not an executable migration chain

`001_weather_schema.PROPOSAL.sql` is a review artifact. Weather never creates a
schema or database at startup. The my-pa database owner must review/adopt this
proposal into my-pa's canonical Alembic chain, validate from empty and preceding
revision on isolated nonproduction PostgreSQL, then explicitly authorize use.
No schema or connection has been applied to the live database.

Use the existing logical database `my_pa`. Provision a separate weather runtime
role with no superuser, role/database creation, inherited owner role, schema
ownership, or privileges on my-pa tables. Grant only schema USAGE; SELECT,
INSERT, UPDATE on locations/stations/forecast_cache; SELECT, INSERT on
observations. Do not grant DELETE or DDL. Owner credentials never enter the
weather service. Startup checks current database, superuser, elevated role flags,
and weather schema ownership, but explicit owner review remains necessary for
indirect membership and unrelated pre-existing table grants.

Direct PostgreSQL mode needs optional psycopg 3.2–3.3 (`pyproject.toml` compatible
range), a dedicated URL naming `/my_pa` with no query parameters, an explicit
`WEATHER_ALLOW_DATABASE=nonproduction` gate, station registry, and a server-only
ingest token. This gate labels intent; it cannot prove a server is nonproduction.
Only configure a verified isolated target authorized by its owner.

The optional adapter passed isolated PostgreSQL 17.10 integration testing with
psycopg 3.3.6: persistence, deduplication, late packets, rain reset, forecast cache,
reopened connections, and role schema restrictions. This is not validation of the
shared my-pa database, its migration history, or its deployed roles. No package
or DB installation is performed by the application. Dependency locking and vulnerability checks
remain a packaging gate before deployment; the standard-library demo needs none.
