# Reviewed host operations for the first NAS installation

These Python 3.8-compatible operator helpers are separate from the application
image. An operations-only commit does not require recreating the authenticated
application container. Keep the image revision/tree and host helper commit/hash
as separate deployment receipt fields.

`activate_weather.py` prepares and validates routing candidates, then separately
applies them against exact NAS container/file identities. It preserves individual
bind-mount inodes and existing routes, keeps private originals/candidates only on
the NAS, and rolls back on activation failure. Never print or export its protected
staging directory. User authorization to access the protected connector config
is required. Only the public proxy reload and single frontend connector restart
are in scope.

`forecast_egress.py` is specific to the admitted installation. It authenticates
the forecast container/image/provenance, exclusive egress network membership,
source address, WAN interface and the existing firewall policy hash. It adds only
three exact weather-source /32 rules: TCP 443, UDP 53 and TCP 53 toward the WAN.
These RETURN to Docker forwarding/isolation; they do not bypass that isolation.
The provider URL remains fixed in the application. This is a port restriction,
not a provider IP allowlist. All unrelated rules remain intact.

Install the reviewed helper as root-owned mode 0500 at
`/volume1/weather-dashboard/operations/forecast_egress.py` inside root-owned mode
0700 `operations`. `--apply` reconciles the three rules. `--apply --remove` removes
all exact owned tuples even after container or firewall drift. Admission drift
also revokes those tuples and records failure. The NAS lacks the optional iptables comment match. Ownership therefore uses
the complete bridge/source/WAN/protocol/port tuple; all other rules remain
subject to the frozen baseline hash and are never adopted or removed. Operator changes require a new reviewed binding.

`--apply --install-cron` creates only its unique root-owned mode 0600
`/etc/cron.d/weather-forecast-egress`; it never rewrites existing crontabs. The
entry invokes isolated Python every five minutes with bounded, suppressed output.
`--apply --install-cron --remove` removes only the byte-exact owned entry and is
available even after runtime drift. Remove the cron entry and rules before
retiring or replacing the installation. The root-only `egress-status.json` is a
metadata heartbeat and must be observed changing under the actual NAS scheduler
before automatic recovery is claimed. DSM firewall edits that change the policy
hash deliberately require operator review, rather than broad automatic repair.

The forecast child has a 120-second timeout and hourly cadence. Failed refreshes
preserve cached data and explicit stale/unavailable state; a running process is
not proof of a successful provider refresh. Private dashboard health checks do
not expose protected weather data or authentication material.
