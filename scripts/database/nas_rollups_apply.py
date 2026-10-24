#!/usr/bin/env python3
"""Explicit owner-only 7→8 weather follow-on; no secrets, stamping, or live defaults."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import sys
from schema_contract import QUERIES, EXPECTED as BEFORE
from schema_contract_rollups import EXPECTED as AFTER
from nas_owner_apply import literal, role_guard, FORECAST_TABLES
from weather_role import TABLES

DDL_PATH=Path(__file__).resolve().parents[2]/'migrations/002_weather_rollups.PROPOSAL.sql'
ROLLUP_TABLES={**TABLES,'observation_rollups':'SELECT, INSERT, UPDATE'}


def shape_guard(expected):
    checks=[]
    for query,rows in zip(QUERIES,expected):
        values='VALUES '+','.join('('+','.join(literal(v) for v in row)+')' for row in rows)
        checks.append(f"IF EXISTS (({query}) EXCEPT ({values})) OR EXISTS (({values}) EXCEPT ({query})) THEN RAISE EXCEPTION 'weather schema mismatch'; END IF;")
    return 'DO $shape$ BEGIN '+''.join(checks)+' END $shape$;'


def build_sql(expected_alembic, ddl, apply=False):
    identity="""DO $identity$ BEGIN
 IF current_database()<>'my_pa' OR current_user<>'my_pa' THEN RAISE EXCEPTION 'physical identity mismatch'; END IF;
 IF (SELECT array_agg(version_num::text ORDER BY version_num) FROM public.alembic_version) IS DISTINCT FROM ARRAY[REVISION]::text[] THEN RAISE EXCEPTION 'owner chain mismatch'; END IF;
 END $identity$;""".replace('REVISION',literal(expected_alembic))
    result="BEGIN; SET LOCAL statement_timeout='15s'; SELECT pg_advisory_xact_lock(823752019);"+identity
    if apply:
        # A nonempty legacy archive requires a separately reviewed bounded
        # backfill campaign. The one-step owner operation never ignores history.
        create=shape_guard(BEFORE)+role_guard('weather_runtime',TABLES)+role_guard('weather_forecast',FORECAST_TABLES)
        create+="LOCK TABLE weather.observations IN SHARE MODE; DO $empty$ BEGIN IF EXISTS(SELECT 1 FROM weather.observations LIMIT 1) THEN RAISE EXCEPTION 'nonempty archive requires reviewed backfill'; END IF; END $empty$;"
        create+=ddl+' GRANT SELECT, INSERT, UPDATE ON weather.observation_rollups TO weather_runtime;'
        result+="DO $create$ BEGIN IF to_regclass('weather.observation_rollups') IS NULL THEN EXECUTE "+literal(create)+"; END IF; END $create$;"
    result+=shape_guard(AFTER)
    if apply:
        # Canonical Alembic DDL intentionally grants no privileges. Admit only
        # the exact preexisting runtime policy before adding this one new grant.
        baseline=role_guard('weather_runtime',TABLES)+role_guard('weather_forecast',FORECAST_TABLES)
        result+="DO $grant_new$ BEGIN IF NOT has_table_privilege('weather_runtime','weather.observation_rollups','SELECT,INSERT,UPDATE') AND NOT has_any_column_privilege('weather_runtime','weather.observation_rollups','SELECT,INSERT,UPDATE') THEN EXECUTE "+literal(baseline)+"; GRANT SELECT, INSERT, UPDATE ON weather.observation_rollups TO weather_runtime; END IF; END $grant_new$;"
    result+=role_guard('weather_runtime',ROLLUP_TABLES)+role_guard('weather_forecast',FORECAST_TABLES)+identity+' COMMIT;'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docker-bin',required=True)
    parser.add_argument('--postgres-container',required=True)
    parser.add_argument('--expected-container-id',required=True)
    parser.add_argument('--expected-alembic',required=True)
    parser.add_argument('--expected-sha256',required=True)
    parser.add_argument('--database',required=True,choices=['my_pa'])
    parser.add_argument('--owner',required=True,choices=['my_pa'])
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--apply',action='store_true')
    modes.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    ddl=DDL_PATH.read_bytes()
    if hashlib.sha256(ddl).hexdigest()!=args.expected_sha256 or not re.fullmatch('[0-9a-f]{64}',args.expected_container_id) or not re.fullmatch('[0-9a-f]{12}',args.expected_alembic) or not Path(args.docker_bin).is_absolute():
        raise ValueError('Exact reviewed bindings required')
    if not (args.apply or args.verify_only):
        print('Dry run only: no Docker connection; owner-chain unchanged; empty-archive guard required')
        return
    inspected=subprocess.run([args.docker_bin,'inspect','--format','{{.Id}}',args.postgres_container],capture_output=True,text=True,check=True,timeout=15)
    if inspected.stdout.strip()!=args.expected_container_id:
        raise ValueError('Container identity mismatch')
    query=build_sql(args.expected_alembic,ddl.decode(),args.apply)
    subprocess.run([args.docker_bin,'exec','-i',args.expected_container_id,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','my_pa','-d','my_pa'],input=query,text=True,check=True,capture_output=True,timeout=30)
    print('Weather rollup schema/roles verified; owner chain unchanged')


if __name__=='__main__':
    try:
        main()
    except Exception:
        print('Weather rollup owner operation refused or outcome unknown; reconcile the exact target before retrying',file=sys.stderr)
        raise SystemExit(1) from None
