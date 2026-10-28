"""Scout: where Lines 5 Eglinton and 6 Finch West show up in the TTC's live feeds, if at all.

The Routes page's live times work for buses, streetcars and the subway, but came back empty for every Line 5 and 6
platform. This looks through every realtime feed (trip updates, subway trips, vehicle positions) for trips or
vehicles whose route_id or trip_id could be the LRT lines, and for any of the LRT platform stop ids, and prints
what it finds. Writes cities/toronto/raw/scouting/lrt_live/summary.json. Runs in Actions (scout-toronto.yml).
"""
import json, os, subprocess, sys, urllib.request
from collections import Counter

subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'gtfs-realtime-bindings'], check=False)
from google.transit import gtfs_realtime_pb2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'scouting', 'lrt_live')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Layers.City (go@layers.city)'}
rapid = json.load(open(os.path.join(HERE, 'raw', 'surface', 'rapid_stops.json')))['stops']
lrt_ids = {s[0] for s in rapid if set(s[4]) & {'5', '6'}}
print('LRT platform ids in the schedule:', len(lrt_ids), sorted(lrt_ids)[:12])

summary = {}
for name in ('trips/update', 'trips/subway', 'vehicles/position', 'trips/modified_update', 'trips/detour'):
    try:
        with urllib.request.urlopen(urllib.request.Request(f'https://gtfsrt.ttc.ca/{name}?format=binary', headers=UA), timeout=60) as r:
            body = r.read()
        f = gtfs_realtime_pb2.FeedMessage(); f.ParseFromString(body)
    except Exception as e:
        print(name, 'failed', e); continue
    routes = Counter(); hits = []; samples = []
    for e in f.entity:
        tu = e.trip_update if e.HasField('trip_update') else None
        vp = e.vehicle if e.HasField('vehicle') else None
        trip = tu.trip if tu else (vp.trip if vp else None)
        rid = trip.route_id if trip else ''
        routes[rid] += 1
        sids = [u.stop_id for u in tu.stop_time_update] if tu else ([vp.stop_id] if vp and vp.stop_id else [])
        if rid in ('5', '6') or set(sids) & lrt_ids or (trip and trip.route_id.startswith(('5', '6')) and len(trip.route_id) <= 3 and trip.route_id in ('5', '6', '905', '906')):
            hits.append({'id': e.id, 'route': rid, 'trip': trip.trip_id if trip else '', 'stops': sids[:6]})
            if len(samples) < 2: samples.append(str(e)[:1200])
    summary[name] = {'entities': len(f.entity), 'routes': dict(routes.most_common(400)), 'lrt_hits': hits[:20], 'lrt_hit_count': len(hits)}
    print(name, len(f.entity), 'entities;', 'routes 5/6:', routes.get('5'), routes.get('6'), '; LRT hits:', len(hits))
    for s in samples: print(s)
    print('  route ids:', sorted(routes, key=lambda x: (len(x), x))[:400])
json.dump(summary, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1)
