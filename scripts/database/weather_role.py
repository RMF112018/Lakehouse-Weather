#!/usr/bin/env python3
"""Explicit owner-only provisioning. No default target, environment, or secret reads."""
import argparse
import json
import os
from pathlib import Path
import secrets
from urllib.parse import quote

REVISION = 'a91b7d3c8e20'
TABLES = {'locations': 'SELECT, INSERT, UPDATE', 'stations': 'SELECT, INSERT, UPDATE',
          'observations': 'SELECT, INSERT', 'forecast_cache': 'SELECT, INSERT, UPDATE'}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', required=True, help='Owner Unix socket directory; no network owner connection')
    p.add_argument('--port', required=True, type=int)
    p.add_argument('--expected-alembic', required=True, help='Exact current owner chain revision; no stamp performed')
    p.add_argument('--database', required=True, choices=['my_pa'])
    p.add_argument('--owner', required=True, choices=['my_pa'])
    p.add_argument('--runtime', required=True, choices=['weather_runtime'])
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true')
    modes.add_argument('--verify-only', action='store_true')
    p.add_argument('--secret-file', type=Path, help='New absolute 0600 DATABASE_URL envfile; never overwritten')
    p.add_argument('--secret-owner-uid', type=int, help='Explicit app UID; requires root when different')
    p.add_argument('--runtime-host', help='Explicit Docker DNS name for runtime DATABASE_URL')
    p.add_argument('--runtime-port', type=int, default=5432)
    return p


def validate_args(a):
    if not a.host.startswith('/') or not 1 <= a.port <= 65535:
        raise ValueError('Owner connection must name a Unix socket directory and valid port')
    if a.secret_owner_uid is not None and (a.secret_owner_uid < 0 or (a.secret_owner_uid != os.getuid() and os.getuid() != 0)):
        raise ValueError('Secret ownership change requires root')
    if a.apply:
        if not a.secret_file or not a.secret_file.is_absolute() or not a.runtime_host:
            raise ValueError('Apply requires absolute --secret-file and explicit --runtime-host')
        if not all(c.isalnum() or c in '.-' for c in a.runtime_host) or not 1 <= a.runtime_port <= 65535:
            raise ValueError('Invalid runtime host or port')
        if a.secret_file.exists() or a.secret_file.is_symlink():
            raise ValueError('Secret destination already exists; refusing credential rotation')
        parent = a.secret_file.parent
        info = parent.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Secret parent must be owned by executor with permissions 0700')


def verify(conn, role):
    flags = conn.execute('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit,rolcanlogin FROM pg_roles WHERE rolname=%s', (role,)).fetchone()
    if flags != (False, False, False, False, False, False, True):
        raise ValueError('Runtime role missing or elevated')
    if conn.execute('SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=%s)', (role,)).fetchone():
        raise ValueError('Runtime role has memberships')
    if conn.execute("SELECT 1 FROM pg_database WHERE has_database_privilege(%s,oid,'CREATE')", (role,)).fetchone():
        raise ValueError('Runtime role can create database schemas')
    if conn.execute('SELECT 1 FROM pg_database WHERE datdba=(SELECT oid FROM pg_roles WHERE rolname=%s)', (role,)).fetchone():
        raise ValueError('Runtime role owns a database')
    if conn.execute('SELECT 1 FROM pg_namespace WHERE nspowner=(SELECT oid FROM pg_roles WHERE rolname=%s) OR (nspname NOT LIKE %s AND nspname <> %s AND has_schema_privilege(%s,oid,%s))', (role, 'pg_%', 'information_schema', role, 'CREATE')).fetchone():
        raise ValueError('Runtime role owns schema or has schema CREATE')
    if conn.execute("SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE p.prosecdef AND n.nspname NOT LIKE 'pg_%%' AND n.nspname NOT IN ('weather','information_schema') AND has_schema_privilege(%s,n.oid,'USAGE') AND has_function_privilege(%s,p.oid,'EXECUTE')", (role,role)).fetchone():
        raise ValueError('Runtime role can invoke application security definer function')
    rows = conn.execute("SELECT n.nspname,c.relname,c.relkind,c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind IN ('r','p','v','m','f','S') AND n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'").fetchall()
    for schema, table, kind, oid in rows:
        if kind == 'S':
            if conn.execute('SELECT has_sequence_privilege(%s,%s,%s)', (role, oid, 'USAGE,SELECT,UPDATE')).fetchone()[0]:
                raise ValueError('Runtime role has sequence privilege')
            continue
        for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
            allowed = schema == 'weather' and table in TABLES and privilege in TABLES[table].split(', ')
            actual = conn.execute('SELECT has_table_privilege(%s,%s,%s)', (role, oid, privilege)).fetchone()[0]
            if privilege in ('SELECT','INSERT','UPDATE','REFERENCES'):
                actual = actual or conn.execute('SELECT has_any_column_privilege(%s,%s,%s)', (role,oid,privilege)).fetchone()[0]
            if actual != allowed:
                raise ValueError('Unexpected runtime table privilege')
    if conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='weather' AND table_name=ANY(%s)", (list(TABLES),)).fetchone()[0] != 4:
        raise ValueError('Weather tables incomplete')
    if not conn.execute("SELECT has_schema_privilege(%s,'weather','USAGE')", (role,)).fetchone()[0]:
        raise ValueError('Missing weather schema USAGE')


def execute(a):
    validate_args(a)
    if not (a.apply or a.verify_only):
        print(json.dumps({'mode':'dry-run','database':a.database,'owner':a.owner,'runtime':a.runtime,'revision':REVISION,'grants':TABLES,'connects':False}))
        return
    import psycopg
    from psycopg import sql
    # Explicit parameters avoid a DSN or environment-derived connection target.
    with psycopg.connect(host=a.host, port=a.port, dbname=a.database, user=a.owner, connect_timeout=5, options='-c statement_timeout=5000') as conn:
        if conn.execute('SELECT current_database(),current_user').fetchone() != ('my_pa','my_pa'):
            raise ValueError('Unexpected physical database or owner identity')
        if conn.execute('SELECT version_num FROM public.alembic_version').fetchall() != [(a.expected_alembic,)]:
            raise ValueError('Unexpected owner migration chain')
        from schema_contract import assert_shape
        assert_shape(conn.execute)
        if a.verify_only:
            verify(conn,a.runtime)
        else:
            if conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(a.runtime,)).fetchone():
                raise ValueError('Runtime already exists; use --verify-only; no credential rotation permitted')
            password = secrets.token_urlsafe(48)
            conn.execute('SELECT pg_advisory_xact_lock(823752019)')
            conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Identifier(a.runtime),sql.Literal(password)))
            conn.execute(sql.SQL('GRANT CONNECT ON DATABASE my_pa TO {}').format(sql.Identifier(a.runtime)))
            conn.execute(sql.SQL('GRANT USAGE ON SCHEMA weather TO {}').format(sql.Identifier(a.runtime)))
            for table, privileges in TABLES.items():
                conn.execute(sql.SQL('GRANT '+privileges+' ON weather.{} TO {}').format(sql.Identifier(table),sql.Identifier(a.runtime)))
            verify(conn,a.runtime)
            fd=os.open(a.secret_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            try:
                with os.fdopen(fd,'w') as f:
                    f.write(f'postgresql://{a.runtime}:{quote(password,safe="")}@{a.runtime_host}:{a.runtime_port}/my_pa\n')
                    f.flush()
                    os.fsync(f.fileno())
                    if a.secret_owner_uid is not None:
                        os.fchown(f.fileno(), a.secret_owner_uid, -1)
                    os.fchmod(f.fileno(), 0o400)
                conn.commit()
            except BaseException:
                # Only this invocation's newly-created artifact; never an existing file.
                a.secret_file.unlink(missing_ok=True)
                raise
    print('Weather role checks passed' if a.verify_only else 'Weather role provisioned; protected envfile written')


if __name__ == '__main__':
    try:
        execute(parser().parse_args())
    except Exception:
        # Database errors can echo SQL/passwords; deliberately do not print exception details.
        raise SystemExit('Weather role operation refused or failed; no credentials printed') from None
