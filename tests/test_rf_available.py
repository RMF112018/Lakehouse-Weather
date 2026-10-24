import copy
import unittest
from datetime import datetime, timezone
from weather.domain import normalize, stamp
from weather.registry import validate_registry, admit
from weather.store import MemoryStore, ObservationConflict

NOW = datetime.now(timezone.utc).replace(microsecond=0)

def registry():
    sources = [{'id':sid,'name':sid,'model':profile,'receiver_model':model,'sensor_id':sensor,'rf_profile':profile,'ingest_enabled':True} for sid,profile,model,sensor in [('array','wh65b','Fineoffset-WH65B',201),('pressure','wh32b','Fineoffset-WH32B',202)]]
    return [{'id':'synthetic','name':'Synthetic','timezone':'UTC','latitude':None,'longitude':None,'stations':sources,'physical_stations':[{'id':'installation','name':'Synthetic installation','source_station_ids':['array','pressure'],'metric_sources':{'temperature_c':'pressure','pressure_hpa':'pressure','wind_speed_ms':'array','uv_index':'array'},'freshness_seconds':{'array':120,'pressure':300}}]}]

def packet(**extra):
    return {'time':stamp(NOW),'model':'Fineoffset-WH65B','id':201,'protocol':78,'mic':'CRC','wind_avg_m_s':2,**extra}

def context(p):
    return {'transport':'local_collector','model':p['model'],'sensor_id':p['id'],'protocol':78,'decoder_build':'synthetic-pinned-build','receiver_received_at_utc':stamp(NOW)}

class RFTests(unittest.TestCase):
    def test_admission(self):
        locations=validate_registry(registry()); p=packet()
        self.assertEqual(admit(locations,p,context(p)),'array')
        for change in ({'model':'Fineoffset-WH24'},{'id':999},{'protocol':True},{'protocol':85},{'mic':'CHECKSUM'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                admit(locations,{**p,**change},context(p))
        with self.assertRaises(ValueError): admit(locations,p)
        with self.assertRaises(ValueError): admit(locations,p,{**context(p),'sensor_id':999})
    def test_sentinels_and_omission(self):
        value=normalize(packet(temperature_raw=0x7ff,humidity_raw=0xff,uv_raw=0xffff,light_raw=0xffffff))
        for key in ('temperature_c','humidity_pct','uv_raw','uv_index','illuminance_lux'):
            self.assertIsNone(value[key]);self.assertEqual(value['unavailable_reasons'][key],'transmitter_invalid_sentinel')
        self.assertEqual(normalize(packet())['unavailable_reasons']['temperature_c'],'not_observed')
        with self.assertRaises(ValueError): normalize(packet(temperature_C=2047))
    def test_duplicate_conflict(self):
        store=MemoryStore(); obs=normalize(packet())
        self.assertTrue(store.insert('array',obs)); self.assertFalse(store.insert('array',obs))
        changed=copy.deepcopy(obs);changed['wind_speed_ms']=3
        with self.assertRaises(ObservationConflict):store.insert('array',changed)
        self.assertTrue(store.insert('pressure',obs))
    def test_group_guards(self):
        for mutate in (lambda r:r[0]['physical_stations'][0]['metric_sources'].update(unknown='array'),lambda r:r[0]['physical_stations'][0]['source_station_ids'].append('missing'),lambda r:r[0]['physical_stations'][0]['freshness_seconds'].update(array=True)):
            r=registry();mutate(r)
            with self.assertRaises(ValueError):validate_registry(r)
