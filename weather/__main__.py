"""Entrypoints: demo server, authorized PostgreSQL mode, receiver forwarding."""
import argparse
import json
import os
import sys
import warnings
from pathlib import Path
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from . import demo, forecast, registry
from .auth import Auth
from .server import Application, Server, handler
from .store import PostgresStore


def secret_setting(name):
    """Read a value OR a mounted secret file; never echo secret contents."""
    value, filename = os.environ.get(name), os.environ.get(name + '_FILE')
    if value is not None and filename:
        raise ValueError('Use one secret configuration source')
    if filename:
        with open(filename, encoding='utf-8') as handle:
            value = handle.read(65537)
        if len(value) > 65536:
            raise ValueError('Secret file too large')
        value = value.rstrip('\r\n')
    return value or ''


def application():
    mode = os.environ.get('WEATHER_MODE', 'demo')
    if mode == 'demo':
        locations, store = demo.build()
        return Application(locations, store)
    if mode != 'postgres':
        raise ValueError('WEATHER_MODE must be demo or postgres')
    locations = registry.load(os.environ['WEATHER_REGISTRY'])
    token = secret_setting('WEATHER_INGEST_TOKEN')
    if len(token) < 32:
        raise ValueError('WEATHER_INGEST_TOKEN requires at least 32 characters')
    store = PostgresStore(secret_setting('WEATHER_DATABASE_URL'), os.environ.get('WEATHER_ALLOW_DATABASE'))
    store.sync_registry(locations)
    auth = Auth(store, os.environ.get('WEATHER_AUTH_ORIGIN', ''))
    return Application(locations, store, mode, token, allow_ingest=True, auth=auth)


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
    setup = commands.add_parser('setup-password', help='Set owner password through hidden interactive TTY prompts')
    setup.add_argument('--email', required=True)
    forward = commands.add_parser('forward', help='Forward bounded rtl_433 JSON lines from stdin')
    forward.add_argument('--url', default='http://127.0.0.1:8765/api/ingest/rtl433')
    args = parser.parse_args()
    try:
        if args.command == 'setup-password':
            import getpass
            if not sys.stdin.isatty() or not sys.stderr.isatty() or os.environ.get('WEATHER_MODE') != 'postgres':
                raise ValueError('Interactive PostgreSQL owner setup required')
            auth = Auth(PostgresStore(secret_setting('WEATHER_DATABASE_URL'), os.environ.get('WEATHER_ALLOW_DATABASE')), os.environ.get('WEATHER_AUTH_ORIGIN',''))
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                try:
                    password = getpass.getpass('New weather password (14–128 characters): ')
                    confirm = getpass.getpass('Confirm weather password: ')
                except getpass.GetPassWarning:
                    raise ValueError('Hidden terminal input unavailable') from None
            if password != confirm:
                raise ValueError('Password confirmation differs')
            auth.setup(args.email, password)
            print('Weather password updated; prior sessions revoked')
            return 0
        if args.command == 'forward':
            url = urlsplit(args.url)
            if url.scheme not in ('http', 'https') or url.username or url.password or url.query or url.fragment or url.path != '/api/ingest/rtl433':
                raise ValueError('Explicit receiver endpoint required')
            if url.scheme == 'http' and url.hostname not in ('127.0.0.1', 'localhost', '::1'):
                raise ValueError('Non-loopback receiver endpoints require HTTPS')
            token = secret_setting('WEATHER_INGEST_TOKEN')
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
                except HTTPError as error:
                    status = error.code
                    error.close()
                    if status == 400:
                        print('Receiver packet rejected; continuing stream', file=sys.stderr)
                        continue
                    print('Receiver delivery failed; packet not acknowledged', file=sys.stderr)
                    return 1
                except OSError:
                    print('Receiver delivery failed; packet not acknowledged', file=sys.stderr)
                    return 1
            return 0
        if args.command == 'refresh-forecasts':
            if os.environ.get('WEATHER_MODE', 'demo') != 'postgres':
                raise ValueError('Remote forecast refresh is disabled in synthetic demo mode')
            # Cache-only role: no Application construction, ingest secret or registry writes.
            try:
                locations = registry.load(os.environ['WEATHER_REGISTRY'])
                store = PostgresStore(secret_setting('WEATHER_DATABASE_URL'), os.environ.get('WEATHER_ALLOW_DATABASE'))
                successes = [forecast.refresh(store, location) for location in locations]
            except Exception:
                # Driver errors can include connection material; never print them.
                print('Forecast refresh failed; check configuration and cache-role readiness', file=sys.stderr)
                return 1
            print(f'Forecast refresh: {sum(successes)}/{len(successes)} locations')
            return 0 if all(successes) else 1
        app = application()
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
