"""Typed RF measurements with bounded, redacted source provenance."""
import json
import math
import re
from datetime import datetime, timezone

# Only rtl_433 names map here. Cloud API/console archive field names are distinct.
# target: (RF name, minimum, maximum, unit, label, aggregation kind)
FIELDS = {
    'temperature_c': ('temperature_C', -90, 65, '°C', 'Temperature', 'gauge'),
    'humidity_pct': ('humidity', 0, 100, '%', 'Humidity', 'gauge'),
    'wind_speed_ms': ('wind_avg_m_s', 0, 150, 'm/s', 'Wind speed', 'gauge'),
    'wind_gust_ms': ('wind_max_m_s', 0, 150, 'm/s', 'Wind gust', 'maximum'),
    'wind_direction_deg': ('wind_dir_deg', 0, 360, '°', 'Wind direction', 'circular'),
    'pressure_hpa': ('pressure_hPa', 300, 1100, 'hPa', 'Pressure (sensor reported)', 'gauge'),
    'rain_total_mm': ('rain_mm', 0, 1000000, 'mm', 'Rain counter', 'cumulative_counter'),
    'uv_index': ('uvi', 0, 30, 'index', 'UV index', 'gauge'),
    'uv_raw': ('uv', 0, 1000000, 'raw', 'Raw UV sensor value', 'gauge'),
    'illuminance_lux': ('light_lux', 0, 1000000, 'lux', 'Illuminance', 'gauge'),
    'lightning_distance_km': ('storm_dist_km', 0, 62, 'km', 'Last reported strike distance', 'gauge'),
    'lightning_count_raw': ('strike_count', 0, 255, 'count', 'Lightning counter (8 bit)', 'raw_counter'),
    'receiver_rssi_db': ('rssi', -200, 100, 'dB', 'Receiver RSSI', 'gauge'),
    'receiver_snr_db': ('snr', -100, 150, 'dB', 'Receiver signal/noise', 'gauge'),
    'receiver_noise_db': ('noise', -200, 100, 'dB', 'Receiver noise', 'gauge'),
}
CATALOG = {key: {'unit': spec[3], 'label': spec[4], 'kind': spec[5], 'source_field': spec[0]} for key, spec in FIELDS.items()}
CATALOG.update({
    'rain_known_mm': {'unit':'mm','label':'Known rainfall (partial)','kind':'accumulation','source_field':'derived_rain_counter'},
    'battery_level': {'unit':'fraction level','label':'Decoder battery level (not charge %)','kind':'gauge','source_field':'battery_ok'},
    'battery_ok': {'unit': None, 'label': 'Battery OK', 'kind': 'status', 'source_field': 'battery_ok'},
    'detector_state': {'unit': None, 'label': 'Lightning detector state', 'kind': 'status', 'source_field': 'state'},
    'detector_flags': {'unit': 'bitmask', 'label': 'Lightning detector flags', 'kind': 'status', 'source_field': 'flags'},
    'integrity': {'unit': None, 'label': 'Decoder integrity check', 'kind': 'status', 'source_field': 'mic'},
})
_SECRET = re.compile(r'auth|token|secret|password|passwd|credential|cookie|session|api.?key|private.?key|dsn|connection.?string', re.I)
_KEY = re.compile(r'^[A-Za-z][A-Za-z0-9_.-]{0,63}$')


def utc(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError('Timestamp must be ISO 8601 with UTC offset')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise ValueError('Timestamp must include explicit UTC offset')
    return result.astimezone(timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def safe_rf(packet):
    """Preserve future RF fields, not credentials or arbitrary unbounded JSON."""
    def clean(value, depth=0):
        if depth > 4:
            raise ValueError('RF object nesting too deep')
        if value is None or type(value) is bool:
            return value
        if type(value) in (int, float):
            if not math.isfinite(value) or abs(value) > 1e18:
                raise ValueError('Invalid RF numeric value')
            return value
        if isinstance(value, str):
            if len(value) > 256:
                raise ValueError('RF string too long')
            if re.search(r'(?i)bearer\s|postgres(?:ql)?://|-----BEGIN .*PRIVATE KEY', value):
                return '[redacted]'
            return value
        if isinstance(value, list):
            if len(value) > 32:
                raise ValueError('RF list too long')
            return [clean(v, depth+1) for v in value]
        if isinstance(value, dict):
            if len(value) > 64:
                raise ValueError('Too many RF fields')
            result = {}
            for key, item in value.items():
                if not isinstance(key, str) or not _KEY.fullmatch(key):
                    raise ValueError('Invalid RF field name')
                if not _SECRET.search(key):
                    result[key] = clean(item, depth+1)
            return result
        raise ValueError('Unsupported RF value')
    result = clean(packet)
    if len(json.dumps(result, allow_nan=False).encode()) > 16384:
        raise ValueError('RF payload too large')
    return result


def normalize(packet, now=None, trusted_context=None):
    if not isinstance(packet, dict):
        raise ValueError('Packet must be an object')
    raw = safe_rf(packet)
    observed = utc(packet.get('time'))
    now = now or datetime.now(timezone.utc)
    if (observed - now).total_seconds() > 300:
        raise ValueError('Timestamp is more than five minutes in the future')
    result = {'observed_at': stamp(observed)}
    unavailable = {}
    if packet.get('model') == 'Fineoffset-WH65B':
        for raw_key, sentinel, targets in [('temperature_raw',0x7ff,['temperature_c']),('humidity_raw',0xff,['humidity_pct']),('uv_raw',0xffff,['uv_raw','uv_index']),('light_raw',0xffffff,['illuminance_lux'])]:
            if type(packet.get(raw_key)) is int and packet[raw_key] == sentinel:
                for target in targets:
                    unavailable[target] = 'transmitter_invalid_sentinel'

    for target, spec in FIELDS.items():
        source, minimum, maximum = spec[:3]
        value = None if target in unavailable else packet.get(source)
        if target == 'lightning_distance_km' and value == 63:
            value = None  # Six-bit no-valid-distance sentinel, retained in raw_rf.
            result.setdefault('unavailable_reasons', {})[target] = 'RF no-valid-distance sentinel (63)'
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError('Invalid measurement: ' + source)
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError('Out-of-range measurement: ' + source)
            if target == 'lightning_count_raw' and int(value) != value:
                raise ValueError('Lightning counter must be an integer')
        result[target] = value
    battery = packet.get('battery_ok')
    lightning_battery = str(packet.get('model','')).lower() == 'fineoffset-wh31l'
    accepted_battery = (0,0.5,1) if lightning_battery else (0,1)
    if battery is not None and (type(battery) not in (int, float, bool) or battery not in accepted_battery):
        raise ValueError('Invalid battery status')
    result['battery_ok'] = None if battery is None or battery == 0.5 else bool(battery)
    result['battery_level'] = float(battery) if lightning_battery and battery is not None else None
    for target, source in [('detector_state', 'state'), ('integrity', 'mic')]:
        value = None if target in unavailable else packet.get(source)
        if value is not None and (not isinstance(value, str) or not 1 <= len(value) <= 32):
            raise ValueError('Invalid RF status')
        result[target] = value
    flags = packet.get('flags')
    if flags is not None and (type(flags) is not int or not 0 <= flags <= 65535):
        raise ValueError('Invalid detector flags')
    result['detector_flags'] = flags
    if all(result.get(key) is None for key in CATALOG):
        raise ValueError('At least one supported measurement or status is required')
    for target in FIELDS:
        if result[target] is None:
            result.setdefault('unavailable_reasons', {}).setdefault(target, unavailable.get(target, 'not_observed'))
    result['raw_rf'] = raw
    result['provenance'] = {'transport': 'rtl_433', 'model': raw.get('model'), 'sensor_id': raw.get('id'), 'timestamp': 'explicit_receiver_utc', 'normalizer_version': 2}
    if trusted_context:
        context = {key:trusted_context[key] for key in ('transport','decoder_build','receiver_received_at_utc') if key in trusted_context}
        result['provenance'].update(safe_rf(context))
    result['rain_known_mm'] = None
    result['rain_interval_mm'] = None
    return result


def rain_intervals(rows):
    """Conservative short-interval rain deltas; never bridge resets or long gaps."""
    result, previous, previous_time = [], None, None
    for row in rows:
        row = dict(row)
        current, at = row.get('rain_total_mm'), utc(row['observed_at'])
        contiguous = previous_time is not None and 0 <= (at-previous_time).total_seconds() <= 900
        row['rain_interval_mm'] = round(current - previous, 3) if current is not None and previous is not None and contiguous and current >= previous else None
        if current is not None:
            previous, previous_time = current, at
        result.append(row)
    return result
