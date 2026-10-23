# RF sensor records and bounded history

This service collects separately identified rtl_433 transmitters. A WS-2000
console, its outdoor WH65B family array, indoor pressure sensor and WH31L detector
are distinct sources. The dashboard shows available readings for each station;
it does not invent pressure, indoor measurements, solar W/m², a daily lightning
count, strike coordinates, or a strike time absent from the packet.

## Typed readings and source evidence

`weather.domain.CATALOG` is the API's authoritative metric catalog. Every entry
has a label, unit, kind and RF source field. A catalog lists supported fields,
not a promise that a particular transmitter supplies them. The dashboard returns
`sensor_catalog` and per-station `available_metrics`; history reports availability
and counts in the selected window. Missing values remain null.

Outdoor fields include temperature °C, humidity %, wind/gust m/s, direction °,
rain counter mm, UV index from `uvi`, raw UV from `uv`, and illuminance lux from
`light_lux`. Raw UV is not the UV index; lux is not W/m². Pressure is retained only
when explicitly present in a sensor packet (300–1100 hPa supported). Receiver
RSSI/noise/SNR are retained when supplied; their units are decoder-reported dB.

WH31L fields include `strike_count` as an eight-bit **raw counter**, distance km,
state, flags, integrity and battery level. Counter wrap/reset is not interpreted
as a daily/hourly strike count. No strike timestamp, direction or coordinate is
derived from heartbeat receipt. Distance 63 is a no-valid-distance sentinel:
normalized distance is null with an unavailable reason and raw 63 is retained.
The decoder's battery level 0, 0.5 or 1 is a fraction level, not a charge percent
or voltage. Binary battery status is unknown at 0.5; the numeric level is still
stored and displayed. Other decoder binary battery 0/1 readings accept float
0.0/1.0 as well.

Each retained observation includes bounded `raw_rf` plus provenance identifying
rtl_433, model, sensor ID, explicit UTC receiver time and normalizer version.
Unknown future RF fields survive without becoming falsely typed measurements.
Keys resembling credentials, authorization, sessions, cookies, passwords, tokens,
API/private keys and connection strings are omitted recursively. Recognizable
bearer/DSN/private-key strings are redacted. JSON has depth, field, list, string,
finite-number and total-size limits; no transport headers are stored. These
limits apply even to direct normalizer use, not only the HTTP body limit.

The five files under `tests/fixtures/reference/` are byte-preserved reference
material from the user-supplied sample ZIP. Their own README/manifest records
provenance and limitations. They are not live observations. The WH65B recording
offset is rejected as a timestamp, and the reconstructed WH31L example lacks a
UTC timestamp. Tests substitute synthetic UTC timestamps in memory only; the
reference files are never imported into station history.

## Query contract

`GET /api/history?station_id=...&range=...` accepts `4h`, `8h`, `12h`, `24h`,
`48h`, `3d`, `7d`, `10d`, `30d`, `60d`, `90d`, `180d`, `1y`, `5y`, `10y`, and
`all`. The default is 24 hours. Years follow the location's calendar, including
leap-day handling. `all` starts at the station's earliest retained raw record.
Legacy `hours=1..168` is supported with the same bounded response.

Custom requests use `range=custom&start=<explicit UTC ISO>&end=<explicit UTC ISO>`
or `local_start=<naive ISO wall time>&local_end=<naive ISO wall time>` plus the
location's IANA `timezone`. The supplied zone must match the station location.
Ambiguous fall-back times and nonexistent spring-forward times are rejected with
an actionable message; use explicit UTC bounds to disambiguate. End must follow
start, start must be 1970 or later, and end cannot be more than five minutes in
the future. Custom history is not artificially limited to ten years.

`metric=<catalog key>` selects one metric for smaller mobile responses.
`max_points` defaults to 600 and accepts 2–800. Points are UTC-aligned buckets;
calendar-local daily rainfall is not implied. Responses include requested and
actual bounds, source bucket width, output bucket width, observation counts,
metric catalog availability/units, summary statistics, `points`, and flattened
`history` compatibility points. Every returned array is capped by `max_points`.
`first`/`last` values include their chronological timestamps. Wind means use
sine/cosine circular averaging; opposite directions can have no defined mean.
Gust compatibility values use maxima. Counter means and sums remain null.

Empty buckets explicitly contain zero observations and null metric statistics;
missing sensor data does not become zero weather. Coverage counts populated
buckets for the selected metric (and separately for any observation).
`temporal_span_fraction` is the span between first/last retained observations
inside the requested window, **not sensor uptime or continuous coverage**.

## Known rainfall is partial

The derived `rain_known_mm` metric reports only increments between adjacent
valid rain counters no more than 15 minutes apart and with no counter decrease.
It exposes `sum` in mm, known interval `count`, counter `sample_count`,
`unknown_intervals`, `reset_count`, `gap_count`, and `partial=true`. With only a
baseline and no measurable interval, sum is null. A measured unchanged counter
produces a known zero. Resets, long gaps and the first missing baseline are
unknown, not manufactured rain or zero. Counter decreases do not become the
entire new lifetime counter. No equivalent lightning increment is inferred.

Five-minute rain summaries retain chronological head/tail counters and known
internal increments. Inserts serialize per station, rebuild that bounded raw
five-minute bucket, then fold 12 children into the hour and 24 hours into the
day. Reads join neighboring heads/tails only when the interval is measurable.
Thus late packets repair subsequent cross-hour/day rain intervals without
rewriting raw records or double-counting duplicate observations. Point sums
agree with the selected-window known partial sum, including cross-bucket
increments in their ending bucket. Original latest/raw `rain_interval_mm` uses
the same 15-minute/reset rule; aggregated compatibility rows leave it null.

## Persistence and scale

The additive `002_weather_rollups.PROPOSAL.sql` adds one weather-owned table with
station, UTC bucket start, width (300/3600/86400 seconds), and JSONB summary.
Raw station/time insertion and all rollup changes share one transaction. Duplicate
raw inserts contribute nothing. Generic numeric statistics are associative;
chronological first/last support late arrivals. No retention deletion is run.

Views up to one day use five-minute source buckets, up to 90 days use hourly
buckets, and longer views use daily buckets. Full interior buckets are read from
the station/width/time primary key. At most two partial source buckets are read
from the raw station/time index and clipped to exact requested bounds. Reads stream through server-side cursors in batches of 64 and fold immediately
into at most 800 output summaries, rather than retaining all source buckets in
Python. Raw edge queries exclude `raw_rf`, provenance and unavailable-reason
payloads; rain repair queries select only timestamps and counters. An 8,001-row
source-bucket sentinel rejects requests exceeding 8,000 source buckets with an
actionable 422 response; this is an input-budget guard, not a ten-year custom
range limit. Each raw boundary scan has a 20,001-row sentinel limit, aborting rather than returning a
misleading partial result above 20,000; statements have a five-second timeout.
This is a deliberate capacity limit for pathological packet frequency, not an
unbounded Python fetch. A bounded `backfill_day(station_id, UTC day)` method can
idempotently repair one day (at most 20,000 raw rows) under the same station lock.
It is never automatically run or treated as permission for live data changes.

The new owner adapter `scripts/database/nas_rollups_apply.py` requires exact
container, my_pa identity, owner-chain revision and SQL hash. The additive
operation checks the frozen seven-table catalog and existing least-privilege
roles, refuses a nonempty raw archive requiring separate backfill, creates only
the rollup table, grants runtime SELECT/INSERT/UPDATE on that table, and verifies
the exact eight-table catalog and all effective privileges. The forecast role
receives no new table grant. It does not read secrets, stamp the owner chain, or
run automatically. Repeated verification accepts only the exact reviewed shape.
Canonical my-pa migrations preserve the original seven-table snapshot, allow
strict exact seven/eight adoption, and add a separately reviewable follow-on.

## Measured synthetic validation

`tests/history_benchmark.py` runs only with explicit disposable-loopback fixture
opt-ins. The measured PostgreSQL 17 fixture retained **1,054,487 raw rows** from
2016-10-23 through 2026-10-22T23:59:30Z: **one** complete year at 30-second cadence
and nine preceding years at daily cadence. It is not ten years of high-frequency
RF data. It contained 108,407 five-minute, 12,047 hourly and 3,652 daily rollups.
A selected-temperature ten-year response returned 523 points in 0.0956, 0.0662
and 0.0719 seconds. EXPLAIN ANALYZE used `observation_rollups_pkey` for 3,652 daily
rows (0.893 ms) and `observations_pkey` for a 2,880-row one-day raw edge (0.849 ms).
These are local disposable-container measurements, not NAS hardware guarantees.
The benchmark uses temperature-only normalized records; full sensor packets and
all-metric payload sizes have not been benchmarked at this scale. The script
reports actual counts, span, cadence, timings and JSON query plans.

Synthetic tests cover reference distinctions, missing/unknown fields, redaction,
nonfinite/deep/oversize data, battery fractions, UTC/DST/custom bounds, empty and
large sparse histories, circular means, counter reset/wrap semantics, clipped
edges, concurrent duplicates, transaction persistence, idempotent repairs,
partial rain/reset/gaps/late cross-day packets, schema adoption and role denials.
No live RF, NAS, shared database, credential or production data was used here.
