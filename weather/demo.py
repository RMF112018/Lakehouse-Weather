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
                store.insert(station['id'], {'observed_at': stamp(observed), 'temperature_c': round(temperature, 1), 'humidity_pct': round(60 - 15 * math.sin(hour * math.pi / 12)), 'wind_speed_ms': round(2 + abs(math.sin(hour)) * 3, 1), 'wind_gust_ms': 6.2, 'wind_direction_deg': 225, 'pressure_hpa': None, 'rain_total_mm': round(rain, 2), 'rain_interval_mm': None, 'uv_index': 2, 'uv_raw': 145, 'illuminance_lux': 18000, 'battery_ok': True, 'integrity': 'CRC', 'raw_rf': {'model':'DEMO','light_lux':18000,'uvi':2,'uv':145}, 'provenance': {'transport':'synthetic','normalizer_version':2}})
        if index == 0:
            # Five-minute synthetic outdoor samples make known rain intervals
            # visible without pretending hourly gaps provide measured increments.
            for step in range(577):
                if step % 12 == 0:
                    continue  # Existing hourly sample owns this synthetic timestamp.
                elapsed=step/12
                at=now-timedelta(hours=48-elapsed)
                store.insert(location['stations'][0]['id'],{'observed_at':stamp(at),'temperature_c':round(17+5*math.sin(elapsed*math.pi/12),1),'humidity_pct':60,'wind_speed_ms':2,'wind_gust_ms':6.2,'wind_direction_deg':225,'rain_total_mm':round(max(0,min(5,elapsed-12))*.4,3),'uv_index':2,'uv_raw':145,'illuminance_lux':18000,'battery_ok':True,'provenance':{'transport':'synthetic','normalizer_version':2}})
            detector = {'id':'station-lightning-demo','name':'WH31L lightning (demo)','model':'Ambient Weather WH31L','receiver_model':'DEMO-LIGHTNING','sensor_id':'synthetic-lightning'}
            location['stations'].append(detector)
            for hour in range(49):
                at=now-timedelta(hours=48-hour)
                store.insert(detector['id'],{'observed_at':stamp(at),'lightning_count_raw':(hour*7)%256,'lightning_distance_km':8+hour%15 if hour%5==0 else None,'detector_state':'strike' if hour%5==0 else 'heartbeat','detector_flags':32856,'battery_ok':True,'integrity':'CRC','raw_rf':{'model':'DEMO-LIGHTNING','strike_count':(hour*7)%256},'provenance':{'transport':'synthetic','normalizer_version':2}})
            # Clearly synthetic daily samples demonstrate long-range controls;
            # their daily cadence is not represented as continuous sensor uptime.
            for day in range(3,3653):
                at=now-timedelta(days=day)
                store.insert(location['stations'][0]['id'],{'observed_at':stamp(at),'temperature_c':round(12+10*math.sin(day*math.pi/182.6),1),'humidity_pct':60,'uv_index':2,'uv_raw':145,'illuminance_lux':18000,'rain_total_mm':day%100,'battery_ok':True,'provenance':{'transport':'synthetic','normalizer_version':2}})
        store.put_forecast(location['id'], {'source': 'Synthetic demo forecast', 'fetched_at': stamp(now), 'status': 'demo', 'daily': [{'date': (now + timedelta(days=day)).date().isoformat(), 'temperature_min_c': 9-index*3+day, 'temperature_max_c': 20-index*3+day, 'precipitation_probability_pct': [10, 65, 30, 5, 15, 35, 20][day], 'weather_code': [1, 61, 3, 0, 2, 3, 1][day]} for day in range(7)]})
        locations.append(location)
    return locations, store
