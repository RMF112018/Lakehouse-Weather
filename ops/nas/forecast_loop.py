#!/usr/bin/env python3
"""Hourly nonoverlapping bounded refresh; health metadata only, no payload logs."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

STATE = Path('/tmp/forecast-state.json')
INTERVAL = 3600
TIMEOUT = 120


def run_once(previous_success=None):
    try:
        result = subprocess.run([sys.executable, '-m', 'weather', 'refresh-forecasts'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=TIMEOUT)
        success = result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        success = False
    now = time.time()
    state = {'last_attempt': now, 'last_success': now if success else previous_success, 'last_result': 'ok' if success else 'failed'}
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state))
    os.replace(temporary, STATE)
    return state['last_success']


def main():
    stop = threading.Event()
    for value in (signal.SIGTERM, signal.SIGINT):
        signal.signal(value, lambda *_: stop.set())
    previous_success = None
    while not stop.is_set():
        previous_success = run_once(previous_success)
        stop.wait(INTERVAL)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
