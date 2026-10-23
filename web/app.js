'use strict';
(() => {
  const signout=document.getElementById('signout');
  if(signout) signout.addEventListener('click',async()=>{signout.disabled=true;try{const status=await fetch('./api/auth/status',{cache:'no-store'});const data=await status.json();if(!data.authenticated){location.replace('./login');return;}const out=await fetch('./api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json','X-Weather-CSRF':data.csrf},body:'{}'});if(out.ok)location.replace('./login');else throw Error();}catch{signout.disabled=false;signout.textContent='Try sign out again';}});
  const $ = id => document.getElementById(id);
  const state = { data: null, location: null, station: null, unit: 'F', hours: 24, metric: 'temperature_c', history: null, request: 0 };
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
    try { const response = await fetch(`./api/${path}`, { signal: controller.signal, headers: { Accept: 'application/json' }, cache: 'no-store' }); if(response.status===401){location.replace('./login');throw new Error('Please sign in again.');} if (!response.ok) throw new Error(`Weather service returned ${response.status}.`); return await response.json(); }
    finally { clearTimeout(timeout); }
  }
  function message(text) { $('error').hidden = !text; set('error', text); }
  async function refresh() {
    $('refresh').disabled = true; $('main').setAttribute('aria-busy', 'true'); message('');
    try {
      const data = await api('dashboard');
      if (!Array.isArray(data.locations)) throw new Error('The weather service returned an unexpected response.');
      state.data = data;
      if(signout)signout.hidden=data.mode==='demo';
      state.location = data.locations.find(l => l.id === state.location?.id) || data.locations[0] || null;
      state.station = state.location?.stations?.find(s => s.id === state.station?.id) || state.location?.stations?.[0] || null;
      state.request++; state.history = null;
      $('loading').hidden = true; $('content').hidden = !state.location;
      if (!state.location) message('No locations are configured yet. Add a location and its weather station to get started.');
      $('notice').hidden = data.mode !== 'demo';
      set('notice', 'DEMO MODE · Illustrative weather data. These are sample locations and readings, not live observations from your WS-2000.');
      set('connection-text', data.mode === 'demo' ? 'Exploring sample weather' : 'Connected to your weather service');
      set('footer-status', data.mode === 'demo' ? 'Sample data · Nonproduction preview' : 'Your stations. Your data.');
      if (state.location) { render(); if (state.hours !== 24) await loadHistory(); }
    } catch (error) { $('loading').hidden = true; message(`${error.name === 'AbortError' ? 'The weather service took too long to respond.' : error.message} Use refresh to try again.${state.data ? ' Previously loaded readings remain visible.' : ''}`); set('connection-text', 'Weather service unavailable'); }
    finally { $('refresh').disabled = false; $('main').setAttribute('aria-busy', 'false'); }
  }
  function renderLocations() {
    $('locations').replaceChildren(); set('place-count', `${state.data.locations.length} ${state.data.locations.length === 1 ? 'location' : 'locations'}`);
    for (const location of state.data.locations) {
      const stations = location.stations || []; const first = stations[0]; const button = node('button', 'location-card'); button.type = 'button'; button.setAttribute('aria-pressed', String(location.id === state.location.id));
      const text = node('span'); text.append(node('span', 'location-name', location.name), node('span', 'location-sub', `${stations.length} ${stations.length === 1 ? 'station' : 'stations'} · ${first ? first.stale ? 'Stale readings' : 'Reporting' : 'Not connected'}`));
      button.append(text, node('span', 'location-temp', `${temp(first?.observation?.temperature_c)}°`));
      button.addEventListener('click', () => { state.location = location; state.station = stations[0] || null; state.history = null; state.request++; $('chart').classList.remove('loading-state'); render(); if (state.hours !== 24) loadHistory(); }); $('locations').append(button);
    }
  }
  function render() {
    $('fahrenheit').setAttribute('aria-pressed', String(state.unit === 'F')); $('celsius').setAttribute('aria-pressed', String(state.unit === 'C'));
    renderLocations();
    set('location-title', state.location.name); set('location-region', `${state.location.timezone || 'UTC'} · LOCAL OBSERVATIONS`);
    const select = $('station-select'); select.replaceChildren(); for (const station of state.location.stations || []) { const option = node('option', '', station.name); option.value = station.id; option.selected = station.id === state.station?.id; select.append(option); } select.disabled = !state.station;
    renderStationComparison(); renderConditions(); renderChart(); renderForecast();
  }
  function chooseStation(station) {
    state.station = station; state.history = null; state.request++;
    $('chart').classList.remove('loading-state');
    render(); if (state.hours !== 24) loadHistory();
  }
  function renderStationComparison() {
    const stations = state.location.stations || []; const root = $('station-comparison'); root.replaceChildren(); root.hidden = stations.length < 2;
    for (const station of stations) {
      const button = node('button', 'station-chip'); button.type = 'button'; button.setAttribute('aria-pressed', String(station.id === state.station?.id));
      button.append(node('span', '', station.name), node('strong', '', `${temp(station.observation?.temperature_c)}°`), node('small', '', station.stale ? 'Stale' : 'Reporting'));
      button.addEventListener('click', () => chooseStation(station)); root.append(button);
    }
  }
  function metric(title, value, unit, detail, image) { const card = node('article', 'metric-card'); const top = node('div', 'metric-top'); top.append(node('span', '', title), icon(image)); const reading = node('div', 'metric-value', value); reading.append(node('small', '', unit)); card.append(top, reading, node('div', 'metric-detail', detail)); return card; }
  function renderConditions() {
    const station = state.station; const obs = station?.observation || {}; const forecast = state.location.forecast;
    set('updated', obs.observed_at ? `Observed ${formatDate(obs.observed_at, { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' })} · ${age(obs.observed_at)}` : 'Waiting for the first observation');
    const temperature = node('span', '', temp(obs.temperature_c)); temperature.append(node('small', '', `°${state.unit}`)); $('temperature').replaceChildren(temperature);
    const today = forecast?.daily?.find(day => day.date === localCalendarDate(state.location.timezone));
    const currentWeather = weather(today?.weather_code);
    set('condition-label', finite(obs.temperature_c) ? 'Outside, right now' : 'Awaiting station data');
    set('hero-detail', today ? `Today’s forecast: ${currentWeather.label.toLowerCase()}` : 'Local measurements from your weather station');
    $('hero-icon').replaceChildren(icon(currentWeather.icon));
    set('station-health', !station ? 'No station' : station.stale ? '● Stale reading' : '● Station reporting'); $('station-health').classList.toggle('stale', !station || station.stale);
    set('station-model', station ? `${station.model || 'Weather station'} · ${station.name}` : 'No station configured');
    set('battery', obs.battery_ok === false ? 'Battery low' : obs.battery_ok === true ? 'Battery healthy' : 'Battery status unknown');
    const direction = finite(obs.wind_direction_deg) ? ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][Math.round(obs.wind_direction_deg / 45) % 8] : 'Direction unavailable';
    $('metrics').replaceChildren(
      metric('Humidity', number(obs.humidity_pct), '%', 'Relative humidity', 'drop'),
      metric('Wind', speed(obs.wind_speed_ms), speedUnit(), `${direction} · Gusts ${speed(obs.wind_gust_ms)} ${speedUnit()}`, 'wind'),
      metric('Rainfall', rain(obs.rain_interval_mm), rainUnit(), 'Latest measurement interval', 'rain'),
      metric('Pressure', state.unit === 'F' ? finite(obs.pressure_hpa) ? number(obs.pressure_hpa / 33.8639, 2) : '—' : number(obs.pressure_hpa, 1), state.unit === 'F' ? 'inHg' : 'hPa', 'Station pressure', 'gauge')
    );
  }
  async function loadHistory() {
    if (!state.station) return;
    const request = ++state.request; const station = state.station.id; const hours = state.hours;
    $('chart').classList.add('loading-state'); set('chart-readout', 'Loading history…');
    try {
      const response = await api(`history?station_id=${encodeURIComponent(station)}&hours=${hours}`);
      if (request !== state.request) return;
      const points = Array.isArray(response) ? response : response.history || response.observations || [];
      if (!Array.isArray(points)) throw new Error('Unexpected history response.');
      state.history = points; renderChart();
    } catch (_) { if (request === state.request) { state.history = []; renderChart(); set('chart-readout', 'History could not be loaded. Change the range or refresh to try again.'); } }
    finally { if (request === state.request) $('chart').classList.remove('loading-state'); }
  }
  function renderChart() {
    $('hours24').setAttribute('aria-pressed', String(state.hours === 24)); $('hours48').setAttribute('aria-pressed', String(state.hours === 48));
    const convert = value => state.metric === 'temperature_c' ? state.unit === 'F' ? value * 9 / 5 + 32 : value : state.metric === 'wind_speed_ms' ? value * (state.unit === 'F' ? 2.23694 : 3.6) : value;
    const unit = state.metric === 'temperature_c' ? `°${state.unit}` : state.metric === 'humidity_pct' ? '%' : speedUnit();
    const raw = state.history ?? state.station?.history ?? [];
    const end = raw.reduce((max, p) => Math.max(max, new Date(p.observed_at).getTime() || 0), 0);
    const points = raw.filter(p => finite(p[state.metric]) && Number.isFinite(new Date(p.observed_at).getTime()) && new Date(p.observed_at).getTime() >= end - state.hours * 3600000).sort((a, b) => new Date(a.observed_at) - new Date(b.observed_at));
    $('chart').replaceChildren(); set('history-current', points.length ? `${number(convert(points[points.length - 1][state.metric]), 1)}${unit}` : 'No readings yet');
    set('history-range', `Past ${state.hours} hours · ${points.length} readings`); set('chart-readout', 'Select a point to see its reading.');
    if (points.length < 2) { $('chart').append(node('p', 'empty', 'A little more history is needed to draw the day.')); return; }
    const values = points.map(p => convert(p[state.metric])); let min = Math.min(...values), max = Math.max(...values); const padding = Math.max((max - min) * .25, 1); min -= padding; max += padding;
    const width = Math.max(270, $('chart').clientWidth || 900), height = width < 500 ? 180 : 208, left = 37, right = 12, top = 17, bottom = 33;
    const startTime = new Date(points[0].observed_at).getTime(); const endTime = new Date(points[points.length - 1].observed_at).getTime();
    const xy = (p, i) => [left + ((new Date(p.observed_at).getTime() - startTime) / Math.max(endTime - startTime, 1)) * (width - left - right), top + (1 - (values[i] - min) / (max - min)) * (height - top - bottom)];
    const svgNS = 'http://www.w3.org/2000/svg'; const svg = document.createElementNS(svgNS, 'svg'); svg.setAttribute('viewBox', `0 0 ${width} ${height}`); svg.setAttribute('role', 'group'); svg.setAttribute('aria-label', `${$('metric-select').selectedOptions[0].textContent} history, ${points.length} readings. Select a point for details.`);
    const element = (tag, attrs, text) => { const el = document.createElementNS(svgNS, tag); for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value)); if (text !== undefined) el.textContent = text; svg.append(el); return el; };
    for (let row = 0; row < 4; row++) { const y = top + row / 3 * (height - top - bottom); element('line', { x1: left, y1: y, x2: width - right, y2: y, class: 'grid' }); element('text', { x: left - 9, y: y + 4, 'text-anchor': 'end' }, number(max - row / 3 * (max - min))); }
    const path = points.map((p, i) => `${i ? 'L' : 'M'}${xy(p, i).join(',')}`).join(' ');
    element('path', { d: `${path} L${width - right},${height - bottom} L${left},${height - bottom} Z`, fill: '#c9884b', 'fill-opacity': '.07', stroke: 'none' }); element('path', { d: path, fill: 'none', class: 'line' });
    for (let tick = 0; tick < 5; tick++) { const time = startTime + tick / 4 * (endTime - startTime); element('text', { x: left + tick / 4 * (width - left - right), y: height - 8, 'text-anchor': tick === 0 ? 'start' : tick === 4 ? 'end' : 'middle' }, formatDate(time, { hour: 'numeric', minute: '2-digit' })); }
    points.forEach((p, i) => { const [x, y] = xy(p, i); const label = `${formatDate(p.observed_at, { weekday: 'short', hour: 'numeric', minute: '2-digit' })}: ${number(values[i], 1)}${unit}`; const point = element('circle', { cx: x, cy: y, r: 9, class: 'point', tabindex: '0', role: 'button', 'aria-label': label }); const show = () => set('chart-readout', label); point.addEventListener('focus', show); point.addEventListener('pointerenter', show); point.addEventListener('click', show); point.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); show(); } }); });
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
  $('station-select').addEventListener('change', event => { chooseStation(state.location.stations.find(s => String(s.id) === event.target.value)); });
  for (const [id, unit] of [['fahrenheit', 'F'], ['celsius', 'C']]) $(id).addEventListener('click', () => { state.unit = unit; try { localStorage.setItem('weatherhouse-unit', unit); } catch (_) {} if (state.location) render(); });
  for (const hours of [24, 48]) $(`hours${hours}`).addEventListener('click', () => { state.hours = hours; renderChart(); loadHistory(); });
  $('metric-select').addEventListener('change', event => { state.metric = event.target.value; renderChart(); });
  let resizeTimer; window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (state.location) renderChart(); }, 120); });
  refresh();
})();
