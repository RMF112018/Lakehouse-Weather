#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p runtime/weewx runtime/backups runtime/logs runtime/mosquitto/data runtime/mosquitto/log captures

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example; populate station values after Gate 1."
else
  echo ".env already exists; leaving it unchanged."
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Synchronizing submodule definitions..."
  git submodule sync --recursive || true
  if [[ "${SKIP_SUBMODULES:-0}" != "1" ]]; then
    echo "Initializing pinned upstream submodules (requires GitHub network access)..."
    git submodule update --init --recursive || {
      echo "WARNING: submodule checkout failed. The scaffold remains usable; retry when network access is available." >&2
    }
  fi
fi

echo "Bootstrap complete. Next: scripts/synology/usb-device-info.sh"
