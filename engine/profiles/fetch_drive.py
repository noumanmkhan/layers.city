"""Highway ramps and drive times for the Driving lens (unreleased: profiles branch only).

Usage:  python3 engine/profiles/fetch_drive.py toronto [--ramps-only | --times-only]
Writes: cities/<city>/raw/ramps.json           every motorway and trunk link (slip road) in the city's box,
                                               as drawn in OpenStreetMap; build.py works out which are
                                               on-ramps, which highway each joins and the street it starts on
        cities/<city>/raw/drive_profiles.json  free-flow drive minutes to each destination below, from each
                                               neighbourhood's label point and from a 1 km grid over the
                                               city (for pins)

Run it on a computer with normal internet (it fails in most sandboxes). Both files are small and are
committed. Times come from the public OSRM demo server's car profile: posted speeds on empty roads,
the same source and caveat as the map's suburban lens (engine/fetch_drive_times.py). Requests are
spaced out (one every 1.5 s) to be polite to free services.

Data: © OpenStreetMap contributors, ODbL.
"""
import json, math, os, sys, time, urllib.parse, urllib.request
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import settings, units_file

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
args = [a for a in sys.argv[1:] if not a.startswith('--')]
city = args[0] if args else sys.exit('usage: fetch_drive.py <city> [--ramps-only | --times-only]')
RAW = os.path.join(ROOT, 'cities', city, 'raw')
DATA = os.path.join(ROOT, 'docs', city, 'data')
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city; go@layers.city)'}
OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter',
            'https://overpass.kumi.systems/api/interpreter']
OSRM = 'https://router.project-osrm.org/table/v1/driving/'
GRID_KM = 1.0
CHUNK = 90

# Where people drive to. Places a newcomer would ask "how far is it from here?" about.
# The places to drive to: "drive": {"destinations": [[name, lon, lat], ...]} in cities/<city>/factsheet.json
DEST = [tuple(d) for d in settings(city).get('drive', {}).get('destinations', [])]
if not DEST:
    sys.exit(f'No drive destinations set for {city}: add drive.destinations to cities/{city}/factsheet.json.')


def get(url, data=None, timeout=300):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def hoods():
    return json.load(open(os.path.join(DATA, units_file(settings(city)))))['features']


def rings(geom):
    cs = geom['coordinates']
    return [p[0] for p in cs] if geom['type'] == 'MultiPolygon' else [cs[0]]


def inside(lon, lat, polys):
    def ring_has(ring):
        hit = False
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                hit = not hit
        return hit
    return any(ring_has(r) for r in polys)


def bbox(feats, pad=0.02):
    xs = [c[0] for f in feats for r in rings(f['geometry']) for c in r]
    ys = [c[1] for f in feats for r in rings(f['geometry']) for c in r]
    return min(ys) - pad, min(xs) - pad, max(ys) + pad, max(xs) + pad


# ---- 1. ramps ------------------------------------------------------------------------------------
def fetch_ramps(feats):
    s, w, n, e = bbox(feats)
    q = f"""[out:json][timeout:300];
way["highway"~"^(motorway_link|trunk_link)$"]({s:.4f},{w:.4f},{n:.4f},{e:.4f});
out geom qt;"""
    body = urllib.parse.urlencode({'data': q}).encode()
    for attempt in range(6):
        url = OVERPASS[attempt % len(OVERPASS)]
        try:
            print(f'  ramps: asking {urllib.parse.urlparse(url).netloc} ...', flush=True)
            els = get(url, body, timeout=360)['elements']
            break
        except Exception as err:
            wait = 20 * (attempt + 1)
            print(f'    {err}; trying again in {wait} s', flush=True)
            time.sleep(wait)
    else:
        sys.exit('Overpass kept failing. Run again later (or with --times-only to do the drive times now).')
    links = []
    for el in els:
        if el.get('type') != 'way' or not el.get('geometry'):
            continue
        t = el.get('tags', {})
        links.append({'coords': [[round(p['lon'], 6), round(p['lat'], 6)] for p in el['geometry']],
                      'kind': t.get('highway'), 'oneway': t.get('oneway', 'yes'),
                      'name': t.get('name'), 'dest': t.get('destination') or t.get('destination:street'),
                      'ref': t.get('destination:ref')})
    out = os.path.join(RAW, 'ramps.json')
    with open(out, 'w') as f:
        json.dump({'asof': date.today().isoformat(), 'source': 'OpenStreetMap (Overpass)', 'links': links},
                  f, separators=(',', ':'))
    print(f'  ramps: {len(links):,} slip roads -> {os.path.relpath(out, ROOT)}', flush=True)


# ---- 2. drive times ------------------------------------------------------------------------------
def fetch_times(feats):
    polys = [r for f in feats for r in rings(f['geometry'])]
    labels = [(f['properties']['name'], *(f['properties'].get('lp') or [None, None])) for f in feats]
    labels = [(n, x, y) for n, x, y in labels if x is not None]
    s, w, n, e = bbox(feats, pad=0)
    lat0 = (s + n) / 2
    dlat, dlon = GRID_KM / 110.574, GRID_KM / (111.32 * math.cos(math.radians(lat0)))
    cols, rows = int(math.ceil((e - w) / dlon)), int(math.ceil((n - s) / dlat))
    cells = []
    for r in range(rows):
        for c in range(cols):
            lon, lat = w + (c + 0.5) * dlon, s + (r + 0.5) * dlat
            if inside(lon, lat, polys):
                cells.append((c, r, lon, lat))
    sources = [(x, y) for _, x, y in labels] + [(lon, lat) for _, _, lon, lat in cells]
    print(f'  times: {len(labels)} neighbourhoods + {len(cells)} grid points to {len(DEST)} places '
          f'({math.ceil(len(sources) / CHUNK)} requests)', flush=True)
    mins = []
    for i in range(0, len(sources), CHUNK):
        chunk = sources[i:i + CHUNK]
        coords = ';'.join(f'{x:.5f},{y:.5f}' for x, y in chunk) + ';' + ';'.join(f'{x},{y}' for _, x, y in DEST)
        url = (OSRM + coords + '?sources=' + ';'.join(map(str, range(len(chunk)))) +
               '&destinations=' + ';'.join(str(len(chunk) + k) for k in range(len(DEST))) + '&annotations=duration')
        for attempt in range(4):
            try:
                d = get(url, timeout=120)
                if d.get('code') != 'Ok':
                    raise RuntimeError(d.get('code'))
                break
            except Exception as err:
                if attempt == 3:
                    sys.exit(f'OSRM kept failing ({err}). Run again later with --times-only.')
                print(f'    {err}; trying again in 30 s', flush=True)
                time.sleep(30)
        for row in d['durations']:
            mins.append([None if v is None else max(1, round(v / 60)) for v in row])
        print(f'    {min(i + CHUNK, len(sources))}/{len(sources)}', flush=True)
        time.sleep(1.5)
    out = os.path.join(RAW, 'drive_profiles.json')
    with open(out, 'w') as f:
        json.dump({'asof': date.today().isoformat(),
                   'source': 'OSRM car profile on OpenStreetMap (router.project-osrm.org), free-flow',
                   'destinations': [{'name': nm, 'at': [x, y]} for nm, x, y in DEST],
                   'hoods': {nm: mins[k] for k, (nm, _, _) in enumerate(labels)},
                   'grid': {'lon0': round(w, 6), 'lat0': round(s, 6), 'dlon': round(dlon, 8), 'dlat': round(dlat, 8),
                            'cols': cols, 'rows': rows,
                            'cells': [[c, r, mins[len(labels) + k]] for k, (c, r, _, _) in enumerate(cells)]}},
                  f, separators=(',', ':'))
    print(f'  times -> {os.path.relpath(out, ROOT)}', flush=True)


feats = hoods()
os.makedirs(RAW, exist_ok=True)
print(f'{city}: highway ramps and drive times', flush=True)
if '--times-only' not in sys.argv:
    fetch_ramps(feats)
if '--ramps-only' not in sys.argv:
    fetch_times(feats)
print('done')
