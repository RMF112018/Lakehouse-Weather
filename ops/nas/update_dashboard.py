#!/usr/bin/env python3
"""Reviewed dashboard-only update. No credentials, sessions, proxy or forecast mutation."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

SPEC = importlib.util.spec_from_file_location('weather_nas_runtime', Path(__file__).with_name('runtime.py'))
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)
FORECAST_ID = '1753bcdc3a2a9a65540dff18be70bbf096748fc41745761a7a6763feca47d3ca'
FORECAST_IMAGE = 'sha256:c8c8e2234d5d12291040d195521f7b7c6e0aa00cab38bd85d24a9a326969d0a6'
BASE = Path('/volume1/weather-dashboard')

def bounded_docker(*args):
    result = subprocess.run([*runtime.DOCKER, *args], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise ValueError('Docker command failed; protected output suppressed')
    return result.stdout.strip()

runtime.docker = bounded_docker


def forecast_identity():
    if runtime.field('container', 'lakehouse-weather-forecast', '{{.Id}} {{.Image}} {{.State.Status}}') != FORECAST_ID + ' ' + FORECAST_IMAGE + ' running':
        raise ValueError('Forecast identity drift')


def compose(image):
    values = {
        'WEATHER_IMAGE_ID': image,
        'WEATHER_REGISTRY_PATH': str(BASE / 'config/stations.json'),
        'WEATHER_DATABASE_URL_PATH': str(BASE / 'secrets/database-url'),
        'WEATHER_INGEST_TOKEN_PATH': str(BASE / 'secrets/ingest-token'),
        'WEATHER_FORECAST_DATABASE_URL_PATH': str(BASE / 'secrets/forecast-database-url'),
        # Parse-only value: --no-deps dashboard never acts on the forecast service.
        'WEATHER_FORECAST_LOOP_PATH': str(BASE / 'a8ac6e20d74d7b0e1b39a36ed21ce947b220fbe7/ops/nas/forecast_loop.py'),
    }
    args = ['sudo', '-n', '/usr/bin/env'] + [k + '=' + v for k,v in values.items()]
    args += [runtime.COMPOSE_BINARY, '--env-file', '/dev/null', '--project-name', 'lakehouse-weather',
             '--file', str(runtime.COMPOSE), 'up', '--detach', '--no-deps', '--no-build', '--pull', 'never', 'dashboard']
    result = subprocess.run(args, capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError('Dashboard-only Compose failed; diagnostic payload suppressed')
    deadline = time.monotonic() + 150
    while runtime.field('container', runtime.APP, '{{if .State.Health}}{{.State.Health.Status}}{{end}}') != 'healthy':
        if time.monotonic() >= deadline:
            raise ValueError('Dashboard readiness deadline exceeded')
        time.sleep(2)
    if runtime.field('container', runtime.APP, '{{.Image}}') != image:
        raise ValueError('Dashboard image drift')
    forecast_identity()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image-id', required=True)
    p.add_argument('--reviewed-head', required=True)
    p.add_argument('--reviewed-tree', required=True)
    p.add_argument('--expected-dashboard-id', required=True)
    p.add_argument('--expected-old-image', required=True)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args(argv)
    if os.geteuid() != 0:
        raise ValueError('Root execution required')
    runtime.identity(a.image_id, a.reviewed_head, a.reviewed_tree)
    forecast_identity()
    if runtime.field('container', runtime.APP, '{{.Id}} {{.Image}}') != a.expected_dashboard_id + ' ' + a.expected_old_image:
        raise ValueError('Prior dashboard identity drift')
    for key, expected in [('project','lakehouse-weather'),('service','dashboard')]:
        if runtime.field('container', runtime.APP, '{{index .Config.Labels "com.docker.compose.' + key + '"}}') != expected:
            raise ValueError('Dashboard ownership drift')
    if not a.apply:
        print('Dashboard-only identity preflight passed; no mutation')
        return 0
    receipt = BASE / 'dashboard-updates' / a.reviewed_head
    receipt.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (receipt / 'receipt.json').open('x') as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump({'source_head':a.reviewed_head,'source_tree':a.reviewed_tree,'new_image':a.image_id,
                   'previous_image':a.expected_old_image,'previous_dashboard':a.expected_dashboard_id,
                   'forecast_unchanged':FORECAST_ID},f)
    try:
        compose(a.image_id)
    except Exception:
        try:
            compose(a.expected_old_image)
        except Exception:
            raise ValueError('Dashboard update and recovery incomplete; inspect nonsecret health metadata')
        raise ValueError('Dashboard update failed; prior image restored')
    print('Dashboard-only update healthy; forecast identity unchanged; database/session state preserved')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Dashboard update refused or failed; no protected diagnostics disclosed')
