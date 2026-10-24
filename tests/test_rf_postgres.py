"""Opt-in tests against the positively attested disposable RF fixture only."""
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from test_rf_available import NOW, packet
from weather.domain import normalize
from weather.store import PostgresStore, ObservationConflict

@unittest.skipUnless(os.environ.get('WEATHER_SYNTHETIC_PG') == '127.0.0.1:55439', 'Requires attested disposable RF PostgreSQL fixture')
class PostgresRFTests(unittest.TestCase):
    def setUp(self):
        self.store=PostgresStore('postgresql://weather_runtime@127.0.0.1:55439/my_pa','nonproduction')
        self.sid='rf-'+uuid.uuid4().hex[:12]
        self.other=self.sid+'-other'
        self.location={'id':self.sid,'name':'Synthetic','timezone':'UTC','latitude':None,'longitude':None,'stations':[{'id':sid,'name':'Synthetic','model':'Synthetic','receiver_model':'SYNTHETIC','sensor_id':sid} for sid in (self.sid,self.other)]}
        self.store.sync_registry([self.location])
    def test_atomic_duplicate_conflict_and_distinct_sources(self):
        obs=normalize(packet())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.store.insert(self.sid,obs),range(2)))
        self.assertEqual(sorted(results),[False,True])
        with self.assertRaises(ObservationConflict):self.store.insert(self.sid,{**obs,'wind_speed_ms':9})
        self.assertTrue(self.store.insert(self.other,obs))
        summary=self.store.history_summary(self.sid,NOW-timedelta(minutes=1),NOW+timedelta(minutes=1),10,'wind_speed_ms')
        self.assertEqual(summary['total_observations'],1)
        self.assertEqual(self.store.current_metrics(self.sid,['wind_speed_ms'],NOW-timedelta(seconds=120),NOW)['wind_speed_ms']['value'],2)
    def test_registry_rebind_rollback(self):
        import copy
        changed=copy.deepcopy(self.location);changed['stations'][0]['sensor_id']='replacement'
        with self.assertRaises(ValueError):self.store.sync_registry([changed])
        self.store.sync_registry([self.location])
    def test_pending_commissioning_requires_disabled_empty_source(self):
        import copy
        pending=copy.deepcopy(self.location)
        pending['id']=self.sid+'-pending-location'
        pending['stations']=[{**pending['stations'][0],'id':self.sid+'-pending','sensor_id':'PENDING_RF_COMMISSIONING','ingest_enabled':False}]
        self.store.sync_registry([pending])
        enrolled=copy.deepcopy(pending);enrolled['stations'][0].update(sensor_id=self.sid+'-commissioned',ingest_enabled=True)
        self.store.sync_registry([enrolled])
        altered=copy.deepcopy(enrolled);altered['stations'][0]['sensor_id']='another'
        with self.assertRaises(ValueError):self.store.sync_registry([altered])
