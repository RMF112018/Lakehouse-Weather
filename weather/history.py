"""Bounded UTC history summaries and calendar-aware range validation."""
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .domain import CATALOG, utc, stamp

class HistoryCapacityError(RuntimeError):
    """Safe public explanation for an explicitly bounded query budget."""


WIDTHS = (300, 3600, 86400)
PRESETS = {'4h':4, '8h':8, '12h':12, '24h':24, '48h':48, '3d':72, '7d':168, '10d':240, '30d':720, '60d':1440, '90d':2160, '180d':4320}


def local_utc(value, zone):
    wall = datetime.fromisoformat(value)
    if wall.tzinfo is not None:
        raise ValueError('Local wall time must not contain an offset')
    candidates = set()
    for fold in (0, 1):
        instant = wall.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if instant.astimezone(zone).replace(tzinfo=None) == wall:
            candidates.add(instant)
    if len(candidates) != 1:
        raise ValueError('Local time is ambiguous or nonexistent; specify explicit UTC bounds')
    return candidates.pop()


def request_range(query, location_zone, now=None, earliest=None):
    now = now or datetime.now(timezone.utc)
    def one(key, default=None):
        values = query.get(key, [default])
        if len(values) != 1:
            raise ValueError('Duplicate history parameter')
        return values[0]
    zone_name = one('timezone', location_zone)
    if zone_name != location_zone:
        raise ValueError('Timezone must match station location')
    zone = ZoneInfo(zone_name)
    limit = int(one('max_points', '600'))
    if not 2 <= limit <= 800:
        raise ValueError('max_points must be between 2 and 800')
    metric = one('metric')
    if metric is not None and metric not in CATALOG:
        raise ValueError('Unknown metric')
    selection = one('range', 'custom' if 'start' in query or 'local_start' in query else '24h')
    if 'hours' in query:
        if 'range' in query:
            raise ValueError('Choose range or hours')
        hours = int(one('hours'))
        if not 1 <= hours <= 168:
            raise ValueError('Legacy hours must be between 1 and 168')
        start, end = now-timedelta(hours=hours), now
    elif selection == 'custom':
        if 'local_start' in query or 'local_end' in query:
            if 'start' in query or 'end' in query:
                raise ValueError('Choose local or UTC bounds')
            start = local_utc(one('local_start'), zone)
            end = local_utc(one('local_end'), zone)
        else:
            start, end = utc(one('start')), utc(one('end'))
    elif selection in PRESETS:
        end, start = now, now-timedelta(hours=PRESETS[selection])
    elif selection in ('1y', '5y', '10y'):
        years = int(selection[:-1])
        local = now.astimezone(zone)
        try:
            start = local.replace(year=local.year-years).astimezone(timezone.utc)
        except ValueError:  # leap day
            start = local.replace(year=local.year-years, day=28).astimezone(timezone.utc)
        end = now
    elif selection == 'all':
        start, end = earliest or now-timedelta(hours=24), now
    else:
        raise ValueError('Unknown history range')
    if end <= start or end > now+timedelta(minutes=5) or start.year < 1970:
        raise ValueError('Invalid history bounds')
    if selection != 'custom' and selection != 'all' and any(k in query for k in ('start','end','local_start','local_end')):
        raise ValueError('Bounds require custom range')
    return start, end, limit, metric, zone_name


def bucket(at, width):
    return datetime.fromtimestamp(math.floor(at.timestamp()/width)*width, timezone.utc)


def rain_empty():
    return {'count':0,'known_mm':0.0,'unknown_intervals':0,'reset_count':0,'gap_count':0,'first_counter':None,'last_counter':None,'first_at':None,'last_at':None}


def rain_merge(left, right):
    if not left.get('count'): return dict(right)
    if not right.get('count'): return dict(left)
    if right['last_at'] < left['first_at']:
        return rain_merge(right,left)
    result=rain_empty()
    gap=(utc(right['first_at'])-utc(left['last_at'])).total_seconds()
    reset=right['first_counter']<left['last_counter']
    # Overlapping partials occur only in the provisional incremental update;
    # insert repairs that bucket from raw rows before transaction commit.
    contiguous=0<=gap<=900 and not reset
    result.update(count=left['count']+right['count'],known_mm=left['known_mm']+right['known_mm']+(right['first_counter']-left['last_counter'] if contiguous else 0),
                  unknown_intervals=left['unknown_intervals']+right['unknown_intervals']-(1 if contiguous else 0),reset_count=left['reset_count']+right['reset_count']+int(reset),gap_count=left['gap_count']+right['gap_count']+int(gap>900),
                  first_counter=left['first_counter'],first_at=left['first_at'],last_counter=right['last_counter'],last_at=right['last_at'])
    return result


def rain_stat(rain):
    known_intervals=max(0,rain['count']-rain['unknown_intervals'])
    return {'count':known_intervals,'sample_count':rain['count'],'sum':round(rain['known_mm'],6) if known_intervals else None,'min':None,'max':None,'mean':None,'first':None,'last':None,'first_at':rain['first_at'],'last_at':rain['last_at'],
            'unknown_intervals':rain['unknown_intervals'],'reset_count':rain['reset_count'],'gap_count':rain['gap_count'],'partial':True}


def empty():
    return {'observation_count': 0, 'first_at': None, 'last_at': None, 'metrics': {},'rain':rain_empty()}


def single(row):
    at = row['observed_at']
    summary = {'observation_count': 1, 'first_at': at, 'last_at': at, 'metrics': {},'rain':rain_empty()}
    if row.get('rain_total_mm') is not None:
        summary['rain'].update(count=1,unknown_intervals=1,first_counter=row['rain_total_mm'],last_counter=row['rain_total_mm'],first_at=at,last_at=at)
    for key, spec in CATALOG.items():
        value = row.get(key)
        if value is None:
            continue
        stat = {'count':1, 'first':value, 'last':value, 'first_at':at, 'last_at':at}
        if spec['kind'] != 'status':
            stat.update(min=value, max=value)
            if spec['kind'] not in ('raw_counter', 'cumulative_counter'):
                stat['sum'] = value
            if spec['kind'] == 'circular':
                stat.update(sin=math.sin(math.radians(value)), cos=math.cos(math.radians(value)))
        summary['metrics'][key] = stat
    return summary


def merge(left, right):
    """Associative; the raw INSERT dedup gate ensures exactly-once contribution."""
    if not right['observation_count']:
        return left
    left['rain'] = rain_merge(left.get('rain',rain_empty()), right.get('rain',rain_empty()))
    left['observation_count'] += right['observation_count']
    left['first_at'] = min(left['first_at'] or right['first_at'], right['first_at'])
    left['last_at'] = max(left['last_at'] or right['last_at'], right['last_at'])
    for key, stat in right['metrics'].items():
        if key not in left['metrics']:
            left['metrics'][key] = dict(stat)
            continue
        target = left['metrics'][key]
        target['count'] += stat['count']
        if stat['first_at'] < target['first_at']:
            target.update(first=stat['first'], first_at=stat['first_at'])
        if stat['last_at'] > target['last_at']:
            target.update(last=stat['last'], last_at=stat['last_at'])
        if 'min' in stat:
            target['min'], target['max'] = min(target['min'], stat['min']), max(target['max'], stat['max'])
        for accumulator in ('sum','sin','cos'):
            if accumulator in stat:
                target[accumulator] += stat[accumulator]
    return left


def public_stat(stat, kind):
    if not stat:
        return {key: (0 if key == 'count' else None) for key in ('count','min','max','mean','first','last','first_at','last_at')}
    result = {key:stat.get(key) for key in ('count','min','max','first','last','first_at','last_at')}
    if kind == 'circular':
        result['mean'] = None if math.hypot(stat['sin'], stat['cos']) < 1e-9 else math.degrees(math.atan2(stat['sin'], stat['cos'])) % 360
    else:
        result['mean'] = stat['sum']/stat['count'] if 'sum' in stat else None
    return result


def output_width(start,end,max_points,source_width):
    return max(source_width,math.ceil((end-start).total_seconds()/((max_points-1)*source_width))*source_width)


def render(station_id, zone, start, end, max_points, metric, pieces, source_width):
    duration = (end-start).total_seconds()
    width = output_width(start,end,max_points,source_width)
    # Epoch-aligned widths; allocating a slot for the initial partial bucket
    # guarantees the point cap even when request start is not bucket-aligned.
    first = bucket(start,width)
    count = math.ceil((end-first).total_seconds()/width)
    points = {stamp(first+timedelta(seconds=index*width)):empty() for index in range(count)}
    summary = empty()
    for at, partial in sorted(pieces,key=lambda item:item[0]):
        key = stamp(bucket(at,width))
        if key in points:
            merge(points[key], partial)
            merge(summary, partial)
    selected = [metric] if metric else list(CATALOG)
    output, legacy = [], []
    prior_rain = rain_empty()
    for at, stats in sorted(points.items()):
        values = {key:public_stat(stats['metrics'].get(key), CATALOG[key]['kind']) for key in selected}
        current_rain=stats.get('rain',rain_empty())
        cumulative=rain_merge(prior_rain,current_rain)
        point_rain=dict(current_rain)
        if current_rain['count'] and prior_rain['count']:
            point_rain['known_mm']=cumulative['known_mm']-prior_rain['known_mm']
            for name in ('unknown_intervals','reset_count','gap_count'):
                point_rain[name]=cumulative[name]-prior_rain[name]
        if 'rain_known_mm' in selected:
            values['rain_known_mm']=rain_stat(point_rain)
        prior_rain=cumulative
        output.append({'observed_at':at,'observation_count':stats['observation_count'],'metrics':values})
        flat = {'observed_at':at, 'observation_count':stats['observation_count']}
        for key, value in values.items():
            kind = CATALOG[key]['kind']
            flat[key] = value['sum'] if kind == 'accumulation' else value['max'] if kind == 'maximum' else value['last'] if kind in ('raw_counter','cumulative_counter','status') else value['mean']
        flat['rain_interval_mm'] = None
        legacy.append(flat)
    catalog = {key:{**spec, 'available': key in summary['metrics'], 'count':summary['metrics'].get(key,{}).get('count',0)} for key,spec in CATALOG.items()}
    rain=summary.get('rain',rain_empty())
    catalog['rain_known_mm'].update(available=rain['count']>rain['unknown_intervals'],count=max(0,rain['count']-rain['unknown_intervals']))
    public_summary={key:rain_stat(rain) if key=='rain_known_mm' else public_stat(summary['metrics'].get(key),CATALOG[key]['kind']) for key in selected}
    first_at, last_at = summary['first_at'], summary['last_at']
    return {'station_id':station_id,'timezone':zone,'start':stamp(start),'end':stamp(end),
            'actual_start':first_at,'actual_end':last_at,'source_resolution_seconds':source_width,'bucket_seconds':width,
            'total_observations':summary['observation_count'],'coverage':{'temporal_span_fraction':(utc(last_at)-utc(first_at)).total_seconds()/duration if first_at else 0, 'populated_buckets':sum(bool(p['metrics'].get(metric,{}).get('count',0)) if metric else bool(p['observation_count']) for p in output), 'observation_populated_buckets':sum(bool(s['observation_count']) for s in points.values()),'total_buckets':len(points)},
            'metrics':catalog,'summary':{'observation_count':summary['observation_count'],'first_at':first_at,'last_at':last_at,'metrics':public_summary},
            'points':output,'history':legacy}


def source_resolution(start,end):
    seconds=(end-start).total_seconds()
    return 300 if seconds<=86400 else 3600 if seconds<=90*86400 else 86400
