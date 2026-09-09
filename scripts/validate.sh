#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

required=(
  README.md
  ROADMAP.md
  compose.yaml
  .env.example
  .gitmodules
  UPSTREAMS.lock
  docker/weewx/Dockerfile
  config/rtl_433/rtl_433.conf
  config/weewx/sdr.conf.example
  docs/runbooks/gate-1-rf.md
  tests/fixtures/wh65b.sample.json
)

for path in "${required[@]}"; do
  [[ -e "$path" ]] || { echo "Missing required path: $path" >&2; exit 1; }
done

for script in scripts/*.sh scripts/synology/*.sh; do
  [[ -f "$script" ]] || continue
  bash -n "$script"
done

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose config --quiet
else
  echo "Docker Compose unavailable; skipped compose schema validation."
fi

echo "Repository validation: PASS"
