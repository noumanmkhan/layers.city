"""Download a city's walking network from OpenStreetMap (unreleased: profiles branch only).

Usage:  python3 engine/profiles/fetch_walk.py toronto
Writes: cities/<city>/raw/walk_network.json   (not committed: large, and rebuilt from OSM on demand)
        {asof, nodes: [[lon, lat], ...], edges: [[a, b], ...]}   a and b index into nodes
        cities/<city>/raw/walk_extras.json    (not committed)
        {asof, entrances: [[lon, lat], ...], parks: [[[lon, lat], ...], ...]}
        Subway entrances, so walks end at the nearest door rather than the middle of the platforms,
        and park outlines, so "nearest park" means its nearest edge rather than its centre.

Run it on a computer with normal internet (it fails in most sandboxes). A whole city is too big for one
Overpass request, so the city's box is cut into TILES_X x TILES_Y tiles, fetched one at a time with a
pause between them, from the first server that answers. Each tile is saved under
cities/<city>/raw/walk_tiles/ as it arrives, so if a run stops partway, running it again carries on
from the missing tiles. Delete that folder to fetch everything fresh. Expect 5 to 15 minutes for Toronto.

What counts as walkable: streets other than expressways, plus footways, paths, steps, pedestrian
areas, cycle tracks, laneways and service roads, minus anything tagged foot=no or private.

Data: © OpenStreetMap contributors, ODbL (credit it wherever the walk times appear).
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: fetch_walk.py <city>')
RAW = os.path.join(ROOT, 'cities', city, 'raw')
TILES = os.path.join(RAW, 'walk_tiles')
OUT = os.path.join(RAW, 'walk_network.json')
DATA = os.path.join(ROOT, 'docs', city, 'data')
SERVERS = ['https://overpass-api.de/api/interpreter',
           'https://overpass.private.coffee/api/interpreter',
           'https://overpass.kumi.systems/api/interpreter']
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city; go@layers.city)'}
TILES_X, TILES_Y = 4, 3
PAUSE_S = 5          # between tiles, to be polite to a free shared service

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


def network_query(s, w, n, e):
    return f"""[out:json][timeout:300];
(way["highway"~"^({WALKABLE})$"]["foot"!~"^(no|private)$"]["access"!~"^(no|private)$"]({s:.5f},{w:.5f},{n:.5f},{e:.5f}););
out skel qt; >; out skel qt;"""


def extras_query(s, w, n, e):
    b = f'{s:.5f},{w:.5f},{n:.5f},{e:.5f}'
    return f"""[out:json][timeout:300];
(node["railway"="subway_entrance"]({b}); way["leisure"="park"]({b}); relation["leisure"="park"]({b}););
out geom qt;"""


def fetch(q):
    body = urllib.parse.urlencode({'data': q}).encode()
    last = None
    for attempt in range(6):
        url = SERVERS[attempt % len(SERVERS)]
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=UA), timeout=360) as r:
                return json.loads(r.read())['elements']
        except Exception as err:
            last = err
            host = urllib.parse.urlparse(url).netloc
            wait = 20 * (attempt + 1)
            print(f'    {host}: {err}; trying again in {wait} s', flush=True)
            time.sleep(wait)
    sys.exit(f'Overpass kept failing ({last}). Run the same command again later: finished tiles are kept.')


S, W, N, E = city_bbox()
os.makedirs(TILES, exist_ok=True)
dy, dx = (N - S) / TILES_Y, (E - W) / TILES_X
print(f'{city}: walkable ways in {S:.3f},{W:.3f},{N:.3f},{E:.3f}, as {TILES_X * TILES_Y} tiles', flush=True)
def tiles(prefix, query, label):
    """Every tile's elements, fetching only the tiles not saved yet."""
    for r in range(TILES_Y):
        for c in range(TILES_X):
            name = os.path.join(TILES, f'{prefix}_{r}_{c}.json')
            tag = f'  {label} tile {r * TILES_X + c + 1}/{TILES_X * TILES_Y}'
            if os.path.exists(name):
                els = json.load(open(name))
                print(f'{tag}: already saved', flush=True)
            else:
                t = time.time()
                print(f'{tag}: fetching ...', flush=True)
                els = fetch(query(S + r * dy, W + c * dx, S + (r + 1) * dy, W + (c + 1) * dx))
                with open(name, 'w') as f:
                    json.dump(els, f, separators=(',', ':'))
                print(f'    {len(els):,} elements in {time.time() - t:.0f} s', flush=True)
                time.sleep(PAUSE_S)
            yield els


coords, ways = {}, []
for els in tiles('tile', network_query, 'streets'):
    for el in els:
        if el['type'] == 'node':
            coords[el['id']] = (el['lon'], el['lat'])
        elif el['type'] == 'way':
            ways.append(el.get('nodes', []))

# Ways that cross a tile edge come back in both tiles, whole; links are kept once.
index, nodes, edges = {}, [], set()


def node(osm_id):
    if osm_id not in index:
        index[osm_id] = len(nodes)
        lon, lat = coords[osm_id]
        nodes.append([round(lon, 6), round(lat, 6)])
    return index[osm_id]


for refs in ways:
    refs = [r for r in refs if r in coords]
    for a, b in zip(refs, refs[1:]):
        if a != b:
            i, j = node(a), node(b)
            edges.add((min(i, j), max(i, j)))

with open(OUT, 'w') as f:
    json.dump({'asof': date.today().isoformat(), 'source': 'OpenStreetMap (Overpass)',
               'nodes': nodes, 'edges': sorted(edges)}, f, separators=(',', ':'))
print(f'{city}: {len(nodes):,} nodes, {len(edges):,} links -> {os.path.relpath(OUT, ROOT)} '
      f'({os.path.getsize(OUT) / 1e6:.0f} MB)', flush=True)

# ---- subway entrances and park outlines -----------------------------------------------------------
entrances, parks = {}, {}
for els in tiles('extras', extras_query, 'entrances and parks'):
    for el in els:
        if el['type'] == 'node':
            entrances[el['id']] = [round(el['lon'], 6), round(el['lat'], 6)]
        elif el['type'] == 'way' and el.get('geometry'):
            parks[('w', el['id'])] = [[[round(p['lon'], 6), round(p['lat'], 6)] for p in el['geometry']]]
        elif el['type'] == 'relation':
            rings = [[[round(p['lon'], 6), round(p['lat'], 6)] for p in m['geometry']]
                     for m in el.get('members', []) if m.get('role') == 'outer' and m.get('geometry')]
            if rings:
                parks[('r', el['id'])] = rings
EXTRAS = os.path.join(RAW, 'walk_extras.json')
with open(EXTRAS, 'w') as f:
    json.dump({'asof': date.today().isoformat(), 'source': 'OpenStreetMap (Overpass)',
               'entrances': list(entrances.values()),
               'parks': [ring for rings in parks.values() for ring in rings]}, f, separators=(',', ':'))
print(f'{city}: {len(entrances):,} subway entrances, {len(parks):,} parks -> {os.path.relpath(EXTRAS, ROOT)}')
