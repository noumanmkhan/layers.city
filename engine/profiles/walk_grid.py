"""Walking times from every spot in the city (unreleased: profiles branch only).

Usage:  python3 engine/profiles/walk_grid.py toronto
Reads:  cities/<city>/raw/walk_network.json    (from fetch_walk.py)
        cities/<city>/raw/walk_extras.json     (from fetch_walk.py: subway entrances and park outlines;
                                                without it, stations and parks are single points)
        docs/<city>/data/*                      (stations, stops, docks, parks, libraries: the map's own)
Writes: docs/<city>/profiles/data/walk_grid.json

The city is cut into squares about SPACING_M across. For each square the file holds the walk, along
real streets and paths, to the nearest thing in each layer (and, for named layers, which one). The
profile page looks up the square under a pin: no routing happens in the browser and nothing about
the pin leaves it.

How: for each layer, one multi-source Dijkstra over the walking network starting from every
station (or stop, or dock) at once gives every street corner its distance to the nearest one. Each
square's centre then joins the network at its closest corner (within SNAP_M). Walking speed is
WALK_M_PER_MIN. Squares with no street close by (lake, rail yards, large ravines) stay empty.

Needs: pip install shapely  (no other packages)
"""
import heapq, json, math, os, sys
from collections import defaultdict
from datetime import date
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import settings, units_file, station_keys, metro_files

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
args = [a for a in sys.argv[1:] if not a.startswith('--')]
city = args[0] if args else sys.exit('usage: walk_grid.py <city> [--network=path] [--snap=metres]')
opts = dict(a[2:].split('=', 1) for a in sys.argv[1:] if a.startswith('--') and '=' in a)
D = os.path.join(ROOT, 'docs', city, 'data')
NET = opts.get('network') or os.path.join(ROOT, 'cities', city, 'raw', 'walk_network.json')
OUT = os.path.join(ROOT, 'docs', city, 'profiles', 'data', 'walk_grid.json')
CFG = settings(city)
RAIL_FILE = CFG.get('rail', {}).get('file')

SPACING_M = 150
SNAP_M = float(opts.get('snap', 250))   # a square farther than this from any street stays empty
WALK_M_PER_MIN = 80                     # 4.8 km/h
MAX_MIN = 60                            # walks longer than this aren't worth stating
CAP_M = MAX_MIN * WALK_M_PER_MIN

if not os.path.exists(NET):
    sys.exit(f'No walking network at {os.path.relpath(NET, ROOT)}. Run: python3 engine/profiles/fetch_walk.py {city}')


def load(name, default=None):
    p = os.path.join(D, name)
    return json.load(open(p)) if os.path.exists(p) else default


# ---- flat projection in metres (same idea as build.py) -----------------------------------------
hoods = load(units_file(CFG))['features']
city_shape = unary_union([shape(f['geometry']).buffer(0) for f in hoods])
LAT0 = city_shape.centroid.y
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110574


def m(lon, lat):
    return lon * KX, lat * KY


# ---- the walking network -------------------------------------------------------------------------
net = json.load(open(NET))
XY = [m(lon, lat) for lon, lat in net['nodes']]
adj = [[] for _ in XY]
for a, b in net['edges']:
    (ax, ay), (bx, by) = XY[a], XY[b]
    d = math.hypot(ax - bx, ay - by)
    adj[a].append((b, d)); adj[b].append((a, d))
print(f'{city}: network {len(XY):,} corners, {len(net["edges"]):,} links (as of {net.get("asof", "?")})', flush=True)

BUCKET = 100.0
buckets = defaultdict(list)
for i, (x, y) in enumerate(XY):
    if adj[i]:
        buckets[(int(x // BUCKET), int(y // BUCKET))].append(i)


def snap(x, y, limit=SNAP_M):
    """Closest network corner to (x, y) within limit metres: (index, metres) or None."""
    r = int(math.ceil(limit / BUCKET))
    bx, by = int(x // BUCKET), int(y // BUCKET)
    best = None
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            for i in buckets.get((bx + dx, by + dy), ()):
                d = math.hypot(XY[i][0] - x, XY[i][1] - y)
                if d <= limit and (best is None or d < best[1]):
                    best = (i, d)
    return best


def reach(sources):
    """Multi-source Dijkstra. sources: [(lon, lat, label index)]. Returns (dist, src) per corner."""
    dist, src = {}, {}
    heap = []
    for k, (lon, lat, s) in enumerate(sources):
        hit = snap(*m(lon, lat), limit=400)
        if hit and hit[1] < dist.get(hit[0], 1e18):
            dist[hit[0]] = hit[1]; src[hit[0]] = s
            heapq.heappush(heap, (hit[1], hit[0]))
    while heap:
        d, i = heapq.heappop(heap)
        if d > dist.get(i, 1e18) or d > CAP_M:
            continue
        for j, w in adj[i]:
            nd = d + w
            if nd < dist.get(j, 1e18):
                dist[j] = nd; src[j] = src[i]
                heapq.heappush(heap, (nd, j))
    return dist, src


# ---- layers: the map's own points ----------------------------------------------------------------
def gj(name):
    return (load(name + '.geojson') or {'features': []})['features']


nearby = (load('nearby.json') or {'groups': {}})['groups']
stations = [f for n in metro_files(CFG)[0] for f in gj(n)]
EXTRAS = os.path.join(ROOT, 'cities', city, 'raw', 'walk_extras.json')
extras = json.load(open(EXTRAS)) if os.path.exists(EXTRAS) else {'entrances': [], 'parks': []}
ENTRANCE_M = 300     # an entrance belongs to the nearest station within this distance


def station_sources():
    """Walks end at a station's nearest mapped entrance (from OSM) or its point, whichever is closer.
    The point stays because OSM often maps only some of a station's entrances."""
    pts = [m(*f['geometry']['coordinates']) for f in stations]
    out, served = [], set()
    for lon, lat in extras['entrances']:
        x, y = m(lon, lat)
        k = min(range(len(pts)), key=lambda i: (pts[i][0] - x) ** 2 + (pts[i][1] - y) ** 2) if pts else None
        if k is not None and math.hypot(pts[k][0] - x, pts[k][1] - y) <= ENTRANCE_M:
            out.append((lon, lat, k)); served.add(k)
    n_ent = len(out)
    out += [(*f['geometry']['coordinates'], k) for k, f in enumerate(stations)]
    print(f'  subway: {n_ent:,} mapped entrances at {len(served)} of {len(stations)} stations', flush=True)
    return out


def park_sources(step=50):
    """Points every `step` metres around each park's outline (from OSM), plus the City's park points."""
    out = [(p[0], p[1], 0) for p in nearby.get('park', [])]
    for ring in extras['parks']:
        for (ax, ay), (bx, by) in zip(ring, ring[1:]):
            (mx0, my0), (mx1, my1) = m(ax, ay), m(bx, by)
            n = max(1, int(math.hypot(mx1 - mx0, my1 - my0) // step))
            out += [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n, 0) for i in range(n)]
    print(f'  park: {len(extras["parks"]):,} park outlines from OSM', flush=True)
    return out


layers = {
    'subway': (station_keys(stations), station_sources()),
    'go': ([f['properties']['name'] for f in gj(RAIL_FILE)] if RAIL_FILE else [],
           [(*f['geometry']['coordinates'], k) for k, f in enumerate(gj(RAIL_FILE))] if RAIL_FILE else []),
    'stop': (None, [(s[0], s[1], 0) for s in (load('transit.json') or {}).get('stops', [])]),
    'bikeshare': (None, [(*f['geometry']['coordinates'], 0) for f in gj('bikeshare')]),
    'park': (None, park_sources()),
    'library': ([p[2].replace(' branch', '') if len(p) > 2 else 'Library' for p in nearby.get('library', [])],
                [(p[0], p[1], k) for k, p in enumerate(nearby.get('library', []))]),
}

# ---- the grid ------------------------------------------------------------------------------------
w, s, e, n = city_shape.bounds
dlat = SPACING_M / KY
dlon = SPACING_M / KX
cols = int(math.ceil((e - w) / dlon))
rows = int(math.ceil((n - s) / dlat))
inside = prep(city_shape.buffer(0.002))
cells = []          # (cell index, corner, metres to corner)
for r in range(rows):
    lat = s + (r + 0.5) * dlat
    for c in range(cols):
        lon = w + (c + 0.5) * dlon
        if inside.contains(Point(lon, lat)):
            hit = snap(*m(lon, lat))
            if hit:
                cells.append((r * cols + c, hit[0], hit[1]))
print(f'  grid {cols} x {rows}, {len(cells):,} squares on a street', flush=True)

out = {'asof': date.today().isoformat(), 'network_asof': net.get('asof'), 'spacing_m': SPACING_M,
       'lon0': round(w, 6), 'lat0': round(s, 6), 'dlon': round(dlon, 8), 'dlat': round(dlat, 8),
       'cols': cols, 'rows': rows, 'walk_m_per_min': WALK_M_PER_MIN, 'max_min': MAX_MIN, 'layers': {}}
for key, (names, sources) in layers.items():
    if not sources:
        continue
    dist, src = reach(sources)
    mins = [None] * (cols * rows)
    which = [None] * (cols * rows) if names else None
    for k, corner, extra in cells:
        if corner in dist:
            t = (dist[corner] + extra) / WALK_M_PER_MIN
            if t <= MAX_MIN:
                mins[k] = max(1, round(t))
                if names:
                    which[k] = src[corner]
    layer = {'min': mins}
    if names:
        layer['names'] = names
        layer['src'] = which
    out['layers'][key] = layer
    have = sum(v is not None for v in mins)
    print(f'  {key}: {len(sources):,} places, {have:,} squares within {MAX_MIN} min', flush=True)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
print(f'{city}: -> {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT) / 1e6:.1f} MB)')
