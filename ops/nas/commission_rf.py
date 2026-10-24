#!/usr/bin/env python3
"""Bind approved RF identities in the private NAS registry; never print its data."""
import argparse
import hashlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid


SPEC = importlib.util.spec_from_file_location('weather_rf_launcher', Path(__file__).with_name('rf_capture.py'))
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)
REGISTRY = Path('/volume1/weather-dashboard/config/stations.json')
BACKUPS = Path('/volume1/weather-dashboard/rf-registry-backups')
METRICS = {'temperature_c': 'lakehouse-ws2000-wh32b', 'humidity_pct': 'lakehouse-ws2000-wh32b',
           'pressure_hpa': 'lakehouse-ws2000-wh32b', 'wind_speed_ms': 'lakehouse-ws2000',
           'wind_gust_ms': 'lakehouse-ws2000', 'wind_direction_deg': 'lakehouse-ws2000',
           'rain_total_mm': 'lakehouse-ws2000', 'rain_known_mm': 'lakehouse-ws2000',
           'uv_raw': 'lakehouse-ws2000', 'uv_index': 'lakehouse-ws2000', 'illuminance_lux': 'lakehouse-ws2000'}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate registry key')
        value[key] = item
    return value


def validate_registry(locations):
    # Host Python3.8 has no zoneinfo. Preserve all existing non-RF configuration
    # verbatim; the image performs its full application validation at startup.
    if not isinstance(locations, list) or not locations:
        raise ValueError('Locations required')
    location_ids, station_ids, sensor_ids = set(), set(), set()
    for location in locations:
        if not isinstance(location, dict) or not isinstance(location.get('id'), str) or location['id'] in location_ids:
            raise ValueError('Unique location required')
        location_ids.add(location['id'])
        if not isinstance(location.get('stations'), list):
            raise ValueError('Source list required')
        for station in location['stations']:
            if not isinstance(station, dict) or not isinstance(station.get('id'), str) or station['id'] in station_ids:
                raise ValueError('Unique source required')
            station_ids.add(station['id'])
            identity = (station.get('receiver_model'), str(station.get('sensor_id')))
            if not isinstance(identity[0], str) or identity in sensor_ids:
                raise ValueError('Unique RF identity required')
            sensor_ids.add(identity)
            if type(station.get('ingest_enabled', True)) is not bool:
                raise ValueError('Boolean source enablement required')
    return locations


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(document, wh65_id, wh32_id):
    # A JSON roundtrip makes the mutation scope testable without sharing references.
    result = json.loads(json.dumps(document, allow_nan=False))
    validate_registry(result['locations'])
    matches = [location for location in result['locations'] if location['id'] == 'lakehouse']
    if len(matches) != 1:
        raise ValueError('Expected unique lakehouse location')
    location = matches[0]
    stations = location['stations']
    array = [s for s in stations if s['id'] == 'lakehouse-ws2000']
    if len(array) != 1 or array[0]['receiver_model'] != 'Fineoffset-WH65B':
        raise ValueError('Expected existing WH65B source')
    indoor = [s for s in stations if s['id'] == 'lakehouse-ws2000-wh32b']
    if len(indoor) > 1 or (indoor and indoor[0]['receiver_model'] != 'Fineoffset-WH32B'):
        raise ValueError('WH32B source mismatch')
    new_indoor = not indoor
    if not indoor:
        indoor = [{'id': 'lakehouse-ws2000-wh32b', 'name': 'Temperature and pressure transmitter',
                   'model': 'Fine Offset WH32B', 'receiver_model': 'Fineoffset-WH32B', 'ingest_enabled': False}]
        stations.append(indoor[0])
    for station, identity, profile in [(array[0], wh65_id, 'wh65b'), (indoor[0], wh32_id, 'wh32b')]:
        same = str(station.get('sensor_id')) == str(identity)
        pending = station.get('sensor_id') == 'PENDING_RF_COMMISSIONING' and station.get('ingest_enabled') is False
        added = station is indoor[0] and new_indoor
        if not same and not pending and not added:
            raise ValueError('Only the explicit disabled commissioning marker can bind once')
        station.update(sensor_id=identity, ingest_enabled=True, rf_profile=profile)
    group = {'id': 'lakehouse-installation', 'name': 'WS-2000 installation',
             'source_station_ids': ['lakehouse-ws2000', 'lakehouse-ws2000-wh32b'],
             'metric_sources': dict(METRICS),
             'freshness_seconds': {'lakehouse-ws2000': 120, 'lakehouse-ws2000-wh32b': 300}}
    groups = location.setdefault('physical_stations', [])
    existing = [g for g in groups if g['id'] == group['id']]
    if existing and existing != [group]:
        raise ValueError('Existing physical station configuration differs')
    if not existing:
        groups.append(group)
    validate_registry(result['locations'])
    return result


def write_exclusive(path, content, uid=0, gid=0, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as handle:
        os.fchown(handle.fileno(), uid, gid)
        os.fchmod(handle.fileno(), mode)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def backup_directory():
    if BACKUPS.is_symlink():
        raise ValueError('Unsafe backup directory')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    backup_info = BACKUPS.stat()
    if backup_info.st_uid != 0 or stat.S_IMODE(backup_info.st_mode) != 0o700:
        raise ValueError('Backups require root mode0700 custody')
    return BACKUPS


def commission(expected_sha, wh65_id, wh32_id, apply=False):
    if not re.fullmatch('[0-9a-f]{64}', expected_sha):
        raise ValueError('Exact prior registry hash required')
    if REGISTRY.is_symlink() or not REGISTRY.is_file():
        raise ValueError('Protected regular registry required')
    info = REGISTRY.stat()
    if info.st_mode & 0o022 or info.st_size > 65536:
        raise ValueError('Unsafe registry permissions or size')
    fd = os.open(REGISTRY, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as handle:
        original = handle.read(65537)
    if len(original) > 65536 or digest(original) != expected_sha:
        raise ValueError('Private registry drift')
    updated = prepare(json.loads(original, object_pairs_hook=unique_object), wh65_id, wh32_id)
    content = (json.dumps(updated, indent=2, allow_nan=False) + '\n').encode()
    if not apply:
        return {'result': 'preflight_passed', 'previous_sha256': expected_sha, 'proposed_sha256': digest(content)}
    backups = backup_directory()
    write_exclusive(backups / (expected_sha + '.' + uuid.uuid4().hex + '.json'), original)
    sync_dir(backups)
    temporary = REGISTRY.with_name('.rf-registry-' + uuid.uuid4().hex + '.tmp')
    write_exclusive(temporary, content, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
    # Recheck at the commit point; retain backup on every ambiguous failure.
    if REGISTRY.stat().st_ino != info.st_ino or digest(REGISTRY.read_bytes()) != expected_sha:
        raise ValueError('Registry changed before atomic replacement')
    os.replace(temporary, REGISTRY)
    sync_dir(REGISTRY.parent)
    if digest(REGISTRY.read_bytes()) != digest(content):
        raise ValueError('Registry readback mismatch')
    return {'result': 'registry_commissioned', 'previous_sha256': expected_sha, 'new_sha256': digest(content)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-registry-sha256', required=True)
    parser.add_argument('--wh65-id', type=int, required=True)
    parser.add_argument('--wh32-id', type=int, required=True)
    parser.add_argument('--dashboard-id', required=True)
    parser.add_argument('--dashboard-image', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    if os.geteuid() != 0 or not 0 <= args.wh65_id <= 2 ** 32 - 1 or not 0 <= args.wh32_id <= 2 ** 32 - 1:
        raise ValueError('Root and bounded approved RF identities required')
    # Existing dashboard may predate the new journal mount. Prove exact identity
    # and project ownership without requiring RF activation or reading credentials.
    if not re.fullmatch('[0-9a-f]{64}', args.dashboard_id) or not re.fullmatch('sha256:[0-9a-f]{64}', args.dashboard_image):
        raise ValueError('Exact dashboard identity required')
    if launcher.metadata('container', 'inspect', '--format', '{{.Id}} {{.Image}} {{.State.Status}}', launcher.APP) != f'{args.dashboard_id} {args.dashboard_image} running':
        raise ValueError('Dashboard identity drift')
    for label, expected in [('project', 'lakehouse-weather'), ('service', 'dashboard')]:
        if launcher.metadata('container', 'inspect', '--format', '{{index .Config.Labels "com.docker.compose.' + label + '"}}', launcher.APP) != expected:
            raise ValueError('Dashboard ownership mismatch')
    lock = os.open('/run/lock/lakehouse-weather-rf.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(json.dumps(commission(args.expected_registry_sha256, args.wh65_id, args.wh32_id, args.apply), sort_keys=True))
    finally:
        os.close(lock)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('RF registry commission refused/failed; private configuration and diagnostics withheld')
