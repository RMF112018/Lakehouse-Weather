"""Memory demo and explicitly gated PostgreSQL persistence, never schema creation."""
import copy
import json
import threading
from datetime import datetime, timezone, timedelta
from . import history as summaries
from urllib.parse import urlparse, unquote
from .domain import rain_intervals, utc


class MemoryStore:
    def __init__(self):
        self.rows, self.forecasts = {}, {}
        self.lock = threading.RLock()

    def check_ready(self):
        return True

    def insert(self, station_id, observation):
        with self.lock:
            rows = self.rows.setdefault(station_id, {})
            key = observation['observed_at']
            if key in rows:
                return False
            rows[key] = copy.deepcopy(observation)
            return True

    def history(self, station_id, since):
        with self.lock:
            rows = rain_intervals(sorted(self.rows.get(station_id, {}).values(), key=lambda r: r['observed_at']))
            return [r for r in rows if utc(r['observed_at']) >= since]

    def latest(self, station_id):
        with self.lock:
            rows = rain_intervals(sorted(self.rows.get(station_id, {}).values(), key=lambda r: r['observed_at']))
            return rows[-1] if rows else None

    def earliest(self, station_id):
        with self.lock:
            keys = self.rows.get(station_id, {})
            return utc(min(keys)) if keys else None

    def history_summary(self, station_id, start, end, max_points=600, metric=None, zone='UTC'):
        width = summaries.source_resolution(start, end)
        with self.lock:
            pieces = [(utc(row['observed_at']), summaries.single(row)) for row in self.rows.get(station_id, {}).values() if start <= utc(row['observed_at']) < end]
            return summaries.render(station_id, zone, start, end, max_points, metric, pieces, width)

    def get_forecast(self, location_id):
        with self.lock:
            return copy.deepcopy(self.forecasts.get(location_id))

    def put_forecast(self, location_id, value):
        with self.lock:
            self.forecasts[location_id] = copy.deepcopy(value)


class PostgresStore:
    def __init__(self, url, gate):
        parsed = urlparse(url)
        # Disallow libpq overrides, service files and alternate dbname parameters.
        if gate not in ('nonproduction', 'production') or parsed.scheme not in ('postgres', 'postgresql') or unquote(parsed.path) != '/my_pa' or parsed.query or parsed.fragment:
            raise ValueError('Explicit my_pa PostgreSQL environment gate and URL required; query options are prohibited')
        import psycopg
        self.psycopg, self.url = psycopg, url
        with self.connection() as connection:
            row = connection.execute('SELECT current_database(), rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname = current_user').fetchone()
            if not row or row[0] != 'my_pa' or row[1]:
                raise ValueError('Expected my_pa database and an unprivileged weather role')
            owner = connection.execute("SELECT pg_has_role(current_user, nspowner, 'MEMBER') FROM pg_namespace WHERE nspname='weather'").fetchone()
            database_owner = connection.execute("SELECT pg_has_role(current_user, datdba, 'MEMBER') FROM pg_database WHERE datname=current_database()").fetchone()
            if owner is None or owner[0] or not database_owner or database_owner[0]:
                raise ValueError('Weather schema must exist and runtime role cannot inherit its owner')

    def connection(self):
        return self.psycopg.connect(self.url, connect_timeout=5, options='-c statement_timeout=5000 -c search_path=pg_catalog')

    def check_ready(self):
        with self.connection() as connection:
            # Prove the schema contract remains available, including an empty registry.
            connection.execute('SELECT id FROM weather.locations LIMIT 0')
            connection.execute('SELECT id FROM weather.stations LIMIT 0')
            connection.execute('SELECT station_id FROM weather.observations LIMIT 0')
            connection.execute('SELECT location_id FROM weather.forecast_cache LIMIT 0')
            connection.execute('SELECT station_id, bucket_start, bucket_seconds, summary FROM weather.observation_rollups LIMIT 0')
            connection.execute('SELECT id FROM weather.auth_users LIMIT 0')
            connection.execute('SELECT token_hash FROM weather.auth_sessions LIMIT 0')
            connection.execute('SELECT scope FROM weather.auth_limits LIMIT 0')
        return True

    def sync_registry(self, locations):
        with self.connection() as conn:
            for location in locations:
                data = {k: v for k, v in location.items() if k != 'stations'}
                conn.execute('INSERT INTO weather.locations (id, metadata) VALUES (%s, %s::jsonb) ON CONFLICT (id) DO UPDATE SET metadata=EXCLUDED.metadata', (location['id'], json.dumps(data)))
                for station in location['stations']:
                    existing = conn.execute('SELECT location_id FROM weather.stations WHERE id=%s', (station['id'],)).fetchone()
                    if existing and existing[0] != location['id']:
                        raise ValueError('Cannot move an existing station between locations')
                    conn.execute('INSERT INTO weather.stations (id, location_id, metadata) VALUES (%s,%s,%s::jsonb) ON CONFLICT (id) DO UPDATE SET metadata=EXCLUDED.metadata', (station['id'], location['id'], json.dumps(station)))

    def insert(self, station_id, observation):
        with self.connection() as conn:
            # Serialize a station against bounded repair/backfill, not other stations.
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 20261023))", (station_id,))
            inserted = conn.execute('INSERT INTO weather.observations (station_id, observed_at, measurements) VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING RETURNING station_id', (station_id, observation['observed_at'], json.dumps(observation, allow_nan=False))).fetchone()
            if not inserted:
                return False
            for width in summaries.WIDTHS:
                at = summaries.bucket(utc(observation['observed_at']), width)
                conn.execute('INSERT INTO weather.observation_rollups (station_id,bucket_start,bucket_seconds,summary) VALUES (%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING', (station_id,at,width,json.dumps(summaries.empty())))
                prior = conn.execute('SELECT summary FROM weather.observation_rollups WHERE station_id=%s AND bucket_seconds=%s AND bucket_start=%s FOR UPDATE', (station_id,width,at)).fetchone()[0]
                summary = summaries.merge(prior, summaries.single(observation))
                conn.execute('UPDATE weather.observation_rollups SET summary=%s::jsonb WHERE station_id=%s AND bucket_seconds=%s AND bucket_start=%s', (json.dumps(summary, allow_nan=False),station_id,width,at))
            self._repair_rain(conn, station_id, utc(observation['observed_at']))
            return True

    def _repair_rain(self, conn, station_id, observed):
        start=summaries.bucket(observed,300)
        rows=conn.execute("SELECT jsonb_build_object('observed_at',measurements->'observed_at','rain_total_mm',measurements->'rain_total_mm') FROM weather.observations WHERE station_id=%s AND observed_at>=%s AND observed_at<%s ORDER BY observed_at LIMIT 20001",(station_id,start,start+timedelta(seconds=300)))
        rain=summaries.rain_empty()
        for index,(row,) in enumerate(rows):
            if index>=20000:raise RuntimeError('Rain repair exceeds bounded raw capacity')
            rain=summaries.rain_merge(rain,summaries.single(row)['rain'])
        for width,child_width in ((300,None),(3600,300),(86400,3600)):
            at=summaries.bucket(observed,width)
            if child_width:
                rain=summaries.rain_empty()
                children=conn.execute('SELECT summary FROM weather.observation_rollups WHERE station_id=%s AND bucket_seconds=%s AND bucket_start>=%s AND bucket_start<%s ORDER BY bucket_start',(station_id,child_width,at,at+timedelta(seconds=width)))
                for (child,) in children:rain=summaries.rain_merge(rain,child.get('rain',summaries.rain_empty()))
            conn.execute("UPDATE weather.observation_rollups SET summary=jsonb_set(summary,'{rain}',%s::jsonb) WHERE station_id=%s AND bucket_seconds=%s AND bucket_start=%s",(json.dumps(rain,allow_nan=False),station_id,width,at))

    def earliest(self, station_id):
        with self.connection() as conn:
            row = conn.execute('SELECT observed_at FROM weather.observations WHERE station_id=%s ORDER BY observed_at LIMIT 1', (station_id,)).fetchone()
            return row[0] if row else None

    def history_summary(self, station_id, start, end, max_points=600, metric=None, zone='UTC'):
        width = summaries.source_resolution(start,end)
        interior_start = summaries.bucket(start,width)
        if interior_start < start:
            interior_start += timedelta(seconds=width)
        interior_end = summaries.bucket(end,width)
        pieces = {}
        output_width=summaries.output_width(start,end,max_points,width)
        def collect(at,summary):
            target=summaries.bucket(at,output_width)
            summaries.merge(pieces.setdefault(target,summaries.empty()),summary)
        with self.connection() as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            if interior_start < interior_end:
                with conn.cursor(name='weather_rollup_read') as rows:
                    rows.itersize=64
                    rows.execute('SELECT bucket_start, summary FROM weather.observation_rollups WHERE station_id=%s AND bucket_seconds=%s AND bucket_start>=%s AND bucket_start<%s ORDER BY bucket_start LIMIT 8001',(station_id,width,interior_start,interior_end))
                    for index,(at,summary) in enumerate(rows):
                        if index>=8000:
                            raise summaries.HistoryCapacityError('History range exceeds the source bucket budget; choose a narrower range')
                        collect(at,summary)
            boundaries = [(start,min(end,interior_start))]
            if interior_end >= interior_start and interior_end < end:
                boundaries.append((max(start,interior_end),end))
            for low, high in boundaries:
                if low >= high:
                    continue
                summary, seen = summaries.empty(), 0
                with conn.cursor(name='weather_raw_edge') as rows:
                    rows.itersize=64
                    rows.execute("SELECT measurements - 'raw_rf' - 'provenance' - 'unavailable_reasons' FROM weather.observations WHERE station_id=%s AND observed_at>=%s AND observed_at<%s ORDER BY observed_at LIMIT 20001",(station_id,low,high))
                    for (row,) in rows:
                        seen += 1
                        if seen > 20000:
                            raise summaries.HistoryCapacityError('Too many observations in a partial source bucket; align UTC bounds or choose a narrower range')
                        summaries.merge(summary,summaries.single(row))
                if summary['observation_count']:
                    collect(low,summary)
        return summaries.render(station_id,zone,start,end,max_points,metric,list(pieces.items()),width)

    def backfill_day(self, station_id, day):
        """Explicit bounded idempotent repair; never automatically called at startup.

        One UTC day per call, owner-controlled orchestration only. The station
        advisory lock excludes concurrent insert updates; replacing that day's
        three widths repairs late/old data without double counting.
        """
        start = summaries.bucket(day,86400)
        end = start+timedelta(days=1)
        with self.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 20261023))", (station_id,))
            rows=conn.execute("SELECT measurements - 'raw_rf' - 'provenance' - 'unavailable_reasons' FROM weather.observations WHERE station_id=%s AND observed_at>=%s AND observed_at<%s ORDER BY observed_at LIMIT 20001",(station_id,start,end))
            buckets={}
            for index,(row,) in enumerate(rows):
                if index >= 20000:
                    raise RuntimeError('Backfill day exceeds bounded capacity')
                for width in summaries.WIDTHS:
                    at=summaries.bucket(utc(row['observed_at']),width)
                    summaries.merge(buckets.setdefault((width,at),summaries.empty()),summaries.single(row))
            for (width,at),summary in buckets.items():
                conn.execute('INSERT INTO weather.observation_rollups(station_id,bucket_start,bucket_seconds,summary) VALUES(%s,%s,%s,%s::jsonb) ON CONFLICT(station_id,bucket_seconds,bucket_start) DO UPDATE SET summary=EXCLUDED.summary',(station_id,at,width,json.dumps(summary,allow_nan=False)))
        return len(buckets)

    def history(self, station_id, since):
        with self.connection() as conn:
            rows = conn.execute("SELECT measurements - 'raw_rf' - 'provenance' FROM weather.observations WHERE station_id=%s AND observed_at >= %s ORDER BY observed_at LIMIT 20001", (station_id, since)).fetchall()
            if len(rows)>20000:
                raise RuntimeError('Raw history capacity exceeded; use summaries')
            prior = conn.execute("SELECT measurements FROM weather.observations WHERE station_id=%s AND observed_at < %s AND measurements->>'rain_total_mm' IS NOT NULL ORDER BY observed_at DESC LIMIT 1", (station_id, since)).fetchone()
            derived = rain_intervals(([prior[0]] if prior else []) + [r[0] for r in rows])
            return derived[1:] if prior else derived

    def latest(self, station_id):
        with self.connection() as conn:
            row = conn.execute('SELECT measurements, observed_at FROM weather.observations WHERE station_id=%s ORDER BY observed_at DESC LIMIT 1', (station_id,)).fetchone()
            if not row:
                return None
            prior = conn.execute("SELECT jsonb_build_object('observed_at',measurements->'observed_at','rain_total_mm',measurements->'rain_total_mm') FROM weather.observations WHERE station_id=%s AND observed_at<%s AND measurements->>'rain_total_mm' IS NOT NULL ORDER BY observed_at DESC LIMIT 1",(station_id,row[1])).fetchone()
            return rain_intervals(([prior[0]] if prior else [])+[row[0]])[-1]

    def get_forecast(self, location_id):
        with self.connection() as conn:
            row = conn.execute('SELECT payload FROM weather.forecast_cache WHERE location_id=%s', (location_id,)).fetchone()
            return row[0] if row else None

    def put_forecast(self, location_id, value):
        with self.connection() as conn:
            conn.execute('INSERT INTO weather.forecast_cache (location_id,payload) VALUES (%s,%s::jsonb) ON CONFLICT (location_id) DO UPDATE SET payload=EXCLUDED.payload', (location_id, json.dumps(value)))
