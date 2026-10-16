"""Download a city's walking network from OpenStreetMap (unreleased: profiles branch only).

Usage:  python3 engine/profiles/fetch_walk.py toronto
Writes: cities/<city>/raw/walk_network.json   (not committed: large, and rebuilt from OSM on demand)
        {asof, nodes: [[lon, lat], ...], edges: [[a, b], ...]}   a and b index into nodes

Run it on a computer with normal internet (it fails in most sandboxes). One Overpass request, usually
one to three minutes for Toronto. Re-run it only when OSM's streets need refreshing (a few times a year);
walk_grid.py reads the saved file.

What counts as walkable: streets other than expressways, plus footways, paths, steps, pedestrian
areas, cycle tracks, laneways and service roads, minus anything tagged foot=no or private.

Data: © OpenStreetMap contributors, ODbL (credit it wherever the walk times appear).
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: fetch_walk.py <city>')
RAW = os.path.join(ROOT, 'cities', city, 'raw')
OUT = os.path.join(RAW, 'walk_network.json')
DATA = os.path.join(ROOT, 'docs', city, 'data')
URL = 'https://overpass-api.de/api/interpreter'
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city; go@layers.city)'}

WALKABLE = ('footway|path|pedestrian|steps|corridor|cycleway|track|living_street|residential|service|'
            'unclassified|tertiary|tertiary_link|secondary|secondary_link|primary|primary_link')


def city_bbox():
    """South, west, north, east of the city's neighbourhoods, plus about 1 km."""
    feats = json.load(open(os.path.join(DATA, 'neighbourhoods.geojson')))['features']
    xs, ys = [], []

    def walk(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1])
        else:
            for p in c:
                walk(p)
    for f in feats:
        walk(f['geometry']['coordinates'])
    pad = 0.012
    return min(ys) - pad, min(xs) - pad, max(ys) + pad, max(xs) + pad


s, w, n, e = city_bbox()
query = f"""[out:json][timeout:600][maxsize:2000000000];
(way["highway"~"^({WALKABLE})$"]["foot"!~"^(no|private)$"]["access"!~"^(no|private)$"]({s:.4f},{w:.4f},{n:.4f},{e:.4f}););
out skel qt; >; out skel qt;"""

print(f'{city}: asking Overpass for walkable ways in {s:.3f},{w:.3f},{n:.3f},{e:.3f} ...', flush=True)
body = urllib.parse.urlencode({'data': query}).encode()
for attempt in range(3):
    try:
        t = time.time()
        with urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=UA), timeout=900) as r:
            raw = r.read()
        break
    except Exception as err:
        if attempt == 2:
            sys.exit(f'Overpass failed: {err}. Try again in a few minutes (the server may be busy).')
        print(f'  {err}; retrying in 60 s', flush=True)
        time.sleep(60)
print(f'  {len(raw) / 1e6:.0f} MB in {time.time() - t:.0f} s; building the network ...', flush=True)

els = json.loads(raw)['elements']
coords = {el['id']: (el['lon'], el['lat']) for el in els if el['type'] == 'node'}
index, nodes, edges = {}, [], set()


def node(osm_id):
    if osm_id not in index:
        index[osm_id] = len(nodes)
        lon, lat = coords[osm_id]
        nodes.append([round(lon, 6), round(lat, 6)])
    return index[osm_id]


for el in els:
    if el['type'] != 'way':
        continue
    refs = [r for r in el.get('nodes', []) if r in coords]
    for a, b in zip(refs, refs[1:]):
        if a != b:
            i, j = node(a), node(b)
            edges.add((min(i, j), max(i, j)))

os.makedirs(RAW, exist_ok=True)
with open(OUT, 'w') as f:
    json.dump({'asof': date.today().isoformat(), 'source': 'OpenStreetMap (Overpass)',
               'nodes': nodes, 'edges': sorted(edges)}, f, separators=(',', ':'))
print(f'{city}: {len(nodes):,} nodes, {len(edges):,} links -> {os.path.relpath(OUT, ROOT)} '
      f'({os.path.getsize(OUT) / 1e6:.0f} MB)')
