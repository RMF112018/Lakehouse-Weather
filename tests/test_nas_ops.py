"""NAS contracts verified without connecting to Docker or reading secrets."""
import contextlib
import ast
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
NAS = ROOT / 'ops' / 'nas'


def load(name):
    spec = importlib.util.spec_from_file_location(name, NAS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load('runtime')
sys.modules.setdefault('runtime', runtime)
backup = load('backup_weather')
prepare = load('prepare_runtime')


class NASContracts(unittest.TestCase):
    def test_compose_additive_hardened(self):
        text = (ROOT / 'compose.dashboard.production.yaml').read_text()
        for required in ['platform: linux/amd64', 'pull_policy: never', 'user: "10001:10001"', 'read_only: true', 'cap_drop: [ALL]', 'no-new-privileges:true', 'restart: unless-stopped', 'mem_limit: 256m', 'WEATHER_ALLOW_DATABASE: production', 'WEATHER_DATABASE_URL_FILE:', 'WEATHER_INGEST_TOKEN_FILE:', 'PostgresStore', 'check_ready()']:
            self.assertIn(required, text)
        self.assertEqual(text.count('external: true'), 2)
        dashboard, forecast = text.split('  forecast:', 1)
        self.assertNotIn('command:', dashboard)
        self.assertNotIn('ingest-token', forecast)
        self.assertIn('WEATHER_AUTH_ORIGIN: https://www.bobby-fetting.me', dashboard)
        self.assertNotIn('WEATHER_AUTH_ORIGIN', forecast)
        self.assertNotIn('WEATHER_DATABASE_URL_PATH', forecast)
        self.assertIn('WEATHER_FORECAST_DATABASE_URL_PATH', forecast)
        self.assertIn('condition: service_healthy', forecast)
        for forbidden in ['ports:', 'build:', 'docker.sock', 'postgres:']:
            self.assertNotIn(forbidden, text)



    def test_nas_supported_memory_and_uid_rlimits_without_missing_cgroups(self):
        text = (ROOT / 'compose.dashboard.production.yaml').read_text()
        dashboard, forecast = text.split('  forecast:', 1)
        forecast = forecast.split('\nnetworks:', 1)[0]
        self.assertIn('mem_limit: 256m', dashboard)
        self.assertIn('mem_limit: 128m', forecast)
        for service in (dashboard, forecast):
            self.assertNotRegex(service, r'(?m)^\s*(cpus|cpu_quota|cpu_period|cpu_shares|pids_limit):')
            self.assertRegex(service, r'ulimits:\n      nproc:\n        soft: 256\n        hard: 256\n      nofile:\n        soft: 256\n        hard: 256')
            self.assertIn('user: "10001:10001"', service)
            self.assertIn('read_only: true', service)
            self.assertIn('cap_drop: [ALL]', service)
            self.assertIn('no-new-privileges:true', service)

    def test_private_health_probe_without_password_or_http_and_redacted_failure(self):
        from weather import __main__ as cli
        from weather import store
        text = (ROOT / 'compose.dashboard.production.yaml').read_text().split('  forecast:', 1)[0]
        line = next(line for line in text.splitlines() if line.strip().startswith('test:'))
        command = ast.literal_eval(line.split('test: ', 1)[1])
        code = command[-1]
        self.assertEqual(command[:3], ['CMD', 'python', '-c'])
        self.assertNotIn('urllib', code)
        self.assertNotIn('application()', code)
        self.assertNotIn('Auth', code)
        with patch.dict(cli.os.environ, {'WEATHER_MODE': 'postgres', 'WEATHER_ALLOW_DATABASE': 'production'}, clear=True), patch.object(cli, 'secret_setting', return_value='opaque-fixture') as secret, patch.object(store, 'PostgresStore') as postgres, patch.object(cli.os, 'kill') as kill:
            exec(code, {})
            kill.assert_called_once_with(1, 0)
            secret.assert_called_once_with('WEATHER_DATABASE_URL')
            postgres.return_value.check_ready.assert_called_once()
            postgres.return_value.check_ready.side_effect = RuntimeError('must-not-appear-in-health-output')
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as failure:
                exec(code, {})
            self.assertEqual(failure.exception.code, 1)
            self.assertEqual(stdout.getvalue() + stderr.getvalue(), '')

    def test_all_runtime_dry_runs_have_no_side_effect(self):
        with patch.object(runtime, 'docker', side_effect=AssertionError('Docker touched')):
            for action in ['admit', 'status', 'stop']:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(runtime.main([action]), 0)

    def test_identity_rejects_mutable_tag_before_docker(self):
        with patch.object(runtime, 'docker', side_effect=AssertionError('Docker touched')):
            with self.assertRaises(ValueError):
                runtime.identity('weather:latest', 'a' * 40, 'b' * 40)

    def test_identity_authenticates_image_network_container_and_gunicorn(self):
        image, head, tree = 'sha256:' + 'c' * 64, 'a' * 40, 'b' * 40
        def fields(kind, target, expression):
            if kind == 'image':
                if expression == '{{.Id}}': return image
                if expression == '{{.Os}}/{{.Architecture}}': return 'linux/amd64'
                if 'source-tree' in expression: return tree
                if 'revision' in expression: return head
                if expression == '{{.Config.User}}': return '10001:10001'
                if expression == '{{json .Config.Cmd}}': return json.dumps(['gunicorn', '--config', 'python:weather.gunicorn_config', 'weather.wsgi:create_app()'])
                if expression == '{{json .Config.Entrypoint}}': return 'null'
            if kind == 'network':
                return 'true' if expression == '{{.Internal}}' else runtime.NETWORKS[target]
            if expression == '{{.Id}}': return runtime.PG_ID
            return json.dumps({'my-pa-nas-contract_data-plane': {'NetworkID': runtime.NETWORKS['my-pa-nas-contract_data-plane']}})
        with patch.object(runtime, 'field', side_effect=fields):
            runtime.identity(image, head, tree)
        with patch.object(runtime, 'field', return_value='unexpected'):
            with self.assertRaises(ValueError): runtime.identity(image, head, tree)

    def test_stop_refuses_unowned_container(self):
        with patch.object(runtime, 'field', return_value='other-project'), patch.object(runtime, 'docker', return_value='existing') as docker:
            with self.assertRaises(ValueError): runtime.main(['stop', '--apply'])
            self.assertTrue(all('stop' not in call.args for call in docker.call_args_list))

    def test_mounts_checked_without_reading_secret(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'secret'
            path.touch(mode=0o400)
            self.assertEqual(runtime.mount_path(str(path), True), str(path))
            path.chmod(0o644)
            with self.assertRaises(ValueError): runtime.mount_path(str(path), True)

    def test_backup_dry_run_never_connects(self):
        with patch.object(backup, 'field', side_effect=AssertionError('Docker touched')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(backup.main(['--destination', '/uncreated/path']), 0)

    def test_backup_scope_and_failure_manifest_contract(self):
        text = (NAS / 'backup_weather.py').read_text()
        for required in ["'--schema=weather'", "'--strict-names'", "'--no-owner'", "'--no-privileges'", "'restore_rehearsed': False", "archive.open('xb')"]:
            self.assertIn(required, text)
        self.assertNotIn("'--clean'", text)

    def test_prepare_token_dry_run_and_wrong_target(self):
        with patch.object(prepare.secrets, 'token_urlsafe', side_effect=AssertionError('Token generated')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(prepare.main(['--secret-dir', str(prepare.SECRET_DIR)]), 0)
            with self.assertRaises(ValueError): prepare.main(['--secret-dir', '/tmp/unapproved', '--apply'])



    def test_secret_parent_root_custody_and_file_only_ownership(self):
        path = unittest.mock.Mock()
        path.parent.is_dir.return_value = True
        path.parent.resolve.return_value = path.parent
        path.parent.stat.return_value = SimpleNamespace(st_uid=0, st_mode=0o755)
        path.exists.return_value = True
        path.is_symlink.return_value = False
        path.is_dir.return_value = True
        path.stat.return_value = SimpleNamespace(st_uid=0, st_mode=0o700)
        with patch.object(prepare.os, 'chown') as chown:
            prepare.ensure_secret_directory(path)
            chown.assert_not_called()
            path.stat.return_value = SimpleNamespace(st_uid=10001, st_mode=0o700)
            with self.assertRaises(ValueError): prepare.ensure_secret_directory(path)
            path.exists.return_value = False
            prepare.ensure_secret_directory(path)
            path.mkdir.assert_called_once_with(mode=0o700)
            chown.assert_called_once_with(path, 0, 0)
        path.open.assert_not_called()
        path.read_text.assert_not_called()

    def test_admit_uses_pinned_standalone_compose_and_two_own_services(self):
        def fields(kind, target, expression):
            if expression == '{{if .State.Health}}{{.State.Health.Status}}{{end}}': return 'healthy'
            if expression == '{{.Id}}': return 'forecast-id'
            if kind == 'network': return json.dumps({'forecast-id': {'Name': runtime.APPS['forecast']}})
            networks = {'my-pa-nas-contract_data-plane': {'NetworkID': runtime.NETWORKS['my-pa-nas-contract_data-plane']}}
            if target == runtime.APP:
                networks['my-pa-nas-contract_browser-origin'] = {'NetworkID': runtime.NETWORKS['my-pa-nas-contract_browser-origin']}
            else:
                networks['lakehouse-weather-egress'] = {'NetworkID': 'egress-id'}
            return json.dumps(networks)
        args = ['admit', '--apply', '--image-id', 'sha256:' + 'c'*64, '--reviewed-head', 'a'*40, '--reviewed-tree', 'b'*40, '--registry', '/registry', '--database-url-file', '/runtime-dsn', '--ingest-token-file', '/ingest', '--forecast-database-url-file', '/forecast-dsn']
        with patch.object(runtime, 'identity'), patch.object(runtime, 'docker', return_value=''), patch.object(runtime, 'mount_path', side_effect=lambda value, *args: value), patch.object(runtime, 'field', side_effect=fields), patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='2.20.3')) as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runtime.main(args), 0)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[0], ['sudo', '-n', '/usr/local/bin/docker-compose', 'version', '--short'])
            self.assertEqual([command[-1] for command in commands[1:]], ['dashboard', 'forecast'])
            for command in commands[1:]:
                self.assertIn('/usr/local/bin/docker-compose', command)
                self.assertNotIn('compose', command)
                self.assertIn('--no-deps', command)
                self.assertIn('--no-build', command)
                self.assertIn('/dev/null', command)

    def test_forecast_loop_timeout_nonoverlap_and_health_metadata(self):
        loop = load('forecast_loop')
        with tempfile.TemporaryDirectory() as folder, patch.object(loop, 'STATE', Path(folder) / 'state.json'), patch.object(loop.subprocess, 'run', side_effect=loop.subprocess.TimeoutExpired('refresh', 120)) as run:
            self.assertEqual(loop.run_once(123), 123)
            run.assert_called_once()
            self.assertEqual(run.call_args.kwargs['timeout'], 120)
            self.assertEqual(run.call_args.kwargs['stdout'], loop.subprocess.DEVNULL)
            self.assertEqual(json.loads((Path(folder) / 'state.json').read_text())['last_result'], 'failed')
        self.assertEqual(loop.INTERVAL, 3600)

    def test_forecast_cli_uses_cache_only_store_without_application(self):
        from weather import __main__ as cli
        env = {'WEATHER_MODE': 'postgres', 'WEATHER_REGISTRY': '/approved/registry', 'WEATHER_ALLOW_DATABASE': 'production'}
        with patch.dict(cli.os.environ, env, clear=True), patch.object(cli.sys, 'argv', ['weather', 'refresh-forecasts']), patch.object(cli, 'application', side_effect=AssertionError('Application invoked')), patch.object(cli.registry, 'load', return_value=[{'id': 'fixture'}]), patch.object(cli, 'secret_setting', return_value='opaque-test-DSN') as secret, patch.object(cli, 'PostgresStore') as store, patch.object(cli.forecast, 'refresh', return_value=True), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(), 0)
            secret.assert_called_once_with('WEATHER_DATABASE_URL')
            store.return_value.sync_registry.assert_not_called()

    def test_forecast_redirect_refused_and_cache_preserved(self):
        from weather import forecast
        from urllib.error import HTTPError
        from urllib.request import Request
        handler = forecast.NoRedirect()
        self.assertIsNone(handler.redirect_request(Request('https://api.open-meteo.com/v1/forecast'), None, 302, 'redirect', {}, 'https://unapproved.invalid/'))
        store = unittest.mock.Mock()
        with patch.object(forecast, 'build_opener') as build:
            build.return_value.open.side_effect = HTTPError('https://api.open-meteo.com/v1/forecast', 302, 'redirect refused', {}, None)
            location = {'id': 'fixture', 'latitude': 26.5, 'longitude': -80.0, 'timezone': 'America/New_York'}
            self.assertFalse(forecast.refresh(store, location))
            store.put_forecast.assert_not_called()

    def test_route_allowlist_blocks_nonbrowser_endpoints(self):
        text = (NAS / 'weather.caddy.fragment').read_text()
        allow = text.split('@weather_read {', 1)[1].split('}', 1)[0]
        self.assertIn('method GET', allow)
        self.assertIn('/weather/api/dashboard', allow)
        for forbidden in ['ingest', 'health', 'ready', '/*']:
            self.assertNotIn(forbidden, allow)
        self.assertIn('redir @weather_redirect /weather/ 308', text)
        self.assertIn('respond 404', text)
        self.assertIn('/weather/login /weather/login.css /weather/login.js /weather/api/auth/status', allow)
        write = text.split('@weather_auth_write {', 1)[1].split('}', 1)[0]
        self.assertIn('method POST', write)
        self.assertIn('path /weather/api/auth/login /weather/api/auth/logout /weather/api/auth/refresh', write)
        self.assertNotIn('Cloudflare Access protects', text)


if __name__ == '__main__':
    unittest.main()
