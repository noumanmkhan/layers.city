"""Scout: can the Routes page show live "next bus in 6, 18, 32 min" from the TTC's GTFS-realtime trip updates?

Fetches https://gtfsrt.ttc.ca/trips/update (and vehicle positions) three times, 30 s apart, and records what a
live-arrivals feature would depend on: the feed's size and refresh rate, its HTTP headers (CORS and caching,
whether a browser could read it directly), how far ahead its predictions reach, whether each stop_time_update
carries a stop_id and an absolute time, and how long decoding takes (Python here, and in Node with the same
protobuf library a Cloudflare Worker would use). Prints a sample of predictions for a few known stops.
Writes cities/toronto/raw/scouting/realtime/summary.json. Runs in Actions (scout-toronto.yml).
"""
import json, os, subprocess, sys, time, urllib.request
from collections import Counter

subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'gtfs-realtime-bindings'], check=False)
from google.transit import gtfs_realtime_pb2

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw', 'scouting', 'realtime')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Layers.City (go@layers.city)', 'Origin': 'https://layers.city'}
BASE = 'https://gtfsrt.ttc.ca'
STOPS = {'8344': '49 Thorncliffe Park Dr', '8361': 'Thorncliffe Park Dr East at Overlea Blvd', '2977': '46 Overlea Blvd'}


def get(url):
    t = time.time()
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        body = r.read()
        return body, dict(r.headers), round(time.time() - t, 2)


summary = {'runs': []}
for run in range(3):
    if run: time.sleep(30)
    body, headers, secs = get(BASE + '/trips/update?format=binary')
    t = time.time(); feed = gtfs_realtime_pb2.FeedMessage(); feed.ParseFromString(body); dec = round(time.time() - t, 3)
    now = int(time.time())
    trips = [e.trip_update for e in feed.entity if e.HasField('trip_update')]
    stus = [u for tu in trips for u in tu.stop_time_update]
    with_time = [u for u in stus if (u.HasField('arrival') and u.arrival.time) or (u.HasField('departure') and u.departure.time)]
    horizon = [((u.arrival.time or u.departure.time) - now) / 60 for u in with_time]
    routes = Counter(tu.trip.route_id for tu in trips)
    r = {'bytes': len(body), 'download_s': secs, 'decode_s': dec, 'header_timestamp': feed.header.timestamp,
         'age_s': now - feed.header.timestamp, 'trips': len(trips), 'stop_time_updates': len(stus),
         'with_absolute_time': len(with_time), 'with_stop_id': sum(1 for u in stus if u.stop_id),
         'per_trip_median': sorted(len(tu.stop_time_update) for tu in trips)[len(trips) // 2] if trips else 0,
         'horizon_min': {'min': round(min(horizon), 1), 'p50': round(sorted(horizon)[len(horizon) // 2], 1), 'max': round(max(horizon), 1)} if horizon else None,
         'routes': len(routes), 'with_vehicle': sum(1 for tu in trips if tu.vehicle.id),
         'schedule_relationship': dict(Counter(gtfs_realtime_pb2.TripDescriptor.ScheduleRelationship.Name(tu.trip.schedule_relationship) for tu in trips))}
    if run == 0:
        r['headers'] = {k: v for k, v in headers.items() if k.lower() in ('content-type', 'content-length', 'cache-control', 'etag', 'last-modified', 'access-control-allow-origin', 'access-control-allow-methods', 'vary', 'age', 'expires', 'server')}
        sample = {}
        for sid, name in STOPS.items():
            hits = []
            for tu in trips:
                for u in tu.stop_time_update:
                    if u.stop_id == sid:
                        ts = u.arrival.time or u.departure.time
                        if ts: hits.append([tu.trip.route_id, tu.trip.trip_id, round((ts - now) / 60, 1), tu.trip.direction_id, tu.vehicle.id])
            sample[f'{sid} {name}'] = sorted(hits, key=lambda h: h[2])[:12]
        r['sample'] = sample
        one = trips[0] if trips else None
        if one: r['example_trip'] = str(one)[:1500]
    summary['runs'].append(r)
    print(json.dumps({k: v for k, v in r.items() if k not in ('sample', 'example_trip')}, indent=1))
    if run == 0:
        for k, v in r['sample'].items(): print(k, v)
        open(os.path.join(OUT, 'trips_update.bin'), 'wb').write(body)

body, headers, secs = get(BASE + '/vehicles/position?format=binary')
vf = gtfs_realtime_pb2.FeedMessage(); vf.ParseFromString(body)
summary['vehicles'] = {'bytes': len(body), 'entities': len(vf.entity), 'age_s': int(time.time()) - vf.header.timestamp}
print('vehicles', summary['vehicles'])

# Decode time in Node, with the protobuf library a Cloudflare Worker would bundle.
js = r"""
const fs = require('fs'); const b = fs.readFileSync(process.argv[2]);
const { transit_realtime } = require('gtfs-realtime-bindings');
let t = process.hrtime.bigint(); const f = transit_realtime.FeedMessage.decode(b); let ms = Number(process.hrtime.bigint() - t) / 1e6;
t = process.hrtime.bigint(); const f2 = transit_realtime.FeedMessage.decode(b); const ms2 = Number(process.hrtime.bigint() - t) / 1e6;
console.log(JSON.stringify({node_decode_ms_first: Math.round(ms), node_decode_ms_warm: Math.round(ms2), entities: f.entity.length}));
"""
try:
    d = os.path.join(OUT, 'node'); os.makedirs(d, exist_ok=True)
    subprocess.run(['npm', 'install', '--silent', '--prefix', d, 'gtfs-realtime-bindings'], check=True, timeout=300)
    open(os.path.join(d, 'decode.js'), 'w').write(js)
    res = subprocess.run(['node', os.path.join(d, 'decode.js'), os.path.join(OUT, 'trips_update.bin')], capture_output=True, text=True, timeout=120,
                         env=dict(os.environ, NODE_PATH=os.path.join(d, 'node_modules')))
    print('node', res.stdout.strip(), res.stderr.strip()[-500:])
    summary['node'] = json.loads(res.stdout.strip() or '{}')
except Exception as e:
    print('node decode failed', e)
finally:
    subprocess.run(['rm', '-rf', os.path.join(OUT, 'node'), os.path.join(OUT, 'trips_update.bin')])

json.dump(summary, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1)
