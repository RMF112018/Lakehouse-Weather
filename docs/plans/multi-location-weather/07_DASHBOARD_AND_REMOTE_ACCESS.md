# 07 — iPhone-first dashboard, API presentation and remote access
**LHW-ML-20261023 | CP-4 | PROPOSED**. No iPhone demonstration, browser deployment, Tailscale ACL, Cloudflare hostname or DNS configuration is verified. API: [03_TARGET_ARCHITECTURE.md](03_TARGET_ARCHITECTURE.md); source semantics: [05_WEATHER_DATA_MODEL.md](05_WEATHER_DATA_MODEL.md).

## 1. Primary interaction design
A mobile-first read-only weather dashboard optimized for a daily-use iPhone, with desktop/tablet progressive adaptation, one tap switching between several user-registered locations, and no requirement to install a native App Store package. Design target: safe-area support, touch targets >=44pt, responsive one-column mobile / two-column tablet / multi-panel desktop, WCAG AA color contrast, keyboard focus, colorblind-safe quality labels, `prefers-reduced-motion`, chart keyboard/screen-reader text equivalents. Dark and light themes follow OS with optional saved preference, scoped locally to device (not a server secret).

**Main screen hierarchy:**
1. Top bar: "Lakehouse Weather" + location picker + primary Home location setting (operator-approved list only); offline/refresh indication; user-friendly last sync.
2. Hero: current local temperature and humidity from *selected displayed source*, observed time, site identity and class badge **"Local station • Measured"**, **"NWS site • Measured remotely"**, or **"Open-Meteo • Model estimate"**. If no qualifying fresh measured data, show unavailable/stale, not substitution without separate disclosure. Forecast high/low adjacent but labeled **"Forecast"**.
3. Conditions: wind sustained/gust/direction, rain counter-derived recent accumulation with completeness flag, solar/UV and pressure only where independently available; indoor WH32B in clearly separated optional "Indoor" section. Rain "since midnight" boundary uses site's IANA timezone, not NAS time. Atmospheric pressure includes raw/sea-level basis label if source supplies both.
4. Time charts: temperature/humidity; wind and gust; cumulative rain increments; pressure (if verified); UV/light (if available). Select 24h, 7d, 30d, date range. Each graph displays legend, units, source, missing gaps and selected local UTC offset. Full-resolution small-range queries, server aggregated larger-range queries with completeness annotations.
5. Source health: last accepted packet for WH65B and optional WH32B, receiver heartbeat, battery when actually reported, last external success, provider error/next retry, stale flag; never show "good" based only on container liveness.
6. Forecast: NWS or accepted Open-Meteo as separate panel with issue/reference time, validity interval, provider/model attribution and observed-vs-modeled legend; never silently fill a measured chart.
7. Location comparison: up to four locations, same metric, compatible SI-converted units, same UTC time axis with per-location local times optionally shown; no naive averaged wind direction. Source comparison within one location is a distinct mode and shows each source site/observed time.

## 2. Meaningful states and copy contract
| Condition | UI text and behavior |
|---|---|
| WH65B packet accepted within configured interval | "Local station — Measured • as of HH:MM" with actual time/zone |
| WH65B interval > freshness threshold | "Local station stale — last measurement at HH:MM"; retain last known reading with visibly stale state |
| WH32B not discovered or no valid pressure field | "Pressure unavailable — no verified sensor" (not 0 hPa and not implied from outdoor array) |
| NWS station assigned to destination | "NWS measured at [station display name]" plus site location/distance if verified; do not imply exact location |
| Open-Meteo current/model value | "Model estimate — Open-Meteo" and attribution; cannot display within measured history endpoint |
| Incomplete rainfall after reset/gap | "Rain total incomplete for this period" and data-quality tooltip; draw known increments with gap |
| Provider 429/timeout | "Provider temporarily unavailable — last updated [time]" and no bogus new timestamp |
| Client offline | "Offline: saved view from [timestamp]"; no "Live" badge, stale data and limited navigation clearly shown |
| Conflict between two measured sources | Display source A and B separately and "Sources differ"; no hidden mean |
| Unknown/unauthorized location | Same privacy-preserving 404 response; no exposed location discovery |
Use plain source names; machine-only sensor IDs should not appear in default UI. Every metric card's accessibility label includes "measured" or "forecast/model", quality, timestamp and source.

## 3. UX flows and information architecture
~~~text
/
  [default location] [location switcher] [refresh status]
  hero + forecast separate
  condition metric cards
  history charts [window] [source filters]
  sensor & provider status
  compare locations [up to 4]
  source details [read-only privacy-filtered]
  settings [local UI preferences only; no DB credentials]
~~~
**Location selection:** only stable configured location IDs; no browser-origin free-text geocoding for MVP. Store default in device-local preferences; server source data remains canonical. Switching updates URLs (e.g., `/locations/{opaque_id}`) for deep links only on tailnet/private surfaces, hides approximate coordinates unless authorized. In no-source states show setup pending and guidance, not a synthetic "weather" value.

**History and timezone:** UTC is chart data authority. Tick labels derive location IANA zone; DST fall-back distinguishes repeated local times by offsets; spring-forward leaves valid discontinuity; daily rain windows use site midnight-to-midnight with timezone transitions. No pixel smoothing over missing-data windows; gaps and error bands explicit. Comparison uses aligned UTC grid; local chart labels can differ by location. API query max 31d for raw readings, 366d aggregates and cursor paging.

**Offline mode:** service worker precaches versioned immutable static assets; may cache bounded last *authorized* read-only response for selected location with short expiry in private device storage, but never persist credential material or raw GPS/address metadata beyond what approved. All cached views carry `cached_at` and explicit stale state. On logout/revocation where application auth later exists, clear caches and storage. Disable client storage of personal location details by default until reviewed privacy policy; public multi-user deployment requires new authorization.

## 4. Design implementation technology selection
Chosen **proposed** stack: React + TypeScript, Vite static build, CSS design tokens, compact accessible charting dependency only after license/accessibility review, Vitest/Testing Library and Playwright for mobile viewport interactions. Rationale: responsive multi-location components with a single app image and a backend read API; SSR/Next.js not required for a private dashboard, and WeeWX New Belchertown skins do not provide a confirmed data/provenance model for this target. No existing real Lakehouse frontend to preserve. Integrating my-pa frontend would couple release gates and user authority unexpectedly; avoid.

Example component boundaries in proposed repo: `LocationSelect`, `CurrentConditions`, `MetricCard`, `TrendChart`, `ForecastPanel`, `SourceBadge`, `SourceHealth`, `ComparePanel`, `OfflineNotice`, `FreshnessClock`. Typed decoders reject undocumented API shape; do not embed provider-derived claims inside UI strings. All browser JavaScript requests limited to relative `/api/v1` through same authenticated ingress.

## 5. Private remote architecture and checks
1. **MVP:** use Tailscale tailnet HTTPS Serve (or verified equivalent private reverse proxy). Test from iPhone on cellular, not merely LAN or a NAS browser. NAS retains DB on internal network only. Require verified tailnet ACL restricting user's enrolled devices; do not infer existing hostname or certificate validity. Use TLS with real certificate chain/SNI acceptance; browser must not see a mixed-content warning.
2. Proxy route allowlist: `GET /,` static assets and `GET /api/v1/*` (only declared read endpoints); admin `/internal/*`, SQL, metrics/prometheus internal, `/docs`, and any private files denied. No query-string user database credentials; no direct reverse proxy to my-pa gateway. Correct cache headers and CSP, HSTS on trusted HTTPS origin, nosniff, referrer policy and clickjacking protection. If website and API share origin, CORS disabled; enforce origin checks before future mutations.
3. **Optional Cloudflare Tunnel + Access** for Lakehouse only if operator chooses; distinct tunnel ID, origin, credential path, auth policy and host from my-pa's existing public browser/MCP tunnels. No unauthenticated public tunnel, port forwarding or silent reuse of my-pa's production auth. Verify Access authorization, logout, session expiry, failure-closed routing, Cloudflare no automatic publication of private location.
4. Gate security tests: unauthenticated WAN GET fails; ingress cannot access PostgreSQL/receiver/private RF endpoint/admin routes; CORS/origin spoof fails; App's restricted DB role cannot read `knowledge`/`observability` or DDL. Tailscale transport-only identity does not mean API is safe if tailnet broader than intended.
5. DNS/hostname/domain/tunnel remains **UNRESOLVED**. Do not place assumed or real private addresses in public plan. Activate only with explicit production approval.

## 6. iPhone acceptance and failure test set
- iPhone Safari on supported iOS: Home Screen install and responsive portrait/landscape; content not obscured by notch/home bar; one-handed location switching; source badge always visible; no scroll-lock/trapped focus.
- Cross-browser desktop/mobile widths 320, 375, 390, 430, 768, 1280 CSS px; no horizontal overflow; touch >=44 CSS px where practicable, keyboard and VoiceOver labels.
- At least two synthetic locations in different timezones; compare 2–4 with unit normalization and offset-correct timestamps.
- Distinguish actual WH65B measurement, NWS remote station reading, Open-Meteo modeled value and forecast run; pressure missing null; rainfall partial.
- Client disconnected while API has older data; visibly cached/expired; refresh-on-reconnect; session/auth blocked path not bypassed by service worker.
- 4xx/5xx cases show meaningful non-secret state, no blank-screen exception; unknown source and stale data do not show zero.
- Lighthouse/performance target proposed (not benchmarked): 95th-percentile current-conditions API <=500 ms on NAS with synthetic moderate load, initial 4G transfer <1 MB gzip JS/CSS, mobile route interactions <200 ms absent network. Measure before final acceptance and adjust based on actual NAS hardware.
- Web Push weather alerts are **DEFERRED**. Apple permits standards-based Web Push for iOS Home Screen web apps starting iOS/iPadOS 16.4, but this requires user gesture/permission, service worker, VAPID, delivery infrastructure and policy; do not implement under passive dashboard scope. https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers

## 7. Future features and authorization
Radar imagery (NWS API status endpoints **do not** supply actual radar tiles), warnings, sunrise/sunset, low-battery notifications, individual thresholds, Web Push and location geofencing require independent data-license/privacy/testing gates. A weather model is not a station; the UI contract must remain clear after enhancements. Work and acceptance mapping [09](09_VALIDATION_AND_ACCEPTANCE.md), [10](10_IMPLEMENTATION_WORK_PACKAGES.md).
