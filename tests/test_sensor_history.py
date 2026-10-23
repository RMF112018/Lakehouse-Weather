"""Synthetic sensor semantics and bounded historical contracts; no live fixtures."""
import json
import math
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from weather.domain import normalize, CATALOG, stamp
from weather.history import request_range, render, single, merge, empty, source_resolution
from weather.store import MemoryStore

NOW=datetime(2026,10,23,12,tzinfo=timezone.utc)
REF=Path(__file__).parent/'fixtures/reference'

def reading(at=NOW, **values):
    return normalize({'time':stamp(at),'model':'Fineoffset-WH65B','id':1,'temperature_C':20,**values},now=NOW)

class SensorTests(unittest.TestCase):
    def test_references_are_not_live_timestamp_evidence(self):
        outdoor=json.loads((REF/'wh65b_upstream_fixture.json').read_text())
        with self.assertRaises(ValueError):normalize(outdoor,now=NOW)
        outdoor['time']=stamp(NOW) # Synthetic UTC substitution only in test memory.
        result=normalize(outdoor,now=NOW)
        self.assertEqual((result['uv_raw'],result['uv_index']),(2,0))
        self.assertEqual(result['illuminance_lux'],0)
        self.assertIsNone(result['pressure_hpa'])
        self.assertEqual(result['raw_rf']['id'],80)
        lightning=json.loads((REF/'wh31l_reconstructed_from_upstream_packet.json').read_text())
        with self.assertRaises(ValueError):normalize(lightning,now=NOW)
        lightning['time']=stamp(NOW)
        value=normalize(lightning,now=NOW)
        self.assertTrue(value['battery_ok'])
        self.assertEqual(value['lightning_count_raw'],1)
        self.assertEqual(value['detector_flags'],32856)
        self.assertEqual(value['detector_state'],'strike')
        self.assertIsNone(value['temperature_c'])
        self.assertEqual(CATALOG['lightning_count_raw']['kind'],'raw_counter')
        for level in (0,0.5,1.0):
            lightning['battery_ok']=level
            mapped=normalize(lightning,now=NOW)
            self.assertEqual(mapped['battery_level'],level)
            self.assertEqual(mapped['raw_rf']['battery_ok'],level)
            self.assertEqual(mapped['battery_ok'],None if level==0.5 else bool(level))

    def test_future_fields_redaction_and_bounded_json(self):
        result=reading(future_sensor={'channel':2,'password':'do not retain'},Authorization='secret',foo='postgresql://secret')
        self.assertEqual(result['raw_rf']['future_sensor'],{'channel':2})
        self.assertNotIn('Authorization',result['raw_rf'])
        self.assertEqual(result['raw_rf']['foo'],'[redacted]')
        for bad in [{'new':float('nan')},{'new':{'a':{'b':{'c':{'d':{'e':1}}}}}},{'new':'x'*257},{'strike_count':256},{'battery_ok':0.5}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):reading(**bad)

    def test_numeric_circular_gust_counter_and_late_summary(self):
        rows=[reading(NOW-timedelta(minutes=1),wind_dir_deg=359,wind_max_m_s=8,rain_mm=254,strike_count=255),reading(NOW,wind_dir_deg=1,wind_max_m_s=12,rain_mm=1,strike_count=0)]
        summary=merge(merge(empty(),single(rows[1])),single(rows[0]))
        result=render('s','UTC',NOW-timedelta(hours=1),NOW+timedelta(seconds=1),10,None,[(NOW,summary)],3600)
        stats=result['summary']['metrics']
        self.assertLess(min(stats['wind_direction_deg']['mean'],360-stats['wind_direction_deg']['mean']),.001)
        self.assertEqual(stats['wind_gust_ms']['max'],12)
        self.assertIsNone(stats['rain_total_mm']['mean'])
        self.assertEqual((stats['lightning_count_raw']['first'],stats['lightning_count_raw']['last']),(255,0))
        self.assertNotIn('sum',stats['lightning_count_raw'])
        opposite=merge(single(reading(NOW-timedelta(minutes=1),wind_dir_deg=0)),single(reading(NOW,wind_dir_deg=180)))
        undefined=render('s','UTC',NOW-timedelta(hours=1),NOW+timedelta(seconds=1),10,'wind_direction_deg',[(NOW,opposite)],3600)
        self.assertIsNone(undefined['summary']['metrics']['wind_direction_deg']['mean'])

class HistoryTests(unittest.TestCase):
    def test_presets_and_dst_validation(self):
        for key in ['4h','8h','12h','24h','3d','7d','10d','30d','60d','90d','1y','5y','10y']:
            start,end,limit,metric,zone=request_range({'range':[key]},'America/New_York',NOW)
            self.assertLess(start,end)
            self.assertEqual(limit,600)
        for wall in ['2026-11-01T01:30','2026-03-08T02:30']:
            with self.assertRaises(ValueError):request_range({'range':['custom'],'local_start':[wall],'local_end':['2026-11-02T03:00']},'America/New_York',datetime(2026,12,1,tzinfo=timezone.utc))
        start,end,*_=request_range({'range':['custom'],'local_start':['2026-03-08T01:30'],'local_end':['2026-03-08T03:30']},'America/New_York',NOW)
        self.assertEqual((end-start).total_seconds(),3600)
        for q in [{'max_points':['801']},{'metric':['DROP TABLE']},{'timezone':['Europe/London']},{'start':['2026-01-01'],'end':[stamp(NOW)]}]:
            with self.assertRaises(ValueError):request_range(q,'America/New_York',NOW)

    def test_bounded_sparse_large_and_null_ranges(self):
        store=MemoryStore()
        for index in range(12000):
            at=NOW-timedelta(minutes=index*5)
            store.insert('s',reading(at,humidity=60 if index%3 else None))
        for days in [.2,1,30,90,3650,5000]:
            result=store.history_summary('s',NOW-timedelta(days=days),NOW,800,'humidity_pct','UTC')
            self.assertLessEqual(len(result['points']),800)
            self.assertEqual(set(result['points'][0]['metrics']),{'humidity_pct'})
            self.assertLessEqual(result['coverage']['temporal_span_fraction'],1)
        empty_result=store.history_summary('empty',NOW-timedelta(days=3650),NOW,600)
        self.assertEqual(empty_result['total_observations'],0)
        self.assertIsNone(empty_result['actual_start'])
        self.assertFalse(empty_result['metrics']['temperature_c']['available'])

    def test_custom_exact_edges_excludes_bucket_neighbors(self):
        store=MemoryStore()
        for minute in [0,1,2,3,4]:store.insert('s',reading(NOW+timedelta(minutes=minute)))
        result=store.history_summary('s',NOW+timedelta(minutes=1),NOW+timedelta(minutes=3),10)
        self.assertEqual(result['total_observations'],2)
        self.assertEqual(result['actual_start'],stamp(NOW+timedelta(minutes=1)))
        self.assertEqual(result['actual_end'],stamp(NOW+timedelta(minutes=2)))

import os
@unittest.skipUnless(os.environ.get('WEATHER_HISTORY_PG')=='127.0.0.1:55439','Requires explicitly authorized disposable history PostgreSQL fixture')
class PostgresHistoryTests(unittest.TestCase):
    def setUp(self):
        from weather.store import PostgresStore
        import uuid
        self.store=PostgresStore('postgresql://weather_runtime@127.0.0.1:55439/my_pa','nonproduction')
        self.sid='history-'+uuid.uuid4().hex[:12]
        locations=[{'id':self.sid,'name':'Synthetic only','timezone':'America/New_York','latitude':0,'longitude':0,'stations':[{'id':self.sid,'name':'Synthetic','model':'Synthetic','receiver_model':'DEMO','sensor_id':1}]}]
        self.store.sync_registry(locations)

    def test_late_duplicates_exact_custom_edges_durable_and_backfill(self):
        for minute,value in [(4,24),(0,20),(2,22),(1,21),(3,23)]:
            self.assertTrue(self.store.insert(self.sid,reading(NOW+timedelta(minutes=minute),temperature_C=value,strike_count=minute)))
        self.assertFalse(self.store.insert(self.sid,reading(NOW+timedelta(minutes=1),temperature_C=30)))
        result=self.store.history_summary(self.sid,NOW+timedelta(minutes=1),NOW+timedelta(minutes=3),800,'temperature_c')
        self.assertEqual(result['total_observations'],2)
        self.assertEqual(result['summary']['metrics']['temperature_c']['mean'],21.5)
        for _ in range(2):self.store.backfill_day(self.sid,NOW)
        full=self.store.history_summary(self.sid,NOW-timedelta(hours=1),NOW+timedelta(hours=1),800)
        self.assertEqual(full['total_observations'],5)
        self.assertEqual(full['summary']['metrics']['temperature_c']['first'],20)
        self.assertEqual(full['summary']['metrics']['temperature_c']['last'],24)
        self.assertIsNone(full['summary']['metrics']['lightning_count_raw']['mean'])
        from weather.store import PostgresStore
        reopened=PostgresStore(self.store.url,'nonproduction')
        self.assertEqual(reopened.history_summary(self.sid,NOW,NOW+timedelta(hours=1))['total_observations'],5)

    def test_concurrent_same_timestamp_contributes_once(self):
        import concurrent.futures
        row=reading()
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            inserted=list(pool.map(lambda _:self.store.insert(self.sid,row),range(12)))
        self.assertEqual(sum(inserted),1)
        full=self.store.history_summary(self.sid,NOW-timedelta(hours=1),NOW+timedelta(hours=1))
        self.assertEqual(full['total_observations'],1)
        self.assertEqual(full['summary']['metrics']['temperature_c']['count'],1)

    def test_owner_followon_shape_roles_and_guarded_adoption(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/database'))
        import psycopg
        import schema_contract_rollups
        import nas_rollups_apply
        with psycopg.connect('postgresql://my_pa@127.0.0.1:55439/my_pa') as owner:
            self.assertEqual(owner.execute('SELECT current_database(),current_user').fetchone(),('my_pa','my_pa'))
            schema_contract_rollups.assert_shape(owner.execute)
            sql=nas_rollups_apply.build_sql('b9025e7fb738',nas_rollups_apply.DDL_PATH.read_text(),False)
            owner.execute(sql)
        with self.store.connection() as runtime:
            for privilege in ('DELETE','TRUNCATE','REFERENCES','TRIGGER'):
                self.assertFalse(runtime.execute('SELECT has_table_privilege(current_user,%s,%s)',('weather.observation_rollups',privilege)).fetchone()[0])
        with psycopg.connect('postgresql://weather_forecast@127.0.0.1:55439/my_pa',autocommit=True) as forecast:
            self.assertFalse(forecast.execute("SELECT has_table_privilege(current_user,'weather.observation_rollups','SELECT')").fetchone()[0])

class RollupMigrationSourceTests(unittest.TestCase):
    def test_frozen_followon_contract_and_old_manifest_preserved(self):
        import ast
        import sys
        root=Path(__file__).resolve().parents[1]
        sys.path.insert(0,str(root/'scripts/database'))
        import schema_contract
        import schema_contract_rollups
        import nas_rollups_apply
        oldpath=root.parent/'my-pa/migrations/versions/20261023_a91b7d3c8e20_weather_schema.py'
        if not oldpath.exists():self.skipTest('Owner source unavailable')
        def constants(path):
            values={}
            for node in ast.parse(path.read_text()).body:
                if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                    try:values[node.targets[0].id]=ast.literal_eval(node.value)
                    except ValueError:pass
            return values
        old=constants(oldpath)
        new=constants(oldpath.with_name('20261023_f8b21e4d6c90_weather_rollups.py'))
        self.assertEqual(old['EXPECTED'],schema_contract.EXPECTED)
        self.assertEqual(old['EXPECTED_ROLLUPS'],schema_contract_rollups.EXPECTED)
        self.assertEqual(new['EXPECTED'],schema_contract_rollups.EXPECTED)
        self.assertEqual(new['BEFORE'],schema_contract.EXPECTED)
        self.assertEqual(new['DDL'],nas_rollups_apply.DDL_PATH.read_text())
        self.assertEqual(new['down_revision'],'a91b7d3c8e20')

@unittest.skipUnless(os.environ.get('WEATHER_HISTORY_PG')=='127.0.0.1:55439','Requires authorized disposable fixture')
class CanonicalRollupTests(unittest.TestCase):
    def test_exact_eight_adoption_and_empty_seven_creation(self):
        import importlib.util
        from sqlalchemy import create_engine
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        root=Path(__file__).resolve().parents[1]
        def load(name):
            path=root.parent/'my-pa/migrations/versions'/name
            spec=importlib.util.spec_from_file_location(name,path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            return module
        old=load('20261023_a91b7d3c8e20_weather_schema.py')
        new=load('20261023_f8b21e4d6c90_weather_rollups.py')
        engine=create_engine('postgresql+psycopg://my_pa@127.0.0.1:55439/my_pa')
        with engine.connect() as conn:
            transaction=conn.begin()
            try:
                marker=conn.exec_driver_sql('SELECT version_num FROM public.alembic_version').all()
                with Operations.context(MigrationContext.configure(conn)):
                    old.upgrade();new.upgrade()
                    new.shape(conn.exec_driver_sql,new.EXPECTED)
                    conn.exec_driver_sql('DROP SCHEMA weather CASCADE') # synthetic rollback-only fixture
                    old.upgrade();new.upgrade()
                    new.shape(conn.exec_driver_sql,new.EXPECTED)
                self.assertEqual(marker,conn.exec_driver_sql('SELECT version_num FROM public.alembic_version').all())
            finally:transaction.rollback()
        engine.dispose()

class RainSummaryTests(unittest.TestCase):
    def test_partial_rain_reset_gap_and_points_sum(self):
        store=MemoryStore()
        base=NOW-timedelta(hours=1)
        for minute,rain in [(0,10),(2,11),(4,1),(6,3),(40,5),(42,6)]:
            store.insert('rain',reading(base+timedelta(minutes=minute),rain_mm=rain))
        result=store.history_summary('rain',base-timedelta(minutes=1),NOW,800,'rain_known_mm')
        stat=result['summary']['metrics']['rain_known_mm']
        self.assertEqual(stat['sum'],4)
        self.assertEqual(stat['count'],3)
        self.assertEqual(stat['sample_count'],6)
        self.assertEqual((stat['unknown_intervals'],stat['reset_count'],stat['gap_count']),(3,1,1))
        self.assertEqual(sum(p['metrics']['rain_known_mm']['sum'] or 0 for p in result['points']),4)
        self.assertTrue(stat['partial'])
        single_result=store.history_summary('rain',base,base+timedelta(seconds=1),10,'rain_known_mm')
        self.assertIsNone(single_result['summary']['metrics']['rain_known_mm']['sum'])
        self.assertEqual(single_result['coverage']['populated_buckets'],0)
        self.assertGreater(result['coverage']['populated_buckets'],0)
        zero=MemoryStore();zero.insert('s',reading(NOW-timedelta(minutes=1),rain_mm=10));zero.insert('s',reading(NOW,rain_mm=10))
        known_zero=zero.history_summary('s',NOW-timedelta(hours=1),NOW+timedelta(seconds=1),10,'rain_known_mm')
        self.assertEqual(known_zero['summary']['metrics']['rain_known_mm']['sum'],0)
        self.assertGreater(known_zero['coverage']['populated_buckets'],0)

@unittest.skipUnless(os.environ.get('WEATHER_HISTORY_PG')=='127.0.0.1:55439','Requires authorized disposable fixture')
class RainPostgresTests(unittest.TestCase):
    setUp=PostgresHistoryTests.setUp
    def test_late_rain_across_hour_and_day_repair(self):
        base=datetime(2026,10,21,23,59,tzinfo=timezone.utc)
        self.store.insert(self.sid,reading(base,rain_mm=10))
        self.store.insert(self.sid,reading(base+timedelta(minutes=2),rain_mm=14))
        def report():
            return self.store.history_summary(self.sid,base-timedelta(hours=1),base+timedelta(days=100),600,'rain_known_mm')
        self.assertEqual(report()['summary']['metrics']['rain_known_mm']['sum'],4)
        # A late counter reset changes the following cross-day interval. Parent
        # head/tail repair makes the subsequent bucket correct without raw edits.
        self.store.insert(self.sid,reading(base+timedelta(seconds=30),rain_mm=5))
        self.assertFalse(self.store.insert(self.sid,reading(base+timedelta(seconds=30),rain_mm=5)))
        result=report()
        stat=result['summary']['metrics']['rain_known_mm']
        self.assertEqual(stat['sum'],9)
        self.assertEqual(stat['reset_count'],1)
        self.assertEqual(stat['unknown_intervals'],2)
        self.assertEqual(sum(p['metrics']['rain_known_mm']['sum'] or 0 for p in result['points']),9)
        self.store.backfill_day(self.sid,base)
        self.store.backfill_day(self.sid,base+timedelta(days=1))
        self.assertEqual(report()['summary']['metrics']['rain_known_mm']['sum'],9)


@unittest.skipUnless(os.environ.get('WEATHER_HISTORY_PG')=='127.0.0.1:55439','Requires authorized disposable fixture')
class RollupSafetyTests(unittest.TestCase):
    setUp=PostgresHistoryTests.setUp

    def test_failed_repair_rolls_back_raw_and_rollups(self):
        from unittest.mock import patch
        with patch.object(self.store,'_repair_rain',side_effect=RuntimeError('synthetic repair failure')):
            with self.assertRaises(RuntimeError):self.store.insert(self.sid,reading(rain_mm=10))
        self.assertIsNone(self.store.latest(self.sid))
        with self.store.connection() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM weather.observation_rollups WHERE station_id=%s',(self.sid,)).fetchone()[0],0)

    def test_pathological_raw_boundary_is_bounded(self):
        import psycopg
        from weather.history import HistoryCapacityError
        with psycopg.connect('postgresql://my_pa@127.0.0.1:55439/my_pa') as owner:
            owner.execute("INSERT INTO weather.observations(station_id,observed_at,measurements) SELECT %s,%s::timestamptz+i*interval '1 millisecond',jsonb_build_object('observed_at',to_char((%s::timestamptz+i*interval '1 millisecond') AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"'),'temperature_c',20,'raw_rf',jsonb_build_object('future_field',repeat('x',10000))) FROM generate_series(0,20001) i",(self.sid,NOW,NOW))
        with self.assertRaises(HistoryCapacityError):
            self.store.history_summary(self.sid,NOW+timedelta(milliseconds=1),NOW+timedelta(minutes=1))

    def test_guarded_owner_sql_real_empty_upgrade_and_nonempty_refusal(self):
        import psycopg
        import sys
        root=Path(__file__).resolve().parents[1]
        sys.path.insert(0,str(root/'scripts/database'))
        import nas_rollups_apply
        import schema_contract_rollups
        from weather_role import TABLES
        sql=nas_rollups_apply.build_sql('b9025e7fb738',nas_rollups_apply.DDL_PATH.read_text(),True)
        # Strip only the generated outer transaction so fixture DDL can be
        # rolled back atomically; every generated identity/catalog/ACL guard runs.
        sql=sql.removeprefix('BEGIN;').removesuffix(' COMMIT;')
        with psycopg.connect('postgresql://my_pa@127.0.0.1:55439/my_pa') as owner:
            try:
                owner.execute('DROP SCHEMA weather CASCADE')
                owner.execute((root/'migrations/001_weather_schema.PROPOSAL.sql').read_text())
                owner.execute('GRANT USAGE ON SCHEMA weather TO weather_runtime,weather_forecast')
                for table,grants in TABLES.items():owner.execute('GRANT '+grants+' ON weather.'+table+' TO weather_runtime')
                owner.execute('GRANT SELECT,INSERT,UPDATE ON weather.forecast_cache TO weather_forecast')
                owner.execute(sql)
                schema_contract_rollups.assert_shape(owner.execute)
                owner.execute('REVOKE ALL ON weather.observation_rollups FROM weather_runtime')
                owner.execute(sql) # canonical-created8 with preexisting7-role policy
                owner.execute('DROP TABLE weather.observation_rollups')
                owner.execute("INSERT INTO weather.locations VALUES('synthetic-refusal','{}')")
                owner.execute("INSERT INTO weather.stations VALUES('synthetic-refusal','synthetic-refusal','{}')")
                owner.execute("INSERT INTO weather.observations(station_id,observed_at,measurements) VALUES('synthetic-refusal',CURRENT_TIMESTAMP,'{}')")
                with self.assertRaises(psycopg.Error):owner.execute(sql)
            finally:owner.rollback()

class RollupOwnerCliTests(unittest.TestCase):
    def test_owner_failures_are_bounded_and_redacted_after_identity(self):
        import contextlib
        import hashlib
        import io
        import runpy
        import subprocess
        from types import SimpleNamespace
        from unittest.mock import patch
        root=Path(__file__).resolve().parents[1]
        import sys
        sys.path.insert(0,str(root/'scripts/database'))
        script=root/'scripts/database/nas_rollups_apply.py'
        digest=hashlib.sha256((root/'migrations/002_weather_rollups.PROPOSAL.sql').read_bytes()).hexdigest()
        identity='a'*64
        args=[str(script),'--docker-bin','/synthetic/docker','--postgres-container','synthetic-only','--expected-container-id',identity,'--expected-alembic','b9025e7fb738','--expected-sha256',digest,'--database','my_pa','--owner','my_pa','--apply']
        error=subprocess.CalledProcessError(1,['synthetic'],stderr='PRIVATE SYNTHETIC DIAGNOSTIC')
        stderr=io.StringIO()
        with patch('sys.argv',args),patch('subprocess.run',side_effect=[SimpleNamespace(stdout=identity+'\n'),error]) as run,contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as result:runpy.run_path(str(script),run_name='__main__')
        self.assertEqual(result.exception.code,1)
        self.assertNotIn('PRIVATE',stderr.getvalue())
        self.assertNotIn('Traceback',stderr.getvalue())
        self.assertEqual(run.call_args_list[0].kwargs['timeout'],15)
        self.assertEqual(run.call_args_list[1].kwargs['timeout'],30)
        self.assertIn(identity,run.call_args_list[1].args[0])
        self.assertTrue(run.call_args_list[1].kwargs['capture_output'])
