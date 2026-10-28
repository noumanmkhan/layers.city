"""Scout: subway and LRT in the TTC's GTFS, for the Routes page (and why the schedule download keeps failing).

1. Lists every resource in the City's "TTC Routes and Schedules" CKAN package (name, format, URL, size) and tries
   each zip: the weekly fetch has been getting a 22-byte reply instead of the 29 MB file since October 27.
2. From the first good zip: the subway and LRT routes (route_type, short and long names, colour), how their
   platforms appear in stops.txt (ids, names, parent stations, codes), trips per direction with headsigns and
   shapes, and whether the platform ids match the ones the live subway feed uses (gtfsrt.ttc.ca/trips/subway).
Writes cities/toronto/raw/scouting/rapid/summary.json. Runs in Actions (scout-toronto.yml).
"""
import csv, io, json, os, subprocess, sys, urllib.request, zipfile
from collections import Counter, defaultdict

subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'gtfs-realtime-bindings'], check=False)
from google.transit import gtfs_realtime_pb2

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw', 'scouting', 'rapid')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Layers.City (go@layers.city)'}
PKG = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show?id=ttc-routes-and-schedules'
summary = {}


def get(url, timeout=600):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read(), dict(r.headers)


pkg = json.loads(get(PKG, 120)[0])['result']
res = [{'name': r.get('name'), 'format': r.get('format'), 'url': r.get('url'), 'size': r.get('size'),
        'modified': r.get('last_modified') or r.get('metadata_modified'), 'datastore': r.get('datastore_active')} for r in pkg['resources']]
summary['resources'] = res
for r in res: print('resource', r)

z = None
for r in res:
    u = r['url'] or ''
    if not ((r['format'] or '').lower() == 'zip' or u.lower().endswith('.zip')): continue
    try:
        body, h = get(u)
        print('download', u, len(body), 'bytes', h.get('Content-Type'))
        r['got'] = len(body)
        if len(body) < 1000: r['body'] = body[:200].decode('utf-8', 'replace'); print('  body:', r['body'])
        try:
            zz = zipfile.ZipFile(io.BytesIO(body)); r['files'] = zz.namelist()
            if 'stop_times.txt' in zz.namelist() and z is None: z = zz; summary['used'] = u
        except zipfile.BadZipFile:
            r['zip'] = 'bad'
    except Exception as e:
        r['error'] = str(e); print('  error', e)

if z is None:
    json.dump(summary, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1); sys.exit('no usable GTFS zip')


def rows(name):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))


routes = {r['route_id']: r for r in rows('routes.txt')}
summary['route_types'] = dict(Counter(r.get('route_type') for r in routes.values()))
rapid = {rid: r for rid, r in routes.items() if r.get('route_type') in ('1', '2') or r.get('route_short_name') in ('1', '2', '3', '4', '5', '6')}
summary['rapid_routes'] = list(rapid.values())
print('rapid routes', json.dumps(list(rapid.values()), indent=1))

trips = [t for t in rows('trips.txt') if t['route_id'] in rapid]
summary['rapid_trips'] = {rid: {'count': sum(1 for t in trips if t['route_id'] == rid),
                                'by_dir_headsign': Counter(f"{t.get('direction_id')}|{t.get('trip_headsign')}" for t in trips if t['route_id'] == rid).most_common(8),
                                'shapes': len({t.get('shape_id') for t in trips if t['route_id'] == rid})} for rid in rapid}
print('trips', json.dumps(summary['rapid_trips'], indent=1))
tids = {t['trip_id']: t for t in trips}

stop_ids = set()
seq = defaultdict(list)
for st in rows('stop_times.txt'):
    if st['trip_id'] in tids:
        stop_ids.add(st['stop_id'])
        if len(seq) < 400 or st['trip_id'] in seq: seq[st['trip_id']].append((int(st['stop_sequence']), st['stop_id'], st.get('arrival_time')))
stops = {s['stop_id']: s for s in rows('stops.txt') if s['stop_id'] in stop_ids or s['stop_id'] in {x.get('parent_station') for x in []}}
summary['rapid_stop_count'] = len(stop_ids)
summary['rapid_stop_sample'] = list(stops.values())[:25]
summary['stop_columns'] = list(next(iter(stops.values())).keys()) if stops else []
print('stops', len(stop_ids)); [print(' ', s) for s in list(stops.values())[:25]]
# One trip per route and direction, as stop names in order.
ex = {}
for tid, ss in seq.items():
    t = tids[tid]; key = (t['route_id'], t.get('direction_id'))
    if key in ex: continue
    ex[key] = [(i, sid, stops.get(sid, {}).get('stop_name'), at) for i, sid, at in sorted(ss)]
summary['example_trips'] = {f'{k[0]}|{k[1]}': v for k, v in ex.items()}
for k, v in ex.items(): print('trip', k, [x[2] for x in v][:40])

# The live subway feed's stop ids, against these.
try:
    body, _ = get('https://gtfsrt.ttc.ca/trips/subway?format=binary', 60)
    f = gtfs_realtime_pb2.FeedMessage(); f.ParseFromString(body)
    live = Counter(); lroutes = Counter(); ids = set()
    for e in f.entity:
        lroutes[e.trip_update.trip.route_id] += 1
        for u in e.trip_update.stop_time_update: ids.add(u.stop_id)
    summary['live'] = {'routes': dict(lroutes), 'stop_ids': len(ids), 'in_gtfs': len(ids & stop_ids), 'not_in_gtfs': sorted(ids - stop_ids)[:30],
                       'entity_ids': [e.id for e in f.entity][:10], 'direction_ids': dict(Counter(e.trip_update.trip.direction_id for e in f.entity))}
    print('live subway', summary['live'])
    body, _ = get('https://gtfsrt.ttc.ca/trips/update?format=binary', 60)
    f = gtfs_realtime_pb2.FeedMessage(); f.ParseFromString(body)
    lr = Counter(e.trip_update.trip.route_id for e in f.entity if e.trip_update.trip.route_id in rapid or e.trip_update.trip.route_id in ('5', '6'))
    summary['live_in_bus_feed'] = dict(lr)
    print('rapid routes in the bus/streetcar feed', dict(lr))
except Exception as e:
    print('live check failed', e)

json.dump(summary, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1, default=str)
