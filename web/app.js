'use strict';
(() => {
  const signout=document.getElementById('signout');
  if(signout) signout.addEventListener('click',async()=>{signout.disabled=true;try{const status=await fetch('./api/auth/status',{cache:'no-store'});const data=await status.json();if(!data.authenticated){location.replace('./login');return;}const out=await fetch('./api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json','X-Weather-CSRF':data.csrf},body:'{}'});if(out.ok)location.replace('./login');else throw Error();}catch{signout.disabled=false;signout.textContent='Try sign out again';}});
  const $ = id => document.getElementById(id);
  const state = { data: null, location: null, station: null, unit: 'F', range: '24h', metric: 'temperature_c', history: null, request: 0, historyError: '' };
  try { state.unit = localStorage.getItem('weatherhouse-unit') === 'C' ? 'C' : 'F'; } catch (_) { /* Private browsing can disable storage. */ }
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const number = (value, digits = 0) => finite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
  const temp = value => finite(value) ? number(state.unit === 'F' ? value * 9 / 5 + 32 : value) : '—';
  const speed = value => finite(value) ? number(state.unit === 'F' ? value * 2.23694 : value * 3.6, 1) : '—';
  const speedUnit = () => state.unit === 'F' ? 'mph' : 'km/h';
  const rain = value => finite(value) ? number(state.unit === 'F' ? value / 25.4 : value, state.unit === 'F' ? 2 : 1) : '—';
  const rainUnit = () => state.unit === 'F' ? 'in' : 'mm';
  const node = (tag, className, text) => { const el = document.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = text; return el; };
  const set = (id, value) => { $(id).textContent = value; };
  function formatDate(value, options, timezone = state.location?.timezone) {
    if (!value || !Number.isFinite(new Date(value).getTime())) return 'Unknown time';
    try { return new Intl.DateTimeFormat(undefined, { ...options, timeZone: timezone || 'UTC' }).format(new Date(value)); }
    catch (_) { return new Intl.DateTimeFormat(undefined, { ...options, timeZone: 'UTC' }).format(new Date(value)); }
  }
  function localCalendarDate(timezone) {
    let parts;
    try { parts = new Intl.DateTimeFormat('en-US', { timeZone: timezone || 'UTC', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date()); }
    catch (_) { parts = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date()); }
    const part = type => parts.find(item => item.type === type).value;
    return `${part('year')}-${part('month')}-${part('day')}`;
  }
  function age(value) {
    const minutes = Math.floor((Date.now() - new Date(value).getTime()) / 60000);
    if (!Number.isFinite(minutes)) return 'Time unavailable';
    if (minutes < 1) return 'Just updated';
    return minutes < 60 ? `${minutes} min ago` : `${Math.floor(minutes / 60)}h ago`;
  }
  function unitFor(sensor) {
    const key = sensor.key || '';
    if (key.endsWith('_c')) return `°${state.unit}`;
    if (key.endsWith('_ms')) return speedUnit();
    if (key.endsWith('_mm')) return rainUnit();
    if (key.endsWith('_hpa')) return state.unit === 'F' ? 'inHg' : 'hPa';
    return sensor.unit || '';
  }
  function converted(value, sensor) {
    const key = sensor.key || '';
    if (!finite(value)) return value;
    if (key.endsWith('_c')) return state.unit === 'F' ? value * 9 / 5 + 32 : value;
    if (key.endsWith('_ms')) return value * (state.unit === 'F' ? 2.23694 : 3.6);
    if (key.endsWith('_mm')) return state.unit === 'F' ? value / 25.4 : value;
    if (key.endsWith('_hpa')) return state.unit === 'F' ? value / 33.8639 : value;
    return value;
  }
  function sensorValue(value, sensor, includeUnit = true) {
    if (value === null || value === undefined) return '—';
    if (typeof value === 'boolean') return value ? (sensor.true_label || 'Yes') : (sensor.false_label || 'No');
    if (!finite(value)) return String(value);
    const key = sensor.key || ''; const digits = key.endsWith('_mm') && state.unit === 'F' ? sensor.kind === 'accumulation' ? 3 : 2 : key.endsWith('_hpa') && state.unit === 'F' ? 2 : 1;
    return `${number(converted(value, sensor), digits)}${includeUnit && unitFor(sensor) ? ` ${unitFor(sensor)}` : ''}`;
  }
  function description(sensor) { return sensor.description || sensor.aggregation || 'Reported by your station'; }
  const icons = {
    sun: '<circle cx="24" cy="24" r="9"/><path d="M24 3v5m0 32v5M3 24h5m32 0h5M9 9l4 4m22 22 4 4M9 39l4-4m22-22 4-4"/>',
    cloud: '<path d="M12 35a8 8 0 0 1-1-16 12 12 0 0 1 23-2 9 9 0 0 1 1 18Z"/>',
    partly: '<path d="M20 10V5M9 21H4m5-12 4 4m18-4-4 4M13 27a9 9 0 1 1 16-8"/><path d="M18 38a7 7 0 0 1 0-14 10 10 0 0 1 19-1 8 8 0 0 1-1 15Z"/>',
    rain: '<path d="M12 29a7 7 0 0 1-1-14 11 11 0 0 1 21-2 8 8 0 0 1 3 16ZM15 35l-2 5m11-5-2 5m11-5-2 5"/>',
    snow: '<path d="M12 28a7 7 0 0 1-1-14 11 11 0 0 1 21-2 8 8 0 0 1 3 16M14 36v6m-3-3h6m14-3v6m-3-3h6m-9-9v6m-3-3h6"/>',
    storm: '<path d="M12 29a7 7 0 0 1-1-14 11 11 0 0 1 21-2 8 8 0 0 1 3 16M25 26l-7 10h8l-5 9"/>',
    fog: '<path d="M12 27a7 7 0 0 1-1-14 11 11 0 0 1 21-2 8 8 0 0 1 3 16M8 34h32M12 40h24"/>',
    drop: '<path d="M24 5S10 22 10 30a14 14 0 0 0 28 0C38 22 24 5 24 5ZM18 30a6 6 0 0 0 6 6"/>',
    wind: '<path d="M5 18h26a6 6 0 1 0-6-6M5 25h32a5 5 0 1 1-5 5M5 32h13a5 5 0 1 1-5 5"/>',
    gauge: '<path d="M9 37a19 19 0 1 1 30 0M24 9v4M11 17l3 3m23-3-3 3M7 29h4m26 0h4M24 29l9-9"/><circle cx="24" cy="29" r="3"/>'
  };
  function icon(type) { const wrap = node('span'); wrap.innerHTML = `<svg viewBox="0 0 48 48" aria-hidden="true">${icons[type] || icons.cloud}</svg>`; return wrap.firstChild; }
  function weather(code) {
    if (!finite(code)) return { icon: 'cloud', label: 'Conditions at your station' };
    if (code === 0) return { icon: 'sun', label: 'Clear skies' };
    if (code < 3) return { icon: 'partly', label: 'Partly cloudy' };
    if (code === 3) return { icon: 'cloud', label: 'Overcast' };
    if (code < 50) return { icon: 'fog', label: 'Foggy' };
    if (code >= 95) return { icon: 'storm', label: 'Thunderstorms' };
    if (code >= 71 && code < 80 || code >= 85 && code < 90) return { icon: 'snow', label: 'Snow' };
    return { icon: 'rain', label: 'Rain' };
  }
  async function api(path) {
    const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 15000);
    try { const response = await fetch(`./api/${path}`, { signal: controller.signal, headers: { Accept: 'application/json' }, cache: 'no-store' }); if(response.status===401){location.replace('./login');throw new Error('Please sign in again.');} if (!response.ok) { let detail; try { const body = await response.json(); detail = typeof body.error === 'string' ? body.error.slice(0, 300) : null; } catch (_) {} if (detail === 'Local time is ambiguous or nonexistent; specify explicit UTC bounds') detail = 'This local time is ambiguous or does not exist because of daylight saving. Choose another local time.'; throw new Error(detail || `Weather service returned ${response.status}.`); } return await response.json(); }
    finally { clearTimeout(timeout); }
  }
  function installations(location) {
    const groups = location.physical_stations || [];
    const grouped = new Set(groups.flatMap(group => group.sources.map(source => source.id)));
    return [...groups.map(group => ({ ...group, physical: true, stale: group.status !== 'fresh', observation: { ...Object.fromEntries(Object.entries(group.metrics).map(([key, field]) => [key, field.value])), unavailable_reasons: Object.fromEntries(Object.entries(group.metrics).filter(([,field]) => field.unavailable_reason).map(([key,field]) => [key,field.unavailable_reason])) } })), ...(location.stations || []).filter(source => !grouped.has(source.id))];
  }
  function unavailableText(code) {
    return {transmitter_invalid_sentinel:'Transmitter reports this field unavailable',never_seen_source:'No readings received from this transmitter',not_observed_in_window:'No recent reading for this field',not_observed:'Field not reported by this transmitter',out_of_projection_window:'Reading is outside the current window',clock_skew:'Receiver sample time is ahead'}[code] || (typeof code === 'string' && !code.includes('_') ? code : 'Field unavailable');
  }
  function fieldDetail(key) {
    const field = state.station?.metrics?.[key];
    if (!field) return '';
    const freshness = field.value === null ? 'Missing' : (Date.now() - new Date(field.observed_at_utc).getTime()) / 1000 > field.freshness_seconds ? 'Stale' : 'Fresh';
    return `${freshness} · ${field.source_model} · ${field.observed_at_utc || 'No sample time'}${field.observed_at_utc ? ` · ${age(field.observed_at_utc)}` : ''}${field.unavailable_reason ? ` · ${unavailableText(field.unavailable_reason)}` : ''}`;
  }
  function message(text) { $('error').hidden = !text; set('error', text); }
  async function refresh() {
    $('refresh').disabled = true; $('main').setAttribute('aria-busy', 'true'); message('');
    try {
      const data = await api('dashboard');
      if (!Array.isArray(data.locations)) throw new Error('The weather service returned an unexpected response.');
      state.data = data;
      if(signout)signout.hidden=data.mode==='demo';
      const previousStation = state.station?.id;
      state.location = data.locations.find(l => l.id === state.location?.id) || data.locations[0] || null;
      state.station = (state.location ? installations(state.location).find(s => s.id === state.station?.id) : null) || (state.location ? installations(state.location)[0] : null) || null;
      if (state.station?.id !== previousStation) selectStationMetric();
      state.request++; state.history = null;
      $('loading').hidden = true; $('content').hidden = !state.location;
      if (!state.location) message('No locations are configured yet. Add a location and its weather station to get started.');
      $('notice').hidden = data.mode !== 'demo';
      set('notice', 'DEMO MODE · Illustrative weather data. These are sample locations and readings, not live observations from your WS-2000.');
      set('connection-text', data.mode === 'demo' ? 'Exploring sample weather' : 'Connected to your weather service');
      set('footer-status', data.mode === 'demo' ? 'Sample data · Nonproduction preview' : 'Your stations. Your data.');
      if (state.location) { render(); await loadHistory(); }
    } catch (error) { $('loading').hidden = true; message(`${error.name === 'AbortError' ? 'The weather service took too long to respond.' : error.message} Use refresh to try again.${state.data ? ' Previously loaded readings remain visible.' : ''}`); set('connection-text', 'Weather service unavailable'); }
    finally { $('refresh').disabled = false; $('main').setAttribute('aria-busy', 'false'); }
  }
  function renderLocations() {
    $('locations').replaceChildren(); set('place-count', `${state.data.locations.length} ${state.data.locations.length === 1 ? 'location' : 'locations'}`);
    for (const location of state.data.locations) {
      const stations = installations(location); const first = stations[0]; const button = node('button', 'location-card'); button.type = 'button'; button.setAttribute('aria-pressed', String(location.id === state.location.id));
      const text = node('span'); text.append(node('span', 'location-name', location.name), node('span', 'location-sub', `${stations.length} ${stations.length === 1 ? 'station' : 'stations'} · ${first ? first.physical ? `${first.status} source coverage` : first.stale ? 'Stale readings' : 'Reporting' : 'Not connected'}`));
      button.append(text, node('span', 'location-temp', `${temp(first?.observation?.temperature_c)}°`));
      button.addEventListener('click', () => { state.location = location; state.station = stations[0] || null; selectStationMetric(); state.history = null; state.request++; $('chart').classList.remove('loading-state'); render(); loadHistory(); }); $('locations').append(button);
    }
  }
  function render() {
    $('fahrenheit').setAttribute('aria-pressed', String(state.unit === 'F')); $('celsius').setAttribute('aria-pressed', String(state.unit === 'C'));
    renderLocations();
    set('location-title', state.location.name); set('location-region', `${state.location.timezone || 'UTC'} · LOCAL OBSERVATIONS`);
    const select = $('station-select'); select.replaceChildren(); for (const station of installations(state.location)) { const option = node('option', '', station.name); option.value = station.id; option.selected = station.id === state.station?.id; select.append(option); } select.disabled = !state.station;
    renderRFStatus(); renderTransmitters(); renderStationComparison(); renderConditions(); renderSensors(); renderMetricOptions(); renderChart(); renderForecast();
  }
  function renderRFStatus() {
    const status = state.data.rf_status || {status:'unknown'};
    const root = $('rf-status-details'); root.replaceChildren();
    root.append(node('p','',status.status === 'available' ? 'Collector status available' : status.status === 'stale_status' ? 'Collector status is stale' : 'Collector status unavailable'));
    const labels = {last_receipt_utc:'Last received',last_commit_utc:'Last database commit',accepted:'Accepted',rejected:'Rejected',duplicates:'Duplicate frames',conflicts:'Conflicts',pending_count:'Pending events',pending_bytes:'Pending bytes',oldest_pending_age_seconds:'Oldest pending age (seconds)'};
    for (const [key,label] of Object.entries(labels)) if (status[key] !== undefined) root.append(node('p','',`${label}: ${status[key]}`));
    if (status.error_code && status.error_code !== 'none') root.append(node('p','','Collector requires attention'));
  }
  function renderTransmitters() {
    const disclosure = $('transmitter-diagnostics');
    disclosure.hidden = !state.station?.physical;
    $('transmitter-details').replaceChildren();
    for (const source of state.station?.sources || []) {
      const obs = source.observation || {};
      const item = node('div', 'sensor-reading');
      item.append(node('strong','',source.name),node('p','',`${source.model} · ${source.last_seen || 'No sample'} · ${source.last_seen ? age(source.last_seen) : 'Missing'} · Battery ${obs.battery_ok === true ? 'OK' : obs.battery_ok === false ? 'low' : 'unknown'}`));
      for (const [key,reason] of Object.entries(obs.unavailable_reasons || {})) if (reason === 'transmitter_invalid_sentinel') item.append(node('p','',`${key}: transmitter reports invalid`));
      $('transmitter-details').append(item);
    }
  }
  function chooseStation(station) {
    state.station = station; selectStationMetric(); state.history = null; state.request++;
    $('chart').classList.remove('loading-state');
    render(); loadHistory();
  }
  function renderStationComparison() {
    const stations = installations(state.location); const root = $('station-comparison'); root.replaceChildren(); root.hidden = stations.length < 2;
    for (const station of stations) {
      const button = node('button', 'station-chip'); button.type = 'button'; button.setAttribute('aria-pressed', String(station.id === state.station?.id));
      button.append(node('span', '', station.name), node('strong', '', `${temp(station.observation?.temperature_c)}°`), node('small', '', station.stale ? 'Stale' : 'Reporting'));
      button.addEventListener('click', () => chooseStation(station)); root.append(button);
    }
  }
  function metric(title, value, unit, detail, image) { const card = node('article', 'metric-card'); const top = node('div', 'metric-top'); top.append(node('span', '', title), icon(image)); const reading = node('div', 'metric-value', value); reading.append(node('small', '', unit)); card.append(top, reading, node('div', 'metric-detail', detail)); return card; }
  function renderConditions() {
    const station = state.station; const obs = station?.observation || {}; const forecast = state.location.forecast;
    set('updated', station?.physical ? 'Each field shows its source and sample time' : obs.observed_at ? `Observed ${formatDate(obs.observed_at, { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' })} · ${age(obs.observed_at)}` : 'Waiting for the first observation');
    const sensors = currentSensors(); let heroSensor; const hasTemperature = finite(obs.temperature_c);
    $('temperature').classList.toggle('sensor-hero', !hasTemperature);
    if (hasTemperature) { const temperature = node('span', '', temp(obs.temperature_c)); temperature.append(node('small', '', `°${state.unit}`)); $('temperature').replaceChildren(temperature); }
    else {
      const key = ['detector_state', 'lightning_distance_km', 'lightning_count_raw', 'battery_ok'].find(item => obs[item] !== null && obs[item] !== undefined) || sensors[0]?.key;
      heroSensor = sensors.find(item => item.key === key);
      set('temperature', heroSensor ? sensorValue(obs[key], heroSensor) : 'No readings');
    }
    const currentWeather = weather(null);
    set('condition-label', hasTemperature ? 'Latest temperature' : heroSensor ? heroSensor.label : 'Awaiting station data');
    set('hero-detail', station?.physical ? fieldDetail('temperature_c') || `Installation status: ${station.status}` : sensors.length ? `${hasTemperature ? 'Reported by' : station?.stale ? 'Latest sensor report ·' : 'Live sensor data ·'} ${station?.model || 'your station'}` : 'Local measurements from your weather station');
    $('hero-icon').replaceChildren(icon(hasTemperature ? currentWeather.icon : 'gauge'));
    if (station?.physical) { const values = Object.values(station.metrics); station.stale = values.some(field => field.value === null || !field.observed_at_utc || (Date.now()-new Date(field.observed_at_utc).getTime())/1000 > field.freshness_seconds); }
    set('station-health', !station ? 'No station' : station.physical ? station.stale ? '● Partial or stale source coverage' : '● All measured fields fresh' : station.stale ? '● Stale reading' : '● Station reporting'); $('station-health').classList.toggle('stale', !station || station.stale);
    set('station-model', station ? `${station.model || 'Weather station'} · ${station.name}` : 'No station configured');
    set('battery', station?.physical ? 'Battery status in transmitter diagnostics' : obs.battery_ok === false ? 'Battery low' : obs.battery_ok === true ? 'Battery healthy' : finite(obs.battery_level) ? `Decoder battery level ${number(obs.battery_level, 2)}` : 'Battery status unknown');
    const priorities = ['humidity_pct', 'wind_speed_ms', 'rain_interval_mm', 'rain_total_mm', 'pressure_hpa', 'wind_gust_ms'];
    const featured = sensors.filter(sensor => sensor.key !== 'temperature_c' || sensors.length === 1).sort((a, b) => { const rank = key => priorities.includes(key) ? priorities.indexOf(key) : 99; return rank(a.key) - rank(b.key); }).slice(0, 4);
    $('metrics').replaceChildren(...featured.map(sensor => metric(sensor.label, sensorValue(obs[sensor.key], sensor, false), unitFor(sensor), fieldDetail(sensor.key) || description(sensor), sensor.key.includes('wind') ? 'wind' : sensor.key.includes('rain') ? 'rain' : sensor.key.includes('humidity') ? 'drop' : 'gauge')));
    if (!featured.length) $('metrics').append(node('p', 'empty', 'Sensor readings will appear after your first station transmission.'));
  }
  function catalog() {
    return Object.entries(state.data?.sensor_catalog || {}).map(([key, spec]) => ({ ...spec, key }));
  }
  function currentSensors() {
    const observation = state.station?.observation || {};
    return catalog().filter(sensor => observation[sensor.key] !== null && observation[sensor.key] !== undefined);
  }
  function selectStationMetric() {
    const sensors = currentSensors();
    if (!sensors.some(sensor => sensor.key === state.metric)) state.metric = sensors.find(sensor => sensor.kind !== 'status')?.key || sensors[0]?.key || state.metric;
  }
  function semanticNote(sensor) {
    const notes = { accumulation: 'Known rainfall only: measured increments, with unknown intervals excluded. Resets and gaps can hide rain; this is not a complete period total.', maximum: 'Maximum reported gust within each history bucket.', circular: 'Circular mean direction; north wraps at 360°.', cumulative_counter: 'Cumulative device counter. Not a daily total; resets are possible.', raw_counter: 'Raw device counter, 0–255. Wraps or resets; not an hourly or daily strike count.', status: 'Reported status. History shows last state in each bucket, not a numerical average.' };
    return notes[sensor.kind] || (sensor.key === 'battery_level' ? 'Decoder-reported level, not charge percentage or voltage.' : sensor.key === 'uv_raw' ? 'Raw UV sensor units; not the UV index.' : sensor.key === 'illuminance_lux' ? 'Visible light in lux; not solar irradiance in W/m².' : sensor.key === 'lightning_distance_km' ? 'Last reported strike distance; not a current storm position.' : 'History: mean of available readings within each bucket.');
  }
  function renderSensors() {
    const obs = state.station?.observation || {};
    const sensors = [...currentSensors(), ...catalog().filter(sensor => (obs[sensor.key] === null || obs[sensor.key] === undefined) && obs.unavailable_reasons?.[sensor.key])];
    set('sensor-count', `${sensors.length} ${state.station?.physical ? 'installation fields' : 'reported fields'}`); $('sensor-details').replaceChildren();
    for (const sensor of sensors) {
      const group = node('div', 'sensor-reading'); const value = node('dd', '', sensorValue(obs[sensor.key], sensor, false));
      if (unitFor(sensor)) value.append(node('small', '', unitFor(sensor)));
      group.append(node('dt', '', sensor.label), value, node('p', '', `${fieldDetail(sensor.key) ? `${fieldDetail(sensor.key)}. ` : ''}${obs.unavailable_reasons?.[sensor.key] ? `${unavailableText(obs.unavailable_reasons[sensor.key])}. ` : ''}${semanticNote(sensor)}${sensor.source_field ? ` Source: ${sensor.source_field}.` : ''}`)); $('sensor-details').append(group);
    }
    if (!sensors.length) $('sensor-details').append(node('p', 'empty', 'No sensor measurements have been received yet.'));
    const known = new Set(catalog().map(sensor => sensor.source_field)); const extras = obs.raw_rf && typeof obs.raw_rf === 'object' && !Array.isArray(obs.raw_rf) ? Object.entries(obs.raw_rf) : [];
    const secret = /auth|token|secret|password|passwd|credential|cookie|session|api.?key|private.?key|dsn|connection.?string/i;
    function safeExtra(value, depth = 0) {
      if (depth > 4) return '[omitted]';
      if (typeof value === 'string') return /bearer\s|postgres(?:ql)?:\/\/|-----BEGIN .*PRIVATE KEY/i.test(value) ? '[redacted]' : value.slice(0, 256);
      if (Array.isArray(value)) return value.slice(0, 32).map(item => safeExtra(item, depth + 1));
      if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).filter(([key]) => !secret.test(key)).slice(0, 64).map(([key, item]) => [key, safeExtra(item, depth + 1)]));
      return value;
    }
    const safe = extras.filter(([key]) => !secret.test(key) && !known.has(key));
    $('extras-disclosure').hidden = !safe.length; $('sensor-extras').replaceChildren();
    for (const [key, value] of safe) { const cleaned = safeExtra(value); $('sensor-extras').append(node('dt', '', key), node('dd', '', typeof cleaned === 'object' ? JSON.stringify(cleaned) : String(cleaned))); }
    if (safe.length && obs.provenance) $('sensor-extras').append(node('dt', '', 'Provenance'), node('dd', '', JSON.stringify(safeExtra(obs.provenance))));
  }
  function renderMetricOptions() {
    const available = new Set(currentSensors().map(sensor => sensor.key));
    const sensors = catalog().filter(sensor => !state.station?.physical || state.station.metrics[sensor.key]);
    if (!sensors.some(sensor => sensor.key === state.metric)) state.metric = sensors.find(sensor => sensor.kind !== 'status')?.key || sensors[0]?.key || '';
    $('metric-select').replaceChildren();
    for (const sensor of sensors) { const option = node('option', '', `${sensor.label}${sensor.kind === 'status' ? ' · status' : ''}${available.has(sensor.key) ? '' : ' (no latest reading)'}`); option.value = sensor.key; option.selected = sensor.key === state.metric; $('metric-select').append(option); }
    $('metric-select').disabled = !sensors.length;
    $('range-select').value = state.range;
    $('custom-range').hidden = state.range !== 'custom';
    set('custom-timezone', `Dates in ${state.location.timezone || 'UTC'} (this location’s timezone).`);
  }
  function selectedSensor() { return catalog().find(sensor => sensor.key === state.metric) || { key: state.metric, label: state.metric, kind: 'gauge', unit: '' }; }
  function resolutionLabel(seconds) {
    if (!finite(seconds)) return 'Unknown resolution';
    const size = seconds >= 86400 ? 86400 : seconds >= 3600 ? 3600 : seconds >= 60 ? 60 : 1;
    const unit = size === 86400 ? 'day' : size === 3600 ? 'hour' : size === 60 ? 'minute' : 'second';
    return `${number(seconds / size, 1)}-${unit} summaries`;
  }
  function bucketBounds(point, data) {
    const start = Math.max(new Date(data.start).getTime(), new Date(point.observed_at).getTime());
    const end = Math.min(new Date(data.end).getTime(), new Date(point.observed_at).getTime() + data.bucket_seconds * 1000);
    return { start, end };
  }
  function historyError(text) { state.historyError = text; set('history-error', text); $('history-error').hidden = !text; }
  async function loadHistory() {
    const request = ++state.request;
    historyError(''); $('chart').classList.remove('loading-state'); $('chart').setAttribute('aria-busy', 'false');
    if (!state.station || !state.metric) { state.history = null; renderChart(); return; }
    if (state.range === 'custom' && (!$('history-start').value || !$('history-end').value)) { state.history = null; renderChart(); return; }
    const params = new URLSearchParams({ [state.station.physical ? 'physical_station_id' : 'station_id']: state.station.id, range: state.range, metric: state.metric, max_points: '600' });
    if (state.range === 'custom') { params.set('local_start', $('history-start').value); params.set('local_end', $('history-end').value); params.set('timezone', state.location.timezone || 'UTC'); }
    state.history = null; historyError(''); renderChart(); $('chart').classList.add('loading-state'); $('chart').setAttribute('aria-busy', 'true'); set('chart-readout', 'Loading history…');
    try {
      const response = await api(`history?${params}`);
      if (request !== state.request) return;
      if (!Array.isArray(response.points)) throw new Error('The weather service returned an unexpected history response.');
      state.history = response; renderChart(); if (state.station.physical) set('history-source', `Source: ${response.resolved_source_station_id}`);
    } catch (error) { if (request === state.request) { state.history = null; renderChart(); historyError(`${error.name === 'AbortError' ? 'History took too long to load.' : error.message} Change the range or refresh to try again.`); } }
    finally { if (request === state.request) { $('chart').classList.remove('loading-state'); $('chart').setAttribute('aria-busy', 'false'); } }
  }
  function renderChart() {
    const data = state.history; const sensor = selectedSensor(); const stats = data?.summary?.metrics?.[state.metric];
    const valueOf = reading => !reading || !reading.count ? null : sensor.kind === 'accumulation' ? reading.sum : sensor.kind === 'maximum' ? reading.max : ['cumulative_counter', 'raw_counter', 'status'].includes(sensor.kind) ? reading.last : reading.mean;
    const pointValue = point => valueOf(point.metrics?.[state.metric]);
    const raw = data?.points || [];
    const points = raw.filter(point => { const value = pointValue(point); return sensor.kind === 'status' ? value !== null && value !== undefined : finite(value); });
    $('chart').replaceChildren(); $('history-stats').replaceChildren();
    set('history-current', sensor.kind === 'accumulation' && stats?.count ? `${sensorValue(stats.sum, sensor)} known` : sensor.kind === 'accumulation' && data ? 'No measured rain intervals' : points.length ? sensorValue(pointValue(points[points.length - 1]), sensor) : stats?.count ? 'No defined bucket value' : 'No readings in this range');
    const rangeLabel = $('range-select').selectedOptions[0]?.textContent || 'Selected range';
    set('history-range', `${rangeLabel}${data ? ` · ${number(stats?.count || 0)} ${sensor.kind === 'accumulation' ? 'measured intervals' : 'sensor readings'}` : ''}`);
    set('history-resolution', data ? resolutionLabel(data.bucket_seconds) : '');
    set('chart-readout', data ? semanticNote(sensor) : state.range === 'custom' ? 'Choose dates and apply to explore a custom range.' : 'History will appear when measurements are available.');
    set('history-bounds', data ? `Requested: ${formatDate(data.start, { dateStyle: 'medium', timeStyle: 'short' })} – ${formatDate(data.end, { dateStyle: 'medium', timeStyle: 'short' })}. Actual station observations: ${data.actual_start ? formatDate(data.actual_start, { dateStyle: 'medium', timeStyle: 'short' }) : 'none'} – ${data.actual_end ? formatDate(data.actual_end, { dateStyle: 'medium', timeStyle: 'short' }) : 'none'} (${data.timezone || state.location.timezone}). ${semanticNote(sensor)} Time span does not imply continuous sensor coverage.` : '');
    if (data) {
      const coverage = data.coverage || {};
      const summaries = sensor.kind === 'accumulation' ? [['Known rainfall (partial)', stats?.count ? sensorValue(stats.sum, sensor) : 'No known intervals'], ['Unknown intervals', number(stats?.unknown_intervals)], ['Counter resets', number(stats?.reset_count)], ['Counter gaps', number(stats?.gap_count)], ['Measured intervals', number(stats?.count || 0)], ['Bucket coverage', `${number(coverage.populated_buckets)} / ${number(coverage.total_buckets)}`], ['Station time span', finite(coverage.temporal_span_fraction) ? `${number(coverage.temporal_span_fraction * 100, 1)}%` : '—'], ['Source bucket (UTC)', finite(data.source_resolution_seconds) ? resolutionLabel(data.source_resolution_seconds).replace(' summaries', '') : 'Unknown']] : [['Sensor readings', number(stats?.count || 0)], ['Lowest reading', sensor.kind === 'status' || sensor.kind === 'circular' ? 'Not linear' : sensorValue(stats?.min, sensor)], ['Highest reading', sensor.kind === 'status' || sensor.kind === 'circular' ? 'Not linear' : sensorValue(stats?.max, sensor)], ['Bucket coverage', `${number(coverage.populated_buckets)} / ${number(coverage.total_buckets)}`], ['First reading', sensorValue(stats?.first, sensor)], ['Last reading', sensorValue(stats?.last, sensor)], ['Station time span', finite(coverage.temporal_span_fraction) ? `${number(coverage.temporal_span_fraction * 100, 1)}%` : '—'], ['Source bucket (UTC)', finite(data.source_resolution_seconds) ? resolutionLabel(data.source_resolution_seconds).replace(' summaries', '') : 'Unknown']];
      for (const [label, value] of summaries) { const group = node('div'); group.append(node('dt', '', label), node('dd', '', value)); $('history-stats').append(group); }
    }
    if (!points.length) { $('chart').append(node('p', 'empty', !state.metric ? 'Connect a station to explore its sensor history.' : sensor.kind === 'accumulation' ? 'No measured rain intervals. Unknown intervals are not assumed dry.' : stats?.count ? 'Source readings exist, but this aggregate is undefined. A circular mean can be undefined for opposing wind directions.' : 'No measurements are available for this selection.')); return; }
    if (sensor.kind === 'status') {
      const list = node('div', 'status-history');
      for (const point of [...points].reverse()) { const row = node('div'); const reported = point.metrics[state.metric].last_at || bucketBounds(point, data).start; const time = node('time', '', formatDate(reported, { dateStyle: 'medium', timeStyle: 'short' })); time.dateTime = new Date(reported).toISOString(); row.append(time, node('span', '', sensorValue(pointValue(point), sensor))); list.append(row); } $('chart').append(list); return;
    }
    const values = points.map(point => converted(pointValue(point), sensor));
    const envelope = points.flatMap(point => { const reading = point.metrics?.[state.metric]; return [reading?.min, reading?.max].filter(finite).map(value => converted(value, sensor)); });
    let min = Math.min(...values, ...envelope), max = Math.max(...values, ...envelope); const padding = Math.max((max - min) * .18, Math.max(Math.abs(max), Math.abs(min)) * .03, .001); min -= padding; max += padding;
    if (sensor.kind === 'circular') { min = 0; max = 360; }
    if (sensor.kind === 'accumulation') min = 0;
    const width = Math.max(270, $('chart').clientWidth || 900), height = width < 500 ? 210 : 230, left = 45, right = 13, top = 17, bottom = 40;
    const startTime = new Date(data.start).getTime(), endTime = new Date(data.end).getTime();
    const x = point => { const bounds = bucketBounds(point, data); return left + (((bounds.start + bounds.end) / 2 - startTime) / Math.max(endTime - startTime, 1)) * (width - left - right); };
    const y = value => top + (1 - (value - min) / (max - min)) * (height - top - bottom);
    const svgNS = 'http://www.w3.org/2000/svg'; const svg = document.createElementNS(svgNS, 'svg'); svg.setAttribute('viewBox', `0 0 ${width} ${height}`); svg.setAttribute('role', 'group'); svg.setAttribute('aria-label', `${sensor.label} history, ${points.length} populated buckets. Gaps indicate missing measurements. Select a point for details.`);
    const element = (tag, attrs, text) => { const el = document.createElementNS(svgNS, tag); for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value)); if (text !== undefined) el.textContent = text; svg.append(el); return el; };
    const rows = sensor.kind === 'circular' ? 5 : 4;
    const axisDigits = max - min >= 2 ? 1 : max - min >= .2 ? 2 : max - min >= .02 ? 3 : 4;
    for (let row = 0; row < rows; row++) { const yy = top + row / (rows - 1) * (height - top - bottom); const value = max - row / (rows - 1) * (max - min); element('line', { x1: left, y1: yy, x2: width - right, y2: yy, class: 'grid' }); element('text', { x: left - 8, y: yy + 4, 'text-anchor': 'end' }, sensor.kind === 'circular' ? ['N', 'W', 'S', 'E', 'N'][row] : Math.abs(value) >= 10000 ? new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(value) : number(value, axisDigits)); }
    let path = '', previous = null;
    for (const point of raw) {
      const value = pointValue(point);
      if (!finite(value)) { previous = null; continue; }
      const time = new Date(point.observed_at).getTime();
      const gap = !previous || time - previous.time > data.bucket_seconds * 1500 || sensor.kind === 'circular' && Math.abs(value - previous.value) > 180;
      path += `${gap ? 'M' : 'L'}${x(point)},${y(converted(value, sensor))} `; previous = { time, value };
      const reading = point.metrics?.[state.metric];
      if (sensor.kind !== 'circular' && finite(reading?.min) && finite(reading?.max)) element('line', { x1: x(point), x2: x(point), y1: y(converted(reading.min, sensor)), y2: y(converted(reading.max, sensor)), class: 'envelope' });
    }
    if (sensor.kind !== 'accumulation') element('path', { d: path.trim(), fill: 'none', class: 'line' });
    else for (const point of points) { const bounds = bucketBounds(point, data); const barWidth = Math.max(1, (bounds.end - bounds.start) / Math.max(endTime - startTime, 1) * (width - left - right) - 2); const value = converted(pointValue(point), sensor); element('rect', { x: x(point) - barWidth / 2, y: y(value), width: barWidth, height: Math.max(1, y(0) - y(value)), fill: '#c9884b', 'fill-opacity': '.55', stroke: 'none', 'aria-hidden': 'true' }); }
    const duration = endTime - startTime; const ticks = width < 500 ? 3 : 5;
    for (let tick = 0; tick < ticks; tick++) { const time = startTime + tick / (ticks - 1) * duration; const options = duration <= 86400000 ? { hour: 'numeric', minute: '2-digit' } : duration > 370 * 86400000 ? { month: 'short', year: 'numeric' } : { month: 'short', day: 'numeric' }; element('text', { x: left + tick / (ticks - 1) * (width - left - right), y: height - 12, 'text-anchor': tick === 0 ? 'start' : tick === ticks - 1 ? 'end' : 'middle' }, formatDate(time, options)); }
    points.forEach((point, index) => {
      const reading = point.metrics[state.metric]; const bounds = bucketBounds(point, data); const label = `Bucket ${formatDate(bounds.start, { dateStyle: 'medium', timeStyle: 'short' })} – ${formatDate(bounds.end, { dateStyle: 'medium', timeStyle: 'short' })}: ${sensorValue(pointValue(point), sensor)} · ${number(reading.count)} readings${sensor.kind === 'accumulation' ? ` · ${number(reading.unknown_intervals)} unknown intervals, ${number(reading.reset_count)} resets, ${number(reading.gap_count)} gaps` : sensor.kind !== 'circular' ? ` · min ${sensorValue(reading.min, sensor)}, max ${sensorValue(reading.max, sensor)}` : ' · circular mean'} · Observed ${formatDate(reading.first_at, { dateStyle: 'medium', timeStyle: 'short' })} – ${formatDate(reading.last_at, { dateStyle: 'medium', timeStyle: 'short' })}`;
      element('circle', { cx: x(point), cy: y(values[index]), r: 2, fill: '#c9884b', stroke: 'none', 'aria-hidden': 'true' });
      const circle = element('circle', { cx: x(point), cy: y(values[index]), r: 9, class: 'point', tabindex: index === 0 ? '0' : '-1', role: 'button', 'aria-label': label, 'data-point': index });
      const show = () => set('chart-readout', label); circle.addEventListener('focus', show); circle.addEventListener('pointerenter', show); circle.addEventListener('click', () => { show(); circle.focus(); });
      circle.addEventListener('keydown', event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); const target = svg.querySelector(`[data-point="${Math.min(points.length - 1, Math.max(0, index + (event.key === 'ArrowRight' ? 1 : -1)))}"]`); if (target) target.focus(); } else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); show(); } });
    });
    $('chart').append(svg);
  }
  function renderForecast() {
    const forecast = state.location.forecast; $('forecast').replaceChildren();
    set('forecast-source', forecast?.source ? `Forecast · ${forecast.source}` : 'Forecast unavailable');
    set('forecast-note', forecast?.fetched_at ? `Forecast updated ${formatDate(forecast.fetched_at, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' })}${forecast.status && !['ok', 'available', 'demo', 'fresh'].includes(forecast.status) ? ` · ${forecast.status}` : ''}. Forecasts describe the wider area; your station measures conditions at home.` : 'Forecasts will appear when a forecast provider is configured.');
    if (!forecast?.daily?.length) { $('forecast').append(node('p', 'empty', 'No forecast is available for this location.')); return; }
    const today = localCalendarDate(state.location.timezone);
    for (const day of forecast.daily.slice(0, 7)) { const cell = node('article', 'forecast-day'); const description = weather(day.weather_code); const date = `${day.date}T12:00:00Z`; const image = icon(description.icon); const descriptionNode = document.createElementNS('http://www.w3.org/2000/svg', 'title'); descriptionNode.textContent = description.label; image.prepend(descriptionNode); image.removeAttribute('aria-hidden'); image.setAttribute('role', 'img'); image.setAttribute('aria-label', description.label); const temperatures = node('div', 'forecast-temps', `${temp(day.temperature_max_c)}°`); temperatures.append(node('span', '', `${temp(day.temperature_min_c)}°`)); cell.append(node('span', 'day', day.date === today ? 'Today' : formatDate(date, { weekday: 'short' }, 'UTC')), node('span', 'date', formatDate(date, { month: 'short', day: 'numeric' }, 'UTC')), image, temperatures, node('span', 'rain-chance', `${number(day.precipitation_probability_pct)}% rain`)); $('forecast').append(cell); }
  }
  $('refresh').addEventListener('click', refresh);
  $('station-select').addEventListener('change', event => { chooseStation(installations(state.location).find(s => String(s.id) === event.target.value)); });
  for (const [id, unit] of [['fahrenheit', 'F'], ['celsius', 'C']]) $(id).addEventListener('click', () => { state.unit = unit; try { localStorage.setItem('weatherhouse-unit', unit); } catch (_) {} if (state.location) render(); });
  $('range-select').addEventListener('change', event => { state.range = event.target.value; state.history = null; state.request++; historyError(''); renderMetricOptions(); renderChart(); loadHistory(); });
  $('custom-range').addEventListener('submit', event => { event.preventDefault(); if ($('history-start').value >= $('history-end').value) { historyError('The end must be later than the start.'); return; } loadHistory(); });
  $('metric-select').addEventListener('change', event => { state.metric = event.target.value; state.history = null; loadHistory(); });
  let resizeTimer; window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (state.location) renderChart(); }, 120); });
  setInterval(() => { if (state.location) { renderConditions(); renderSensors(); renderTransmitters(); } }, 30000);
  refresh();
})();
