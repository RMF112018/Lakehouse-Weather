import io
import unittest
from datetime import timedelta
from test_rf_available import NOW, registry, packet
from weather.composite import assemble
from weather.domain import normalize, stamp
from weather.store import MemoryStore
from weather.server import Application, dispatch

class CompositeTests(unittest.TestCase):
    def setUp(self):
        self.locations=registry();self.store=MemoryStore();self.group=self.locations[0]['physical_stations'][0]
    def result(self):return assemble(self.group,self.locations[0]['stations'],self.store,NOW)
    def test_partial_packet_keeps_fresh_metric_and_sentinel_barrier(self):
        self.store.insert('array',normalize(packet(time=stamp(NOW-timedelta(seconds=60)),uv=5)))
        self.store.insert('array',normalize(packet(time=stamp(NOW-timedelta(seconds=30)))))
        self.group['metric_sources']['uv_raw']='array'
        self.assertEqual(self.result()['metrics']['uv_raw']['value'],5)
        self.store.insert('array',normalize(packet(uv_raw=65535)))
        self.assertIsNone(self.result()['metrics']['uv_raw']['value'])
        self.assertEqual(self.result()['metrics']['uv_raw']['unavailable_reason'],'transmitter_invalid_sentinel')
    def test_independent_sources_and_history_routing(self):
        self.store.insert('array',normalize(packet(time=stamp(NOW-timedelta(seconds=130)))))
        self.store.insert('pressure',normalize(packet(model='Fineoffset-WH32B',id=202,temperature_C=21,pressure_hPa=1000)))
        value=self.result();self.assertEqual(value['metrics']['temperature_c']['source_station_id'],'pressure');self.assertEqual(value['metrics']['wind_speed_ms']['freshness'],'stale');self.assertEqual(value['status'],'partial')
        app=Application(self.locations,self.store)
        status,body,_=dispatch(app,'web','GET','/api/history?physical_station_id=installation&metric=temperature_c&range=24h',{},io.BytesIO())
        self.assertEqual(status,200);self.assertEqual(body['resolved_source_station_id'],'pressure')
        for suffix in ('&station_id=array','&metric=humidity_pct'):
            self.assertEqual(dispatch(app,'web','GET','/api/history?physical_station_id=installation&metric=temperature_c&range=24h'+suffix,{},io.BytesIO())[0],400)
    def test_future_sample_missing(self):
        self.store.insert('array',normalize(packet(time=stamp(NOW+timedelta(seconds=20)))))
        field=self.result()['metrics']['wind_speed_ms'];self.assertIsNone(field['value']);self.assertEqual(field['unavailable_reason'],'clock_skew')
    def test_bounded_status_projection_and_symlink_refusal(self):
        import tempfile,json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic-status.json'
            path.write_text(json.dumps({'updated_at_utc':stamp(NOW),'pending_count':2,'error_code':'capacity','unrelated':'omitted'}))
            app=Application(self.locations,self.store,rf_status_path=str(path))
            self.assertEqual(app.rf_status(NOW)['status'],'available')
            self.assertEqual(app.rf_status(NOW)['pending_count'],2)
            self.assertNotIn('unrelated',app.rf_status(NOW))
            self.assertEqual(app.rf_status(NOW+timedelta(seconds=121))['status'],'stale_status')
            link=Path(directory)/'link';link.symlink_to(path)
            app.rf_status_path=str(link)
            self.assertEqual(app.rf_status(NOW),{'status':'unknown'})
