import ast
import contextlib
import importlib.util
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
HELPER = HERE.parent / 'ops' / 'nas' / 'activate_weather.py'
spec = importlib.util.spec_from_file_location('ingress', HELPER)
ingress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingress)
BASELINE_CADDY = b'# Public browser-only reverse proxy for https://pa.bobby-fetting.me.\n# This listener is NOT the Tailscale private proxy. Machine and MCP routes\n# stay on the private Tailscale allowlist proxy; this origin never forwards them.\n:8080 {\n    @hostile_host not host pa.bobby-fetting.me\n    handle @hostile_host {\n        respond "not found" 404\n    }\n\n    @internal_capabilities path /v1/*\n    handle @internal_capabilities {\n        respond "not found" 404\n    }\n\n    @unmatched_remote path /remote/*\n    handle @unmatched_remote {\n        respond "not found" 404\n    }\n\n    @reserved_apple path /apple/*\n    handle @reserved_apple {\n        respond "not found" 404\n    }\n\n    @mcp path /mcp /mcp/*\n    handle @mcp {\n        respond "not found" 404\n    }\n\n    handle /healthz {\n        respond "ok" 200\n    }\n\n    header Strict-Transport-Security "max-age=31536000"\n\n    handle {\n        reverse_proxy web:3000 {\n            header_up -Authorization\n            header_up -Forwarded\n            header_up -X-Forwarded-For\n            header_up -X-Forwarded-Host\n            header_up -X-Forwarded-Proto\n            header_up -X-Forwarded-*\n            header_up -Tailscale-User-Login\n            header_up -Tailscale-User-Name\n            header_up -Tailscale-User-Profile-Pic\n            header_up -Tailscale-App-Capabilities\n            header_up -Cf-Access-Authenticated-User-Email\n            header_up -Cf-Access-Jwt-Assertion\n            header_up -Cf-Access-Token\n        }\n    }\n}\n'


class IngressTests(unittest.TestCase):
    def source(self):
        return BASELINE_CADDY

    def tunnel(self):
        return b'tunnel: synthetic-id\ncredentials-file: /synthetic/fixture.json\ningress:\n  - hostname: pa.bobby-fetting.me\n    service: http://public-proxy:8080\n  - service: http_status:404\n'

    def test_exact_proxy_preservation_and_narrow_rule(self):
        old = self.source()
        new = ingress.candidates(old, self.tunnel())
        self.assertTrue(new['caddy'].endswith(old.split(b':8080 {', 1)[1]))
        self.assertIn(b'@weather_host host www.bobby-fetting.me', new['caddy'])
        self.assertLess(new['caddy'].index(b'handle @weather_host'), new['caddy'].index(b'handle @hostile_host'))
        self.assertIn(b'path: ^/weather(?:/.*)?$', new['tunnel'])
        rule = b'  - hostname: www.bobby-fetting.me\n    path: ^/weather(?:/.*)?$\n    service: http://public-proxy:8080\n'
        self.assertEqual(new['tunnel'].replace(rule, b'', 1), self.tunnel())
        self.assertIn(b'/weather/api/auth/login /weather/api/auth/logout /weather/api/auth/refresh', new['caddy'])
        self.assertNotIn(b'path /weather/*', new['caddy'])

    def test_fail_closed_on_proxy_or_tunnel_drift(self):
        with self.assertRaises(ValueError): ingress.candidates(self.source() + b'\n', self.tunnel())
        for value in [self.tunnel().replace(b'http_status:404', b'http_status:200'), self.tunnel().replace(b'pa.bobby-fetting.me', b'www.bobby-fetting.me'), self.tunnel().replace(b'ingress:', b'other:')]:
            with self.assertRaises(ValueError): ingress.candidates(self.source(), value)

    def test_in_place_preserves_inode_permissions_and_truncates(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fixture'
            path.write_bytes(b'long original synthetic contents')
            path.chmod(0o640)
            before = path.stat()
            ingress.in_place(path, b'short')
            after = path.stat()
            self.assertEqual(before.st_ino, after.st_ino)
            self.assertEqual((before.st_uid,before.st_gid,before.st_mode),(after.st_uid,after.st_gid,after.st_mode))
            self.assertEqual(path.read_bytes(), b'short')

    def test_helper_gate_precedes_any_container_action(self):
        with patch.object(ingress.os, 'geteuid', return_value=0), patch.object(ingress, 'identities') as identities:
            with self.assertRaises(ValueError): ingress.main(['apply','--reviewed-helper-sha','wrong'])
            identities.assert_not_called()

    def test_diagnostics_never_disclosed(self):
        result = type('Result', (), {'returncode': 1, 'stdout': b'synthetic-sensitive-body', 'stderr': b'synthetic-sensitive-diagnostic'})()
        with patch.object(ingress.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(ValueError, '^Ingress command failed; diagnostic payload suppressed$'):
                ingress.command(['unexecuted-fixture'])


    def test_apply_validation_failure_never_changes_live_files(self):
        reviewed = ingress.digest(HELPER.read_bytes())
        with tempfile.TemporaryDirectory() as folder, patch.object(ingress, 'ROOT', Path(folder)), patch.object(ingress.os, 'geteuid', return_value=0), patch.object(ingress, 'identities'), patch.object(ingress, 'manifest', return_value={}), patch.object(ingress, 'unchanged'), patch.object(ingress, 'validate', side_effect=ValueError('fixture failed')), patch.object(ingress, 'activate') as activate:
            (Path(folder) / 'validated').touch()
            with self.assertRaises(ValueError): ingress.main(['apply', '--reviewed-helper-sha', reviewed])
            activate.assert_not_called()

    def test_apply_failure_attempts_exact_original_rollback(self):
        reviewed = ingress.digest(HELPER.read_bytes())
        record = {'fixture': 'metadata-only'}
        with tempfile.TemporaryDirectory() as folder, patch.object(ingress, 'ROOT', Path(folder)), patch.object(ingress.os, 'geteuid', return_value=0), patch.object(ingress, 'identities'), patch.object(ingress, 'manifest', return_value=record), patch.object(ingress, 'unchanged'), patch.object(ingress, 'validate'), patch.object(ingress, 'activate', side_effect=[ValueError('fixture failed'), None]) as activate:
            (Path(folder) / 'validated').touch()
            with self.assertRaisesRegex(ValueError, 'original configurations restored'):
                ingress.main(['apply', '--reviewed-helper-sha', reviewed])
            self.assertEqual(activate.call_args_list[0].args, (record, 'candidate'))
            self.assertEqual(activate.call_args_list[1].args, (record, 'original'))

    def test_native_python38_compatible(self):
        ast.parse(HELPER.read_text(), feature_version=(3,8))


if __name__ == '__main__': unittest.main()
