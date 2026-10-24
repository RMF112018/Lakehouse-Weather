#!/usr/bin/env python3
"""Exact USB + cached receiver -> private durable collector. No receiver network/logs."""
import argparse
import fcntl
import hashlib
import shlex
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import subprocess

DOCKER = '/usr/local/bin/docker'
IMAGE = 'sha256:d46c11edfc6029a1f7d603ccf0cb7fb1c6bdee848b5a9a03e6bb9323eedfc6e6'
DIGEST = 'hertzg/rtl_433@sha256:79243e8ebc0ee086603d34789aca905be50b99e328cef72f927f1a47c0233a0e'
APP = 'lakehouse-weather-dashboard'
NAME = 'lakehouse-weather-rf'
CRON = Path('/etc/cron.d/weather-rf-capture')
RUNTIME_STATUS = Path('/volume1/weather-dashboard/rf-runtime-status.json')
ARGV = ['-d', '0', '-f', '915M', '-R', '78', '-Y', 'classic', '-s', '250k', '-M', 'time:utc', '-M', 'protocol', '-F', 'json']


def metadata(*args):
    result = subprocess.run([DOCKER, *args], capture_output=True, text=True, timeout=15)
    if result.returncode or len(result.stdout) > 32768:
        raise ValueError('Receiver identity check failed')
    return result.stdout.strip()


def usb_device(root=Path('/sys/bus/usb/devices'), devices=Path('/dev/bus/usb')):
    matches = []
    for path in root.iterdir():
        if path.name != '1-2':
            continue
        if (path / 'idVendor').read_text().strip() != '0bda' or (path / 'idProduct').read_text().strip() != '2838':
            raise ValueError('USB topology identity changed')
        bus, dev = int((path / 'busnum').read_text()), int((path / 'devnum').read_text())
        node = devices / f'{bus:03d}' / f'{dev:03d}'
        info = node.stat()
        if not stat.S_ISCHR(info.st_mode) or os.major(info.st_rdev) != 189 or os.minor(info.st_rdev) != (bus - 1) * 128 + dev - 1:
            raise ValueError('USB device node identity mismatch')
        matches.append(str(node))
    if len(matches) != 1:
        raise ValueError('Expected exactly one bound RTL-SDR')
    return matches[0]


def preflight(app_id, app_image):
    if not re.fullmatch('[0-9a-f]{64}', app_id) or not re.fullmatch('sha256:[0-9a-f]{64}', app_image):
        raise ValueError('Exact dashboard identity required')
    if metadata('image', 'inspect', '--format', '{{.Id}}', DIGEST) != IMAGE:
        raise ValueError('Cached receiver digest/image mismatch')
    if metadata('image', 'inspect', '--format', '{{.Os}}/{{.Architecture}}', IMAGE) != 'linux/amd64':
        raise ValueError('Receiver platform mismatch')
    if metadata('container', 'inspect', '--format', '{{.Id}} {{.Image}} {{.State.Status}}', APP) != f'{app_id} {app_image} running':
        raise ValueError('Dashboard identity drift')
    if metadata('container', 'inspect', '--format', '{{if .State.Health}}{{.State.Health.Status}}{{end}}', APP) != 'healthy':
        raise ValueError('Dashboard not healthy')
    for label, value in [('project', 'lakehouse-weather'), ('service', 'dashboard')]:
        if metadata('container', 'inspect', '--format', '{{index .Config.Labels "com.docker.compose.' + label + '"}}', APP) != value:
            raise ValueError('Dashboard ownership drift')
    mounts = json.loads(metadata('container', 'inspect', '--format', '{{json .Mounts}}', APP))
    journals = [m for m in mounts if m.get('Destination') == '/var/lib/weather-rf']
    if len(journals) != 1 or journals[0].get('Source') != '/volume1/weather-dashboard/rf-journal' or not journals[0].get('RW'):
        raise ValueError('Durable RF journal mount missing')
    if metadata('container', 'ls', '--all', '--filter', 'name=^/' + NAME + '$', '--format', '{{.ID}}'):
        raise ValueError('RF container already exists; reconcile before start')
    journal = Path('/volume1/weather-dashboard/rf-journal')
    if journal.is_symlink() or not journal.is_dir():
        raise ValueError('Protected journal missing')
    info = journal.stat()
    if info.st_uid != 10001 or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Journal owner/mode mismatch')
    status_path = journal / 'status.json'
    if status_path.exists():
        fd = os.open(status_path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as handle:
            data = handle.read(4097)
        if len(data) > 4096:
            raise ValueError('Invalid collector status')
        status_value = json.loads(data)
        if status_value.get('error_code') in ('observation_conflict', 'pending_age_limit', 'capacity'):
            raise ValueError('Collector halted pending operator reconciliation')
    return usb_device()


def launch(device):
    receiver = [DOCKER, 'run', '--rm', '--name', NAME, '--pull', 'never', '--network', 'none',
                '--log-driver', 'none', '--label', 'weather.rf.owner=Lakehouse-Weather',
                '--label', 'weather.rf.source-image=' + IMAGE, '--read-only', '--cap-drop', 'ALL', '--security-opt',
                'no-new-privileges:true', '--memory', '128m', '--memory-swap', '128m', '--cpuset-cpus', '2',
                '--tmpfs', '/tmp:rw,noexec,nosuid,size=8m,mode=700', '--device', device + ':' + device + ':rwm',
                IMAGE, *ARGV]
    consumer = [DOCKER, 'exec', '-i', APP, 'python', '-m', 'weather', 'collect']
    source = sink = None
    try:
        source = subprocess.Popen(receiver, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        sink = subprocess.Popen(consumer, stdin=source.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        source.stdout.close()
        code = sink.wait()
        # A successful finite collector means the receiver ended. A failed collector
        # must stop RF immediately; no in-memory radio data is acknowledged.
        return code if code else source.wait()
    finally:
        if source is not None and source.poll() is None:
            subprocess.run([DOCKER, 'stop', '--time', '5', NAME], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            source.wait(timeout=10)
        if sink is not None and sink.poll() is None:
            sink.terminate()
            sink.wait(timeout=10)


def source_identity(expected_sha, head, tree, image):
    source = Path(__file__).resolve()
    if not re.fullmatch('[0-9a-f]{64}', expected_sha) or not all(re.fullmatch('[0-9a-f]{40}', v) for v in (head, tree)):
        raise ValueError('Reviewed source hash/head/tree required')
    info = source.stat()
    if info.st_uid != 0 or info.st_mode & 0o022 or hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha:
        raise ValueError('Root-owned reviewed launcher hash mismatch')
    # Prevent replacement through an untrusted source directory after installation.
    for parent in source.parents:
        if parent.stat().st_uid != 0 or parent.stat().st_mode & 0o022:
            raise ValueError('Launcher source directory custody mismatch')
        if str(parent) == '/volume1/weather-dashboard':
            break
    for key, expected in [('revision', head), ('source-tree', tree)]:
        if metadata('image', 'inspect', '--format', '{{index .Config.Labels "org.opencontainers.image.' + key + '"}}', image) != expected:
            raise ValueError('Reviewed dashboard source provenance mismatch')
    return source


def heartbeat(state, code=None):
    content = json.dumps({'supervisor_tick_utc': datetime.now(timezone.utc).isoformat(),
                          'state': state, 'exit_code': code}).encode()
    temporary = RUNTIME_STATUS.with_name('.rf-runtime-status.tmp.' + str(os.getpid()))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, RUNTIME_STATUS)
    directory = os.open(RUNTIME_STATUS.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def reconcile_receiver():
    existing = metadata('container', 'ls', '--all', '--filter', 'name=^/' + NAME + '$', '--format', '{{.ID}}')
    if not existing:
        return
    for expression, expected in [
        ('{{.Image}}', IMAGE),
        ('{{index .Config.Labels "weather.rf.owner"}}', 'Lakehouse-Weather'),
        ('{{index .Config.Labels "weather.rf.source-image"}}', IMAGE),
        ('{{.HostConfig.NetworkMode}}', 'none'),
        ('{{.HostConfig.LogConfig.Type}}', 'none')]:
        if metadata('container', 'inspect', '--format', expression, NAME) != expected:
            raise ValueError('Ambiguous stale receiver; operator reconciliation required')
    # Holding the host lock proves no other reviewed launcher owns this receiver.
    metadata('container', 'rm', '--force', NAME)


def cron_content(source, args):
    command = ['/usr/bin/python3', '-I', '-B', str(source), '--apply',
               '--dashboard-id', args.dashboard_id, '--dashboard-image', args.dashboard_image,
               '--source-sha256', args.source_sha256, '--reviewed-head', args.reviewed_head,
               '--reviewed-tree', args.reviewed_tree]
    if any('%' in value or '\n' in value for value in command):
        raise ValueError('Unsafe scheduler argument')
    return ('# Weather RF only; exact reviewed launcher, private pipeline, host process lock.\n'
            '* * * * * root ' + ' '.join(shlex.quote(value) for value in command) + ' >/dev/null 2>&1\n').encode()


def install_supervisor(source, args):
    content = cron_content(source, args)
    if CRON.exists() or CRON.is_symlink():
        raise ValueError('RF supervisor already exists; no automatic overwrite')
    fd = os.open(CRON, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    if CRON.read_bytes() != content:
        raise ValueError('RF scheduler readback mismatch')
    directory = os.open(CRON.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dashboard-id', required=True)
    parser.add_argument('--dashboard-image', required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--reviewed-head', required=True)
    parser.add_argument('--reviewed-tree', required=True)
    parser.add_argument('--install-supervisor', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        raise ValueError('NAS root operator required')
    source = source_identity(args.source_sha256, args.reviewed_head, args.reviewed_tree, args.dashboard_image)
    if not args.apply:
        preflight(args.dashboard_id, args.dashboard_image)
        print('RF preflight passed; receiver/collector/supervisor not started')
        return 0
    lock = os.open('/run/lock/lakehouse-weather-rf.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            heartbeat('launcher_active')
            return 0
        reconcile_receiver()
        device = preflight(args.dashboard_id, args.dashboard_image)
        if args.install_supervisor:
            install_supervisor(source, args)
            print('Exclusive RF supervisor installed; observe a real scheduler tick before claiming recovery')
            return 0
        heartbeat('started')
        result = launch(device)
        heartbeat('exited', result)
        return result
    except Exception:
        heartbeat('refused')
        raise
    finally:
        os.close(lock)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception:
        raise SystemExit('RF capture stopped/refused; reconcile identity, capacity or pending events without exposing payloads')
