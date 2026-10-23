# 05 — Multi-location, source-aware weather data model
**Package LHW-ML-20261023 | CP-3 | STATUS: PROPOSED | Not production DDL.**
Design goal: multiple independently configured geographic locations; **only the local WS-2000 installation communicates with the NAS SDR**; external locations use authorized network providers. Must preserve sensor and upstream origins across hardware changes, outages, corrections and conflicting sources.

## 1. Identity and cardinalities
- **Location** is a named geographic destination/site with time zone, optional coordinates/elevation and privacy class; never a sensor ID or weather API key. Stable UUID across relabeling. Coordinates required when calling lat/lon provider; otherwise mark location unresolved until supplied by operator.
- **StationInstallation** groups local hardware (WH65B outdoor plus optional WH32B indoor/pressure) and survives sensor replacement or movement. Not itself a geographic coordinate.
- **Source** is a stable logical origin (`ambient_local_station`, `nws_observation_station:{site-id}`, `nws_grid_forecast:{grid-id}`, `open_meteo_model:{model/config}`). A source may serve multiple locations; a location may select several sources. An ambient installation typically maps to exactly one geographic site at any instant.
- **Device** is a *physical sensor identity epoch* within a station. WH65B and WH32B have different devices, models, RF IDs, optional low-battery and capabilities. A replaced sensor or previously reidentified device gets a **new epoch/UUID** until physically attested otherwise; historical old device stays unchanged. RF ID by itself is **not globally unique**.
- **SourceAssignment** links a source and a location with `effective_from <= observed_at < effective_to` (or open interval), preserves provider observation-site geometry separately from selected location geometry and preference rank. Retire/append epochs, no silent change to history; reject conflicting active local installation assignments and unauthorized many-to-many duplicates. Source preferred rank is a **view selection policy**, never a fact overwriting records.
- **RawEvent** is an origin-specific input envelope, provider response or receiver packet persisted with event digest, parser/provider version, source and optional device. It can back multiple normalized metrics and/or multiple location assignments.
- **Observation** is only a measured environmental condition: one metric, one canonical numeric value/unit, UTC `observed_at`, `observed_at_basis` (`sensor_clock/provider_timestamp/receiver_clock`), `ingested_at`, source, assignment, optional device, raw event, validation outcome, normalization version. No forecast is an observation.
- **ModelRun/ModelValue** stores issued forecasts, nowcasts and modeled historic/current analysis separately. `product_kind` and model/provider/run metadata mandatory. Each value has forecast/analysis validity interval, issue time via model run and attribution. Must not be renamed measured at presentation.
- **PollState** tracks per-source poll/cursor, errors, backoff and freshness. Operational health and stale state are distinct from meteorological quality.
- **Aggregate (conditional)** is explicit derived metric with window boundaries, completeness, source selection policy version, computation version and source-window evidence, not an alternate raw authority.

## 2. Canonical metric registry and units
MVP closed registry (expand only under reviewed versioned mapping):
| code | canonical unit | eligible data sources | policy |
|---|---|---|---|
| `air_temperature` | `degC` | WH65B outdoor; WH32B indoor distinguished as `indoor_air_temperature`; provider measured | no indoor/outdoor merging |
| `relative_humidity` | `percent` | WH65B outdoor; distinct `indoor_relative_humidity` | validate 0–100 |
| `wind_speed` / `wind_gust` | `m/s` | WH65B or qualified provider | gust semantics source-dependent, preserve interval definition |
| `wind_direction` | `degree` | WH65B or provider | normalize [0,360), circular aggregation; calm => null if direction undefined |
| `rain_counter` | `mm` | WH65B cumulative counter | never display as rain rate or local-day rainfall total |
| `rain_increment` / `rain_rate` | `mm` / `mm/h` | **derived** from counter | reset/rollover/gaps invalidate deltas |
| `barometric_pressure` | `hPa` | independently decoded WH32B/qualified provider | **not inferred from WH65B** |
| `uv_index` | `index` | WH65B when emitted | not zero when unsupported |
| `illuminance` / `solar_irradiance` | `lux` / `W/m2` | WH65B when emitted | cannot arbitrarily convert lux to W/m² |
Additional models (dew point, feels-like, pressure trend, daily rain, highs/lows, sunrise) are derived views with recorded algorithm/version; do not claim independently sensed. Unit conversion occurs once on ingest with versioned rule. Storage numeric precision: preserve decoder supplied significant digits; no fabricated significant figures.

## 3. Ingestion identity and idempotency
**RF:** `rtl_433` output lacks trustworthy sensor clock or globally unique sequence number. Capture an immutable `receiver_event_id` (UUID) **before** forward/retry; attach monotonically tracked receiver boot ID, receive UTC, decoder code/version and RF ID; persist envelope for bounded replay. `UNIQUE(source_id,receiver_event_id)` assures idempotent retries. Identical payload bytes in different genuine 16s broadcasts are distinct observations. Optional near-duplicate suppression must be evidence-tested and never use `hash(payload)` alone. Sensor clock cannot be invented: `observed_at=receiver UTC` with `observed_at_basis=receiver_clock`.
**External observation API:** use stable provider observation ID/site + measured timestamp + metric where provider supplies it. Store `provider_event_key` and payload hash; repeated identical requests are idempotent. **Provider correction** with same key but changed value creates a new revision/event and appended `supersedes_observation_id` link; never delete the earlier reading. If provider does not guarantee stable IDs, define tested derived key with its limitation recorded.
**Forecast/model:** idempotency key `(provider,model,run_timestamp/issue_timestamp,assignment,valid_interval,metric,revision)`; new forecast issue or correction is a new run/revision, not an overwrite of measured observations. If provider fails, do not synthesize a new issue time.
**Replay:** each event has parse version, source contract version, validation results; replay same version produces same normalized values. A new normalizer version may produce linked corrections, not change existing row bytes. Record permanent rejection/quarantine reason for unregistered IDs and invalid measurements without inventing a location.

## 4. Temporal authority and source movement
All instants stored as `timestamptz` in UTC. User location has **IANA zone** to derive local display date and calendar-bound buckets, including DST 23/25-hour days. For WH65B, receive timestamp marks approximate packet measurement time and separate ingestion timestamp marks DB commit; if receiver clock skew exceeds proposed 30s, reject or quarantine. Provider timestamps with timezone offsets are parsed strictly, never attached to operator local timezone by default. NWS station issue time, receive time and forecast model issue/validity time are different concepts.

Assignment uses half-open effective ranges to preserve a device/station relocation. Do not rewrite past observations on reassignment. If a source moves to a new location, append a new assignment and retire old one. Changing a user-friendly location name keeps `location_id` stable. When station RF ID changes, stop matching old ID and open a new device epoch after physical evidence; station `source_id` remains stable. Conflicting RF broadcasts from unknown IDs are quarantined, not joined by guessed identity.

## 5. Rainfall algorithm (D-007)
Raw `rain_counter` is a cumulative gauge amount; meaning/reset range must be established on physical decoder test before converting into true accumulation.
1. Sort accepted consecutive samples by `observed_at,event_id` *within same physical rain sensor identity epoch*.
2. A prior valid value is required. First sample after startup/replacement: `rain_increment=NULL`, continuity `initial`; cannot backfill unknown history.
3. If `current>=previous` and elapsed/physically plausible, `delta=current-previous`; store zero if exactly equal, and a derived interval with both supporting observation IDs.
4. If `current<previous`, set `rain_increment=NULL` and continuity `counter_reset_or_rollover_unknown`. **Do not add an assumed modulus** until device-specific modulus is verified; if verified, version a precise rollover rule.
5. For missing packets/long gaps, conflicting RF IDs, parser error, duplicate correction, implausible jump or clock skew, mark interval `partial/unknown`; do not pretend a zero-rain interval.
6. For a local calendar day, bucket increments by event/interval and IANA local-day convention. An interval crossing local midnight without subinterval evidence must be flagged `boundary_uncertain` rather than perfectly apportioned.
7. Rain rate `mm/h` requires a defined averaging window with elapsed seconds and enough valid samples. Never equate accumulated rainfall with rain rate. Daily aggregate includes `completeness_ratio`/quality state; UI flags partial days and reset.
8. Station/device changes create a continuity break unless an independently verified counter transfer is possible; resetting on hardware replacement does not erase historical records.

Wind/gust: gust maxima are interval-specific, not comparable across feeds without interval metadata; wind direction circular mean weighted by speed when meaningful; reject north/east arithmetic wrap-around errors. Pressure unit and station/sea-level definition must be preserved; do not silently compare adjusted sea-level pressure to raw station pressure.

## 6. Preferred-source / conflicts and freshness
Each location displays an explicit **source badge on every metric or grouped panel**. Metric-specific priorities select among sources, not one global source. Selection conditions: measurement class, explicitly assigned site, quality accepted, freshness within per-source TTL, metric capability, operator preference, then deterministic tie-break by `source_id`. Do not automatically promote NWS observation to "local station", model estimate to observation, or stale value to current. Conflicting valid sources remain separately queryable with their own timestamp/site; display "sources disagree" if outside metric-specific tolerance (tolerance itself proposal), not an averaged fabricated observation.
Example **proposed** staleness warnings: WH65B no accepted packet for >2min; NWS observations >30min or provider-declared update cadence; Open-Meteo forecast beyond last declared model validity; final thresholds depend on verified cadence. Distinguish provider outage, unknown source, rejected metrics, missing sensor and stale accepted last reading. Client offline cache always stamped "cached as of" rather than live.

## 7. Five mandatory scenarios — synthetic proofs, not live data
| Scenario ID | Synthetic fixture and invariant |
|---|---|
| SC-01 Local installation | Location `loc_lake_test`, station `st_test`, source `ambient_local_station`, devices `wh65b_test_1` and optional `wh32b_test_1`. WH65B temp/humidity/wind/rain; WH32B indoor/pressure. No outdoor pressure without evidenced compatible device. Both remain within one station but have unique device provenance. |
| SC-02 Second location | `loc_other_test` with different IANA zone and location ID. NWS source-site observation and Open-Meteo model forecast share destination but differ origin type. Neither remote location is read by local SDR. |
| SC-03 Competing sources | `loc_lake_test` gets WH65B and NWS observation of air temp at different values/times. Both stored; preference chooses WH65B when fresh; comparisons reveal both and actual provider site. |
| SC-04 Replacement | Retire RF `id_test_1` device at T; append `id_test_2` epoch at T+; same station logical source and location assignment preserved; old historic queries point to prior device; no retroactive reassignment. |
| SC-05 Provider outage | NWS returns 429/503 for synthetic periods; last stored observation unmodified, UI stale, poll backoff respects Retry-After, recovery replays duplicate external event keys with no duplicated accepted measurements. |

Further negative fixtures: no coordinates, invalid zones, DST fall-back repeated hour/spring-forward missing hour; indoor pressure absent; device unknown/duplicate/overlapping assignments; RF same-payload consecutive packets; cumulative rain reset at 23:59 local; pressure definition mismatch; zero vs missing; forecast correction; provider geographic mismatch; out-of-order event; clock jumps; net+DB outage; malformed oversized JSON; UI offline cache.

## 8. Data protection and retention
No user addresses, precise coordinates, RF recordings, API keys or private home-site information in public repository fixtures/logs. Use synthetic UUIDs and neutral labels. Real source coordinates go only to approved weather tables; no public telemetry. Raw external response may carry provider metadata and should be sanitized/size-bounded. Implement row-level privileges; weather reader may see weather data, never `knowledge` or other my-pa personal data. Raw-event retention is proposed 30–90 days, fine-grained weather 12–24 months, derived aggregates longer after budget; **no destructive cleanup until explicit retention approval** and tested weather-only restore. Every exported API response must have source attribution plus observed_at/ingested_at for measured data and issued_at/valid_at for forecast.

## 9. Formal executable invariants
I-01: no observation without valid event, source, assignment, matching time range and finite canonical value.
I-02: every physical sensor sample retains device ID and raw event lineage.
I-03: provider measured, model analysis and forecast are visibly distinct all the way to UI.
I-04: replay of identical receiver_event_id or provider_event_key/revision is byte-identical and row-count-invariant.
I-05: corrected values append supersession lineage; never mutate historical evidence.
I-06: no cross-location reassignment of past observations after station relocation.
I-07: a blank/missing/invalid sensor metric is null/not served, never zero or invented estimate.
I-08: loss/outage/restart never silently advances collection watermark past uncommitted records.
I-09: rain reset/unknown boundary marks incomplete, never negative or fabricated gain.
I-10: database schema owner and app role have disjoint migration/data privileges, and weather app has zero access to my-pa private schemas.
I-11: model values cannot appear in observation-only API endpoints or measured dashboard components.
I-12: raw and metric records are non-destructively versioned and the source selection choice is reconstructible.
Map I-01..I-12 to AT-007..AT-019, AT-023 in [09 acceptance](09_VALIDATION_AND_ACCEPTANCE.md).
