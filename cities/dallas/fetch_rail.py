"""Fetch DART's rail lines and stations from its GTFS feed into raw/dart_rail.json: light rail (Red, Blue, Green,
Orange), the Dallas Streetcar (route_type 0), and the Silver Line and Trinity Railway Express (route_type 2).
Runs in GitHub Actions (fetch-dallas.yml)."""
import csv, io, os, sys, zipfile
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import *

URLS = ['https://www.dart.org/transitdata/latest/google_transit.zip', 'https://www.dart.org/transitdata/google_transit.zip']


def dart():
    for u in URLS:
        try:
            z = zipfile.ZipFile(io.BytesIO(get(u, tries=2))); print('  feed', u); break
        except Exception as e:
            print('  feed failed', u, e)
    else:
        raise RuntimeError('no DART feed')
    rd = lambda n: list(csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig')))
    routes = {r['route_id']: r for r in rd('routes.txt') if r['route_type'] in ('0', '1', '2')}
    print('  rail routes:', [(r['route_short_name'], r['route_long_name'], r['route_type'], r.get('route_color')) for r in routes.values()])
    trips = [t for t in rd('trips.txt') if t['route_id'] in routes]
    shape_n = Counter((t['route_id'], t['shape_id']) for t in trips)
    want = {s for _, s in shape_n}
    shapes = defaultdict(list)
    for p in rd('shapes.txt'):
        if p['shape_id'] in want:
            shapes[p['shape_id']].append((int(p['shape_pt_sequence']), round(float(p['shape_pt_lon']), 6), round(float(p['shape_pt_lat']), 6)))
    trip_ids = {t['trip_id']: t['route_id'] for t in trips}
    stop_routes = defaultdict(set)
    for st in rd('stop_times.txt'):
        r = trip_ids.get(st['trip_id'])
        if r: stop_routes[st['stop_id']].add(r)
    stops = {s['stop_id']: s for s in rd('stops.txt')}
    stations = {}
    for sid, rs in stop_routes.items():
        s = stops[sid]; key = s.get('parent_station') or sid
        p = stops.get(key, s)
        st = stations.setdefault(key, {'id': key, 'name': p['stop_name'], 'lon': float(p['stop_lon']), 'lat': float(p['stop_lat']), 'routes': set()})
        st['routes'] |= rs
    feed = rd('feed_info.txt') if 'feed_info.txt' in z.namelist() else []
    save('dart_rail.json', {
        'feed': feed[:1],
        'routes': {rid: {'short': r['route_short_name'], 'long': r['route_long_name'], 'type': r['route_type'], 'color': r.get('route_color', ''),
                         'shapes': {sid: [[x, y] for _, x, y in sorted(shapes[sid])] for (ri, sid) in shape_n if ri == rid},
                         'counts': {sid: c for (ri, sid), c in shape_n.items() if ri == rid}} for rid, r in routes.items()},
        'stations': [dict(s, routes=sorted(s['routes'])) for s in stations.values()]})


step('dart rail', dart)
print('FAILED:', FAILED or 'none')
