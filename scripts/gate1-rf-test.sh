#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Load local values without exporting arbitrary shell code.
TZ_VALUE="America/New_York"
FREQ="915M"
SERIAL=""
if [[ -f .env ]]; then
  TZ_VALUE="$(grep -E '^TZ=' .env | tail -1 | cut -d= -f2- || true)"
  FREQ="$(grep -E '^RTL433_FREQUENCY=' .env | tail -1 | cut -d= -f2- || true)"
  SERIAL="$(grep -E '^RTLSDR_SERIAL=' .env | tail -1 | cut -d= -f2- || true)"
fi
TZ_VALUE="${TZ_VALUE:-America/New_York}"
FREQ="${FREQ:-915M}"

IMAGE="${RTL433_IMAGE:-hertzg/rtl_433:master}"
SECONDS_TO_RUN="${GATE1_SECONDS:-300}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="captures/${STAMP}-gate1-rtl433.jsonl"
mkdir -p captures

echo "== GATE-1-RF =="
echo "Image:     $IMAGE"
echo "Frequency: $FREQ"
echo "Duration:  ${SECONDS_TO_RUN}s (if timeout is available)"
echo "Capture:   $OUT"
echo

echo "Expected success evidence includes JSON packets with model=Fineoffset-WH65B."
echo "The script does not declare Gate 1 passed automatically; review the capture."
echo

DEVICE_ARGS=(--device /dev/bus/usb:/dev/bus/usb)
RTL_ARGS=(-f "$FREQ" -M time:utc -M protocol -F json)

# Use serial selection only when the value has been intentionally changed from the example default.
if [[ -n "$SERIAL" && "$SERIAL" != "00000001" ]]; then
  RTL_ARGS=(-d ":$SERIAL" "${RTL_ARGS[@]}")
fi

set +e
if command -v timeout >/dev/null 2>&1; then
  timeout "${SECONDS_TO_RUN}s" docker run --rm \
    "${DEVICE_ARGS[@]}" \
    -e "TZ=$TZ_VALUE" \
    "$IMAGE" \
    "${RTL_ARGS[@]}" 2>&1 | tee "$OUT"
  rc=${PIPESTATUS[0]}
  # GNU timeout exits 124 when the requested observation window completes.
  [[ $rc -eq 124 ]] && rc=0
else
  echo "No timeout utility found; stop manually with Ctrl-C after at least 5 minutes." >&2
  docker run --rm \
    "${DEVICE_ARGS[@]}" \
    -e "TZ=$TZ_VALUE" \
    "$IMAGE" \
    "${RTL_ARGS[@]}" 2>&1 | tee "$OUT"
  rc=${PIPESTATUS[0]}
fi
set -e

echo
echo "== Capture summary =="
count="$(grep -c 'Fineoffset-WH65B' "$OUT" 2>/dev/null || true)"
echo "Fineoffset-WH65B packet lines: $count"
if [[ "$count" -ge 3 ]]; then
  echo "RF decode evidence threshold met (>=3 WH65B packets)."
  echo "Next: identify the stable sensor ID and follow docs/runbooks/gate-2-sensor-map.md"
else
  echo "Gate-1 acceptance threshold not met yet. Inspect $OUT and container/USB errors." >&2
fi

exit "$rc"
