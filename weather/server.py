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


def handler(app, web_root):
    root = Path(web_root).resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = 'LakehouseWeather'
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass  # Do not log paths, headers, bodies or tokens.

        def send_data(self, status, value, content_type='application/json; charset=utf-8'):
            raw = json.dumps(value, allow_nan=False).encode() if content_type.startswith('application/json') else value
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            try:
                parsed = urlsplit(self.path)
                if parsed.path == '/api/dashboard':
                    return self.send_data(200, app.dashboard())
                if parsed.path == '/api/history':
                    query = parse_qs(parsed.query, strict_parsing=True)
                    station = query.get('station_id', [''])[0]
                    hours = int(query.get('hours', ['48'])[0])
                    if station not in app.station_ids or not 1 <= hours <= 168:
                        return self.send_data(400, {'error': 'Known station and hours between 1 and 168 required'})
                    return self.send_data(200, {'station_id': station, 'hours': hours, 'history': app.store.history(station, datetime.now(timezone.utc)-timedelta(hours=hours))})
                if parsed.path.startswith('/api/'):
                    return self.send_data(404, {'error': 'Not found'})
                relative = unquote(parsed.path).lstrip('/') or 'index.html'
                path = root / relative
                if '..' in Path(relative).parts or any(p.is_symlink() for p in [path, *path.parents]) or not path.resolve().is_relative_to(root) or not path.is_file():
                    return self.send_data(404, {'error': 'Not found'})
                return self.send_data(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            except (ValueError, TypeError):
                self.send_data(400, {'error': 'Invalid request'})
            except Exception:
                self.send_data(503, {'error': 'Weather service unavailable'})

        def do_POST(self):
            self.close_connection = True
            try:
                if urlsplit(self.path).path != '/api/ingest/rtl433':
                    return self.send_data(404, {'error': 'Not found'})
                if not app.allow_ingest or not app.token:
                    return self.send_data(403, {'error': 'Ingestion is disabled'})
                supplied = self.headers.get('Authorization', '')
                if not hmac.compare_digest(supplied.encode(), ('Bearer ' + app.token).encode()):
                    return self.send_data(401, {'error': 'Unauthorized'})
                if self.headers.get('Transfer-Encoding') or self.headers.get_content_type() != 'application/json':
                    return self.send_data(400, {'error': 'JSON with Content-Length required'})
                length = int(self.headers.get('Content-Length', '0'))
                if not 1 <= length <= 16384:
                    return self.send_data(413, {'error': 'Body must be between 1 and 16384 bytes'})
                raw = self.rfile.read(length)
                if len(raw) != length:
                    return self.send_data(400, {'error': 'Incomplete body'})
                packet = json.loads(raw)
                if not isinstance(packet, dict):
                    raise ValueError('Packet object required')
                return self.send_data(200, app.ingest(packet))
            except (ValueError, TypeError, UnicodeError):
                self.send_data(400, {'error': 'Invalid sensor packet or station identity'})
            except (socket.timeout, TimeoutError):
                self.send_data(408, {'error': 'Request timed out'})
            except Exception:
                self.send_data(503, {'error': 'Weather service unavailable'})
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
