"""Explicit synthetic PostgreSQL scale evidence; never run by unittest discovery.

Requires WEATHER_HISTORY_PG=127.0.0.1:55439 and WEATHER_HISTORY_BENCHMARK=1.
One full year at 30-second cadence plus nine preceding years of daily samples.
Actual cadence/count/span and EXPLAIN output are reported, never extrapolated.
"""
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    if os.environ.get('WEATHER_HISTORY_PG')!='127.0.0.1:55439' or os.environ.get('WEATHER_HISTORY_BENCHMARK')!='1':
        raise ValueError('Explicit disposable synthetic fixture opt-in required')
    import psycopg
    from weather.store import PostgresStore
    from weather.domain import stamp
    start=datetime(2016,10,23,tzinfo=timezone.utc)
    end=datetime(2026,10,23,tzinfo=timezone.utc)
    sid='benchmark-30s-one-year-plus-nine-daily'
    with psycopg.connect('postgresql://my_pa@127.0.0.1:55439/my_pa') as owner:
        assert owner.execute('SELECT current_database(),current_user').fetchone()==('my_pa','my_pa')
        owner.execute("INSERT INTO weather.locations VALUES(%s,'{}') ON CONFLICT DO NOTHING",(sid,))
        owner.execute("INSERT INTO weather.stations VALUES(%s,%s,'{}') ON CONFLICT DO NOTHING",(sid,sid))
        existing=owner.execute('SELECT count(*) FROM weather.observations WHERE station_id=%s',(sid,)).fetchone()[0]
        if not existing:
            owner.execute("""INSERT INTO weather.observations(station_id,observed_at,measurements)
             SELECT %s,t,jsonb_build_object('observed_at',to_char(t AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),'temperature_c',value)
             FROM (
               SELECT '2025-10-23 00:00+00'::timestamptz+i*interval '30 seconds' AS t,10+(i%%100)/10.0 AS value FROM generate_series(0,1051199) i
               UNION ALL SELECT t,15.0 FROM generate_series('2016-10-23 00:00+00'::timestamptz,'2025-10-22 00:00+00'::timestamptz,interval '1 day') t
             ) samples""",(sid,))
            for width in (300,3600,86400):
                owner.execute("""INSERT INTO weather.observation_rollups(station_id,bucket_start,bucket_seconds,summary)
                 SELECT %s,to_timestamp(floor(extract(epoch from observed_at)/%s)*%s),%s,
                 jsonb_build_object('observation_count',count(*),'first_at',to_char(min(observed_at) AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),'last_at',to_char(max(observed_at) AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
                  'metrics',jsonb_build_object('temperature_c',jsonb_build_object('count',count(*),'sum',sum((measurements->>'temperature_c')::numeric),'min',min((measurements->>'temperature_c')::numeric),'max',max((measurements->>'temperature_c')::numeric),
                   'first',(array_agg((measurements->>'temperature_c')::numeric ORDER BY observed_at))[1], 'last',(array_agg((measurements->>'temperature_c')::numeric ORDER BY observed_at DESC))[1],
                   'first_at',to_char(min(observed_at) AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),'last_at',to_char(max(observed_at) AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))))
                 FROM weather.observations WHERE station_id=%s GROUP BY 2""",(sid,width,width,width,sid))
        owner.execute('ANALYZE weather.observations')
        owner.execute('ANALYZE weather.observation_rollups')
        count,actual_start,actual_end=owner.execute('SELECT count(*),min(observed_at),max(observed_at) FROM weather.observations WHERE station_id=%s',(sid,)).fetchone()
        rollups=owner.execute('SELECT bucket_seconds,count(*) FROM weather.observation_rollups WHERE station_id=%s GROUP BY bucket_seconds ORDER BY bucket_seconds',(sid,)).fetchall()
    store=PostgresStore('postgresql://weather_runtime@127.0.0.1:55439/my_pa','nonproduction')
    timings=[]
    for _ in range(3):
        begin=time.perf_counter()
        result=store.history_summary(sid,start,end,600,'temperature_c')
        timings.append(round(time.perf_counter()-begin,4))
        assert result['total_observations']==count
        assert len(result['points'])<=600
    with store.connection() as conn:
        plans={}
        for name,sql,params in [
          ('daily_rollups','SELECT bucket_start,summary FROM weather.observation_rollups WHERE station_id=%s AND bucket_seconds=86400 AND bucket_start>=%s AND bucket_start<%s ORDER BY bucket_start',(sid,start,end)),
          ('raw_boundary','SELECT measurements FROM weather.observations WHERE station_id=%s AND observed_at>=%s AND observed_at<%s ORDER BY observed_at LIMIT 20001',(sid,datetime(2026,10,22,tzinfo=timezone.utc),end))]:
            plans[name]=conn.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+sql,params).fetchone()[0]
    print(json.dumps({'fixture':'local disposable PostgreSQL17, not NAS hardware','raw_rows':count,'actual_start':stamp(actual_start),'actual_end':stamp(actual_end),'cadence':'one year at30seconds; preceding nine years daily','rollup_rows':rollups,'history_points':len(result['points']),'query_seconds':timings,'plans':plans},indent=2))


if __name__=='__main__':main()
