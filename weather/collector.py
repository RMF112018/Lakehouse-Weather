"""Private stdin collector: allowlist, durable journal, committed delivery, replay.

The journal is a protected local directory, never an HTTP acknowledgement queue.
No payloads or driver errors are logged. A failure retains the pending file.
"""
import fcntl
import json
import os
import re
from pathlib import Path
import stat
import time
import uuid
from datetime import datetime, timezone
from . import registry
from .domain import normalize, stamp, utc

DECODER_BUILD = 'sha256:d46c11edfc6029a1f7d603ccf0cb7fb1c6bdee848b5a9a03e6bb9323eedfc6e6'
MAX_LINE = 16384


class Journal:
    def __init__(self, path, max_bytes=256 * 1024 * 1024, max_events=50000):
        self.path = Path(path)
        self.max_bytes, self.max_events = max_bytes, max_events
        if max_bytes < MAX_LINE * 4 or max_events < 1:
            raise ValueError('Invalid journal budget')
        if self.path.is_symlink() or not self.path.is_dir():
            raise ValueError('Precreated protected journal required')
        info = self.path.stat()
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError('Journal must be private and collector owned')
        self.status = {key: None for key in ('last_receipt_utc', 'last_commit_utc', 'updated_at_utc', 'error_code')}
        self.status.update({key: 0 for key in ('accepted', 'rejected', 'duplicates', 'conflicts', 'pending_count', 'pending_bytes', 'oldest_pending_age_seconds')})
        self.lock = os.open(self.path / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            os.close(self.lock)
            raise ValueError('Collector already active') from None
        try:
            status_path = self.path / 'status.json'
            if status_path.exists():
                fd = os.open(status_path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, 'rb') as handle:
                    prior = json.loads(handle.read(4097))
                if not isinstance(prior, dict) or set(prior) != set(self.status):
                    raise ValueError('Invalid status schema')
                for key, value in prior.items():
                    if key in ('last_receipt_utc', 'last_commit_utc', 'updated_at_utc'):
                        if value is not None:
                            utc(value)
                    elif key == 'error_code':
                        if value not in (None, 'capacity', 'pending_age_limit', 'observation_conflict', 'database_unavailable'):
                            raise ValueError('Invalid status code')
                    elif type(value) is not int or not 0 <= value <= 10 ** 15:
                        raise ValueError('Invalid status counter')
                self.status = prior
        except Exception:
            os.close(self.lock)
            raise ValueError('Journal status requires reconciliation') from None

    def close(self):
        os.close(self.lock)

    def sync(self):
        descriptor = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def update_status(self, **updates):
        self.status.update(updates)
        self.status['updated_at_utc'] = stamp(datetime.now(timezone.utc))
        temporary = self.path / '.status.tmp'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(self.status, handle, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path / 'status.json')
        self.sync()

    def pending(self):
        paths = sorted(p for p in self.path.iterdir() if p.name not in {'.lock', 'status.json', '.status.tmp'})
        if len(paths) > self.max_events:
            self.update_status(error_code='capacity')
            raise ValueError('Journal event budget exceeded')
        total = 0
        for path in paths:
            if path.is_symlink() or not path.is_file() or not path.name.endswith('.json'):
                raise ValueError('Journal needs operator reconciliation')
            total += path.stat().st_size
        if total > self.max_bytes:
            self.update_status(error_code='capacity')
            raise ValueError('Journal byte budget exceeded')
        age = max((max(0, time.time() - p.stat().st_mtime) for p in paths), default=0)
        self.status.update(pending_count=len(paths), pending_bytes=total, oldest_pending_age_seconds=int(age))
        if age > 7 * 86400:
            self.update_status(error_code='pending_age_limit')
            raise ValueError('Pending journal age requires operator reconciliation')
        return paths, total

    def append(self, record):
        data = json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if len(data) > 65536:
            raise ValueError('Normalized journal event exceeds record bound')
        paths, total = self.pending()
        if len(paths) >= self.max_events or total + len(data) > self.max_bytes:
            self.update_status(error_code='capacity')
            raise ValueError('Journal capacity reached; source must stop')
        path = self.path / (uuid.uuid4().hex + '.json')
        # An interrupted partial write is retained and blocks replay; never guess an ACK.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            self.sync()
        self.pending()
        self.update_status(accepted=self.status['accepted'] + 1, error_code=None)
        return path

    def replay(self, deliver):
        paths, _ = self.pending()
        for path in paths:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as handle:
                content = handle.read(65537)
            if len(content) > 65536:
                raise ValueError('Journal record too large')
            record = json.loads(content, object_pairs_hook=unique_object)
            if set(record) != {'station_id', 'observation'}:
                raise ValueError('Invalid journal record')
            # deliver returns only after transaction commit, including exact duplicates.
            deliver(record['station_id'], record['observation'])
            path.unlink()
            self.sync()
            self.pending()
            self.update_status()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def collect(stream, locations, journal, deliver):
    """Backpressure: finish replay/delivery before consuming another radio line."""
    journal.replay(deliver)
    while True:
        line = stream.readline(MAX_LINE + 2)
        if not line:
            return
        if len(line) > MAX_LINE or not line.endswith(b'\n'):
            raise ValueError('Oversized or incomplete receiver line; source must stop')
        journal.status['last_receipt_utc'] = stamp(datetime.now(timezone.utc))
        try:
            packet = json.loads(line, object_pairs_hook=unique_object)
            if not isinstance(packet, dict):
                raise ValueError('Packet object required')
            # Resolve before constructing context, normalizing, or writing anything.
            station_id = registry.resolve(locations, packet)
            if not registry.source(locations, station_id).get('rf_profile'):
                raise ValueError('Explicit RF source profile required')
            context = {'transport': 'local_collector', 'model': packet.get('model'),
                       'sensor_id': packet.get('id'), 'protocol': packet.get('protocol'),
                       'decoder_build': DECODER_BUILD,
                       'receiver_received_at_utc': stamp(datetime.now(timezone.utc))}
            registry.admit(locations, packet, context)
            at = packet.get('time')
            if isinstance(at, str) and len(at) == 19:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', at):
                    raise ValueError('Invalid local decoder UTC timestamp')
                datetime.strptime(at, '%Y-%m-%d %H:%M:%S')
                packet['time'] = at.replace(' ', 'T') + 'Z'
            observation = normalize(packet, trusted_context=context)
        except (ValueError, TypeError, KeyError, UnicodeError):
            # Unknown neighbors and malformed data never enter disk/logs/database.
            journal.update_status(rejected=journal.status['rejected'] + 1)
            continue
        journal.append({'station_id': station_id, 'observation': observation})
        journal.replay(deliver)


def run(stream, locations, path, store_factory, retry_seconds=5):
    from .store import ObservationConflict
    journal = Journal(path)
    store = None

    def deliver(station_id, observation):
        nonlocal store
        while True:
            try:
                if store is None:
                    store = store_factory()
                inserted = store.insert(station_id, observation)
                journal.update_status(last_commit_utc=stamp(datetime.now(timezone.utc)),
                                      duplicates=journal.status['duplicates'] + int(inserted is False), error_code=None)
                return
            except ObservationConflict:
                # Retain the original pending event, stop consuming RF, require repair.
                journal.update_status(conflicts=journal.status['conflicts'] + 1, error_code='observation_conflict')
                raise
            except Exception:
                store = None
                journal.pending()
                journal.update_status(error_code='database_unavailable')
                # No diagnostic exception text: database errors can contain secrets.
                time.sleep(retry_seconds)
    try:
        collect(stream, locations, journal, deliver)
    finally:
        journal.close()
