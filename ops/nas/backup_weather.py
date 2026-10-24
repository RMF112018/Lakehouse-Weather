#!/usr/bin/env python3
"""Explicit weather-only backup; dry-run default, no credential access or logs."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess
from datetime import datetime, timezone
from runtime import DOCKER, PG_ID, PG_NAME, field


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True, help='Existing empty absolute owner-only directory')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    if not args.apply:
        print('Dry run: custom-format pg_dump of weather schema in my_pa only; no backup performed')
        return 0
    destination = Path(args.destination)
    if not destination.is_absolute() or destination.is_symlink() or not destination.is_dir():
        raise ValueError('Explicit backup directory required')
    if stat.S_IMODE(destination.stat().st_mode) != 0o700 or any(destination.iterdir()):
        raise ValueError('Empty mode-0700 destination required')
    if field('container', PG_NAME, '{{.Id}}') != PG_ID:
        raise ValueError('Source container identity drift')
    database = subprocess.run([*DOCKER, 'exec', '--user', 'postgres', PG_ID, 'psql', '-X', '-U', 'my_pa', '-d', 'my_pa', '-Atc', 'SELECT current_database()'], capture_output=True, text=True)
    if database.returncode or database.stdout.strip() != 'my_pa':
        raise ValueError('Source database identity mismatch')
    archive = destination / 'weather.dump'
    # Exclusive creation: preserve partial failed attempts for operator review.
    with archive.open('xb') as handle:
        archive.chmod(0o600)
        result = subprocess.run([*DOCKER, 'exec', '--user', 'postgres', PG_ID, 'pg_dump', '-U', 'my_pa', '-d', 'my_pa', '--format=custom', '--schema=weather', '--strict-names', '--no-owner', '--no-privileges'], stdout=handle, stderr=subprocess.DEVNULL)
    if result.returncode or not archive.stat().st_size:
        raise ValueError('Weather backup failed; partial artifact retained, no success manifest')
    digest_state = hashlib.sha256()
    with archive.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest_state.update(chunk)
    digest = digest_state.hexdigest()
    manifest = {'scope': 'weather schema only; excludes my-pa-owned schemas', 'source_container_id': PG_ID,
                'source_database': 'my_pa', 'created_at': datetime.now(timezone.utc).isoformat(),
                'file': 'weather.dump', 'bytes': archive.stat().st_size, 'sha256': digest,
                'restore_rehearsed': False, 'roles_included': False}
    with (destination / 'manifest.json').open('x') as handle:
        json.dump(manifest, handle, indent=2)
    (destination / 'manifest.json').chmod(0o600)
    print('Weather-only backup and hash manifest created; restore rehearsal remains required')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError):
        raise SystemExit('Weather backup refused or failed; no private diagnostic payload disclosed')
