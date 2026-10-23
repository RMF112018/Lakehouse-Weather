"""Weather validation and chronological cumulative-rain handling."""
import math
from datetime import datetime, timezone

FIELDS = {
    'temperature_c': ('temperature_C', -90, 65),
    'humidity_pct': ('humidity', 0, 100),
    'wind_speed_ms': ('wind_avg_m_s', 0, 150),
    'wind_gust_ms': ('wind_max_m_s', 0, 150),
    'wind_direction_deg': ('wind_dir_deg', 0, 360),
    'pressure_hpa': ('pressure_hPa', 800, 1100),
    'rain_total_mm': ('rain_mm', 0, 1000000),
    'uv_index': ('uvi', 0, 30),
}


def utc(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be ISO 8601 with UTC offset')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise ValueError('Timestamp must include explicit UTC offset')
    return result.astimezone(timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def normalize(packet, now=None):
    if not isinstance(packet, dict):
        raise ValueError('Packet must be an object')
    observed = utc(packet.get('time'))
    now = now or datetime.now(timezone.utc)
    if (observed - now).total_seconds() > 300:
        raise ValueError('Timestamp is more than five minutes in the future')
    result = {'observed_at': stamp(observed)}
    for target, (source, minimum, maximum) in FIELDS.items():
        value = packet.get(source)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError('Invalid measurement: ' + source)
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError('Out-of-range measurement: ' + source)
        result[target] = value
    if all(result[key] is None for key in FIELDS):
        raise ValueError('At least one supported measurement is required')
    battery = packet.get('battery_ok')
    if battery is not None and (type(battery) not in (int, bool) or battery not in (0, 1)):
        raise ValueError('Invalid battery status')
    result['battery_ok'] = None if battery is None else bool(battery)
    result['rain_interval_mm'] = None
    return result


def rain_intervals(rows):
    """Derive deltas at read time so late packets repair subsequent intervals.

    First reading and counter resets have unknown increments (null), never a
    fabricated zero or the entire lifetime counter. Missing counters preserve
    the previous valid baseline.
    """
    result, previous = [], None
    for row in rows:
        row = dict(row)
        current = row.get('rain_total_mm')
        row['rain_interval_mm'] = (
            round(current - previous, 3)
            if current is not None and previous is not None and current >= previous
            else None
        )
        if current is not None:
            previous = current
        result.append(row)
    return result
