import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('commission_rf', Path(__file__).resolve().parents[1] / 'ops/nas/commission_rf.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class CommissionTests(unittest.TestCase):
    def fixture(self):
        return {'version': 7, 'locations': [{'id': 'lakehouse', 'name': 'Private location',
            'timezone': 'America/New_York', 'latitude': 12.345, 'longitude': -56.789,
            'operator_extra': {'preserve': True}, 'stations': [{'id': 'lakehouse-ws2000',
            'name': 'Array', 'model': 'WS2000', 'receiver_model': 'Fineoffset-WH65B',
            'sensor_id': 'PENDING_RF_COMMISSIONING', 'ingest_enabled': False}]}]}

    def test_prepare_preserves_coordinates_and_other_configuration(self):
        source = self.fixture()
        unchanged = copy.deepcopy(source)
        result = m.prepare(source, 111, 222)
        self.assertEqual(source, unchanged)
        for key in ('latitude', 'longitude', 'timezone', 'name', 'operator_extra'):
            self.assertEqual(source['locations'][0][key], result['locations'][0][key])
        self.assertEqual(result['version'], 7)
        stations = result['locations'][0]['stations']
        self.assertEqual([s['sensor_id'] for s in stations], [111, 222])
        self.assertTrue(all(s['ingest_enabled'] for s in stations))
        self.assertEqual(result['locations'][0]['physical_stations'][0]['metric_sources']['pressure_hpa'], 'lakehouse-ws2000-wh32b')

    def test_active_identity_change_and_group_drift_refused(self):
        result = m.prepare(self.fixture(), 111, 222)
        with self.assertRaises(ValueError):
            m.prepare(result, 333, 222)
        result['locations'][0]['physical_stations'][0]['metric_sources']['temperature_c'] = 'lakehouse-ws2000'
        with self.assertRaises(ValueError):
            m.prepare(result, 111, 222)

    def test_disabled_prior_real_identity_cannot_be_overwritten(self):
        source = self.fixture()
        source['locations'][0]['stations'][0]['sensor_id'] = 444
        with self.assertRaises(ValueError):
            m.prepare(source, 111, 222)
        # Equal approved identity is idempotent even while temporarily disabled.
        self.assertEqual(m.prepare(source, 444, 222)['locations'][0]['stations'][0]['sensor_id'], 444)

    def test_dry_run_hash_guard_and_atomic_backup_readback(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / 'stations.json'
            backups = Path(temporary) / 'backups'
            backups.mkdir(mode=0o700)
            content = json.dumps(self.fixture()).encode()
            registry.write_bytes(content)
            registry.chmod(0o600)
            expected = m.digest(content)
            with patch.object(m, 'REGISTRY', registry), patch.object(m, 'backup_directory', return_value=backups), patch.object(m.os, 'fchown'):
                receipt = m.commission(expected, 111, 222)
                self.assertEqual(receipt['result'], 'preflight_passed')
                self.assertEqual(registry.read_bytes(), content)
                self.assertEqual(list(backups.iterdir()), [])
                with self.assertRaises(ValueError):
                    m.commission('0' * 64, 111, 222, True)
                receipt = m.commission(expected, 111, 222, True)
                self.assertEqual(receipt['result'], 'registry_commissioned')
                self.assertEqual(next(backups.iterdir()).read_bytes(), content)
                self.assertEqual(m.digest(registry.read_bytes()), receipt['new_sha256'])
                self.assertEqual(json.loads(registry.read_bytes())['locations'][0]['latitude'], 12.345)
                self.assertEqual(registry.stat().st_mode & 0o777, 0o600)
                self.assertNotIn('111', json.dumps(receipt))
                self.assertNotIn('12.345', json.dumps(receipt))

if __name__ == '__main__':
    unittest.main()
