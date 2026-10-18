"""Best-case drive minutes and road distance from each GTA origin in venues.json to each venue, for the
Venues pages' "From …" picker.

Usage:  python3 cities/toronto/fetch_venue_drives.py
Reads:  cities/toronto/venues.json (origins, venues), docs/toronto/data/go_stations.geojson (origin points)
Writes: cities/toronto/raw/venue_drives.json   {asof, origins, venues, min[origin][venue], km[origin][venue]}

One OSRM table request (the public demo server's car profile: posted speeds on empty roads, the same
source and caveat as the map's suburban lens). Run it in Actions or on a computer with normal internet;
most sandboxes can't reach the server. The road distance feeds the taxi-meter estimate on the pages.
Data: © OpenStreetMap contributors, ODbL.
"""
import json, os, sys, urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
cfg = json.load(open(os.path.join(HERE, 'venues.json')))
go = {f['properties']['name']: f['geometry']['coordinates']
      for f in json.load(open(os.path.join(ROOT, 'docs', 'toronto', 'data', 'go_stations.geojson')))['features']}

origins = []
for o in cfg['origins']:
    at = o.get('at') or go.get(o['via'])
    if not at:
        sys.exit(f"origin {o['name']}: no coordinates and {o['via']} is not in go_stations.geojson")
    origins.append((o['name'], at))
venues = [(v['slug'], v['at']) for v in cfg['venues']]
coords = ';'.join(f'{lon:.5f},{lat:.5f}' for _, (lon, lat) in origins + venues)
n = len(origins)
url = ('https://router.project-osrm.org/table/v1/driving/' + coords +
       '?sources=' + ';'.join(map(str, range(n))) + '&destinations=' + ';'.join(map(str, range(n, n + len(venues)))) +
       '&annotations=duration,distance')
req = urllib.request.Request(url, headers={'User-Agent': 'city-layers/1.0 (https://layers.city; go@layers.city)'})
data = json.loads(urllib.request.urlopen(req, timeout=120).read())
if data.get('code') != 'Ok':
    sys.exit(f"OSRM: {data.get('code')} {data.get('message')}")
mins = [[round(s / 60) if s is not None else None for s in row] for row in data['durations']]
kms = [[round(m / 1000, 1) if m is not None else None for m in row] for row in data['distances']]
out = os.path.join(HERE, 'raw', 'venue_drives.json')
json.dump({'asof': date.today().isoformat(), 'origins': [o for o, _ in origins], 'venues': [s for s, _ in venues],
           'min': mins, 'km': kms}, open(out, 'w'), separators=(',', ':'))
print(f'{len(origins)} origins x {len(venues)} venues -> {os.path.relpath(out, ROOT)}')
