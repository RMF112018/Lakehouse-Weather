# Architecture

## Scope

Lakehouse Weather replaces the failed WS-2000 console as the receiver, archive, and dashboard path while retaining the existing outdoor sensor array.

## Runtime components

### 1. RF sensor layer
- Existing Ambient Weather WS-2000 outdoor array / Fine Offset WH65B family.
- Optional existing WH32B indoor temperature/humidity/pressure sensor if it is still transmitting.
- 915 MHz ISM-band transmissions.

### 2. RF receiver
- RTL-SDR USB dongle and 915 MHz antenna.
- Attached to the Synology DS923+.
- `/dev/bus/usb` is passed into the receiver container only after Gate 1 proves DSM/Container Manager access.

### 3. Decoder
- `rtl_433`, pinned to a known commit in `UPSTREAMS.lock`.
- Produces JSON during Gate 1.
- In steady state it is launched by `weewx-sdr` in the WeeWX container.

### 4. Weather engine
- WeeWX 5 using `weewx-sdr` as the station driver.
- Default archive is SQLite unless future scale or integrations justify PostgreSQL.
- WeeWX owns archive intervals, derived observations, summaries, records, reports, and unit conversion.

### 5. Presentation
- New Belchertown WeeWX skin.
- Static/realtime generated site served by nginx.
- Mobile-first presentation is expected to work on Safari/iPhone; project-specific styling belongs in `patches/belchertown/` or a dedicated skin fork.

### 6. Remote access
- Preferred private path: Tailscale.
- Optional public hostname: Cloudflare Tunnel + Access.
- No direct WAN exposure of RTL-SDR, WeeWX internals, SQLite, or MQTT.

## Deployment gates

1. **GATE-1-RF** — Synology sees RTL-SDR and `rtl_433` decodes `Fineoffset-WH65B` packets.
2. **GATE-2-MAP** — WH65B sensor ID and exact field mappings are frozen in WeeWX configuration.
3. **GATE-3-WEEWX** — WeeWX archives valid observations for at least 24 hours without gaps attributable to the application.
4. **GATE-4-UI** — New Belchertown renders current/history data correctly on iPhone and desktop.
5. **GATE-5-REMOTE** — Tailscale and/or Cloudflare Access reaches only the dashboard endpoint.
6. **GATE-6-OPS** — backup, restore, healthcheck, restart, and sensor-ID-change procedures are tested.

## Non-goals for v1

- Rebuilding a custom FastAPI/React stack.
- Exposing MQTT to the Internet.
- Replacing proven WeeWX archive/calculation logic.
- Automating sensor-ID selection before real RF captures exist.
