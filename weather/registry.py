"""Explicit station identity; unrecognized radio packets never create stations."""
import json
import math
from zoneinfo import ZoneInfo


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
        for key, bound in [('latitude', 90), ('longitude', 180)]:
            coordinate = location[key]
            if type(coordinate) not in (int, float) or not math.isfinite(coordinate) or abs(coordinate) > bound:
                raise ValueError('Invalid coordinate')
        for station in location['stations']:
            sid = station['id']
            sensor = (station['receiver_model'], str(station['sensor_id']))
            if not isinstance(sid, str) or not sid or sid in station_ids or sensor in sensors:
                raise ValueError('Station and receiver identities must be unique')
            if not all(isinstance(station[k], str) and station[k] for k in ('name', 'model', 'receiver_model')):
                raise ValueError('Station names and models required')
            station_ids.add(sid)
            sensors.add(sensor)
    return value


def load(path):
    with open(path, encoding='utf-8') as handle:
        return validate_registry(json.load(handle)['locations'])


def resolve(locations, packet):
    for location in locations:
        for station in location['stations']:
            if (packet.get('model'), str(packet.get('id'))) == (station['receiver_model'], str(station['sensor_id'])):
                return station['id']
    raise ValueError('Unknown receiver model or sensor ID')
