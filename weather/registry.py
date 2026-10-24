"""Explicit station identity; unrecognized radio packets never create stations."""
import json
import math
from zoneinfo import ZoneInfo
from .domain import CATALOG, utc


def validate_registry(value):
    if not isinstance(value, list) or not value:
        raise ValueError('Registry requires a nonempty locations array')
    location_ids, station_ids, sensors = set(), set(), set()
    for location in value:
        lid = location['id']
        if not isinstance(lid, str) or not lid or lid in location_ids:
            raise ValueError('Location IDs must be unique nonempty strings')
        location_ids.add(lid)
        ZoneInfo(location['timezone'])
        if not isinstance(location['name'], str) or not location['name']:
            raise ValueError('Location name required')
        coordinates = (location['latitude'], location['longitude'])
        if None in coordinates and coordinates != (None, None):
            raise ValueError('Coordinates must both be configured or both pending')
        for key, bound in [('latitude', 90), ('longitude', 180)]:
            coordinate = location[key]
            if coordinate is None:
                continue
            if type(coordinate) not in (int, float) or not math.isfinite(coordinate) or abs(coordinate) > bound:
                raise ValueError('Invalid coordinate')
        for station in location['stations']:
            if type(station.get('ingest_enabled', True)) is not bool:
                raise ValueError('Ingest enabled must be boolean')
            sid = station['id']
            sensor = (station['receiver_model'], str(station['sensor_id']))
            if not isinstance(sid, str) or not sid or sid in station_ids or sensor in sensors:
                raise ValueError('Station and receiver identities must be unique')
            if not all(isinstance(station[k], str) and station[k] for k in ('name', 'model', 'receiver_model')):
                raise ValueError('Station names and models required')
            station_ids.add(sid)
            sensors.add(sensor)
    groups, grouped = set(), set()
    for location in value:
        children = {s['id']: s for s in location['stations']}
        for station in children.values():
            profile = station.get('rf_profile')
            if profile is not None and profile not in ('wh65b', 'wh32b'):
                raise ValueError('Unknown RF profile')
            if profile and station['receiver_model'] != {'wh65b':'Fineoffset-WH65B','wh32b':'Fineoffset-WH32B'}[profile]:
                raise ValueError('RF profile model mismatch')
        for group in location.get('physical_stations', []):
            gid = group['id']
            if not isinstance(gid,str) or not gid or gid in groups or gid in station_ids:
                raise ValueError('Physical station IDs must be globally unique')
            groups.add(gid)
            members = group['source_station_ids']
            if not isinstance(members,list) or not members or len(set(members)) != len(members):
                raise ValueError('Unique physical station sources required')
            if any(s not in children or s in grouped for s in members):
                raise ValueError('Physical source binding invalid')
            grouped.update(members)
            if not isinstance(group.get('name'),str) or not group['name']:
                raise ValueError('Physical station name required')
            routes = group['metric_sources']
            if not isinstance(routes,dict) or not routes or any(k not in CATALOG or v not in members for k,v in routes.items()):
                raise ValueError('Invalid physical metric ownership')
            capabilities = {'wh65b': {'wind_speed_ms','wind_gust_ms','wind_direction_deg','rain_total_mm','rain_known_mm','uv_raw','uv_index','illuminance_lux'}, 'wh32b': {'temperature_c','humidity_pct','pressure_hpa'}}
            for metric, owner in routes.items():
                profile = children[owner].get('rf_profile')
                if profile and metric not in capabilities[profile]:
                    raise ValueError('Metric conflicts with RF profile ownership')
            windows = group['freshness_seconds']
            if not isinstance(windows,dict) or set(windows) != set(members) or any(type(v) is not int or not 1 <= v <= 3600 for v in windows.values()):
                raise ValueError('Invalid source freshness window')
    return value


def load(path):
    with open(path, encoding='utf-8') as handle:
        return validate_registry(json.load(handle)['locations'])


def resolve(locations, packet):
    for location in locations:
        for station in location['stations']:
            if station.get('ingest_enabled', True) and (packet.get('model'), str(packet.get('id'))) == (station['receiver_model'], str(station['sensor_id'])):
                return station['id']
    raise ValueError('Unknown receiver model or sensor ID')


def source(locations, station_id):
    for loc in locations:
        for station in loc['stations']:
            if station['id'] == station_id:
                return station
    raise ValueError('Unknown source station')


def admit(locations, packet, trusted_context=None):
    if not isinstance(packet,dict):
        raise ValueError('Packet object required')
    station_id = resolve(locations, packet)
    station = source(locations, station_id)
    if station.get('rf_profile'):
        if type(packet.get('protocol')) is not int or packet['protocol'] != 78 or packet.get('mic') != 'CRC':
            raise ValueError('RF protocol or integrity rejected')
        context = trusted_context or {}
        if (context.get('transport') != 'local_collector' or context.get('model') != station['receiver_model'] or str(context.get('sensor_id')) != str(station['sensor_id']) or context.get('protocol') != 78 or not isinstance(context.get('decoder_build'),str) or not 1 <= len(context['decoder_build']) <= 128):
            raise ValueError('Trusted collector context required')
        utc(context.get('receiver_received_at_utc'))
    return station_id
