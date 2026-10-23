"""Deterministic synthetic fixtures; no measurement or forecast is live."""
import math
from datetime import datetime, timezone, timedelta
from .domain import stamp
from .store import MemoryStore


def build(now=None):
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    locations = []
    store = MemoryStore()
    for index, (name, zone, lat, lon) in enumerate([
        ('Lakehouse', 'America/New_York', 44.48, -73.21),
        ('Home', 'America/New_York', 40.71, -74.01),
        ('Mountain cabin', 'America/Denver', 39.64, -106.37),
    ]):
        location = {'id': f'location-{index+1}', 'name': name, 'timezone': zone, 'latitude': lat, 'longitude': lon, 'stations': []}
        for n in range(2 if index == 0 else 1):
            station = {'id': f'station-{index+1}-{n+1}', 'name': 'WS-2000' if n == 0 else 'Garden sensor', 'model': 'Ambient Weather WS-2000' if n == 0 else 'Synthetic temperature sensor', 'receiver_model': 'DEMO', 'sensor_id': f'{index}-{n}'}
            location['stations'].append(station)
            rain = 0
            for hour in range(49):
                rain += .4 if 12 < hour < 18 else 0
                observed = now - timedelta(hours=48-hour + (3 if index == 2 else 0))
                temperature = 17 - index * 4 + 5 * math.sin(hour * math.pi / 12) + n * .8
                store.insert(station['id'], {'observed_at': stamp(observed), 'temperature_c': round(temperature, 1), 'humidity_pct': round(60 - 15 * math.sin(hour * math.pi / 12)), 'wind_speed_ms': round(2 + abs(math.sin(hour)) * 3, 1), 'wind_gust_ms': 6.2, 'wind_direction_deg': 225, 'pressure_hpa': 1013.2, 'rain_total_mm': round(rain, 2), 'rain_interval_mm': None, 'uv_index': 2, 'battery_ok': True})
        store.put_forecast(location['id'], {'source': 'Synthetic demo forecast', 'fetched_at': stamp(now), 'status': 'demo', 'daily': [{'date': (now + timedelta(days=day)).date().isoformat(), 'temperature_min_c': 9-index*3+day, 'temperature_max_c': 20-index*3+day, 'precipitation_probability_pct': [10, 65, 30, 5, 15, 35, 20][day], 'weather_code': [1, 61, 3, 0, 2, 3, 1][day]} for day in range(7)]})
        locations.append(location)
    return locations, store
