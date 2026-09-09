# ADR-0001: Use WeeWX ecosystem rather than a custom weather backend

- Status: Accepted
- Date: 2026-09-09

## Context

The failed WS-2000 console removes local display and network upload but does not prevent the WH65B-class outdoor sensor from transmitting. A replacement solution needs RF capture, weather-domain calculations, historical storage, responsive presentation, and remote access.

## Decision

Use WeeWX 5 as the weather engine, `weewx-sdr` as the SDR driver, `rtl_433` as the RF decoder, and New Belchertown as the initial dashboard skin.

## Consequences

### Positive
- Reduces custom code surface.
- Reuses mature weather calculations and historical reporting.
- Keeps RF decoding in the established `rtl_433` project.
- Supports a staged deployment where USB/RF is proven before UI work.

### Negative
- GPLv3 compatibility must be respected for modified upstream components.
- New Belchertown customization follows WeeWX skin conventions rather than a clean-sheet React design.
- Synology USB passthrough remains an environment-specific Gate-1 risk.
