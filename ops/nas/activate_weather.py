#!/usr/bin/env python3
"""Reviewed NAS-only weather ingress change. No protected contents are emitted."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

DOCKER = '/usr/local/bin/docker'
ROOT = Path('/volume1/weather-dashboard/ingress-a8ac6e20')
CADDY = Path('/volume1/my-pa/runtime-cf17f7f2-prod-20260924/ops/nas/proxy-public-browser.example.caddy')
TUNNEL = Path('/volume1/my-pa/secrets/frontend-cloudflared.dd0951a3.config.yml')
PROXY = 'my-pa-nas-contract-public-proxy-1'
CONNECTOR = 'my-pa-nas-contract-frontend-cloudflared-1'
APP = 'lakehouse-weather-dashboard'
CONTAINERS = {
    PROXY: ('250db1f5036d36a80166f45574481d028419eaa2636d549628510da2aaa976cd', 'sha256:af555904a0961945f16bb323a501457b13a4f7e9bde969b145b97da80b38ecbe'),
    CONNECTOR: ('3a7c04d4898d9e10e331fdb7591187c5e78f180f967497e6ed7ce1789b1825a8', 'sha256:41320ce229c5fb52a316a5e3af2e6a1faa32b114aa9e2a5eed0652eff59e8eef'),
    APP: ('00d293ed610d8a9c12ba3f1364fb707f659838598dd8159b54593428c1faccb3', 'sha256:c8c8e2234d5d12291040d195521f7b7c6e0aa00cab38bd85d24a9a326969d0a6'),
}
FILES = {'caddy': (CADDY, 4322087, 0, 0o644), 'tunnel': (TUNNEL, 3193789, 65532, 0o640)}
CADDY_SOURCE_SHA = '621d6a1d1a3b4738e887b54ec7c784f14ec2aade620f15afff1d1073e69d64e3'
FRAGMENT = '# INERT REVIEW FRAGMENT: insert inside the existing www.bobby-fetting.me site\n# only AFTER application password/session authentication is independently\n# verified fail-closed and the owner has completed hidden TTY password setup.\n# Keep existing /pa handlers. No Cloudflare Access dependency. Never import blindly.\n@weather_redirect {\n    method GET\n    path /weather\n}\nredir @weather_redirect /weather/ 308\n@weather_read {\n    method GET\n    path /weather/ /weather/index.html /weather/app.js /weather/style.css /weather/icon.svg /weather/manifest.webmanifest /weather/api/dashboard /weather/api/history /weather/login /weather/login.css /weather/login.js /weather/api/auth/status\n}\nhandle @weather_read {\n    uri strip_prefix /weather\n    reverse_proxy weather-dashboard:8765 {\n        transport http {\n            dial_timeout 3s\n            response_header_timeout 15s\n        }\n    }\n}\n@weather_auth_write {\n    method POST\n    path /weather/api/auth/login /weather/api/auth/logout /weather/api/auth/refresh\n}\nhandle @weather_auth_write {\n    uri strip_prefix /weather\n    reverse_proxy weather-dashboard:8765 {\n        transport http {\n            dial_timeout 3s\n            response_header_timeout 15s\n        }\n    }\n}\n# Reject every other weather path/method, including health, ready and ingestion.\n@weather_other path /weather /weather/*\nhandle @weather_other {\n    respond 404\n}\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def command(args):
    result = subprocess.run(args, capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError('Ingress command failed; diagnostic payload suppressed')
    return result.stdout


def inspect(name, expression):
    return command([DOCKER, 'inspect', '--format', expression, name]).decode().strip()


def identities():
    for name, (container_id, image) in CONTAINERS.items():
        if inspect(name, '{{.Id}}') != container_id or inspect(name, '{{.Image}}') != image or inspect(name, '{{.State.Status}}') != 'running':
            raise ValueError('Ingress container identity/state drift')
    for key, (path, inode, uid, mode) in FILES.items():
        meta = path.lstat()
        if not stat.S_ISREG(meta.st_mode) or meta.st_ino != inode or meta.st_uid != uid or stat.S_IMODE(meta.st_mode) != mode:
            raise ValueError('Mounted ingress file identity/permissions drift')
    for name, path, destination in [(PROXY, CADDY, '/etc/caddy/Caddyfile'), (CONNECTOR, TUNNEL, '/etc/cloudflared/config.yml')]:
        mounts = json.loads(inspect(name, '{{json .Mounts}}'))
        selected = [row for row in mounts if row.get('Destination') == destination]
        if len(selected) != 1 or selected[0].get('Source') != str(path) or selected[0].get('RW') is not False or selected[0].get('Type') != 'bind':
            raise ValueError('Ingress bind mount identity drift')


def candidates(caddy, tunnel):
    if digest(caddy) != CADDY_SOURCE_SHA:
        raise ValueError('Existing pa proxy differs from exact reviewed source')
    text = caddy.decode('utf-8')
    if text.count(':8080 {') != 1 or 'www.bobby-fetting.me' in text or 'weather-dashboard' in text:
        raise ValueError('Unexpected existing proxy structure')
    # Named handle appears before the original hostile-host handle. Preserve all
    # original pa bytes, including its guards, header stripping and web upstream.
    inserted = '\n    @weather_host host www.bobby-fetting.me\n    handle @weather_host {\n        route {\n' + '\n'.join('            ' + line for line in FRAGMENT.splitlines() if not line.startswith('#')) + '\n            respond 404\n        }\n    }\n'
    new_caddy = text.replace(':8080 {', ':8080 {' + inserted, 1).encode()
    if new_caddy.decode().replace(inserted, '', 1).encode() != caddy:
        raise ValueError('Proxy preservation check failed')
    text = tunnel.decode('utf-8')
    if text.count('ingress:') != 1 or 'www.bobby-fetting.me' in text or not re.search(r'^tunnel:', text, re.M) or not re.search(r'^credentials-file:', text, re.M):
        raise ValueError('Unexpected protected tunnel structure')
    if len(re.findall(r'hostname:\s*pa\.bobby-fetting\.me\s*$', text, re.M)) != 1 or 'service: http://public-proxy:8080' not in text or 'service: http_status:404' not in text:
        raise ValueError('Existing tunnel pa/fallback guard failed')
    # Keep all original protected bytes. Only add one host+path ingress rule.
    rule = '  - hostname: www.bobby-fetting.me\n    path: ^/weather(?:/.*)?$\n    service: http://public-proxy:8080\n'
    new_tunnel, count = re.subn(r'(?m)^ingress:\s*\n', lambda match: match.group(0) + rule, text, count=1)
    if count != 1 or new_tunnel.replace(rule, '', 1) != text:
        raise ValueError('Tunnel preservation check failed')
    return {'caddy': new_caddy, 'tunnel': new_tunnel.encode()}


def private_file(path, data, source):
    meta = source.stat()
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, stat.S_IMODE(meta.st_mode))
    with os.fdopen(descriptor, 'wb') as handle:
        os.fchown(handle.fileno(), meta.st_uid, meta.st_gid)
        os.fchmod(handle.fileno(), stat.S_IMODE(meta.st_mode))
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def validate():
    command([DOCKER, 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--mount', 'type=bind,src=' + str(ROOT / 'caddy.candidate') + ',dst=/etc/caddy/Caddyfile,readonly', '--entrypoint', 'caddy', CONTAINERS[PROXY][1], 'validate', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile'])
    command([DOCKER, 'run', '--rm', '--network', 'none', '--read-only', '--user', '65532:65532', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--mount', 'type=bind,src=' + str(ROOT / 'tunnel.candidate') + ',dst=/etc/cloudflared/config.yml,readonly', CONTAINERS[CONNECTOR][1], 'tunnel', '--config', '/etc/cloudflared/config.yml', 'ingress', 'validate'])


def manifest():
    if ROOT.is_symlink() or ROOT.stat().st_uid != 0 or stat.S_IMODE(ROOT.stat().st_mode) != 0o700:
        raise ValueError('Protected ingress directory identity drift')
    for name in ['manifest.json', 'validated', 'caddy.original', 'caddy.candidate', 'tunnel.original', 'tunnel.candidate']:
        meta = (ROOT / name).lstat()
        if not stat.S_ISREG(meta.st_mode):
            raise ValueError('Protected ingress artifact type drift')
    return json.loads((ROOT / 'manifest.json').read_text())


def unchanged(record, suffix):
    for key, (path, _, _, _) in FILES.items():
        if digest(path.read_bytes()) != record[key][suffix]:
            raise ValueError('Ingress content drift; no overwrite performed')
        if digest((ROOT / (key + '.original')).read_bytes()) != record[key]['original'] or digest((ROOT / (key + '.candidate')).read_bytes()) != record[key]['candidate']:
            raise ValueError('Ingress backup/candidate drift')


def in_place(path, data):
    before = path.stat()
    descriptor = os.open(str(path), os.O_WRONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'wb') as handle:
        opened = os.fstat(handle.fileno())
        if opened.st_ino != before.st_ino:
            raise ValueError('Ingress file changed during open')
        handle.write(data)
        handle.truncate()
        handle.flush()
        os.fsync(handle.fileno())
    after = path.stat()
    if (after.st_ino, after.st_uid, after.st_gid, after.st_mode) != (before.st_ino, before.st_uid, before.st_gid, before.st_mode) or path.read_bytes() != data:
        raise ValueError('Ingress in-place verification failed')


def mounted_bytes(key):
    # Read inside the existing container and print only a digest internally.
    if key == 'caddy':
        return command([DOCKER, 'exec', PROXY, 'sha256sum', '/etc/caddy/Caddyfile']).decode().split()[0]
    return command([DOCKER, 'run', '--rm', '--network', 'none', '--read-only', '--volumes-from', CONNECTOR + ':ro', '--entrypoint', 'sha256sum', CONTAINERS[PROXY][1], '/etc/cloudflared/config.yml']).decode().split()[0]


def activate(record, suffix):
    for key, (path, _, _, _) in FILES.items():
        in_place(path, (ROOT / (key + '.' + suffix)).read_bytes())
    for key in FILES:
        if mounted_bytes(key) != record[key][suffix]:
            raise ValueError('Running bind mount does not see approved bytes')
    command([DOCKER, 'exec', PROXY, 'caddy', 'reload', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile'])
    command([DOCKER, 'restart', '--time', '30', CONNECTOR])
    identities()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'apply', 'rollback'])
    parser.add_argument('--reviewed-helper-sha', required=True)
    args = parser.parse_args(argv)
    if os.geteuid() != 0 or digest(Path(__file__).read_bytes()) != args.reviewed_helper_sha:
        raise ValueError('Reviewed helper identity and root execution required')
    identities()
    if args.action == 'prepare':
        if ROOT.exists():
            raise ValueError('Ingress preparation directory already exists')
        originals = {key: path.read_bytes() for key, (path, _, _, _) in FILES.items()}
        proposed = candidates(originals['caddy'], originals['tunnel'])
        ROOT.mkdir(mode=0o700)
        record = {}
        for key, (source, _, _, _) in FILES.items():
            private_file(ROOT / (key + '.original'), originals[key], source)
            private_file(ROOT / (key + '.candidate'), proposed[key], source)
            record[key] = {'original': digest(originals[key]), 'candidate': digest(proposed[key])}
        # Store protected digests only in the protected NAS directory, never output.
        (ROOT / 'manifest.json').write_text(json.dumps(record))
        (ROOT / 'manifest.json').chmod(0o600)
        validate()
        unchanged(record, 'original')
        (ROOT / 'validated').touch(mode=0o600)
        print('Ingress candidates validated; originals unchanged; activation pending')
        return 0
    record = manifest()
    if not (ROOT / 'validated').is_file():
        raise ValueError('Candidate validation receipt missing')
    if args.action == 'apply':
        unchanged(record, 'original')
        validate()
        try:
            activate(record, 'candidate')
        except Exception:
            activate(record, 'original')
            raise ValueError('Ingress activation failed; original configurations restored')
        print('Weather-only ingress activated; proxy reloaded and one connector restarted')
    else:
        unchanged(record, 'candidate')
        activate(record, 'original')
        print('Weather ingress rolled back; original pa configurations restored')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Ingress action refused or failed; all protected diagnostics suppressed')
