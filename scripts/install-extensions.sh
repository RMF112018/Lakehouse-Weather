#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

required=(vendor/weewx-sdr vendor/weewx-belchertown-new)
for path in "${required[@]}"; do
  if [[ ! -d "$path" || -z "$(find "$path" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    echo "Missing populated submodule: $path" >&2
    echo "Run: git submodule update --init --recursive" >&2
    exit 1
  fi
done

# Initialize /data before extension installation if needed.
docker compose run --rm weewx || true

echo "Installing weewx-sdr from pinned local submodule..."
docker compose run --rm weewx extension install --yes /workspace/vendor/weewx-sdr

echo "Installing New Belchertown from pinned local submodule..."
docker compose run --rm weewx extension install --yes /workspace/vendor/weewx-belchertown-new

echo "Extensions installed into runtime/weewx. Configure the authoritative weewx.conf next."
