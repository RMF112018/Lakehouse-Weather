"""Memory demo and explicitly gated PostgreSQL persistence, never schema creation."""
import copy
import json
import threading
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
            rows[key] = dict(observation)
            return True

    def history(self, station_id, since):
        with self.lock:
            rows = rain_intervals(sorted(self.rows.get(station_id, {}).values(), key=lambda r: r['observed_at']))
            return [r for r in rows if utc(r['observed_at']) >= since]

    def latest(self, station_id):
        with self.lock:
            rows = rain_intervals(sorted(self.rows.get(station_id, {}).values(), key=lambda r: r['observed_at']))
            return rows[-1] if rows else None

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
            return conn.execute('INSERT INTO weather.observations (station_id, observed_at, measurements) VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING RETURNING station_id', (station_id, observation['observed_at'], json.dumps(observation))).fetchone() is not None

    def history(self, station_id, since):
        with self.connection() as conn:
            rows = conn.execute('SELECT measurements FROM weather.observations WHERE station_id=%s AND observed_at >= %s ORDER BY observed_at', (station_id, since)).fetchall()
            prior = conn.execute("SELECT measurements FROM weather.observations WHERE station_id=%s AND observed_at < %s AND measurements->>'rain_total_mm' IS NOT NULL ORDER BY observed_at DESC LIMIT 1", (station_id, since)).fetchone()
            derived = rain_intervals(([prior[0]] if prior else []) + [r[0] for r in rows])
            return derived[1:] if prior else derived

    def latest(self, station_id):
        with self.connection() as conn:
            row = conn.execute('SELECT measurements, observed_at FROM weather.observations WHERE station_id=%s ORDER BY observed_at DESC LIMIT 1', (station_id,)).fetchone()
            if not row:
                return None
            return self.history(station_id, row[1])[-1]

    def get_forecast(self, location_id):
        with self.connection() as conn:
            row = conn.execute('SELECT payload FROM weather.forecast_cache WHERE location_id=%s', (location_id,)).fetchone()
            return row[0] if row else None

    def put_forecast(self, location_id, value):
        with self.connection() as conn:
            conn.execute('INSERT INTO weather.forecast_cache (location_id,payload) VALUES (%s,%s::jsonb) ON CONFLICT (location_id) DO UPDATE SET payload=EXCLUDED.payload', (location_id, json.dumps(value)))
