#!/usr/bin/env python3
"""Owner-approved additive weather schema only; never advances my-pa Alembic."""
import argparse
import hashlib
from pathlib import Path
from schema_contract import assert_shape

DDL_PATH = Path(__file__).resolve().parents[2] / 'migrations/001_weather_schema.PROPOSAL.sql'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',required=True)
    p.add_argument('--port',required=True,type=int)
    p.add_argument('--database',required=True,choices=['my_pa'])
    p.add_argument('--owner',required=True,choices=['my_pa'])
    p.add_argument('--expected-alembic',required=True)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    ddl=DDL_PATH.read_bytes()
    digest=hashlib.sha256(ddl).hexdigest()
    if digest != a.expected_sha256 or not a.host.startswith('/') or not 1 <= a.port <= 65535:
        raise ValueError('Explicit socket target and exact reviewed DDL digest required')
    if not a.apply:
        print(f'Dry run: database=my_pa owner=my_pa alembic={a.expected_alembic} weatherDDLsha256={digest}; no connection')
        return
    import psycopg
    with psycopg.connect(host=a.host,port=a.port,dbname=a.database,user=a.owner,connect_timeout=5,options='-c statement_timeout=5000') as conn:
        conn.execute('SELECT pg_advisory_xact_lock(823752019)')
        if conn.execute('SELECT current_database(),current_user').fetchone()!=('my_pa','my_pa'):
            raise ValueError('Unexpected physical identity')
        before=conn.execute('SELECT version_num FROM public.alembic_version').fetchall()
        if before != [(a.expected_alembic,)]:
            raise ValueError('Alembic version differs from approved target')
        if conn.execute("SELECT 1 FROM pg_namespace WHERE nspname='weather'").fetchone():
            assert_shape(conn.execute)
        else:
            conn.execute(ddl.decode())
            assert_shape(conn.execute)
        if conn.execute('SELECT version_num FROM public.alembic_version').fetchall()!=before:
            raise ValueError('Unexpected Alembic mutation')
    print(f'Weather schema verified; Alembic unchanged={a.expected_alembic}; source_sha256={digest}')


if __name__=='__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Weather schema operation refused or failed; no credentials printed') from None
