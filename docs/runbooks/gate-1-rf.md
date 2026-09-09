# Runbook: GATE-1-RF

## Objective

Prove that the DS923+ can pass the RTL-SDR to a container and that current `rtl_433` software can decode the existing WS-2000/WH65B transmissions at 915 MHz.

## Acceptance criteria

All must pass:

- [ ] DSM/Linux host enumerates the RTL-SDR USB device.
- [ ] Container can open the RTL-SDR without permission or kernel-driver errors.
- [ ] `rtl_433` runs at 915 MHz for at least 5 minutes.
- [ ] At least three packets identify as `Fineoffset-WH65B`.
- [ ] A stable sensor ID is observed across those packets.
- [ ] Temperature/humidity values are locally plausible.
- [ ] Wind/rain/UV/light fields appear when available.
- [ ] Representative JSON is saved under `captures/` locally and sanitized fixture is committed to `tests/fixtures/`.

## Procedure

```bash
cp .env.example .env
./scripts/synology/usb-device-info.sh
./scripts/gate1-rf-test.sh
```

The Gate-1 script intentionally uses the maintained `hertzg/rtl_433` image independently of WeeWX. This isolates USB/RF failure from application configuration.

## Failure handling

- Host cannot see dongle: resolve DSM/USB hardware enumeration first.
- Host sees dongle but container cannot: resolve Container Manager device passthrough/permissions.
- Container opens dongle but no packets: confirm antenna, 915 MHz tuning, sensor power, and placement.
- Packets appear but WH65B is not decoded: test the pinned/current `rtl_433` development build before changing any Lakehouse application code.
