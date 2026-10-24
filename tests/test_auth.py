"""Real disposable PostgreSQL authentication and transport acceptance tests."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from datetime import timedelta
from weather.auth import Auth, ORIGIN, COOKIE, LOGIN_COOKIE, digest, password_hash, verify_password
from weather.server import Application, dispatch, response
from weather.store import PostgresStore

ROOT=Path(__file__).resolve().parents[1]

class PasswordTests(unittest.TestCase):
    def test_bounded_salted_kdf(self):
        first=password_hash('synthetic-password-123')
        self.assertNotEqual(first,password_hash('synthetic-password-123'))
        self.assertTrue(verify_password('synthetic-password-123',first))
        self.assertFalse(verify_password('incorrect-password',first))
        for value in ('short','x'*129,'😀'*129):
            with self.assertRaises(ValueError):password_hash(value)
        self.assertFalse(verify_password('synthetic-password-123','scrypt$999999$8$1$bad$bad'))

    def test_setup_refuses_noninteractive_plaintext_arguments(self):
        env=dict(os.environ,WEATHER_MODE='postgres')
        p=subprocess.run([sys.executable,'-m','weather','setup-password','--email','synthetic@example.invalid'],cwd=ROOT,env=env,input='',text=True,capture_output=True)
        self.assertEqual(p.returncode,1)
        self.assertNotIn('password-',p.stdout+p.stderr)

    def test_setup_redacts_driver_constructor_and_write_failures(self):
        from unittest.mock import patch
        from weather.__main__ import main
        class DriverFailure(Exception):
            pass
        sentinel='synthetic-secret%ZZ-never-display'
        for phase in ('constructor','write'):
            stderr=io.StringIO()
            with patch.dict(os.environ,{'WEATHER_MODE':'postgres','WEATHER_AUTH_ORIGIN':ORIGIN}), patch.object(sys,'argv',['weather','setup-password','--email','synthetic@example.invalid']), patch('sys.stdin.isatty',return_value=True), patch('sys.stderr',stderr), patch('sys.stderr.isatty',return_value=True), patch('weather.__main__.PostgresStore') as store, patch('weather.__main__.Auth') as auth, patch('getpass.getpass',side_effect=['synthetic-password-123','synthetic-password-123']) as prompt:
                if phase=='constructor':store.side_effect=DriverFailure(sentinel)
                else:auth.return_value.setup.side_effect=DriverFailure(sentinel)
                self.assertEqual(main(),1)
                if phase=='constructor':prompt.assert_not_called()
                else:auth.return_value.setup.assert_called_once()
            self.assertNotIn(sentinel,stderr.getvalue())
            self.assertNotIn('Traceback',stderr.getvalue())
            self.assertIn('Weather startup/request failed',stderr.getvalue())

    def test_setup_refuses_getpass_fallback_warning_without_plaintext_read(self):
        import getpass
        import warnings
        from unittest.mock import patch
        from weather.__main__ import main
        def unavailable(*args):
            warnings.warn('Synthetic hidden terminal unavailable',getpass.GetPassWarning)
            sys.stdin.readline()  # Must never execute after the warning.
        with patch.dict(os.environ,{'WEATHER_MODE':'postgres','WEATHER_AUTH_ORIGIN':ORIGIN}), patch.object(sys,'argv',['weather','setup-password','--email','synthetic@example.invalid']), patch('sys.stdin.isatty',return_value=True), patch('sys.stderr.isatty',return_value=True), patch('weather.__main__.PostgresStore'), patch('getpass.getpass',side_effect=unavailable), patch('sys.stdin.readline',side_effect=AssertionError('Plaintext read attempted')) as reader:
            self.assertEqual(main(),1)
            reader.assert_not_called()

@unittest.skipUnless(os.environ.get('WEATHER_SYNTHETIC_PG')=='127.0.0.1:55439','Disposable fixture opt-in required')
class AuthPostgresTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.psycopg=psycopg
        with self.owner() as c:
            c.execute('TRUNCATE weather.auth_sessions,weather.auth_limits,weather.auth_users')
        self.store=PostgresStore('postgresql://weather_runtime@127.0.0.1:55439/my_pa','nonproduction')
        self.auth=Auth(self.store)
        self.auth.setup('synthetic@example.invalid','synthetic-password-123')
        self.other=Auth(self.store)
        self.app=Application([],self.store,'postgres',auth=self.auth)
    def owner(self):
        return self.psycopg.connect(host='127.0.0.1',port=55439,dbname='my_pa',user='my_pa')
    def request(self,method,path,headers=None,body=None,app=None):
        raw=json.dumps(body or {}).encode();h={'content-type':'application/json','content-length':str(len(raw)),**(headers or {})}
        return dispatch(app or self.app,ROOT/'web',method,path,h,io.BytesIO(raw))
    def challenge(self,auth=None):
        status,data,_,headers=(auth or self.auth).handle('GET','/api/auth/status',{}, {})
        self.assertEqual(status,200)
        return {'cookie':headers[0][1].split(';')[0],'origin':ORIGIN,'x-weather-csrf':data['csrf']}
    def login(self):
        h=self.challenge();r=self.request('POST','/api/auth/login',h,{'email':'synthetic@example.invalid','password':'synthetic-password-123'})
        self.assertEqual(r[0],200)
        cookie=r[3][0][1]
        for field in ('Secure','HttpOnly','SameSite=Strict','Path=/weather/','Max-Age=5183999'):
            if field.startswith('Max-Age'):continue
            self.assertIn(field,cookie)
        self.assertNotIn('Domain=',cookie)
        return {'cookie':cookie.split(';')[0],'origin':ORIGIN,'x-weather-csrf':r[1]['csrf']}
    def test_protected_assets_api_setup_and_generic_failure(self):
        for path in ('/app.js','/style.css','/api/dashboard','/api/health','/api/ready','/api/history','/login.html'):
            self.assertEqual(self.request('GET',path)[0],401,path)
        self.assertEqual(self.request('GET','/')[0],303)
        for path in ('/login','/login.js','/login.css'):
            self.assertEqual(self.request('GET',path)[0],200)
        h=self.challenge()
        body={'email':'synthetic@example.invalid','password':'incorrect-password'}
        self.assertEqual(self.request('POST','/api/auth/login',h,body)[0],401)
        self.assertEqual(self.request('POST','/api/auth/setup',h,body)[0],404)
        with self.owner() as c:
            stored=c.execute('SELECT password_hash FROM weather.auth_users').fetchone()[0]
            self.assertNotIn('synthetic-password',stored)
            rows=c.execute('SELECT token_hash,csrf_hash FROM weather.auth_sessions').fetchall()
            self.assertTrue(all(len(a)==64 and len(b)==64 for a,b in rows))
    def test_origin_csrf_rotation_logout_and_replay(self):
        h=self.challenge();body={'email':'synthetic@example.invalid','password':'synthetic-password-123'}
        for changes in ({'origin':''},{'origin':ORIGIN+'.evil'},{'x-weather-csrf':'0'*64}):
            self.assertEqual(self.request('POST','/api/auth/login',{**h,**changes},body)[0],403)
        h=self.login()
        for route in ('logout','refresh'):
            self.assertEqual(self.request('POST','/api/auth/'+route,{**h,'origin':ORIGIN+'.evil'})[0],403)
            self.assertEqual(self.request('POST','/api/auth/'+route,{**h,'x-weather-csrf':'0'*64})[0],403)
        self.assertEqual(self.request('GET','/api/dashboard',h)[0],200)
        status=self.request('GET','/api/auth/status',h)
        self.assertEqual(status[1]['csrf'],h['x-weather-csrf'])
        with self.owner() as c:
            old=c.execute("SELECT created_at,expires_at FROM weather.auth_sessions WHERE kind='session' AND NOT revoked").fetchone()
        r=self.request('POST','/api/auth/refresh',h)
        self.assertEqual(r[0],200)
        self.assertEqual(self.request('GET','/api/dashboard',h)[0],401)
        self.assertEqual(self.request('POST','/api/auth/refresh',h)[0],403)
        new={**h,'cookie':r[3][0][1].split(';')[0],'x-weather-csrf':r[1]['csrf']}
        with self.owner() as c:
            self.assertEqual(c.execute("SELECT created_at,expires_at FROM weather.auth_sessions WHERE kind='session' AND NOT revoked").fetchone(),old)
        self.assertEqual(self.request('POST','/api/auth/logout',new)[0],200)
        self.assertEqual(self.request('GET','/api/dashboard',new)[0],401)
    def test_expiry_password_reset_and_absolute_cap(self):
        h=self.login()
        self.auth.setup('synthetic@example.invalid','replacement-password-123')
        self.assertEqual(self.request('GET','/api/dashboard',h)[0],401)
        self.auth.setup('synthetic@example.invalid','synthetic-password-123');h=self.login()
        with self.owner() as c:
            c.execute("UPDATE weather.auth_sessions SET created_at=CURRENT_TIMESTAMP-INTERVAL '61 days',expires_at=CURRENT_TIMESTAMP-INTERVAL '1 day' WHERE kind='session'")
        self.assertEqual(self.request('GET','/api/dashboard',h)[0],401)
    def test_shared_limits_two_contexts_and_kdf_slots(self):
        for i in range(11):
            h=self.challenge(self.auth if i%2 else self.other)
            r=self.request('POST','/api/auth/login',h,{'email':'unknown@example.invalid','password':'incorrect-password'})
            self.assertEqual(r[0],401 if i<10 else 429)
        with self.owner() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM weather.auth_limits').fetchone()[0],3)
        with self.owner() as c:
            c.execute('TRUNCATE weather.auth_limits')
            c.commit()
            c.execute('SELECT pg_advisory_xact_lock(823752022)');c.execute('SELECT pg_advisory_xact_lock(823752023)')
            h=self.challenge();r=self.request('POST','/api/auth/login',h,{'email':'synthetic@example.invalid','password':'synthetic-password-123'})
            self.assertEqual(r[0],429)
    def test_concurrent_refresh_one_winner_and_challenge_limit(self):
        from concurrent.futures import ThreadPoolExecutor
        h=self.login()
        app2=Application([],self.store,'postgres',auth=self.other)
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending=[pool.submit(self.request,'POST','/api/auth/refresh',h,None,app) for app in (self.app,app2)]
            results=[f.result() for f in pending]
        self.assertEqual(sorted(r[0] for r in results),[200,403])
        winner=next(r for r in results if r[0]==200)
        self.assertEqual(next(r for r in results if r[0]==403)[3],[])
        winning_cookie=winner[3][0][1].split(';')[0]
        self.assertEqual(self.request('GET','/api/dashboard',{'cookie':winning_cookie})[0],200)
        self.assertEqual(self.request('POST','/api/auth/logout',{**h,'origin':ORIGIN})[0],403)
        with self.owner() as c:
            c.execute("UPDATE weather.auth_limits SET attempts=60 WHERE scope='challenge'")
        self.assertEqual(self.request('GET','/api/auth/status')[0],429)
        with self.owner() as c:
            self.assertLessEqual(c.execute('SELECT count(*) FROM weather.auth_sessions').fetchone()[0],3)

    def test_wsgi_cookie_and_prefix_contract(self):
        from weather.server import wsgi
        status=[]
        environ={'REQUEST_METHOD':'GET','PATH_INFO':'/','SCRIPT_NAME':'/weather','QUERY_STRING':'','wsgi.input':io.BytesIO(b'')}
        raw=b''.join(wsgi(self.app,ROOT/'web')(environ,lambda value,headers:status.append((value,headers))))
        self.assertEqual(status[0][0],'303 See Other')
        self.assertIn(('Location','/weather/login'),status[0][1])
        self.assertIn(('Cache-Control','no-store'),status[0][1])
        self.assertNotIn(b'synthetic@example.invalid',raw)
        h=self.challenge();body=json.dumps({'email':'synthetic@example.invalid','password':'synthetic-password-123'}).encode()
        environ.update(REQUEST_METHOD='POST',PATH_INFO='/api/auth/login',CONTENT_TYPE='application/json',CONTENT_LENGTH=str(len(body)),HTTP_COOKIE=h['cookie'],HTTP_ORIGIN=ORIGIN,HTTP_X_WEATHER_CSRF=h['x-weather-csrf'])
        environ['wsgi.input']=io.BytesIO(body);status=[]
        raw=b''.join(wsgi(self.app,ROOT/'web')(environ,lambda value,headers:status.append((value,headers))))
        self.assertEqual(status[0][0],'200 OK')
        cookie=next(value for key,value in status[0][1] if key=='Set-Cookie')
        self.assertTrue(cookie.startswith('__Secure-weather_session='))
        for field in ('Path=/weather/','HttpOnly','Secure','SameSite=Strict'):
            self.assertIn(field,cookie)
        self.assertNotIn(b'synthetic-password-123',raw)

    def test_challenge_cookie_cannot_overwrite_remembered_session(self):
        remembered=self.login()
        anonymous=self.request('GET','/api/auth/status')
        cookies=[v for k,v in anonymous[3] if k=='Set-Cookie']
        self.assertEqual(len(cookies),1)
        self.assertTrue(cookies[0].startswith(LOGIN_COOKIE+'='))
        self.assertFalse(any(v.startswith(COOKIE+'=') for v in cookies))
        self.assertEqual(self.request('GET','/api/dashboard',remembered)[0],200)
        challenge={'cookie':cookies[0].split(';')[0]+'; '+remembered['cookie'],'origin':ORIGIN,'x-weather-csrf':anonymous[1]['csrf']}
        login=self.request('POST','/api/auth/login',challenge,{'email':'synthetic@example.invalid','password':'synthetic-password-123'})
        self.assertEqual(login[0],200)
        self.assertTrue(login[3][0][1].startswith(COOKIE+'='))
        self.assertTrue(login[3][1][1].startswith(LOGIN_COOKIE+'=;'))
        self.assertIn('Max-Age=0',login[3][1][1])

    def test_password_reset_serializes_with_login_and_refresh(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        for route in ('login','refresh'):
            self.auth.setup('synthetic@example.invalid','synthetic-password-123')
            headers=self.challenge() if route=='login' else self.login()
            body={'email':'synthetic@example.invalid','password':'synthetic-password-123'} if route=='login' else {}
            paused,release,reset_waiting,reset_acquired=(threading.Event() for _ in range(4))
            underlying=self.store
            class PausedAuth(Auth):
                def _issue(inner,c,kind,expires,created=None):
                    if kind=='session':
                        paused.set()
                        if not release.wait(4):raise AssertionError('Reset coordination timed out')
                    return super()._issue(c,kind,expires,created)
            class TraceConnection:
                def __enter__(inner):
                    inner.real=underlying.connection();inner.real.__enter__();return inner
                def __exit__(inner,*args):return inner.real.__exit__(*args)
                def execute(inner,sql,*args):
                    if sql=='SELECT pg_advisory_xact_lock(823752020)':
                        reset_waiting.set()
                        result=inner.real.execute(sql,*args)
                        reset_acquired.set()
                        return result
                    return inner.real.execute(sql,*args)
            class TraceStore:
                def connection(inner):return TraceConnection()
            app=Application([],self.store,'postgres',auth=PausedAuth(self.store))
            with ThreadPoolExecutor(max_workers=2) as pool:
                mutation=pool.submit(self.request,'POST','/api/auth/'+route,headers,body,app)
                self.assertTrue(paused.wait(4))
                reset=pool.submit(Auth(TraceStore()).setup,'synthetic@example.invalid','replacement-password-123')
                try:
                    self.assertTrue(reset_waiting.wait(4))
                    self.assertFalse(reset_acquired.is_set())
                finally:release.set()
                issued=mutation.result(timeout=5)
                reset.result(timeout=5)
            self.assertEqual(issued[0],200)
            self.assertTrue(reset_acquired.is_set())
            self.assertEqual(self.request('GET','/api/dashboard',{'cookie':issued[3][0][1].split(';')[0]})[0],401)
            with self.owner() as c:
                self.assertEqual(c.execute("SELECT count(*) FROM weather.auth_sessions WHERE kind='session' AND NOT revoked").fetchone()[0],0)

    def test_forecast_denied_auth_tables(self):
        with self.psycopg.connect(host='127.0.0.1',port=55439,dbname='my_pa',user='weather_forecast',autocommit=True) as c:
            for table in ('auth_users','auth_sessions','auth_limits','observations'):
                with self.assertRaises(self.psycopg.errors.InsufficientPrivilege):c.execute('SELECT * FROM weather.'+table)
    def test_unconfigured_fails_closed(self):
        with self.owner() as c:c.execute('TRUNCATE weather.auth_users')
        self.assertEqual(self.request('GET','/api/auth/status')[0],503)
        self.assertEqual(self.request('GET','/api/dashboard')[0],401)
        with self.assertRaises(ValueError):Auth(self.store,'https://unexpected.invalid')

if __name__=='__main__':unittest.main()
