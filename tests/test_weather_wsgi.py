"""Transport contract without a network or real credentials."""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from weather import demo, forecast
from weather.__main__ import secret_setting
from weather.registry import validate_registry, resolve
from weather.server import Application, wsgi


class WsgiTests(unittest.TestCase):
    def setUp(self):
        locations, store = demo.build()
        self.app = Application(locations, store, token='synthetic-' * 4, allow_ingest=True)
        self.temp = tempfile.TemporaryDirectory()
        Path(self.temp.name, 'index.html').write_text('synthetic UI')
        self.call = wsgi(self.app, self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def request(self, path, method='GET', body=b'', **extra):
        env = {'REQUEST_METHOD': method, 'PATH_INFO': path, 'QUERY_STRING': '',
               'wsgi.input': io.BytesIO(body), 'CONTENT_LENGTH': str(len(body)),
               'CONTENT_TYPE': 'application/json', **extra}
        self.result = None
        def start(status, headers):
            self.result = int(status.split()[0]), dict(headers)
        raw = b''.join(self.call(env, start))
        status, headers = self.result
        self.assertEqual(int(headers['Content-Length']), len(raw))
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        return status, raw

    def test_liveness_and_dependency_readiness(self):
        self.assertEqual(self.request('/api/health')[0], 200)
        self.assertEqual(self.request('/api/ready')[0], 200)
        self.app.store.check_ready = Mock(side_effect=RuntimeError('synthetic confidential detail'))
        self.assertEqual(self.request('/api/health')[0], 200)
        status, raw = self.request('/api/ready')
        self.assertEqual(status, 503)
        self.assertNotIn(b'confidential', raw)

    def test_ingest_auth_bounds_framing_and_object(self):
        path = '/api/ingest/rtl433'
        auth = {'HTTP_AUTHORIZATION': 'Bearer ' + self.app.token}
        self.assertEqual(self.request(path, 'POST', b'{}')[0], 401)
        self.assertEqual(self.request(path, 'POST', b'{}', **auth, HTTP_TRANSFER_ENCODING='chunked')[0], 400)
        self.assertEqual(self.request(path, 'POST', b'{}', **auth, CONTENT_LENGTH='-1')[0], 413)
        self.assertEqual(self.request(path, 'POST', b'{}', **auth, CONTENT_LENGTH='16385')[0], 413)
        self.assertEqual(self.request(path, 'POST', b'{}', **auth, CONTENT_LENGTH='4')[0], 400)
        self.assertEqual(self.request(path, 'POST', b'[]', **auth)[0], 400)
        self.assertEqual(self.request(path, 'POST', b'{}', **auth, CONTENT_LENGTH='bogus')[0], 400)
        self.assertEqual(self.request(path, 'PUT')[0], 405)

    def test_paths_prefix_mount_and_proxy_headers(self):
        self.assertEqual(self.request('/')[1], b'synthetic UI')
        self.assertEqual(self.request('/../pyproject.toml')[0], 404)
        Path(self.temp.name, 'link').symlink_to('/etc/hosts')
        self.assertEqual(self.request('/link')[0], 404)
        # WSGI PATH_INFO excludes the prefix. Client forwarding headers do not rewrite it.
        self.assertEqual(self.request('/api/dashboard', SCRIPT_NAME='/weather', HTTP_PATH_INFO='/', HTTP_SCRIPT_NAME='/attacker')[0], 200)
        self.assertEqual(self.request('/weather/api/dashboard')[0], 404)
        self.app.dashboard = Mock(side_effect=RuntimeError('synthetic secret'))
        status, raw = self.request('/api/dashboard')
        self.assertEqual(status, 503)
        self.assertNotIn(b'synthetic secret', raw)

    def test_pending_coordinates_and_uncommissioned_receiver(self):
        locations, store = demo.build()
        loc = locations[0]
        loc.update(latitude=None, longitude=None)
        station = loc['stations'][0]
        station['ingest_enabled'] = False
        self.assertIs(validate_registry(locations), locations)
        with self.assertRaises(ValueError):
            resolve(locations, {'model': station['receiver_model'], 'id': station['sensor_id']})
        opener = Mock()
        store.forecasts.clear()
        self.assertFalse(forecast.refresh(store, loc, opener))
        opener.assert_not_called()
        self.assertEqual(forecast.cached(store, loc['id'], None)['status'], 'unavailable')
        loc['latitude'] = 0
        with self.assertRaises(ValueError):
            validate_registry(locations)

    def test_secret_file_source_exclusivity_and_bounds(self):
        # Only synthetic values created by this test are opened.
        path = Path(self.temp.name, 'synthetic-secret')
        path.write_text('synthetic-value\n')
        with patch.dict(os.environ, {'TEST_WEATHER_SECRET_FILE': str(path)}, clear=True):
            self.assertEqual(secret_setting('TEST_WEATHER_SECRET'), 'synthetic-value')
            with patch.dict(os.environ, {'TEST_WEATHER_SECRET': 'conflict'}), self.assertRaises(ValueError):
                secret_setting('TEST_WEATHER_SECRET')
            path.write_text('s' * 65537)
            with self.assertRaises(ValueError):
                secret_setting('TEST_WEATHER_SECRET')
