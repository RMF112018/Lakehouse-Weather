"""Database readiness. Integration explicitly opts into synthetic loopback fixture."""
import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts/database'
sys.path.insert(0,str(SCRIPTS))
import schema_contract
import weather_role
import schema_contract_rollups
import nas_rollups_apply
import nas_owner_apply


class DatabaseReadinessTests(unittest.TestCase):
    def args(self,*extra):
        return weather_role.parser().parse_args(['--host','/tmp/fixture','--port','5432','--database','my_pa','--owner','my_pa','--runtime','weather_runtime','--expected-alembic','synthetic',*extra])

    def test_dry_run_has_no_driver_dependency(self):
        result=subprocess.run([sys.executable,str(SCRIPTS/'weather_role.py'),'--host','/tmp/fixture','--port','5432','--database','my_pa','--owner','my_pa','--runtime','weather_runtime','--expected-alembic','synthetic'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0)
        self.assertIn('"connects": false',result.stdout)

    def test_refuses_unsafe_target_and_existing_secret(self):
        a=self.args();a.host='production.example'
        with self.assertRaises(ValueError):weather_role.validate_args(a)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'secret';path.touch()
            with self.assertRaises(ValueError):weather_role.validate_args(self.args('--apply','--secret-file',str(path),'--runtime-host','postgres'))

    def test_owner_revision_embeds_exact_contract(self):
        migration=ROOT.parent/'my-pa/migrations/versions/20261023_a91b7d3c8e20_weather_schema.py'
        if not migration.exists():self.skipTest('Owner repository not checked out alongside Lakehouse')
        tree=ast.parse(migration.read_text())
        frozen=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and n.targets[0].id=='EXPECTED')
        self.assertEqual(frozen,schema_contract.EXPECTED)


@unittest.skipUnless(os.environ.get('WEATHER_SYNTHETIC_PG')=='127.0.0.1:55439','Explicit disposable fixture opt-in required')
class SyntheticPostgresTests(unittest.TestCase):
    """Never accepts arbitrary DSNs: this suite has one fixed synthetic target."""
    def test_schema_roles_persistence_and_denials(self):
        import psycopg
        from psycopg import sql
        with psycopg.connect(host='127.0.0.1',port=55439,dbname='my_pa',user='my_pa') as owner:
            schema_contract_rollups.assert_shape(owner.execute)
            # Isolated ownerchain predecessor marker is synthetic; no canonical history claim.
            owner.execute('CREATE TABLE IF NOT EXISTS public.alembic_version(version_num text NOT NULL)')
            owner.execute('TRUNCATE public.alembic_version')
            owner.execute("INSERT INTO public.alembic_version VALUES ('b9025e7fb738')")
            if not owner.execute("SELECT 1 FROM pg_roles WHERE rolname='weather_runtime'").fetchone():
                owner.execute('CREATE ROLE weather_runtime LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
                owner.execute('GRANT CONNECT ON DATABASE my_pa TO weather_runtime')
                owner.execute('GRANT USAGE ON SCHEMA weather TO weather_runtime')
                for table,privileges in nas_rollups_apply.ROLLUP_TABLES.items():
                    owner.execute(sql.SQL('GRANT '+privileges+' ON weather.{} TO weather_runtime').format(sql.Identifier(table)))
            if not owner.execute("SELECT 1 FROM pg_roles WHERE rolname='weather_forecast'").fetchone():
                owner.execute('CREATE ROLE weather_forecast LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
                owner.execute('GRANT CONNECT ON DATABASE my_pa TO weather_forecast')
                owner.execute('GRANT USAGE ON SCHEMA weather TO weather_forecast')
                owner.execute('GRANT SELECT,INSERT,UPDATE ON weather.forecast_cache TO weather_forecast')
            owner.execute('CREATE TABLE IF NOT EXISTS public.synthetic_owner_fact(id integer)')
            owner.execute(nas_owner_apply.role_guard('weather_runtime',nas_rollups_apply.ROLLUP_TABLES))
            owner.commit()
            owner.execute('GRANT SELECT ON public.synthetic_owner_fact TO weather_runtime')
            with self.assertRaises(psycopg.errors.RaiseException):owner.execute(nas_owner_apply.role_guard('weather_runtime',nas_rollups_apply.ROLLUP_TABLES))
            owner.rollback()
            owner.execute('ALTER ROLE weather_runtime INHERIT')
            with self.assertRaises(psycopg.errors.RaiseException):owner.execute(nas_owner_apply.role_guard('weather_runtime',nas_rollups_apply.ROLLUP_TABLES))
            owner.rollback()
            owner.execute('ALTER TABLE weather.locations ADD COLUMN drift text')
            with self.assertRaises(ValueError):schema_contract_rollups.assert_shape(owner.execute)
            owner.rollback()
        from weather.store import PostgresStore
        self.assertTrue(PostgresStore('postgresql://weather_runtime@127.0.0.1:55439/my_pa','nonproduction').check_ready())
        with psycopg.connect(host='127.0.0.1',port=55439,dbname='my_pa',user='weather_runtime',autocommit=True) as runtime:
            runtime.execute("INSERT INTO weather.locations VALUES ('synthetic-readiness','{}') ON CONFLICT DO NOTHING")
            self.assertEqual(runtime.execute("SELECT count(*) FROM weather.locations WHERE id='synthetic-readiness'").fetchone()[0],1)
            for statement in ('DELETE FROM weather.locations','TRUNCATE weather.locations','CREATE TABLE weather.forbidden(id int)','SELECT * FROM public.synthetic_owner_fact','UPDATE weather.observations SET measurements=measurements'):
                with self.subTest(statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):runtime.execute(statement)

    def test_canonical_revision_empty_and_adoption_without_ownerchain_upgrade(self):
        import importlib.util
        from sqlalchemy import create_engine
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        migration=ROOT.parent/'my-pa/migrations/versions/20261023_a91b7d3c8e20_weather_schema.py'
        spec=importlib.util.spec_from_file_location('synthetic_weather_migration',migration)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        engine=create_engine('postgresql+psycopg://my_pa@127.0.0.1:55439/my_pa')
        with engine.connect() as conn:
            transaction=conn.begin()
            before=conn.exec_driver_sql('SELECT version_num FROM public.alembic_version').fetchall()
            original=conn.exec_driver_sql('SELECT * FROM weather.locations ORDER BY id').fetchall()
            with Operations.context(MigrationContext.configure(conn)):
                module.upgrade()  # exact deployed-schema adoption preserves synthetic rows
            self.assertEqual(original,conn.exec_driver_sql('SELECT * FROM weather.locations ORDER BY id').fetchall())
            conn.exec_driver_sql('DROP SCHEMA weather CASCADE')  # transaction rolls back owned fixture only
            with Operations.context(MigrationContext.configure(conn)):
                module.upgrade()  # same frozen revision from absent weather schema
            schema_contract.assert_shape(conn.exec_driver_sql) # original frozen seven-table contract
            # Exercise the frozen7 owner ACL/catalog adapter before the additive
            # follow-on, rather than weakening its historical assertions to8.
            conn.exec_driver_sql('GRANT USAGE ON SCHEMA weather TO weather_runtime,weather_forecast')
            for table,privileges in weather_role.TABLES.items():
                conn.exec_driver_sql('GRANT '+privileges+' ON weather.'+table+' TO weather_runtime')
            conn.exec_driver_sql('GRANT SELECT,INSERT,UPDATE ON weather.forecast_cache TO weather_forecast')
            conn.exec_driver_sql((nas_owner_apply.shape_guard()+nas_owner_apply.privilege_guard()).replace('%','%%'))
            followon=migration.with_name('20261023_f8b21e4d6c90_weather_rollups.py')
            spec=importlib.util.spec_from_file_location('synthetic_rollup_migration',followon)
            rollup=importlib.util.module_from_spec(spec);spec.loader.exec_module(rollup)
            with Operations.context(MigrationContext.configure(conn)):
                rollup.upgrade()
            conn.exec_driver_sql('GRANT SELECT,INSERT,UPDATE ON weather.observation_rollups TO weather_runtime')
            schema_contract_rollups.assert_shape(conn.exec_driver_sql)
            conn.exec_driver_sql(nas_owner_apply.role_guard('weather_runtime',nas_rollups_apply.ROLLUP_TABLES).replace('%','%%'))
            self.assertEqual(before,conn.exec_driver_sql('SELECT version_num FROM public.alembic_version').fetchall())
            with Operations.context(MigrationContext.configure(conn)),self.assertRaises(RuntimeError):module.downgrade()
            transaction.rollback()
        engine.dispose()

    def test_stdlib_owner_adapter_catalog_audit(self):
        import nas_owner_apply
        import psycopg
        from types import SimpleNamespace
        verify=nas_rollups_apply.build_sql('b9025e7fb738','',False)
        with psycopg.connect(host='127.0.0.1',port=55439,dbname='my_pa',user='my_pa',autocommit=True) as conn:
            conn.execute(verify)
            for drift in ('GRANT SELECT ON public.synthetic_owner_fact TO PUBLIC',
                          'GRANT SELECT(id) ON public.synthetic_owner_fact TO weather_forecast',
                          "CREATE FUNCTION public.synthetic_definer() RETURNS int LANGUAGE SQL SECURITY DEFINER AS 'SELECT 1'",
                          'GRANT CREATE ON DATABASE my_pa TO weather_runtime',
                          'GRANT SELECT ON weather.observations TO weather_forecast'):
                conn.execute('BEGIN')
                conn.execute(drift)
                with self.subTest(drift=drift),self.assertRaises(psycopg.errors.RaiseException):conn.execute(nas_owner_apply.role_guard('weather_runtime',nas_rollups_apply.ROLLUP_TABLES)+nas_owner_apply.role_guard('weather_forecast',nas_owner_apply.FORECAST_TABLES))
                conn.execute('ROLLBACK')

    def test_z_forecast_role_cache_only(self):
        import psycopg
        with psycopg.connect(host='127.0.0.1',port=55439,dbname='my_pa',user='weather_forecast',autocommit=True) as conn:
            # Does not need location-table SELECT to write an existing location FK.
            conn.execute("INSERT INTO weather.forecast_cache VALUES ('synthetic-readiness','{}') ON CONFLICT(location_id) DO UPDATE SET payload=EXCLUDED.payload")
            self.assertIsNotNone(conn.execute("SELECT payload FROM weather.forecast_cache WHERE location_id='synthetic-readiness'").fetchone())
            for statement in ('SELECT * FROM weather.observation_rollups','SELECT * FROM weather.observations','SELECT * FROM weather.locations','INSERT INTO weather.locations VALUES (\'forbidden\',\'{}\')','DELETE FROM weather.forecast_cache','CREATE TABLE weather.forbidden(id int)','SELECT * FROM public.synthetic_owner_fact'):
                with self.subTest(statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):conn.execute(statement)
