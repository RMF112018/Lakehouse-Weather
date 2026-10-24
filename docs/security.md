# Current dashboard boundary

The ADR-0002 dashboard defaults to loopback synthetic mode with no external request or persistent store. PostgreSQL is explicit nonproduction only, with a dedicated weather runtime role and owner-provisioned schema. Ingest requires a server-only bearer token and a configured sensor identity; demo ingest is disabled. Public ingress must allow only read dashboard routes and exclude machine ingest. Browser authentication/access protection is not yet commissioned. The HTTP server is nonproduction. No existing my-pa browser protection is inherited automatically.

# Historical WeeWX deployment security notes

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
