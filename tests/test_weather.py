import io
import json
import os
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from weather import demo, forecast
from weather.domain import normalize, stamp
from weather.registry import resolve, validate_registry
from weather.server import Application, Server, handler
from weather.store import MemoryStore, PostgresStore

NOW = datetime.now(timezone.utc).replace(microsecond=0)

def packet(minutes=0, rain=10, **extra):
    return {'time': stamp(NOW + timedelta(minutes=minutes)), 'model': 'DEMO', 'id': '0-0', 'temperature_C': 20, 'rain_mm': rain, **extra}

def persistence_checks(test, store, sid, other):
    test.assertTrue(store.insert(sid, normalize(packet(-3, 10))))
    test.assertTrue(store.insert(sid, normalize(packet(-1, 13))))
    test.assertFalse(store.insert(sid, normalize(packet(-1, 99))))
    store.insert(sid, normalize(packet(-2, 11)))
    test.assertEqual(store.latest(sid)['rain_interval_mm'], 2)
    test.assertEqual(store.history(sid, NOW-timedelta(minutes=1))[0]['rain_interval_mm'], 2)
    store.insert(sid, normalize(packet(0, 1)))
    test.assertIsNone(store.latest(sid)['rain_interval_mm'])
    test.assertEqual(store.latest(sid)['rain_total_mm'], 1)
    test.assertIsNone(store.latest(other))
    test.assertEqual([r['rain_interval_mm'] for r in store.history(sid, NOW-timedelta(hours=1))], [None, 1, 2, None])

class DomainTests(unittest.TestCase):
    def test_duplicate_late_rain_reset_isolation(self):
        persistence_checks(self, MemoryStore(), 'one', 'other')

    def test_validation(self):
        for invalid in [packet(time='2026-01-01 12:00:00'), packet(time='2026-01-01T12:00:00+01:00'), packet(temperature_C=float('nan')), packet(humidity=101), packet(wind_avg_m_s=-1), packet(battery_ok='yes'), packet(10), packet(temperature_C=True)]:
            with self.subTest(packet=invalid), self.assertRaises(ValueError):
                normalize(invalid)

    def test_mapping(self):
        locations, _ = demo.build(NOW)
        self.assertEqual(resolve(validate_registry(locations), packet()), 'station-1-1')
        with self.assertRaises(ValueError):
            resolve(locations, packet(id='unknown'))
        locations[1]['stations'][0]['id'] = 'station-1-1'
        with self.assertRaises(ValueError):
            validate_registry(locations)

    def test_demo_contract(self):
        locations, store = demo.build(NOW)
        dashboard = Application(locations, store).dashboard()
        self.assertEqual(dashboard['mode'], 'demo')
        self.assertEqual(len(dashboard['locations']), 3)
        self.assertEqual(len(dashboard['locations'][0]['stations']), 2)
        self.assertEqual(dashboard['locations'][0]['forecast']['status'], 'demo')
        self.assertTrue(dashboard['locations'][2]['stations'][0]['stale'])
        self.assertFalse(dashboard['locations'][0]['stations'][0]['stale'])

    def test_database_gate(self):
        for url, gate in [('postgresql://localhost/other', 'nonproduction'), ('postgresql://localhost/my_pa?dbname=other', 'nonproduction'), ('postgresql://localhost/my_pa', '')]:
            with self.assertRaises(ValueError):
                PostgresStore(url, gate)

    def test_forecast_cache_failure_staleness(self):
        locations, store = demo.build(NOW)
        store.forecasts.clear()
        payload = {'daily': {'time': ['2026-10-23'], 'temperature_2m_min': [10], 'temperature_2m_max': [20], 'precipitation_probability_max': [30], 'weather_code': [3]}}
        def opener(request, timeout):
            self.assertEqual(timeout, 8)
            return io.BytesIO(json.dumps(payload).encode())
        self.assertTrue(forecast.refresh(store, locations[0], opener, NOW))
        self.assertEqual(forecast.cached(store, 'location-1', NOW)['status'], 'ok')
        def fail(*args, **kwargs):
            raise OSError('synthetic outage')
        self.assertFalse(forecast.refresh(store, locations[0], fail, NOW))
        self.assertEqual(forecast.cached(store, 'location-1', NOW+timedelta(hours=7))['status'], 'stale')
        payload['daily']['temperature_2m_min'] = [float('inf')]
        self.assertFalse(forecast.refresh(store, locations[0], opener, NOW))
        self.assertEqual(forecast.cached(store, 'other', NOW)['status'], 'unavailable')

class HttpTests(unittest.TestCase):
    def setUp(self):
        locations, store = demo.build(NOW)
        self.app = Application(locations, store, token='x'*32, allow_ingest=True)
        self.temp = tempfile.TemporaryDirectory()
        Path(self.temp.name, 'index.html').write_text('synthetic UI')
        self.server = Server(('127.0.0.1', 0), handler(self.app, self.temp.name))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, data=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        return urlopen(Request(self.base + path, data=data, headers=headers), timeout=3)

    def test_auth_and_duplicate(self):
        with self.request('/api/dashboard') as response:
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertEqual(json.load(response)['mode'], 'demo')
        raw = json.dumps(packet(-1)).encode()
        with self.assertRaises(HTTPError) as error:
            self.request('/api/ingest/rtl433', raw)
        self.assertEqual(error.exception.code, 401)
        error.exception.close()
        with self.request('/api/ingest/rtl433', raw, 'x'*32) as response:
            self.assertTrue(json.load(response)['inserted'])
        with self.request('/api/ingest/rtl433', raw, 'x'*32) as response:
            self.assertFalse(json.load(response)['inserted'])
        self.app.allow_ingest = False
        with self.assertRaises(HTTPError) as error:
            self.request('/api/ingest/rtl433', raw, 'x'*32)
        self.assertEqual(error.exception.code, 403)
        error.exception.close()

    def test_bounds_mapping_and_traversal(self):
        for path in ['/api/history?station_id=station-1-1&hours=169', '/api/history?station_id=unknown&hours=1', '/api/history?hours=nan', '/%2e%2e/pyproject.toml']:
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.request(path)
            self.assertIn(error.exception.code, (400, 404))
            error.exception.close()
        with self.request('/api/history?station_id=station-1-1&hours=24') as response:
            self.assertEqual(json.load(response)['hours'], 24)
        with self.assertRaises(HTTPError) as error:
            self.request('/api/ingest/rtl433', b' '*16385, 'x'*32)
        self.assertEqual(error.exception.code, 413)
        error.exception.close()
        with self.assertRaises(HTTPError) as error:
            self.request('/api/ingest/rtl433', json.dumps(packet(id='unknown')).encode(), 'x'*32)
        self.assertEqual(error.exception.code, 400)
        error.exception.close()
        Path(self.temp.name, 'link').symlink_to('/etc/hosts')
        with self.assertRaises(HTTPError) as error:
            self.request('/link')
        self.assertEqual(error.exception.code, 404)
        error.exception.close()

@unittest.skipUnless(os.environ.get('WEATHER_TEST_DATABASE_URL') and os.environ.get('WEATHER_TEST_DATABASE_CONFIRMED') == 'isolated', 'Requires authorized isolated PostgreSQL my_pa fixture')
class PostgresIntegrationTests(unittest.TestCase):
    def test_persistence_restart_and_scope(self):
        store = PostgresStore(os.environ['WEATHER_TEST_DATABASE_URL'], 'nonproduction')
        locations, _ = demo.build(NOW)
        suffix = uuid.uuid4().hex[:12]
        for location in locations:
            location['id'] += suffix
            for station in location['stations']:
                station['id'] += suffix
        store.sync_registry(locations)
        sid = locations[0]['stations'][0]['id']
        persistence_checks(self, store, sid, locations[1]['stations'][0]['id'])
        cache = {'source': 'synthetic test', 'fetched_at': stamp(NOW), 'status': 'ok', 'daily': []}
        store.put_forecast(locations[0]['id'], cache)
        reopened = PostgresStore(os.environ['WEATHER_TEST_DATABASE_URL'], 'nonproduction')
        self.assertEqual(reopened.get_forecast(locations[0]['id']), cache)
        self.assertEqual(reopened.latest(sid)['rain_total_mm'], 1)
        with store.connection() as conn:
            grants = conn.execute("SELECT has_schema_privilege(current_user,'public','CREATE'), has_schema_privilege(current_user,'weather','CREATE')").fetchone()
            self.assertEqual(grants, (False, False))


class ForwardTests(unittest.TestCase):
    def run_stream(self, outcomes):
        from types import SimpleNamespace
        from unittest.mock import patch, Mock
        from weather.__main__ import main
        stream = io.BytesIO(b'{"model":"neighbor","id":123}\n{"model":"DEMO","id":"0-0"}\n')
        opener = Mock()
        opener.open.side_effect = outcomes
        stderr = io.StringIO()
        with patch('weather.__main__.build_opener', return_value=opener), patch('weather.__main__.sys.argv', ['weather', 'forward']), patch('weather.__main__.sys.stdin', SimpleNamespace(buffer=stream)), patch('weather.__main__.sys.stderr', stderr), patch.dict(os.environ, {'WEATHER_INGEST_TOKEN': 'x'*32}):
            result = main()
        self.assertNotIn('neighbor', stderr.getvalue())
        self.assertNotIn('x'*32, stderr.getvalue())
        return result, opener

    def test_unknown_rejection_continues_to_valid_packet(self):
        error = HTTPError('http://localhost/api/ingest/rtl433', 400, 'synthetic rejection', {}, io.BytesIO(b''))
        result, opener = self.run_stream([error, io.BytesIO(b'{"inserted":true}')])
        self.assertEqual(result, 0)
        self.assertEqual(opener.open.call_count, 2)
        accepted_request = opener.open.call_args_list[1].args[0]
        self.assertEqual(json.loads(accepted_request.data)['id'], '0-0')

    def test_auth_and_transport_failure_stop_stream(self):
        for failure in [HTTPError('http://localhost/api/ingest/rtl433', 401, 'synthetic denied', {}, io.BytesIO(b'')), OSError('synthetic transport failure')]:
            with self.subTest(failure=type(failure).__name__):
                result, opener = self.run_stream([failure])
                self.assertEqual(result, 1)
                self.assertEqual(opener.open.call_count, 1)
