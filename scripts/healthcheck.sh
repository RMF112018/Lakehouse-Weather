#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HTTP_PORT="8088"
if [[ -f .env ]]; then
  HTTP_PORT="$(grep -E '^HTTP_PORT=' .env | tail -1 | cut -d= -f2- || true)"
fi
HTTP_PORT="${HTTP_PORT:-8088}"

echo "== Container state =="
docker compose ps

echo
echo "== Dashboard health =="
if command -v curl >/dev/null 2>&1; then
  curl -fsS "http://127.0.0.1:${HTTP_PORT}/healthz"
elif command -v wget >/dev/null 2>&1; then
  wget -qO- "http://127.0.0.1:${HTTP_PORT}/healthz"
else
  echo "Neither curl nor wget is available; skipping HTTP probe." >&2
fi
