#!/usr/bin/env bash
set -euo pipefail

echo "== Lakehouse Weather: USB inventory =="

if command -v lsusb >/dev/null 2>&1; then
  lsusb
  echo
  echo "Likely RTL-SDR entries:"
  lsusb | grep -Ei '0bda:2838|RTL283|RTL-SDR|Realtek' || true
else
  echo "lsusb is not installed. Inspecting /sys/bus/usb/devices instead."
  for d in /sys/bus/usb/devices/*; do
    [[ -f "$d/idVendor" && -f "$d/idProduct" ]] || continue
    vendor="$(cat "$d/idVendor")"
    product="$(cat "$d/idProduct")"
    manufacturer="$(cat "$d/manufacturer" 2>/dev/null || true)"
    name="$(cat "$d/product" 2>/dev/null || true)"
    serial="$(cat "$d/serial" 2>/dev/null || true)"
    printf '%s:%s  %s %s  serial=%s\n' "$vendor" "$product" "$manufacturer" "$name" "$serial"
  done
fi

echo
if [[ -e /dev/bus/usb ]]; then
  echo "/dev/bus/usb exists: PASS candidate"
  ls -ld /dev/bus/usb
else
  echo "/dev/bus/usb is not present: Gate 1 cannot use the default passthrough path." >&2
fi
