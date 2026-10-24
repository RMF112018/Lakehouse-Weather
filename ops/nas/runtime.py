#!/usr/bin/env python3
"""Narrow NAS admission/status/stop tool. Never prints inspect/config/env/logs."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

PG_NAME = 'my-pa-nas-contract-postgres-1'
PG_ID = '6f2581014af3e6f41f4b5c8f412334ac371d9875a75a553fe96bd74936fbbe83'
NETWORKS = {
    'my-pa-nas-contract_data-plane': 'd4d93b256b6e07878a87cc57ff17ec6813cc6b69fa62251939b0bef8ea402dff',
    'my-pa-nas-contract_browser-origin': '07066b683c5e585d4516803c9c90ab748139f69c8672d2e24fc646cd1983faa2',
}
APP = 'lakehouse-weather-dashboard'
APPS = {'dashboard': APP, 'forecast': 'lakehouse-weather-forecast'}
COMPOSE = Path(__file__).resolve().parents[2] / 'compose.dashboard.production.yaml'
DOCKER = ['sudo', '-n', '/usr/local/bin/docker']
COMPOSE_BINARY = '/usr/local/bin/docker-compose'


def docker(*args):
    result = subprocess.run([*DOCKER, *args], capture_output=True, text=True)
    if result.returncode:
        raise ValueError('Docker operation failed; no diagnostic payload disclosed')
    return result.stdout.strip()


def field(kind, target, expression):
    return docker(kind, 'inspect', '--format', expression, target)


def identity(image, head, tree):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('Immutable image ID required')
    if not all(re.fullmatch('[0-9a-f]{40}', value) for value in (head, tree)):
        raise ValueError('Exact reviewed Git head and tree required')
    if field('image', image, '{{.Id}}') != image:
        raise ValueError('Image identity drift')
    if field('image', image, '{{.Os}}/{{.Architecture}}') != 'linux/amd64':
        raise ValueError('NAS image platform mismatch')
    for label, expected in [('revision', head), ('source-tree', tree)]:
        actual = field('image', image, '{{index .Config.Labels "org.opencontainers.image.' + label + '"}}')
        if actual != expected:
            raise ValueError('Reviewed image provenance mismatch')
    if field('image', image, '{{.Config.User}}') != '10001:10001':
        raise ValueError('Image UID contract mismatch')
    command = json.loads(field('image', image, '{{json .Config.Cmd}}'))
    if command != ['gunicorn', '--config', 'python:weather.gunicorn_config', 'weather.wsgi:create_app()']:
        raise ValueError('Production Gunicorn entry point required')
    if field('image', image, '{{json .Config.Entrypoint}}') not in ('null', '[]'):
        raise ValueError('Unexpected image entry point')
    if field('container', PG_NAME, '{{.Id}}') != PG_ID:
        raise ValueError('PostgreSQL container identity drift')
    for name, expected in NETWORKS.items():
        if field('network', name, '{{.Id}}') != expected or field('network', name, '{{.Internal}}') != 'true':
            raise ValueError('Canonical network identity drift')
    attached = json.loads(field('container', PG_NAME, '{{json .NetworkSettings.Networks}}'))
    if attached.get('my-pa-nas-contract_data-plane', {}).get('NetworkID') != NETWORKS['my-pa-nas-contract_data-plane']:
        raise ValueError('PostgreSQL network attachment mismatch')


def mount_path(value, secret=False, directory=False):
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not (path.is_dir() if directory else path.is_file()):
        raise ValueError('Explicit regular absolute mount path required')
    if directory and (path.stat().st_uid != 10001 or stat.S_IMODE(path.stat().st_mode) != 0o700):
        raise ValueError('RF journal requires UID 10001 and mode 0700')
    mode = path.stat().st_mode
    if mode & stat.S_IWOTH or (secret and mode & stat.S_IROTH):
        raise ValueError('Mount permissions too broad')
    return str(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['admit', 'status', 'stop'])
    parser.add_argument('--apply', action='store_true', help='Execute explicit action; otherwise print bounded plan')
    parser.add_argument('--image-id')
    parser.add_argument('--reviewed-head')
    parser.add_argument('--reviewed-tree')
    parser.add_argument('--registry')
    parser.add_argument('--database-url-file')
    parser.add_argument('--ingest-token-file')
    parser.add_argument('--forecast-database-url-file')
    args = parser.parse_args(argv)
    if not args.apply:
        print('Dry run: ' + args.action + ' own weather services only; admit creates only the weather egress network, no database/proxy mutation')
        return 0
    if args.action == 'status':
        # This expression deliberately excludes health output, command and environment.
        for name in APPS.values():
            print(field('container', name, '{{.Id}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}'))
        return 0
    if args.action == 'stop':
        # Refuse similarly named containers outside this Compose project/service.
        present = []
        for service, name in APPS.items():
            if not docker('container', 'ls', '--all', '--filter', 'name=^/' + name + '$', '--format', '{{.ID}}'):
                continue
            present.append(name)
            for key, expected in [('project', 'lakehouse-weather'), ('service', service)]:
                if field('container', name, '{{index .Config.Labels "com.docker.compose.' + key + '"}}') != expected:
                    raise ValueError('Weather container ownership mismatch')
        for name in present:
            docker('container', 'stop', '--time', '130', name)
        print('Weather containers stopped; schema and dedicated role retained')
        return 0
    required = (args.image_id, args.reviewed_head, args.reviewed_tree, args.registry, args.database_url_file, args.ingest_token_file, args.forecast_database_url_file)
    if not all(required):
        raise ValueError('Admission requires image ID, reviewed head/tree, registry and secret file paths')
    identity(args.image_id, args.reviewed_head, args.reviewed_tree)
    for service, name in APPS.items():
        existing = docker('container', 'ls', '--all', '--filter', 'name=^/' + name + '$', '--format', '{{.ID}}')
        if existing:
            for key, expected in [('project', 'lakehouse-weather'), ('service', service)]:
                if field('container', name, '{{index .Config.Labels "com.docker.compose.' + key + '"}}') != expected:
                    raise ValueError('Existing weather container ownership mismatch')
    own_network = docker('network', 'ls', '--filter', 'name=^lakehouse-weather-egress$', '--format', '{{.ID}}')
    if own_network:
        if field('network', 'lakehouse-weather-egress', '{{index .Labels "com.docker.compose.project"}}') != 'lakehouse-weather' or field('network', 'lakehouse-weather-egress', '{{.Internal}}') != 'false':
            raise ValueError('Weather egress network ownership mismatch')
        if field('network', 'lakehouse-weather-egress', '{{.Driver}}') != 'bridge':
            raise ValueError('Weather egress bridge driver mismatch')
        members = json.loads(field('network', 'lakehouse-weather-egress', '{{json .Containers}}'))
        if any(member.get('Name') != APPS['forecast'] for member in members.values()):
            raise ValueError('Weather egress bridge has a foreign member')
    env = {**os.environ, 'WEATHER_IMAGE_ID': args.image_id,
           'WEATHER_RF_JOURNAL_PATH': mount_path('/volume1/weather-dashboard/rf-journal', False, True),
           'WEATHER_REGISTRY_PATH': mount_path(args.registry),
           'WEATHER_DATABASE_URL_PATH': mount_path(args.database_url_file, True),
           'WEATHER_INGEST_TOKEN_PATH': mount_path(args.ingest_token_file, True),
           'WEATHER_FORECAST_DATABASE_URL_PATH': mount_path(args.forecast_database_url_file, True),
           'WEATHER_FORECAST_LOOP_PATH': mount_path(str(Path(__file__).with_name('forecast_loop.py')))}
    # sudo normally filters environment. Pass only non-secret mount paths and the
    # immutable image ID explicitly through env; secret contents never enter argv.
    compose_env = ['WEATHER_RF_JOURNAL_PATH', 'WEATHER_IMAGE_ID', 'WEATHER_REGISTRY_PATH', 'WEATHER_DATABASE_URL_PATH', 'WEATHER_INGEST_TOKEN_PATH', 'WEATHER_FORECAST_LOOP_PATH', 'WEATHER_FORECAST_DATABASE_URL_PATH']
    # Synology exposes Compose as its separate reviewed absolute executable.
    # Do not discover an executable via PATH or assume docker compose exists.
    version = subprocess.run(['sudo', '-n', COMPOSE_BINARY, 'version', '--short'], capture_output=True, text=True)
    if version.returncode or not re.fullmatch(r'v?2\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9_.-]+)?', version.stdout.strip()):
        raise ValueError('Verified standalone Docker Compose v2 required')
    privileged = ['sudo', '-n', '/usr/bin/env', *[key + '=' + env[key] for key in compose_env], COMPOSE_BINARY]
    # Explicit file/project and --no-deps cannot recreate my-pa services. Image
    # has no mutable tag and pulling/building are forbidden by this command.
    compose = [*privileged, '--env-file', '/dev/null', '--project-name', 'lakehouse-weather', '--file', str(COMPOSE),
               'up', '--detach', '--no-deps', '--no-build', '--pull', 'never']
    for service in ('dashboard', 'forecast'):
        result = subprocess.run([*compose, service], env=env, capture_output=True)
        if result.returncode:
            raise ValueError('Weather admission failed; output withheld to protect secret paths')
        if service == 'dashboard':
            # Explicit ordering avoids relying on --no-deps condition semantics.
            deadline = time.monotonic() + 120
            while field('container', APP, '{{if .State.Health}}{{.State.Health.Status}}{{end}}') != 'healthy':
                if time.monotonic() >= deadline:
                    raise ValueError('Dashboard readiness deadline exceeded; forecast not started')
                time.sleep(2)
    for service, name in APPS.items():
        attached = json.loads(field('container', name, '{{json .NetworkSettings.Networks}}'))
        expected = {'my-pa-nas-contract_data-plane', 'my-pa-nas-contract_browser-origin'} if service == 'dashboard' else {'my-pa-nas-contract_data-plane', 'lakehouse-weather-egress'}
        if set(attached) != expected:
            raise ValueError('Weather container network set mismatch; stop own services and investigate')
        for network in expected & NETWORKS.keys():
            if attached[network]['NetworkID'] != NETWORKS[network]:
                raise ValueError('Weather container network identity drift')
    forecast_id = field('container', APPS['forecast'], '{{.Id}}')
    egress_members = json.loads(field('network', 'lakehouse-weather-egress', '{{json .Containers}}'))
    if set(egress_members) != {forecast_id}:
        raise ValueError('Weather egress bridge has unexpected members; stop own services and investigate')
    print('Weather services admitted; public route remains separately gated')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, json.JSONDecodeError):
        raise SystemExit('Weather operation refused or failed; no private diagnostic payload disclosed')
