#!/usr/bin/env python3
"""Identity-bound weather-only NAS forwarding exception. No secret inputs."""
import argparse
import fcntl
import hashlib
import shlex
import stat
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import subprocess
import sys

DOCKER = '/usr/local/bin/docker'
IPTABLES = '/sbin/iptables'
CONTAINER = '1753bcdc3a2a9a65540dff18be70bbf096748fc41745761a7a6763feca47d3ca'
IMAGE = 'sha256:c8c8e2234d5d12291040d195521f7b7c6e0aa00cab38bd85d24a9a326969d0a6'
NETWORK = '452efc8852b18bd8a3bcc73ba784b18a64ad1ae6aeadfd13b6ec8cc58bacd9d3'
CHAIN = 'FORWARD_FIREWALL'
BRIDGE = 'docker-452efc88'
SOURCE = '172.28.0.2/32'
WAN = 'ovs_eth0'
MARKER = 'weather-forecast-egress-v1'
ROOT = Path('/volume1/weather-dashboard/operations')
DEPLOYED = ROOT / 'forecast_egress.py'
CRON = Path('/etc/cron.d/weather-forecast-egress')
CRON_CONTENT = '*/5 * * * * root /usr/bin/python3 -I /volume1/weather-dashboard/operations/forecast_egress.py --apply >/dev/null 2>&1\n'


def run(argv, check=True):
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=15)
    if check and result.returncode:
        raise RuntimeError('Bounded network command failed')
    return result


def inspect(kind, ident, template):
    return run([DOCKER, kind, 'inspect', ident, '--format', template]).stdout.strip()


def authenticate():
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    if inspect('container', 'lakehouse-weather-forecast', '{{.Id}}') != CONTAINER:
        raise RuntimeError('Forecast identity drift')
    if inspect('container', CONTAINER, '{{.Image}}') != IMAGE:
        raise RuntimeError('Forecast image drift')
    if inspect('container', CONTAINER, '{{.State.Running}}') != 'true':
        raise RuntimeError('Forecast must be running')
    if inspect('container', CONTAINER, '{{index .Config.Labels "org.opencontainers.image.revision"}} {{index .Config.Labels "org.opencontainers.image.source-tree"}} {{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.service"}}') != 'a8ac6e20d74d7b0e1b39a36ed21ce947b220fbe7 5b203057454d6e066caf3e2f7b625f5cb2753a58 lakehouse-weather forecast':
        raise RuntimeError('Forecast provenance drift')
    members = json.loads(inspect('network', 'lakehouse-weather-egress', '{{json .Containers}}'))
    if set(members) != {CONTAINER} or members[CONTAINER]['IPv4Address'] != '172.28.0.2/16':
        raise RuntimeError('Exclusive forecast network ownership drift')
    if inspect('network', 'lakehouse-weather-egress', '{{.Id}} {{.Internal}}') != NETWORK + ' false':
        raise RuntimeError('Weather network identity drift')
    route = run(['/sbin/ip', '-o', 'route', 'get', '1.1.1.1']).stdout.split()
    if 'dev' not in route or route[route.index('dev') + 1] != WAN:
        raise RuntimeError('WAN interface drift')
    policy = run([IPTABLES, '-S', CHAIN]).stdout
    expected = {tuple(['-A', CHAIN] + rule) for rule in rules()}
    # The NAS lacks xt_comment. Ownership is the complete exact rule tuple,
    # including this exclusive bridge, source /32 and WAN interface.
    baseline = ''.join(line + '\n' for line in policy.splitlines()
                       if tuple(shlex.split(line)) not in expected)
    if hashlib.sha256(baseline.encode()).hexdigest() != '545cbe27225a6bd1571b5e5436e153fd68ab63648e265fe7898251646f6b589a':
        raise RuntimeError('Firewall baseline drift; operator review required')
    if '-j DROP' not in policy:
        raise RuntimeError('Expected deny-by-default firewall absent')


def rules():
    return [['-i', BRIDGE, '-o', WAN, '-s', SOURCE, '-p', protocol, '-m', protocol,
             '--dport', port, '-j', 'RETURN'] for protocol, port in [('tcp', '443'), ('udp', '53'), ('tcp', '53')]]


def reconcile(remove=False):
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    if not remove:
        try:
            authenticate()
        except Exception:
            # Revoke ONLY our exact tuples even after identity/baseline drift.
            # Never retain stale authority merely because admission now fails.
            reconcile(remove=True)
            raise
    changed = 0
    for rule in rules():
        present = run([IPTABLES, '-C', CHAIN] + rule, check=False).returncode == 0
        if remove and present:
            for _ in range(256):
                run([IPTABLES, '-D', CHAIN] + rule)
                changed += 1
                if run([IPTABLES, '-C', CHAIN] + rule, check=False).returncode != 0:
                    break
            else:
                raise RuntimeError('Excess duplicate owned rules')
        elif not remove and not present:
            # Before the terminal DROP; leave all existing rules in their order.
            run([IPTABLES, '-I', CHAIN, '1'] + rule)
            changed += 1
    print('Weather-only forwarding rules ' + ('removed' if remove else 'verified') + '; changed=' + str(changed))


def secure_path(path, file=False):
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
        raise RuntimeError('Unsafe operator path')
    if file and not stat.S_ISREG(st.st_mode):
        raise RuntimeError('Expected regular operator file')


def cron_install(remove=False):
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    if not remove:
        authenticate()
    for parent in [Path('/volume1'), ROOT.parent, ROOT]:
        secure_path(parent)
    secure_path(DEPLOYED, file=True)
    if Path(__file__).resolve() != DEPLOYED:
        raise RuntimeError('Only the installed operator artifact can register cron')
    if CRON.exists() or CRON.is_symlink():
        secure_path(CRON, file=True)
        if CRON.read_text() != CRON_CONTENT:
            raise RuntimeError('Cron collision')
        if remove:
            CRON.unlink()
    elif not remove:
        with CRON.open('x') as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(CRON_CONTENT)
            handle.flush()
            os.fsync(handle.fileno())
    print('Weather-only cron entry ' + ('removed' if remove else 'verified'))


def reconcile_locked(remove=False):
    secure_path(ROOT)
    with (ROOT / 'egress.lock').open('a') as lock:
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        ok = False
        try:
            reconcile(remove)
            ok = True
        finally:
            path = ROOT / 'egress-status.json'
            if path.is_symlink():
                raise RuntimeError('Unsafe status path')
            with path.open('w') as handle:
                os.fchmod(handle.fileno(), 0o600)
                json.dump({'checked_at': datetime.now(timezone.utc).isoformat(),
                           'verified': ok, 'rules_removed': remove,
                           'helper_sha256': hashlib.sha256(DEPLOYED.read_bytes()).hexdigest()}, handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--remove', action='store_true')
    parser.add_argument('--install-cron', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        authenticate()
        print('Weather egress identity preflight passed; no mutation')
    elif args.install_cron:
        cron_install(args.remove)
    else:
        reconcile_locked(args.remove)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        sys.exit('Weather egress reconciliation refused or failed; no private diagnostic output')
