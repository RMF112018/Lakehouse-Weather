# Security model

## Exposed surface

Only the nginx dashboard endpoint should be remotely reachable.

## Private components

- RTL-SDR USB device
- `rtl_433`
- WeeWX process and database
- optional Mosquitto broker
- persistent runtime volume

## Remote access

Preferred: Tailscale-private dashboard access.

Optional: Cloudflare Tunnel protected by Cloudflare Access. Do not expose a bare tunnel hostname without an authentication policy if the endpoint is intended to remain private.

## Secrets

- `.env` is ignored.
- Cloudflare tunnel tokens/credentials are never committed.
- Future weather-service API keys must use environment variables or mounted secret files.
