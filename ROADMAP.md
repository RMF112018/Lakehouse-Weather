# Lakehouse Weather Roadmap

## Gate 0 — Repository scaffold

- [x] Define architecture and security boundary.
- [x] Pin upstream projects.
- [x] Add Synology-oriented deployment scaffolding.
- [x] Add RF acceptance-test workflow.

## Gate 1 — RF / USB acceptance

**Objective:** prove the DS923+ can expose the RTL-SDR and decode the Lakehouse WH65B sensor reliably.

Acceptance:

- RTL-SDR enumerates on the Synology host.
- Container can open the SDR without intermittent USB claim errors.
- `rtl_433` decodes at least three valid `Fineoffset-WH65B` packets.
- Sensor ID is stable during the observation window.
- Capture is retained as evidence.

No weather-app implementation proceeds until this gate passes.

## Gate 2 — Sensor mapping

- Identify WH65B sensor ID.
- Determine whether the existing WH32B indoor/pressure sensor is also receivable.
- Map verified fields into WeeWX.
- Validate rain counter/delta handling.
- Preserve representative raw packets as test fixtures.

## Gate 3 — WeeWX baseline

- Install `weewx-sdr`.
- Create station configuration.
- Confirm SQLite archive writes.
- Confirm daily aggregates and derived values.
- Establish backup/restore test.

## Gate 4 — Dashboard

- Install New Belchertown.
- Apply Lakehouse naming/branding.
- Configure iPhone-responsive presentation.
- Validate live/stale state behavior.
- Add forecast/radar only after measured-data presentation is sound.

## Gate 5 — Remote access

- Private Tailscale access.
- Optional Cloudflare Tunnel + Access.
- No direct router port forwarding.
- Verify dashboard only is externally reachable.

## Gate 6 — Production hardening

- Health checks and restart policy.
- Retention/backup automation.
- Upgrade procedure with pinned upstream review.
- Low-battery/stale-station alerting.
- Disaster-recovery runbook.
