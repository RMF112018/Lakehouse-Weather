"""Explicit server-side forecast refresh; never a request-time external fetch."""
import json
import math
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from .domain import stamp, utc


def cached(store, location_id, now):
    value = store.get_forecast(location_id)
    if value is None:
        return {'source': 'Open-Meteo', 'fetched_at': None, 'status': 'unavailable', 'daily': []}
    if value.get('status') != 'demo' and now - utc(value['fetched_at']) > timedelta(hours=6):
        value['status'] = 'stale'
    return value


def refresh(store, location, opener=urlopen, now=None):
    now = now or datetime.now(timezone.utc)
    query = urlencode({'latitude': location['latitude'], 'longitude': location['longitude'], 'daily': 'temperature_2m_min,temperature_2m_max,precipitation_probability_max,weather_code', 'timezone': location['timezone'], 'forecast_days': 7})
    try:
        request = Request('https://api.open-meteo.com/v1/forecast?' + query, headers={'User-Agent': 'LakehouseWeather/0.1'})
        with opener(request, timeout=8) as response:
            raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError('Forecast response too large')
        data = json.loads(raw)['daily']
        days = data['time']
        if not 1 <= len(days) <= 7:
            raise ValueError('Invalid forecast day count')
        daily = []
        fields = [('temperature_min_c', 'temperature_2m_min', -90, 65), ('temperature_max_c', 'temperature_2m_max', -90, 65), ('precipitation_probability_pct', 'precipitation_probability_max', 0, 100), ('weather_code', 'weather_code', 0, 99)]
        for index, day in enumerate(days):
            datetime.strptime(day, '%Y-%m-%d')
            row = {'date': day}
            for target, source, low, high in fields:
                number = data[source][index]
                if type(number) not in (float, int) or not math.isfinite(number) or not low <= number <= high:
                    raise ValueError('Invalid forecast value')
                row[target] = number
            if row['temperature_min_c'] > row['temperature_max_c']:
                raise ValueError('Invalid forecast temperature range')
            daily.append(row)
        result = {'source': 'Open-Meteo', 'fetched_at': stamp(now), 'status': 'ok', 'daily': daily}
        store.put_forecast(location['id'], result)
        return True
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        # Preserve the last successful cache; age remains visible to clients.
        return False
