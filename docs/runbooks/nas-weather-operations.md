# Additive weather NAS operations

## Scope and gates

This package manages only `lakehouse-weather-dashboard` and `lakehouse-weather-forecast`. It never starts a database,
recreates my-pa services, attaches networks to PostgreSQL, changes a tunnel, or
installs a public route. It creates one approved weather-only egress bridge for
forecast HTTPS access; only the forecast service joins it. Run the scripts on the NAS as the authorized operator. Verify Python 3 is
available before staging; no interpreter installation is performed here. Admission
requires authorized root execution (`sudo -n python3`) to stat protected secret
paths; file contents are never read by admission. NAS Python 3.8 is supported.
Docker metadata uses `/usr/local/bin/docker`; admission uses the explicitly pinned
standalone `/usr/local/bin/docker-compose`, whose v2 version is checked before
mutation. It does not assume a Docker CLI Compose plugin or search PATH.
No script has been executed against the NAS as part of authoring this package.

Admission requires independently reviewed source head and tree, the corresponding
locally loaded exact `sha256:` image ID, image provenance labels matching that
head/tree, Linux amd64, UID 10001 and the default Gunicorn command. A label is a
binding checked against the operator's reviewed build record, not a cryptographic
build attestation. Never invent the reviewed head/tree or substitute a mutable tag.

The two pre-existing internal networks and PostgreSQL container are pinned in
`ops/nas/runtime.py`; any drift requires renewed owner review. There is no Docker
socket mount, published port or additional database service. The application joins
existing data-plane and browser-origin networks. Dashboard memory is limited to
256 MiB and forecast memory to 128 MiB. Both services set soft and hard `nproc` and
`nofile` limits to 256. Linux `RLIMIT_NPROC` counts processes/threads across the real
UID; UID 10001 can be shared with other containers. This is a UID-wide ceiling,
not a per-container PID cap. `RLIMIT_NOFILE` bounds each process's open descriptors.
Record existing UID-10001 task counts before admission and investigate headroom if
startup or worker creation fails; do not silently raise limits or switch to root.

The verified NAS Docker 24/kernel 4.4 cgroup-v1 runtime cannot apply CPU CFS quotas
and discards PIDs-controller limits. Accordingly this package sets no `cpus`, CPU
shares or `pids_limit`; CPU has no hard quota. Two Gunicorn workers, two shared KDF
slots, authentication rate limits, request/subprocess timeouts, supported memory
limits and the UID-wide process ceiling bound application work. These controls do
not provide CPU scheduling isolation. Reassess memory and resource headroom using
metadata, and verify the configured memory/rlimits inside the actual NAS image
before admitting the dashboard. Local contract tests do not prove kernel enforcement.

Prepare `/volume1/weather-dashboard/<reviewed-head>/` containing this exact reviewed
source/package. Prepare four explicit read-only files: approved station registry,
dedicated weather-runtime database URL, separate cache-only forecast-role database
URL and a random ingest token of at least 32
characters. Secrets live under `/volume1/weather-dashboard/secrets/` with a root-owned mode-0700 parent directory and files owned by UID 10001 mode 0400; operator-only
files use 0600. Never display the secret contents or place them in command arguments.
For a new installation, the authorized root operator can run `python3
ops/nas/prepare_runtime.py --secret-dir /volume1/weather-dashboard/secrets --uid
10001` to review the dry run, then add `--apply` to generate an exclusive new
ingest-token. It refuses existing token paths and never prints or reads token
contents. The database owner provisions both database URL files separately. Both provisioners
accept the same root-owned mode-0700 secret directory, so either can run first.
Docker binds the individual secret files into the container; UID 10001 does not
need host-parent traversal permission. Never chown the secret directory to the
application user. The forecast
role can access only forecast cache rows, without observations or registry writes;
only its DSN and the registry are mounted into the egress-capable service. The
application requires the ingest token even while all stations are disabled.

Registry coordinates require explicit owner approval and RF identity must remain
uncommissioned until physical capture. The application may show empty/stale data
before commissioning. Complete owner-controlled weather-schema and dedicated-role
provisioning before admission; never provide owner credentials to the application.

## Internal admission and verification

First run a dry run (does not connect to Docker):

```sh
python3 ops/nas/runtime.py admit
```

Then execute this template with actual reviewed identifiers and absolute paths:

```sh
sudo -n python3 ops/nas/runtime.py admit --apply \
  --image-id sha256:REVIEWED_IMAGE_ID \
  --reviewed-head REVIEWED_40_HEX_HEAD --reviewed-tree REVIEWED_40_HEX_TREE \
  --registry /volume1/weather-dashboard/REVIEWED_HEAD/stations.json \
  --database-url-file /volume1/weather-dashboard/secrets/database-url \
  --ingest-token-file /volume1/weather-dashboard/secrets/ingest-token \
  --forecast-database-url-file /volume1/weather-dashboard/secrets/forecast-database-url
python3 ops/nas/runtime.py status --apply
```

Record existing my-pa service IDs/status/health metadata before and after admission;
compare without dumping configuration, environment, commands or logs. The script
pins network and PostgreSQL IDs but does not prove every my-pa service stayed healthy.
Admission success means Compose returned successfully and both weather services
have their exact expected network attachments. Admission starts dashboard first, waits up to 120 seconds for health, then starts
forecast; this seeds location keys before cache writes. Failure before readiness
never starts the forecast service. Public exposure remains separately gated. Wait for health to become
`healthy`; the probe checks process health and database readiness, including required
weather relations/grants. Independently check internal GET dashboard/history through
the existing authorized proxy path and ensure the mode is `postgres`. Stale sensor
and forecast indicators are expected until their respective producers are enabled.

Compose has no command override: the reviewed image's Gunicorn command starts two
bounded workers. Restart policy is `unless-stopped`. Health does not trigger Docker
automatic restarts; investigate persistent unhealthy status using status and
redacted readiness checks. Logging is disabled to prevent payload leakage; no
operations command reads container logs. Temporary worker files use bounded tmpfs.

The existing my-pa networks are internal and provide no Internet egress. The
approved `lakehouse-weather-egress` bridge joins only the forecast service; dashboard,
PostgreSQL and public proxy retain their original network sets. The forecast worker
uses the same reviewed image with a mounted reviewed standard-library loop. It runs
one `refresh-forecasts` subprocess to completion, bounded at 120 seconds, then waits
3600 seconds; runs never overlap. It uses the cache-only dedicated database role,
loads registry locally, and never initializes Application, writes registry rows or
requires an ingest token. A failed attempt preserves the prior cache and retries
after the cadence. Its health metadata contains only attempt/success timestamps and
result, with stale success after six hours or missing attempts after 3900 seconds
marking unhealthy. No payload output is retained.

The provider request is fixed to HTTPS `api.open-meteo.com/v1/forecast`; HTTP
redirects are refused. This is application-level request restriction. The new bridge
does not enforce an L3 destination allowlist. Do not claim firewall isolation of
arbitrary compromised-process traffic. This narrow additional process/network is
justified by hourly Internet forecast refresh while keeping the browser/runtime
service off general egress. RF remains deferred.

## Protected public route

`ops/nas/weather.caddy.fragment` is an inert candidate for the existing public
proxy. It proxies named browser GET routes and only the exact login/logout/refresh
POST routes to the application, strips `/weather`, and returns 404 for other weather
paths/methods. It never serves files directly or exposes health, readiness or ingestion.
The `/weather` redirect uses relative `/weather/`.

The operator selected the application's dedicated password and remembered sessions;
Cloudflare Access is not required. PostgreSQL mode enables application authentication
unconditionally and requires `WEATHER_AUTH_ORIGIN=https://www.bobby-fetting.me`, fixed
in the dashboard Compose environment. The forecast service receives no browser-auth
configuration. Password material and opaque session hashes live in weather-owned
PostgreSQL tables; there is no password file or additional authentication service.

Before public route activation, the owner must establish the password through an
interactive SSH TTY and the hidden setup command in the admitted dashboard container:

```sh
sudo -n /usr/local/bin/docker exec -it lakehouse-weather-dashboard \
  python -m weather setup-password --email OWNER_EMAIL
```

Replace `OWNER_EMAIL` privately. The command requires a real TTY and asks for the
password twice with getpass; never put passwords in arguments, environment, chat,
files, screenshots or command output. No public account-bootstrap endpoint is
exposed. Initial setup is operator-controlled; credential replacement remains a
separate explicit owner decision.

Only `/login`, `/login.css`, `/login.js` and `/api/auth/status` are public application
paths. Other browser assets, dashboard and history require a valid session. Login,
logout and refresh require exact canonical Origin and CSRF validation. Remembered
sessions use Secure, HttpOnly, SameSite=Strict, host-only cookies scoped to
`/weather/`, with the selected 60-day remembered-session policy. Do not alter the
canonical origin or trust a client-supplied authentication header to bypass this.

Activation is blocked until independent review and internal verification prove that
unconfigured authentication fails closed and the owner has completed hidden password
setup. Preserve existing `/pa` rules and upstream identity. Validate the fragment
inside the complete Caddy config using `caddy validate`; only then perform a
separately authorized proxy reload and existing-tunnel update. No fragment import,
proxy reload or tunnel mutation is performed by this package.

Acceptance must prove: unauthenticated dashboard/assets/history denied or redirected
to login; public login/status works without leaking credentials; wrong password and
wrong Origin/CSRF denied; authenticated dashboard/history/assets work; logout revokes
the session; remembered-session persistence and expiry work; `/weather` redirects;
ingest/health/ready/unknown paths remain blocked; `/pa` remains healthy. Complete an
actual iPhone Safari check before claiming mobile commissioning. Backup archives now
include weather credential/session hashes and require the same protected handling
as database backups; never display or publish their contents.

## Weather-only backup and restore rehearsal

After owner review, create an empty operator-owned mode-0700 directory on the NAS
outside the source checkout. This backup contains weather data and weather credential/session hashes. Treat it
as sensitive and never display or publish its contents:

```sh
python3 ops/nas/backup_weather.py --destination /EXPLICIT/EMPTY/BACKUP/DIRECTORY
python3 ops/nas/backup_weather.py --destination /EXPLICIT/EMPTY/BACKUP/DIRECTORY --apply
```

The tool verifies source container/database identity, uses local owner socket auth,
and executes custom-format `pg_dump --schema=weather --strict-names --no-owner
--no-privileges`. It creates a byte-count/SHA-256 manifest only after success. Never
remove the schema filter or dump the whole my-pa database. Dedicated roles/grants
are owner-managed migration evidence and are not included. PostgreSQL snapshot
consistency covers this archive; it does not replace my-pa's own backup policy.
The backup file is opened exclusively, and failed partial attempts are preserved.
Do not count a hash-only backup as proven recoverable.

Restore rehearsal is deliberately an owner-reviewed manual procedure:

1. Provision a disposable isolated PostgreSQL instance of a compatible version;
   record its new container ID and database name. Verify the target ID differs from
   `6f2581014af3e6f41f4b5c8f412334ac371d9875a75a553fe96bd74936fbbe83`, target
   name differs from `my_pa`, and no live my-pa network or volume is attached.
   Refuse an unknown, production, shared, or source identity.
2. Verify archive size/hash against the manifest without displaying records. List
   archive TOC locally and verify every application object belongs to `weather`.
   Do not publish the dump or TOC. Resolve extensions/schema privileges explicitly.
3. Against that verified isolated target only, restore with `pg_restore
   --exit-on-error --single-transaction --no-owner --no-privileges` using an explicit
   target database. Never use `--clean`, source DSN, implicit PG environment or the
   source container. Reapply reviewed dedicated-role grants separately if testing
   runtime access. Record role and target identities without credentials.
4. Compare table counts, station IDs, timestamp bounds, uniqueness constraints and
   latest/history queries to bounded expected metadata; test runtime readiness.
   Record SHA-256, target identity, exit codes and results in a rehearsal receipt.
   Keep `restore_rehearsed=false` until successful evidence exists. Cleanup of the
   disposable instance needs its own bounded authorization.

No backup, restore or rehearsal is claimed performed by this runbook.

## Monitoring and safe rollback

Use `status --apply` for ID/state/health only. Monitor freshness in the authenticated
dashboard, health degradation, backup age and successful rehearsal receipts.
A process marked healthy can still have stale sensor/forecast data; distinguish them.
Establish a backup cadence and retention with the owner before unattended operation.

To roll back runtime safely:

```sh
python3 ops/nas/runtime.py stop
python3 ops/nas/runtime.py stop --apply
```

The tool checks weather Compose ownership before stopping the weather container.
It leaves all schemas, rows, roles, images, my-pa containers and networks intact,
including the idle weather egress bridge. Both own containers are stopped; no
forecast process remains scheduled after container stop.
If a public route was subsequently activated, the authorized operator must disable
only its weather fragment/policy while preserving `/pa`; runtime stop alone is not
route rollback. A previous reviewed immutable image can be readmitted through the
same gate only after migration compatibility is assessed. Never downgrade the live
schema or drop the dedicated role as routine rollback.
