import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from weather.collector import Journal, collect

SPEC = importlib.util.spec_from_file_location('rf_capture', Path(__file__).resolve().parents[1] / 'ops/nas/rf_capture.py')
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.chmod(self.tmp.name, 0o700)
        self.journal = Journal(self.tmp.name)

    def tearDown(self):
        self.journal.close()
        self.tmp.cleanup()

    def test_disk_survives_failed_commit_then_restart_replay(self):
        record = {'station_id': 'owned', 'observation': {'observed_at': '2026-10-24T00:00:00Z', 'temperature_c': 12}}
        path = self.journal.append(record)
        with self.assertRaises(OSError):
            self.journal.replay(lambda *_: (_ for _ in ()).throw(OSError('disconnected')))
        self.assertEqual(json.loads(path.read_text()), record)
        self.journal.close()
        self.journal = Journal(self.tmp.name)
        received = []
        self.journal.replay(lambda *r: received.append(r))
        self.assertEqual(received, [('owned', record['observation'])])
        self.assertEqual(self.journal.pending()[0], [])

    def test_commit_occurs_after_file_and_directory_fsync(self):
        real_sync = os.fsync
        calls = []
        def sync(fd):
            calls.append('sync')
            real_sync(fd)
        with patch('weather.collector.os.fsync', sync):
            path = self.journal.append({'station_id': 's', 'observation': {}})
            self.journal.replay(lambda *_: calls.append('commit') if path.exists() else self.fail('missing journal'))
        self.assertGreaterEqual(calls.index('commit'), 2)
        self.assertEqual(calls[-1], 'sync')

    def test_conflict_stays_pending_and_blocks_next_input(self):
        self.journal.append({'station_id': 's', 'observation': {}})
        stream = io.BytesIO(b'{"neighbor":true}\n')
        with self.assertRaises(ValueError):
            collect(stream, [], self.journal, lambda *_: (_ for _ in ()).throw(ValueError('conflict')))
        self.assertEqual(stream.tell(), 0)
        self.assertEqual(len(self.journal.pending()[0]), 1)

    def test_capacity_never_deletes_or_acknowledges(self):
        self.journal.max_events = 1
        self.journal.append({'station_id': 's', 'observation': {}})
        with self.assertRaises(ValueError):
            self.journal.append({'station_id': 's', 'observation': {}})
        self.assertEqual(len(self.journal.pending()[0]), 1)

    def test_second_process_lock_and_incomplete_record_fail_closed(self):
        with self.assertRaises(ValueError):
            Journal(self.tmp.name)
        (Path(self.tmp.name) / 'partial.json').write_text('{')
        with self.assertRaises(ValueError):
            self.journal.replay(lambda *_: self.fail('must not commit partial record'))
        self.assertTrue((Path(self.tmp.name) / 'partial.json').exists())

    def test_neighbors_rejected_before_normalization_or_journal(self):
        with patch('weather.collector.registry.resolve', side_effect=ValueError), patch('weather.collector.normalize') as normalize:
            collect(io.BytesIO(b'{"model":"neighbor","id":99}\n'), [], self.journal, lambda *_: self.fail('neighbor delivered'))
        normalize.assert_not_called()
        self.assertEqual(self.journal.pending()[0], [])

    def test_admission_precedes_journal_and_normalization(self):
        packet = b'{"model":"owned","id":1,"protocol":78,"time":"2026-10-24 00:00:00"}\n'
        with patch('weather.collector.registry.resolve', return_value='s'), patch('weather.collector.registry.source', return_value={'rf_profile': 'wh65b'}), patch('weather.collector.registry.admit', create=True, side_effect=ValueError), patch('weather.collector.normalize') as normalize:
            collect(io.BytesIO(packet), [], self.journal, lambda *_: self.fail('rejected delivery'))
        normalize.assert_not_called()
        self.assertEqual(self.journal.pending()[0], [])

    def test_real_admission_normalization_duplicate_and_collision(self):
        from weather.store import MemoryStore, ObservationConflict
        locations = [{'stations': [{'id': 's', 'receiver_model': 'Fineoffset-WH65B',
                      'sensor_id': 111, 'ingest_enabled': True, 'rf_profile': 'wh65b'}]}]
        packet = {'time': '2026-09-09 20:00:00', 'model': 'Fineoffset-WH65B',
                  'id': 111, 'protocol': 78, 'mic': 'CRC', 'temperature_C': 12}
        store = MemoryStore()
        stream = lambda: io.BytesIO((json.dumps(packet) + '\n').encode())
        collect(stream(), locations, self.journal, store.insert)
        collect(stream(), locations, self.journal, store.insert)
        self.assertEqual(len(store.rows['s']), 1)
        row = next(iter(store.rows['s'].values()))
        self.assertEqual(row['provenance']['transport'], 'local_collector')
        packet['temperature_C'] = 13
        with self.assertRaises(ObservationConflict):
            collect(stream(), locations, self.journal, store.insert)
        self.assertEqual(len(self.journal.pending()[0]), 1)
        self.assertEqual(next(iter(store.rows['s'].values()))['temperature_c'], 12)

    def test_age_limit_retains_event_and_reports_metadata(self):
        path = self.journal.append({'station_id': 's', 'observation': {}})
        import time
        old = time.time() - 8 * 86400
        os.utime(path, (old, old))
        with self.assertRaises(ValueError):
            self.journal.replay(lambda *_: self.fail('expired pending auto delivery'))
        status = json.loads((Path(self.tmp.name) / 'status.json').read_text())
        self.assertEqual(status['error_code'], 'pending_age_limit')
        self.assertTrue(path.exists())
        self.assertEqual(status['pending_count'], 1)

    def test_duplicate_json_keys_rejected_without_payload_persistence(self):
        collect(io.BytesIO(b'{"model":"neighbor","id":1,"id":2}\n'), [], self.journal, lambda *_: self.fail('delivery'))
        self.assertEqual(self.journal.pending()[0], [])
        status = json.loads((Path(self.tmp.name) / 'status.json').read_text())
        self.assertEqual(status['rejected'], 1)
        self.assertNotIn('neighbor', json.dumps(status))
        self.journal.close()
        self.journal = Journal(self.tmp.name)
        self.assertEqual(self.journal.status['rejected'], 1)

    def test_naive_decoder_timestamp_requires_exact_format_and_calendar(self):
        locations = [{'stations': [{'id': 's', 'receiver_model': 'Fineoffset-WH65B',
                      'sensor_id': 111, 'ingest_enabled': True, 'rf_profile': 'wh65b'}]}]
        for timestamp in ('2026-10-24X00:00:00', '2026-02-30 00:00:00', '2026-10-24T00:00:00'):
            packet = {'time': timestamp, 'model': 'Fineoffset-WH65B', 'id': 111,
                      'protocol': 78, 'mic': 'CRC', 'temperature_C': 12}
            collect(io.BytesIO((json.dumps(packet) + '\n').encode()), locations, self.journal,
                    lambda *_: self.fail('malformed timestamp delivered'))
            self.assertEqual(self.journal.pending()[0], [])

    def test_exclusive_supervisor_installer_and_reviewed_arguments(self):
        import types
        args = types.SimpleNamespace(dashboard_id='a' * 64, dashboard_image='sha256:' + 'b' * 64,
                    source_sha256='c' * 64, reviewed_head='d' * 40, reviewed_tree='e' * 40)
        with tempfile.TemporaryDirectory() as temporary:
            cron = Path(temporary) / 'weather-rf-capture'
            with patch.object(launcher, 'CRON', cron):
                launcher.install_supervisor(Path('/volume1/weather-dashboard/reviewed/ops/nas/rf_capture.py'), args)
                text = cron.read_text()
                self.assertIn('* * * * * root /usr/bin/python3 -I -B ', text)
                self.assertIn('--source-sha256 ' + 'c' * 64, text)
                self.assertIn('>/dev/null 2>&1', text)
                self.assertEqual(cron.stat().st_mode & 0o777, 0o600)
                with self.assertRaises(ValueError):
                    launcher.install_supervisor(Path('/reviewed'), args)
                self.assertEqual(cron.read_text(), text)

    def test_stale_receiver_reconciliation_fails_closed_on_ownership(self):
        def value(*args):
            if args[1] == 'ls':
                return 'existing'
            if args[-2] == '{{.Image}}':
                return launcher.IMAGE
            return 'wrong-owner'
        with patch.object(launcher, 'metadata', side_effect=value) as metadata:
            with self.assertRaises(ValueError):
                launcher.reconcile_receiver()
        self.assertFalse(any(call.args[:3] == ('container', 'rm', '--force') for call in metadata.call_args_list))

    def test_host_helpers_have_no_app_import_and_python38_grammar(self):
        import ast
        for name in ('rf_capture.py', 'commission_rf.py'):
            source = (Path(__file__).resolve().parents[1] / 'ops/nas' / name).read_text()
            tree = ast.parse(source, feature_version=(3, 8))
            imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            self.assertFalse(any(module and module.startswith('weather') for module in imports))

    def test_receiver_command_is_pinned_networkless_and_logless(self):
        calls = []
        class Process:
            def __init__(self, argv, **kwargs):
                calls.append((argv, kwargs))
                self.stdout = io.BytesIO()
            def wait(self, **kwargs): return 0
            def poll(self): return 0
        with patch.object(launcher.subprocess, 'Popen', Process):
            self.assertEqual(launcher.launch('/dev/bus/usb/001/004'), 0)
        command = calls[0][0]
        for flag, value in [('--network', 'none'), ('--log-driver', 'none'), ('--pull', 'never')]:
            self.assertEqual(command[command.index(flag)+1], value)
        self.assertIn(launcher.IMAGE, command)
        self.assertEqual(command[-len(launcher.ARGV):], launcher.ARGV)
        self.assertEqual(calls[1][0][-4:], ['python', '-m', 'weather', 'collect'])
        self.assertNotIn('http', str(calls))

if __name__ == '__main__':
    unittest.main()
