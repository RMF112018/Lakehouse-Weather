# Lakehouse Weather

Self-hosted replacement receiver and remote dashboard stack for an Ambient Weather WS-2000 / Fine Offset WH65B-class sensor array.

The target host is a Synology DS923+ running Container Manager. The target client is an iPhone-accessible web/PWA dashboard. The project is deliberately staged so RF/USB reception is proven before the weather application is deployed.

## Target architecture

```text
WH65B / WS-2000 outdoor array
          |
          | 915 MHz RF
          v
     RTL-SDR receiver
          |
          v
       rtl_433
          |
          v
      weewx-sdr
          |
          v
        WeeWX 5
       /       \
 SQLite       reports
 archive      + skin
                 |
                 v
        New Belchertown
                 |
                 v
             nginx
                 |
        Tailscale / Cloudflare
                 |
                 v
               iPhone
```

## Design principles

1. **Gate RF first.** No application work depends on unproven Synology USB passthrough.
2. **Use mature weather software.** WeeWX owns observation archiving, unit conversion, derived metrics, records, reports, and historical calculations.
3. **Keep upstream provenance explicit.** GPL dependencies are pinned as Git submodules and tracked in `UPSTREAMS.lock`.
4. **Keep remote exposure narrow.** Only the HTTP dashboard should be remotely reachable. SDR, WeeWX data, and optional MQTT remain private.
5. **Preserve raw evidence.** Gate-1 captures and sample packets are retained for mapping and regression tests.

## Repository status

This repository is an implementation scaffold, not a claim that the DS923+ USB path has already passed. The first deployment milestone is `GATE-1-RF` in `docs/runbooks/gate-1-rf.md`.

## Quick start

```bash
cp .env.example .env
./scripts/bootstrap.sh
./scripts/synology/usb-device-info.sh
./scripts/gate1-rf-test.sh
```

Do not continue to the WeeWX application stack until the Gate-1 acceptance criteria pass.

## Main directories

```text
config/       Runtime configuration templates
docker/       Lakehouse-owned container extensions
docs/         Architecture, ADRs, deployment notes, and runbooks
patches/      Local patches maintained against upstream projects
runtime/      Persistent runtime data; contents are gitignored
scripts/      Bootstrap, validation, RF testing, backup, health checks
tests/        Fixtures and structural checks
vendor/       Pinned upstream Git submodules
```

## Upstreams

See `UPSTREAMS.lock` and `docs/upstreams/README.md`.

## License

Lakehouse Weather integration code is licensed under GPL-3.0-only to remain compatible with the GPLv3 components intended for modification and redistribution. Third-party components retain their own copyrights and licenses.
