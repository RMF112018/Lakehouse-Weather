# Synology DS923+ deployment notes

## Target

- Host: Synology DS923+
- Runtime: DSM + Container Manager
- Time zone: America/New_York
- Persistent root: `/volume1/docker/lakehouse-weather` by default; adjust to match the NAS storage plan.

## Gate 1 prerequisites

1. Insert the RTL-SDR dongle using a short USB extension if desired.
2. Confirm DSM sees a Realtek RTL2832/RTL2838-class USB device.
3. Confirm `/dev/bus/usb` is visible to Container Manager or an equivalent stable device path can be passed through.
4. Run `scripts/gate1-rf-test.sh`.
5. Record the `Fineoffset-WH65B` sensor ID and save a sample JSON packet.

## Persistent directories

The runtime volume must survive container replacement:

```text
runtime/weewx/        WeeWX config, SQLite DB, reports, extensions
runtime/backups/      Local backup archives
runtime/logs/         Script-level diagnostics
```

For production, these may be symlinked or bind-mounted to the NAS shared-folder layout.

## USB note

Do not assume the bus/device number is stable across reboots. Prefer RTL-SDR EEPROM serial selection once the dongle is identified. Gate 1 deliberately starts broad because Synology enumeration behavior must be observed first.
