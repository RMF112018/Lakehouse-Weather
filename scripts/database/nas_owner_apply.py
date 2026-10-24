#!/usr/bin/env python3
"""Stdlib owner provisioner: reviewed SQL through exact Docker container Unix socket."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import secrets
import subprocess
from urllib.parse import quote
from schema_contract import QUERIES, EXPECTED
from weather_role import TABLES

DDL_PATH=Path(__file__).resolve().parents[2]/'migrations/001_weather_schema.PROPOSAL.sql'


def literal(value):
    if isinstance(value,bool):return 'TRUE' if value else 'FALSE'
    if isinstance(value,int):return str(value)
    return "'"+str(value).replace("'","''")+"'"


def shape_guard():
    checks=[]
    for q,rows in zip(QUERIES,EXPECTED):
        # Positional VALUES avoid duplicate result-column labels and preserve every field.
        expected='VALUES '+','.join('('+','.join(literal(v) for v in row)+')' for row in rows)
        checks.append(f"IF EXISTS (({q}) EXCEPT ({expected})) OR EXISTS (({expected}) EXCEPT ({q})) THEN RAISE EXCEPTION 'weather schema mismatch'; END IF;")
    return 'DO $shape$ BEGIN '+''.join(checks)+' END $shape$;'


FORECAST_TABLES = {'forecast_cache': 'SELECT, INSERT, UPDATE'}


def role_guard(role, tables):
    base = """DO $role$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=ROLE AND rolcanlogin AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolinherit)) THEN RAISE EXCEPTION 'role flags'; END IF;
 IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=ROLE)) THEN RAISE EXCEPTION 'role membership'; END IF;
 IF EXISTS (SELECT 1 FROM pg_database WHERE datdba=(SELECT oid FROM pg_roles WHERE rolname=ROLE) OR has_database_privilege(ROLE,oid,'CREATE')) THEN RAISE EXCEPTION 'database authority'; END IF;
 IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner=(SELECT oid FROM pg_roles WHERE rolname=ROLE) OR (nspname NOT LIKE 'pg_%' AND nspname<>'information_schema' AND has_schema_privilege(ROLE,oid,'CREATE'))) THEN RAISE EXCEPTION 'schema authority'; END IF;
 IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='S' AND n.nspname NOT LIKE 'pg_%' AND CASE WHEN c.relkind='S' THEN has_sequence_privilege(ROLE,c.oid,'USAGE,SELECT,UPDATE') ELSE FALSE END) THEN RAISE EXCEPTION 'sequence authority'; END IF;
 IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE p.prosecdef AND n.nspname NOT LIKE 'pg_%' AND n.nspname NOT IN ('weather','information_schema') AND has_schema_privilege(ROLE,n.oid,'USAGE') AND has_function_privilege(ROLE,p.oid,'EXECUTE')) THEN RAISE EXCEPTION 'security definer authority'; END IF;
 IF NOT has_schema_privilege(ROLE,'weather','USAGE') THEN RAISE EXCEPTION 'schema usage'; END IF;
 END $role$;""".replace('ROLE',literal(role))
    for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
        names=[table for table,grants in tables.items() if privilege in grants.split(', ')]
        allowed="n.nspname='weather' AND c.relname IN ("+','.join(literal(n) for n in names)+')' if names else 'FALSE'
        effective="has_table_privilege("+literal(role)+",c.oid,"+literal(privilege)+")"
        if privilege in ('SELECT','INSERT','UPDATE','REFERENCES'):
            effective="("+effective+" OR has_any_column_privilege("+literal(role)+",c.oid,"+literal(privilege)+"))"
        base+="DO $acl$ BEGIN IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind IN ('r','p','v','m','f') AND n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' AND "+effective+" AND NOT ("+allowed+")) THEN RAISE EXCEPTION 'unexpected effective table privilege'; END IF; END $acl$;"
    for table,grants in tables.items():
        for privilege in grants.split(', '):
            base+="DO $grant$ BEGIN IF NOT has_table_privilege("+literal(role)+","+literal('weather.'+table)+","+literal(privilege)+") THEN RAISE EXCEPTION 'missing role privilege'; END IF; END $grant$;"
    return base


def privilege_guard():
    return role_guard('weather_runtime',TABLES)+role_guard('weather_forecast',FORECAST_TABLES)


def build_sql(a,ddl,password=None,forecast_password=None):
    guard=f"""BEGIN;
SET LOCAL statement_timeout='15s';
SELECT pg_advisory_xact_lock(823752019);
DO $identity$ BEGIN
 IF current_database()<>'my_pa' OR current_user<>'my_pa' THEN RAISE EXCEPTION 'physical identity mismatch'; END IF;
 IF (SELECT array_agg(version_num::text ORDER BY version_num) FROM public.alembic_version) IS DISTINCT FROM ARRAY[{literal(a.expected_alembic)}]::text[] THEN RAISE EXCEPTION 'owner chain mismatch'; END IF;
 END $identity$;
"""
    if password is not None:
        guard+="DO $exists$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='weather') THEN EXECUTE "+literal(ddl)+"; END IF; END $exists$;\n"
    guard+=shape_guard()
    if password is not None:
        guard+='CREATE ROLE weather_runtime LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '+literal(password)+';\n'
        guard+='GRANT CONNECT ON DATABASE my_pa TO weather_runtime; GRANT USAGE ON SCHEMA weather TO weather_runtime;\n'
        for table,privileges in TABLES.items():guard+=f'GRANT {privileges} ON weather.{table} TO weather_runtime;\n'
    if password is not None:
        if forecast_password is None:raise ValueError('Both fresh role credentials required')
        guard+='CREATE ROLE weather_forecast LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '+literal(forecast_password)+';\n'
        guard+='GRANT CONNECT ON DATABASE my_pa TO weather_forecast; GRANT USAGE ON SCHEMA weather TO weather_forecast; GRANT SELECT, INSERT, UPDATE ON weather.forecast_cache TO weather_forecast;\n'
    guard+=privilege_guard()
    guard+=f"DO $unchanged$ BEGIN IF (SELECT array_agg(version_num::text ORDER BY version_num) FROM public.alembic_version) IS DISTINCT FROM ARRAY[{literal(a.expected_alembic)}]::text[] THEN RAISE EXCEPTION 'owner chain changed'; END IF; END $unchanged$; COMMIT;"
    return guard


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--docker-bin',required=True)
    p.add_argument('--postgres-container',required=True)
    p.add_argument('--expected-container-id',required=True)
    p.add_argument('--expected-alembic',required=True)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--database',required=True,choices=['my_pa'])
    p.add_argument('--owner',required=True,choices=['my_pa'])
    modes=p.add_mutually_exclusive_group()
    modes.add_argument('--apply',action='store_true')
    modes.add_argument('--verify-only',action='store_true')
    p.add_argument('--secret-file',type=Path)
    p.add_argument('--forecast-secret-file',type=Path)
    p.add_argument('--secret-owner-uid',type=int)
    p.add_argument('--runtime-host')
    p.add_argument('--runtime-port',type=int,default=5432)
    a=p.parse_args()
    ddl=DDL_PATH.read_bytes();digest=hashlib.sha256(ddl).hexdigest()
    if digest!=a.expected_sha256 or not re.fullmatch('[0-9a-f]{64}',a.expected_container_id) or not re.fullmatch('[0-9a-f]{12}',a.expected_alembic) or not Path(a.docker_bin).is_absolute():raise ValueError('Explicit exact bindings required')
    if not (a.apply or a.verify_only):
        print(f'Dry run only; no Docker connection; database=my_pa owner=my_pa expected_alembic={a.expected_alembic} schema_sha256={digest}')
        return
    inspected=subprocess.run([a.docker_bin,'inspect','--format','{{.Id}}',a.postgres_container],capture_output=True,text=True,check=True)
    if inspected.stdout.strip()!=a.expected_container_id:raise ValueError('Container identity mismatch')
    password=None
    forecast_password=None
    if a.apply:
        if not a.secret_file or not a.secret_file.is_absolute() or not a.runtime_host or not re.fullmatch('[A-Za-z0-9.-]+',a.runtime_host) or not 1<=a.runtime_port<=65535:raise ValueError('Secret path and runtime host required')
        if not a.forecast_secret_file or not a.forecast_secret_file.is_absolute() or a.forecast_secret_file==a.secret_file:raise ValueError('Two distinct new absolute secret destinations required')
        for path in (a.secret_file,a.forecast_secret_file):
            info=path.parent.stat()
            if info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('Secret parent must be executor owned 0700')
            if path.exists() or path.is_symlink():raise ValueError('Existing secret destination; refusing rotation')
        if a.secret_owner_uid is not None and (a.secret_owner_uid<0 or (a.secret_owner_uid!=os.getuid() and os.getuid()!=0)):raise ValueError('Secret UID requires root')
        password=secrets.token_urlsafe(48)
        forecast_password=secrets.token_urlsafe(48)
        for role,path,secret in (('weather_runtime',a.secret_file,password),('weather_forecast',a.forecast_secret_file,forecast_password)):
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as f:
                f.write(f'postgresql://{role}:{quote(secret,safe="")}@{a.runtime_host}:{a.runtime_port}/my_pa\n')
                f.flush();os.fsync(f.fileno())
                if a.secret_owner_uid is not None:os.fchown(f.fileno(),a.secret_owner_uid,-1)
                os.fchmod(f.fileno(),0o400)
    # Immutable inspected ID is used for exec, avoiding a container-name replacement race.
    result=subprocess.run([a.docker_bin,'exec','-i',a.expected_container_id,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','my_pa','-d','my_pa'],input=build_sql(a,ddl.decode(),password,forecast_password),capture_output=True,text=True)
    if result.returncode:
        # Keep owned protected artifact on ambiguous transport failure; do not rotate/retry.
        # Transaction rolls back on ordinary SQL failure. Owner must reconcile unknown commit outcome.
        raise RuntimeError('Owner SQL failed or transport outcome unknown; preserve secret and reconcile, never retry blindly')
    print(f'Weather owner operation verified; alembic unchanged={a.expected_alembic}; schema_sha256={digest}')


if __name__=='__main__':
    try:main()
    except Exception:
        raise SystemExit('Owner operation refused/failed; if apply began, retain protected secret and reconcile transaction outcome; no credentials printed') from None
