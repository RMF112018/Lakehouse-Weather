"""Read-only physical installation projection; source archives stay separate."""
from datetime import timedelta
from .domain import CATALOG, utc


def assemble(group, stations, store, now):
    sources = {s['id']:s for s in stations}
    metrics, diagnostics = {}, []
    for sid in group['source_station_ids']:
        source = sources[sid]
        latest = store.latest(sid)
        window = group['freshness_seconds'][sid]
        keys = [key for key,owner in group['metric_sources'].items() if owner == sid]
        current = store.current_metrics(sid,keys,now-timedelta(seconds=window),now)
        last_seen = latest['observed_at'] if latest else None
        source_age = max(0,(now-utc(last_seen)).total_seconds()) if last_seen else None
        diagnostics.append({'id':sid,'name':source['name'],'model':source['model'],'last_seen':last_seen,'stale':source_age is None or source_age > window or utc(last_seen) > now,'status':'missing' if not latest else 'clock_skew' if utc(last_seen) > now else 'stale' if source_age > window else 'fresh','observation':latest})
        for key in keys:
            field = current.get(key)
            if field is None and latest and utc(latest['observed_at']) <= now and latest.get(key) is not None:
                field = {'value':latest[key],'observed_at':latest['observed_at'],'provenance':latest.get('provenance',{})}
            at = field['observed_at'] if field else None
            age = max(0,(now-utc(at)).total_seconds()) if at else None
            reason = field.get('unavailable_reason') if field else ('never_seen_source' if not latest else 'clock_skew' if utc(last_seen)>now else latest.get('unavailable_reasons',{}).get(key,'not_observed_in_window'))
            value = field.get('value') if field else None
            metrics[key] = {'value':value,'unit':CATALOG[key]['unit'],'source_station_id':sid,'source_model':source['receiver_model'],'source_sensor_id':source['sensor_id'],'observed_at_utc':at,'receiver_received_at_utc':field.get('provenance',{}).get('receiver_received_at_utc') if field else None,'last_seen':last_seen,'age_seconds':age,'freshness':'missing' if value is None else 'fresh' if age <= window else 'stale','freshness_seconds':window,'unavailable_reason':reason,'history':{'physical_station_id':group['id'],'metric':key}}
    states = [m['freshness'] for m in metrics.values()]
    status = 'fresh' if states and all(s=='fresh' for s in states) else 'partial' if 'fresh' in states else 'stale' if 'stale' in states else 'missing'
    return {'id':group['id'],'name':group['name'],'model':'Physical weather installation','status':status,'metrics':metrics,'sources':diagnostics}
