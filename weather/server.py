"""Small same-origin HTTP API; safe loopback defaults and bounded ingestion."""
import hmac
import json
import mimetypes
import stat
import math
import os
import socket
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, unquote
from . import forecast
from .domain import normalize, stamp, utc, CATALOG
from .history import request_range, HistoryCapacityError
from .registry import admit, validate_registry
from .composite import assemble
from .store import ObservationConflict


class Application:
    def __init__(self, locations, store, mode='demo', token='', allow_ingest=False, auth=None, rf_status_path=None):
        # Empty installations support authentication-only startup and readiness.
        # File-backed registries retain their nonempty validation contract.
        validated = [] if isinstance(locations, list) and not locations else validate_registry(locations)
        self.locations, self.store, self.mode = validated, store, mode
        self.token = token
        self.auth = auth
        self.rf_status_path = rf_status_path or ('/var/lib/weather-rf/status.json' if mode != 'demo' else None)
        if mode != 'demo' and auth is None:
            raise ValueError('Password authentication required')
        self.allow_ingest = allow_ingest
        self.groups = {g['id']:(loc,g) for loc in locations for g in loc.get('physical_stations',[])}
        self.station_ids = {s['id'] for loc in locations for s in loc['stations']}
        self.station_zones = {s['id']:loc['timezone'] for loc in locations for s in loc['stations']}

    def dashboard(self):
        now = datetime.now(timezone.utc)
        locations = []
        for location in self.locations:
            row = {key: location[key] for key in ('id', 'name', 'timezone', 'latitude', 'longitude')}
            stations = []
            for station in location['stations']:
                latest = self.store.latest(station['id'])
                history = self.store.history_summary(station['id'], now-timedelta(hours=48), now, max_points=200, zone=location['timezone'])
                stations.append({'id': station['id'], 'name': station['name'], 'model': station['model'], 'last_seen': latest['observed_at'] if latest else None, 'stale': latest is None or now - utc(latest['observed_at']) > timedelta(minutes=20), 'observation': latest, 'history': history['history'], 'history_summary': {key:history[key] for key in ('start','end','bucket_seconds','total_observations','coverage')}, 'available_metrics': [key for key in CATALOG if latest and latest.get(key) is not None]})
            row['physical_stations'] = [assemble(group, location['stations'], self.store, now) for group in location.get('physical_stations',[])]
            row.update(stations=stations, forecast=forecast.cached(self.store, location['id'], now))
            locations.append(row)
        return {'rf_status':self.rf_status(now), 'mode': self.mode, 'generated_at': stamp(now), 'locations': locations, 'sensor_catalog': CATALOG}

    def rf_status(self, now):
        result = {'status':'unknown'}
        if not self.rf_status_path:
            return result
        try:
            fd = os.open(self.rf_status_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 32768:
                    return result
                raw = handle.read(32769)
            if len(raw) > 32768:
                return result
            value = json.loads(raw)
            if not isinstance(value,dict):
                return result
            for key in ('last_receipt_utc','last_commit_utc','updated_at_utc','generated_at_utc'):
                if value.get(key) is not None:
                    result[key] = stamp(utc(value[key]))
            for key in ('accepted','rejected','duplicates','conflicts','pending_count','pending_bytes','oldest_pending_age_seconds'):
                number = value.get(key)
                if type(number) in (int,float) and math.isfinite(number) and 0 <= number <= 1e18:
                    result[key] = number
            code = value.get('error_code')
            if code in ('none','capacity','pending_age_limit','database_unavailable','observation_conflict','journal_full','journal_age_limit','store_unavailable','conflict','capture_stopped'):
                result['error_code'] = code
            at = result.get('updated_at_utc') or result.get('generated_at_utc') or result.get('last_receipt_utc')
            result['status'] = 'unknown' if not at else 'stale_status' if not 0 <= (now-utc(at)).total_seconds() <= 120 else 'available'
        except (OSError,ValueError,TypeError,UnicodeError):
            return {'status':'unknown'}
        return result

    def ingest(self, packet, trusted_context=None):
        station_id = admit(self.locations, packet, trusted_context)
        observation = normalize(packet, trusted_context=trusted_context)
        return {'station_id': station_id, 'inserted': self.store.insert(station_id, observation)}


def dispatch(app, web_root, method, target, headers, stream):
    """One bounded HTTP contract shared by WSGI and the local demo adapter."""
    try:
        parsed = urlsplit(target)
        if app.auth:
            if parsed.path.startswith('/api/auth/'):
                body = {}
                if method == 'POST':
                    if headers.get('transfer-encoding') or headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                        return 400, {'error':'JSON required'}, None
                    length = int(headers.get('content-length', '0'))
                    if not 1 <= length <= 2048:
                        return 413, {'error':'Body too large'}, None
                    raw = stream.read(length)
                    if len(raw) != length:
                        return 400, {'error':'Incomplete body'}, None
                    body = json.loads(raw)
                    if not isinstance(body,dict):
                        return 400, {'error':'Invalid request'}, None
                return app.auth.handle(method,parsed.path,headers,body)
            public = method == 'GET' and parsed.path in ('/login','/login.css','/login.js')
            ingest = method == 'POST' and parsed.path == '/api/ingest/rtl433'
            if not public and not ingest and not app.auth.session(headers):
                if method == 'GET' and parsed.path in ('/', '/index.html'):
                    return 303, {'error':'Sign in required'}, None, [('Location','/weather/login')]
                return 401, {'error':'Sign in required'}, None
        if method == 'GET':
            if parsed.path == '/api/health':
                return 200, {'status': 'ok'}, None
            if parsed.path == '/api/ready':
                app.store.check_ready()
                return 200, {'status': 'ready', 'mode': app.mode}, None
            if parsed.path == '/api/dashboard':
                return 200, app.dashboard(), None
            if parsed.path == '/api/history':
                query = parse_qs(parsed.query, strict_parsing=True, max_num_fields=8)
                group_id = query.get('physical_station_id', [''])[0]
                if group_id:
                    if 'station_id' in query or len(query.get('physical_station_id',[])) != 1 or len(query.get('metric',[])) != 1 or group_id not in app.groups:
                        raise ValueError('Invalid physical history selector')
                    group = app.groups[group_id][1]
                    station = group['metric_sources'].get(query['metric'][0])
                    if not station:
                        raise ValueError('Unsupported physical metric')
                else:
                    station = query.get('station_id', [''])[0]
                if station not in app.station_ids:
                    return 400, {'error': 'Known station required'}, None
                try:
                    start,end,limit,metric,zone = request_range(query, app.station_zones[station], earliest=app.store.earliest(station) if query.get('range') == ['all'] else None)
                except (ValueError, TypeError) as error:
                    safe = {'Duplicate history parameter','Timezone must match station location','max_points must be between 2 and 800','Unknown metric','Local wall time must not contain an offset','Local time is ambiguous or nonexistent; specify explicit UTC bounds','Choose range or hours','Choose local or UTC bounds','Legacy hours must be between 1 and 168','Unknown history range','Invalid history bounds','Bounds require custom range','Timestamp must be ISO 8601 with UTC offset','Timestamp must include explicit UTC offset'}
                    message = str(error) if str(error) in safe else 'Invalid history range or timestamp'
                    return 400, {'error':message}, None
                result = app.store.history_summary(station,start,end,limit,metric,zone)
                if group_id:
                    result['resolved_source_station_id'] = station
                    result['physical_station_id'] = group_id
                if 'hours' in query:
                    result['hours'] = int(query['hours'][0])
                return 200, result, None
            if parsed.path.startswith('/api/'):
                return 404, {'error': 'Not found'}, None
            root = Path(web_root).resolve()
            relative = ('login.html' if parsed.path == '/login' else unquote(parsed.path).lstrip('/')) or 'index.html'
            path = root / relative
            if '..' in Path(relative).parts or any(p.is_symlink() for p in [path, *path.parents]) or not path.resolve().is_relative_to(root) or not path.is_file():
                return 404, {'error': 'Not found'}, None
            return 200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        if method != 'POST':
            return 405, {'error': 'Method not allowed'}, None
        if parsed.path != '/api/ingest/rtl433':
            return 404, {'error': 'Not found'}, None
        if not app.allow_ingest or not app.token:
            return 403, {'error': 'Ingestion is disabled'}, None
        supplied = headers.get('authorization', '')
        if not hmac.compare_digest(supplied.encode(), ('Bearer ' + app.token).encode()):
            return 401, {'error': 'Unauthorized'}, None
        if headers.get('transfer-encoding') or headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
            return 400, {'error': 'JSON with Content-Length required'}, None
        length = int(headers.get('content-length', '0'))
        if not 1 <= length <= 16384:
            return 413, {'error': 'Body must be between 1 and 16384 bytes'}, None
        raw = stream.read(length)
        if len(raw) != length:
            return 400, {'error': 'Incomplete body'}, None
        packet = json.loads(raw)
        if not isinstance(packet, dict):
            raise ValueError('Packet object required')
        return 200, app.ingest(packet), None
    except ObservationConflict:
        return 409, {'error':'Conflicting RF observation'}, None
    except HistoryCapacityError as error:
        return 422, {'error':str(error)}, None
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return 400, {'error': 'Invalid request or sensor identity'}, None
    except (socket.timeout, TimeoutError):
        return 408, {'error': 'Request timed out'}, None
    except Exception:
        return 503, {'error': 'Weather service unavailable'}, None


def response(status, value, content_type=None, extra_headers=None):
    content_type = content_type or 'application/json; charset=utf-8'
    raw = json.dumps(value, allow_nan=False).encode() if content_type.startswith('application/json') else value
    headers = [('Content-Type', content_type), ('Content-Length', str(len(raw))),
               ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
               ('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"),
               ('Referrer-Policy', 'no-referrer')]
    return status, headers + (extra_headers or []), raw


def wsgi(app, web_root):
    """WSGI callable. Proxy strips /weather/; SCRIPT_NAME is never inferred from headers."""
    from http import HTTPStatus
    def application(environ, start_response):
        headers = {key[5:].replace('_', '-').lower(): value for key, value in environ.items() if key.startswith('HTTP_')}
        headers.update({'content-type': environ.get('CONTENT_TYPE', ''), 'content-length': environ.get('CONTENT_LENGTH', '')})
        # PATH_INFO is already percent-decoded by WSGI. Quote it once to share
        # the exact traversal checks with the stdlib transport.
        from urllib.parse import quote
        target = quote(environ.get('PATH_INFO', '/'), safe='/') + '?' + environ.get('QUERY_STRING', '')
        result = dispatch(app, web_root, environ['REQUEST_METHOD'], target, headers, environ['wsgi.input'])
        status, response_headers, raw = response(*result)
        start_response(f'{status} {HTTPStatus(status).phrase}', response_headers)
        return [raw]
    return application


def handler(app, web_root):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'LakehouseWeather'
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass  # Never log paths, headers, bodies or tokens.

        def handle_request(self):
            self.close_connection = True
            result = dispatch(app, web_root, self.command, self.path,
                              {key.lower(): value for key, value in self.headers.items()}, self.rfile)
            status, headers, raw = response(*result)
            self.send_response(status)
            for key, value in headers:
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(raw)

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = handle_request
    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # Bound simultaneous handlers, including slow clients.
    def __init__(self, *args, **kwargs):
        import threading
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()
