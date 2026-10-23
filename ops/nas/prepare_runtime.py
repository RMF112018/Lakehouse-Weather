#!/usr/bin/env python3
"""Provision a new ingest token only; never read existing secrets or rotate."""
import argparse
import os
from pathlib import Path
import secrets
import stat

SECRET_DIR = Path('/volume1/weather-dashboard/secrets')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--secret-dir', required=True)
    parser.add_argument('--uid', type=int, default=10001)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    path = Path(args.secret_dir)
    if path != SECRET_DIR or args.uid != 10001:
        raise ValueError('Exact reviewed secret directory and UID 10001 required')
    if not args.apply:
        print('Dry run: create one new mode-0400 UID-10001 ingest-token; no token generated')
        return 0
    if os.geteuid() != 0:
        raise ValueError('Authorized root operator execution required')
    if not path.parent.is_dir() or path.parent.resolve() != path.parent:
        raise ValueError('Prepare the root-owned reviewed parent directory first')
    if path.exists():
        if path.is_symlink() or not path.is_dir() or path.stat().st_uid != 10001 or stat.S_IMODE(path.stat().st_mode) != 0o700:
            raise ValueError('Existing secret directory metadata mismatch')
    else:
        path.mkdir(mode=0o700)
        os.chown(path, 10001, 10001)
    # O_EXCL/O_NOFOLLOW fail closed on existing paths. No existing file is read.
    descriptor = os.open(path / 'ingest-token', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        os.fchown(descriptor, 10001, 10001)
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(secrets.token_urlsafe(48) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        # Preserve failed artifact for explicit operator resolution; no rotation.
        raise
    print('New ingest-token prepared: UID 10001, mode 0400; value withheld')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError):
        raise SystemExit('Secret provisioning refused or failed; existing secrets not read or replaced')
