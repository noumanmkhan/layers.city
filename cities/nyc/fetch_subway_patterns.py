"""Subway service patterns for the fact sheets -> raw/subway_patterns.json (committed).

engine/profiles/build.py counts stops and changes from each district's station to the hubs along these: for each
service (the A, the 6), each run it makes in the middle of a weekday (the A to Far Rockaway, the A to Lefferts Blvd),
the stations it calls at in order, as the station points of docs/nyc/data/subway_stations.geojson (the map's
stations, where one complex's platforms are joined). Midday trips only, so late-night local runs and rush-hour
variants don't add stops a daytime rider never sees. A run must make at least a tenth as many trips as the
service's busiest one to count. Also the free transfers between stations the map keeps apart, as pairs of points.

Source: MTA subway GTFS (the static schedule). Run in Actions (fetch-nyc.yml): the sandbox can't reach it.
"""
import csv, io, json, math, os, urllib.request, zipfile
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip'
SERVICE = {'GS': 'S', 'FS': 'S', 'H': 'S', 'FX': 'F', '6X': '6', '7X': '7', 'SI': 'SIR'}

z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(urllib.request.Request(URL, headers={'User-Agent': 'city-layers/1.0'}), timeout=300).read()))
table = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), encoding='utf-8-sig'))

stops = {s['stop_id']: s for s in table('stops.txt')}
parent = lambda sid: stops[sid].get('parent_station') or sid
weekday = {c['service_id'] for c in table('calendar.txt') if c.get('wednesday') == '1'} if 'calendar.txt' in z.namelist() else None
routes = {r['route_id']: (r.get('route_short_name') or r['route_id']).strip() for r in table('routes.txt')}
trips = {t['trip_id']: t['route_id'] for t in table('trips.txt') if weekday is None or t['service_id'] in weekday}

seqs = defaultdict(list)
for st in table('stop_times.txt'):
    if st['trip_id'] in trips:
        seqs[st['trip_id']].append((int(st['stop_sequence']), st['departure_time'] or st['arrival_time'], parent(st['stop_id'])))

runs = defaultdict(Counter)   # service -> Counter(tuple of parent stations)
for tid, s in seqs.items():
    s.sort()
    h = int(s[0][1].split(':')[0])
    if not 10 <= h < 15: continue
    svc = SERVICE.get(routes[trips[tid]], routes[trips[tid]])
    runs[svc][tuple(p for _, _, p in s)] += 1

# Each GTFS station to the map's station point: the nearest one within 300 m.
pts = [f['geometry']['coordinates'] for f in json.load(open(os.path.join(HERE, '..', '..', 'docs', 'nyc', 'data', 'subway_stations.geojson')))['features']]
KX, KY = 84.4, 111.2


def point(pid):
    s = stops[pid]; x, y = float(s['stop_lon']), float(s['stop_lat'])
    d, p = min((math.hypot((x - q[0]) * KX, (y - q[1]) * KY), q) for q in pts)
    return p if d < 0.3 else None


at = {}
patterns, missing = [], set()
for svc, c in sorted(runs.items()):
    top = max(c.values())
    for seq, n in c.items():
        if n < top * 0.1: continue
        out = []
        for pid in seq:
            if pid not in at: at[pid] = point(pid)
            if at[pid] is None: missing.add(stops[pid]['stop_name']); continue
            if not out or out[-1] != at[pid]: out.append(at[pid])
        if len(out) > 1:
            patterns.append({'line': svc, 'trips': n, 'stops': out})
# Free transfers between stations the map keeps apart (Times Sq-42 St and 42 St-Port Authority): pairs of points.
transfers = set()
if 'transfers.txt' in z.namelist():
    for t in table('transfers.txt'):
        a, b = parent(t['from_stop_id']), parent(t['to_stop_id'])
        if a == b or a not in stops or b not in stops: continue
        for pid in (a, b):
            if pid not in at: at[pid] = point(pid)
        if at[a] and at[b] and at[a] != at[b]: transfers.add(tuple(sorted((tuple(at[a]), tuple(at[b])))))
json.dump({'source': 'MTA subway GTFS (' + URL + '), weekday trips leaving 10:00–15:00', 'asof': date.today().isoformat(),
           'patterns': patterns, 'transfers': [list(map(list, t)) for t in sorted(transfers)]}, open(os.path.join(HERE, 'raw', 'subway_patterns.json'), 'w'), separators=(',', ':'))
print(len(patterns), 'patterns,', len(transfers), 'transfers, for', len(runs), 'services:', sorted(runs), '· stations not on the map:', sorted(missing))
