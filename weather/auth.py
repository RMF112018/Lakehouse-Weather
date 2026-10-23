"""Weather-owned password authentication; no plaintext persistence or token logging."""
import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta
from http.cookies import SimpleCookie

ORIGIN = 'https://www.bobby-fetting.me'
COOKIE = '__Secure-weather_session'
LOGIN_COOKIE = '__Secure-weather_login'
CAP = timedelta(days=60)


def digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def password_hash(password, salt=None):
    if not isinstance(password, str) or not 14 <= len(password) <= 128 or len(password.encode()) > 512:
        raise ValueError('Password must contain 14 to 128 characters')
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64*1024*1024).hex()
    return 'scrypt$32768$8$3$' + salt + '$' + value


def verify_password(password, encoded):
    try:
        parts = encoded.split('$')
        if len(parts) != 6 or parts[:4] != ['scrypt','32768','8','3'] or len(parts[4]) != 32 or len(parts[5]) != 128:
            return False
        return hmac.compare_digest(password_hash(password, parts[4]), encoded)
    except (ValueError, TypeError):
        return False


class Auth:
    def __init__(self, store, origin=ORIGIN, insecure_test=False):
        if origin != ORIGIN and not (insecure_test and origin == 'http://127.0.0.1'):
            raise ValueError('Canonical weather origin required')
        self.store, self.origin, self.secure = store, origin, not insecure_test
        if not self.secure and origin != 'http://127.0.0.1':
            raise ValueError('Insecure cookies only allowed for synthetic loopback tests')

    def cookie(self, token, seconds, name=COOKIE):
        return f'{name}={token}; Path=/weather/; Max-Age={max(0, int(seconds))}; HttpOnly; SameSite=Strict' + ('; Secure' if self.secure else '')

    def token(self, headers, name=COOKIE):
        try:
            c = SimpleCookie(); c.load(headers.get('cookie', ''))
            token = c[name].value
            if len(token) != 64 or any(x not in '0123456789abcdef' for x in token):
                return ''
            return token
        except (KeyError, ValueError):
            return ''

    def setup(self, email, password):
        if not isinstance(email, str) or len(email) > 254 or '@' not in email or any(c.isspace() for c in email):
            raise ValueError('Owner email required')
        encoded = password_hash(password)
        with self.store.connection() as c:
            c.execute('SELECT pg_advisory_xact_lock(823752020)')
            c.execute('INSERT INTO weather.auth_users (id,email,password_hash) VALUES (1,%s,%s) ON CONFLICT(id) DO UPDATE SET email=EXCLUDED.email,password_hash=EXCLUDED.password_hash', (email.casefold(), encoded))
            c.execute('UPDATE weather.auth_sessions SET revoked=TRUE WHERE NOT revoked')

    def _rate(self, c, scope, limit, seconds):
        # A fixed small set of keys; no raw client addresses or user input retained.
        c.execute('SELECT pg_advisory_xact_lock(823752021)')
        now = datetime.now(timezone.utc)
        row = c.execute('SELECT window_start,attempts FROM weather.auth_limits WHERE scope=%s FOR UPDATE', (scope,)).fetchone()
        reset = row is None or now >= row[0] + timedelta(seconds=seconds)
        count = 1 if reset else row[1] + 1
        c.execute('INSERT INTO weather.auth_limits(scope,window_start,attempts) VALUES(%s,%s,%s) ON CONFLICT(scope) DO UPDATE SET window_start=EXCLUDED.window_start,attempts=EXCLUDED.attempts', (scope, now if reset else row[0], count))
        return count <= limit

    def _clean(self, c):
        c.execute('DELETE FROM weather.auth_sessions WHERE token_hash IN (SELECT token_hash FROM weather.auth_sessions WHERE revoked OR expires_at < CURRENT_TIMESTAMP ORDER BY expires_at LIMIT 100)')

    def _issue(self, c, kind, expires, created=None):
        c.execute('SELECT pg_advisory_xact_lock(823752025)')
        if c.execute("SELECT count(*) FROM weather.auth_sessions WHERE expires_at>CURRENT_TIMESTAMP AND NOT revoked").fetchone()[0] >= 1024:
            raise ValueError('Active authentication capacity reached')
        token = secrets.token_hex(32)
        csrf = digest(token + 'csrf')
        now = datetime.now(timezone.utc)
        c.execute('INSERT INTO weather.auth_sessions(token_hash,csrf_hash,kind,created_at,expires_at,revoked) VALUES(%s,%s,%s,%s,%s,FALSE)', (digest(token),digest(csrf),kind,created or now,expires))
        return token, csrf

    def session(self, headers):
        token = self.token(headers)
        if not token:
            return None
        with self.store.connection() as c:
            return c.execute("SELECT created_at,expires_at,csrf_hash FROM weather.auth_sessions WHERE token_hash=%s AND kind='session' AND NOT revoked AND expires_at>CURRENT_TIMESTAMP AND expires_at<=created_at+INTERVAL '60 days'", (digest(token),)).fetchone()

    def handle(self, method, path, headers, body):
        """Returns HTTP result plus headers; only tightly enumerated auth routes."""
        def result(status, value, cookies=None):
            return status, value, None, [('Set-Cookie', cookies)] if cookies else []
        now = datetime.now(timezone.utc)
        if method == 'GET' and path == '/api/auth/status':
            existing = self.session(headers)
            if existing:
                # Only same-origin scripts can read this CSRF proof; the session token stays HttpOnly.
                return result(200, {'authenticated': True, 'csrf':digest(self.token(headers)+'csrf')})
            with self.store.connection() as c:
                if not c.execute('SELECT id FROM weather.auth_users WHERE id=1').fetchone():
                    return result(503, {'error':'Weather sign-in unavailable'})
                if not self._rate(c,'challenge',60,60):
                    return result(429, {'error':'Weather sign-in unavailable'})
                self._clean(c)
                token, csrf = self._issue(c,'challenge',now+timedelta(minutes=10))
            return result(200, {'authenticated':False,'csrf':csrf}, self.cookie(token,600,LOGIN_COOKIE))
        if method != 'POST' or path not in ('/api/auth/login','/api/auth/logout','/api/auth/refresh'):
            return result(404, {'error':'Not found'})
        if headers.get('origin') != self.origin:
            return result(403, {'error':'Request refused'})
        token = self.token(headers, LOGIN_COOKIE if path == '/api/auth/login' else COOKIE)
        csrf = headers.get('x-weather-csrf','')
        if not token or len(csrf) != 64 or any(x not in '0123456789abcdef' for x in csrf):
            return result(403, {'error':'Request refused'})
        with self.store.connection() as c:
            # Reset takes the exclusive counterpart before its UPDATE snapshot.
            # Every session mutation finishes before reset can revoke sessions.
            c.execute('SELECT pg_advisory_xact_lock_shared(823752020)')
            row = c.execute('SELECT kind,created_at,expires_at,csrf_hash FROM weather.auth_sessions WHERE token_hash=%s AND NOT revoked AND expires_at>CURRENT_TIMESTAMP FOR UPDATE', (digest(token),)).fetchone()
            if not row or not hmac.compare_digest(row[3],digest(csrf)):
                return result(403, {'error':'Request refused'})
            kind,created,expires,_ = row
            if path == '/api/auth/login':
                if kind != 'challenge':
                    return result(403, {'error':'Request refused'})
                c.execute('UPDATE weather.auth_sessions SET revoked=TRUE WHERE token_hash=%s',(digest(token),))
                with self.store.connection() as rate_connection:
                    allowed = self._rate(rate_connection,'login-global',30,600)
                    allowed = self._rate(rate_connection,'login-owner',10,600) and allowed
                # Two transaction-scoped slots shared by every process. No hashing queue.
                slot = allowed and any(c.execute('SELECT pg_try_advisory_xact_lock(%s)',(n,)).fetchone()[0] for n in (823752022,823752023))
                if not slot:
                    return result(429, {'error':'Unable to sign in'})
                owner = c.execute('SELECT email,password_hash FROM weather.auth_users WHERE id=1 FOR SHARE').fetchone()
                password = body.get('password')
                email = body.get('email')
                valid = bool(owner) and verify_password(password,owner[1])
                if not valid or not isinstance(email,str) or not hmac.compare_digest(email.casefold().encode(),owner[0].encode()):
                    return result(401, {'error':'Unable to sign in'})
                expires,created = now+CAP,now
            elif kind != 'session' or expires > created+CAP:
                return result(403, {'error':'Request refused'})
            c.execute('UPDATE weather.auth_sessions SET revoked=TRUE WHERE token_hash=%s',(digest(token),))
            if path == '/api/auth/logout':
                return result(200, {'authenticated':False}, self.cookie('',0))
            self._clean(c)
            new_token,new_csrf = self._issue(c,'session',expires,created)
            issued = result(200, {'authenticated':True,'csrf':new_csrf}, self.cookie(new_token,(expires-now).total_seconds()))
            if path == '/api/auth/login':
                issued[3].append(('Set-Cookie',self.cookie('',0,LOGIN_COOKIE)))
            return issued
