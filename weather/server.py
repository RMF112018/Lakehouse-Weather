"""Small same-origin HTTP API; safe loopback defaults and bounded ingestion."""
import hmac
import json
import mimetypes
import os
import socket
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, unquote
from . import forecast
from .domain import normalize, stamp, utc
from .registry import resolve


class Application:
    def __init__(self, locations, store, mode='demo', token='', allow_ingest=False):
        self.locations, self.store, self.mode = locations, store, mode
        self.token = token
        self.allow_ingest = allow_ingest
        self.station_ids = {s['id'] for loc in locations for s in loc['stations']}

    def dashboard(self):
        now = datetime.now(timezone.utc)
        locations = []
        for location in self.locations:
            row = {key: location[key] for key in ('id', 'name', 'timezone', 'latitude', 'longitude')}
            stations = []
            for station in location['stations']:
                latest = self.store.latest(station['id'])
                stations.append({'id': station['id'], 'name': station['name'], 'model': station['model'], 'last_seen': latest['observed_at'] if latest else None, 'stale': latest is None or now - utc(latest['observed_at']) > timedelta(minutes=20), 'observation': latest, 'history': self.store.history(station['id'], now-timedelta(hours=48))})
            row.update(stations=stations, forecast=forecast.cached(self.store, location['id'], now))
            locations.append(row)
        return {'mode': self.mode, 'generated_at': stamp(now), 'locations': locations}

    def ingest(self, packet):
        station_id = resolve(self.locations, packet)
        observation = normalize(packet)
        return {'station_id': station_id, 'inserted': self.store.insert(station_id, observation)}


def dispatch(app, web_root, method, target, headers, stream):
    """One bounded HTTP contract shared by WSGI and the local demo adapter."""
    try:
        parsed = urlsplit(target)
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
                station = query.get('station_id', [''])[0]
                hours = int(query.get('hours', ['48'])[0])
                if station not in app.station_ids or not 1 <= hours <= 168:
                    return 400, {'error': 'Known station and hours between 1 and 168 required'}, None
                return 200, {'station_id': station, 'hours': hours, 'history': app.store.history(station, datetime.now(timezone.utc)-timedelta(hours=hours))}, None
            if parsed.path.startswith('/api/'):
                return 404, {'error': 'Not found'}, None
            root = Path(web_root).resolve()
            relative = unquote(parsed.path).lstrip('/') or 'index.html'
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
    except (ValueError, TypeError, UnicodeError):
        return 400, {'error': 'Invalid request or sensor identity'}, None
    except (socket.timeout, TimeoutError):
        return 408, {'error': 'Request timed out'}, None
    except Exception:
        return 503, {'error': 'Weather service unavailable'}, None


def response(status, value, content_type=None):
    content_type = content_type or 'application/json; charset=utf-8'
    raw = json.dumps(value, allow_nan=False).encode() if content_type.startswith('application/json') else value
    headers = [('Content-Type', content_type), ('Content-Length', str(len(raw))),
               ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
               ('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"),
               ('Referrer-Policy', 'no-referrer')]
    return status, headers, raw


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
