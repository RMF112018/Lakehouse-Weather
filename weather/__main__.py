"""Entrypoints: demo server, authorized PostgreSQL mode, receiver forwarding."""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from . import demo, forecast, registry
from .server import Application, Server, handler
from .store import PostgresStore


def application():
    mode = os.environ.get('WEATHER_MODE', 'demo')
    if mode == 'demo':
        locations, store = demo.build()
        return Application(locations, store)
    if mode != 'postgres':
        raise ValueError('WEATHER_MODE must be demo or postgres')
    locations = registry.load(os.environ['WEATHER_REGISTRY'])
    token = os.environ.get('WEATHER_INGEST_TOKEN', '')
    if len(token) < 32:
        raise ValueError('WEATHER_INGEST_TOKEN requires at least 32 characters')
    store = PostgresStore(os.environ['WEATHER_DATABASE_URL'], os.environ.get('WEATHER_ALLOW_DATABASE'))
    store.sync_registry(locations)
    return Application(locations, store, mode, token, allow_ingest=True)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description='Lakehouse Weather (synthetic demo by default)')
    commands = parser.add_subparsers(dest='command', required=True)
    serve = commands.add_parser('serve')
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', default=8765, type=int)
    commands.add_parser('refresh-forecasts')
    forward = commands.add_parser('forward', help='Forward bounded rtl_433 JSON lines from stdin')
    forward.add_argument('--url', default='http://127.0.0.1:8765/api/ingest/rtl433')
    args = parser.parse_args()
    try:
        if args.command == 'forward':
            url = urlsplit(args.url)
            if url.scheme not in ('http', 'https') or url.username or url.password or url.query or url.fragment or url.path != '/api/ingest/rtl433':
                raise ValueError('Explicit receiver endpoint required')
            if url.scheme == 'http' and url.hostname not in ('127.0.0.1', 'localhost', '::1'):
                raise ValueError('Non-loopback receiver endpoints require HTTPS')
            token = os.environ.get('WEATHER_INGEST_TOKEN', '')
            if len(token) < 32:
                raise ValueError('Receiver token required')
            while True:
                line = sys.stdin.buffer.readline(16386)
                if not line:
                    break
                if len(line) > 16384:
                    raise ValueError('Receiver packet too large')
                if not line.strip():
                    continue
                packet = json.loads(line)
                if not isinstance(packet, dict):
                    raise ValueError('Receiver packet object required')
                # rtl_433 -M time:utc emits a documented naive UTC timestamp.
                # Convert only in this explicit bridge, never in the ingest API.
                time = packet.get('time', '')
                if isinstance(time, str) and len(time) == 19:
                    packet['time'] = time.replace(' ', 'T') + 'Z'
                request = Request(args.url, data=json.dumps(packet).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}, method='POST')
                try:
                    with build_opener(NoRedirect).open(request, timeout=10) as response:
                        response.read(4096)
                except OSError:
                    print('Receiver delivery failed; packet not acknowledged', file=sys.stderr)
                    return 1
            return 0
        app = application()
        if args.command == 'refresh-forecasts':
            if app.mode != 'postgres':
                raise ValueError('Remote forecast refresh is disabled in synthetic demo mode')
            successes = [forecast.refresh(app.store, location) for location in app.locations]
            print(f'Forecast refresh: {sum(successes)}/{len(successes)} locations')
            return 0 if all(successes) else 1
        web_root = Path(__file__).resolve().parents[1] / 'web'
        with Server((args.host, args.port), handler(app, web_root)) as server:
            print(f'Weather dashboard mode={app.mode} listening at {args.host}:{args.port}', flush=True)
            server.serve_forever()
    except (ValueError, KeyError, ImportError, OSError):
        # Never print driver exceptions: they may contain connection credentials.
        print('Weather startup/request failed; check non-secret configuration and database readiness', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
