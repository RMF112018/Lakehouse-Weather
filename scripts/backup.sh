#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p runtime/backups
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="runtime/backups/${STAMP}-weewx.tar.gz"

tar -czf "$OUT" -C runtime weewx
printf 'Created %s\n' "$OUT"
