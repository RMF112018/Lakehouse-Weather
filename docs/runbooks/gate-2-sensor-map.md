# Runbook: GATE-2-MAP

## Objective

Freeze the exact WH65B sensor ID, optional WH32B sensor ID, parser class names, and WeeWX field mappings from real captures.

## Rules

- Do not guess sensor IDs.
- Do not assume an example parser mapping is correct for the installed `rtl_433`/`weewx-sdr` combination.
- Preserve the raw Gate-1 JSON evidence.
- Prefer station-specific ID filtering in WeeWX configuration rather than globally suppressing all other RF devices during discovery.

## Outputs

- `runtime/weewx/weewx.conf` with authoritative `[SDR]` mappings.
- Sanitized fixture in `tests/fixtures/wh65b.detected.json`.
- Gate decision recorded in `docs/status.md`.
