"""Fetch Vancouver's raw inputs into cities/vancouver/raw/. Runs in GitHub Actions
(.github/workflows/fetch-vancouver.yml); the sandbox can't reach these hosts.

- City of Vancouver Open Data (Opendatasoft): the 22 local areas (OGL – Vancouver)
- Statistics Canada 2021 cartographic boundaries (land-clipped), from its ArcGIS service: census subdivisions
  (municipalities and reserves) around the Lower Mainland, and dissemination areas inside the City of Vancouver
- U.S. Census Bureau cartographic boundary: Washington State, so the land south of the border shows
- OpenStreetMap via Overpass (ODbL): main streets and collectors in the city, highways across the region,
  neighbourhood place points and the curated landmarks
- TransLink GTFS: SkyTrain, SeaBus and West Coast Express lines and stations
Each step logs its own failure and the rest carry on. Needs gdal-bin (ogr2ogr) for Washington's shapefile.
"""
import csv, io, json, os, re, subprocess, sys, tempfile, time, urllib.parse, urllib.request, zipfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
os.makedirs(RAW, exist_ok=True)
sys.path.insert(0, HERE)
from names import LANDMARKS, KNOWN_AS

UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}
FRAME = (-125.0, 48.2, -121.0, 50.2)        # land shown around the region: Vancouver Island to the Fraser Valley
REGION = (-123.45, 49.0, -122.2, 49.6)      # Metro Vancouver
CITY = (-123.235, 49.195, -123.02, 49.32)   # the City of Vancouver, Stanley Park included
TMP = tempfile.mkdtemp()
FAILED = []


def get(url, data=None, tries=4, timeout=300):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, url[:140], e); time.sleep(15 * (i + 1))
    raise RuntimeError('failed: ' + url)


def download(url, path, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=900) as r, open(path, 'wb') as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b)
            print('  downloaded', os.path.basename(path), os.path.getsize(path) // 1_000_000, 'MB')
            return path
        except Exception as e:
            print('  retry', i + 1, url[:140], e); time.sleep(30 * (i + 1))
    raise RuntimeError('failed: ' + url)


def step(label, fn):
    try:
        fn()
    except Exception as e:
        import traceback
        print('FAILED', label, repr(e)); traceback.print_exc()
        FAILED.append(label)


def save(name, obj):
    with open(os.path.join(RAW, name), 'w') as f:
        json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
    print('wrote', name, os.path.getsize(os.path.join(RAW, name)) // 1000, 'KB')


def shp_to_geojson(zip_path, where, out, select=None):
    """Unzip a shapefile and write the matching features as WGS84 GeoJSON with ogr2ogr."""
    d = tempfile.mkdtemp(dir=TMP)
    zipfile.ZipFile(zip_path).extractall(d)
    shp = next(os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f.endswith('.shp'))
    cmd = ['ogr2ogr', '-f', 'GeoJSON', '-t_srs', 'EPSG:4326', '-lco', 'COORDINATE_PRECISION=6', '-where', where]
    if select: cmd += ['-select', select]
    subprocess.run(cmd + [os.path.join(RAW, out), shp], check=True)
    n = len(json.load(open(os.path.join(RAW, out)))['features'])
    print('wrote', out, n, 'features')


# ---------- City of Vancouver: local areas ----------
ODS = 'https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/'
step('local areas', lambda: save('local_areas.geojson', json.loads(get(ODS + 'local-area-boundary/exports/geojson'))))

# ---------- Statistics Canada boundaries (2021, cartographic: clipped to the shoreline) ----------
# From Statistics Canada's ArcGIS service (www12.statcan.gc.ca refuses GitHub's runners with 403; this answers).
GEO = 'https://geo.statcan.gc.ca/geo_wa/rest/services/2021/Cartographic_boundary_files/MapServer/'


def arcgis(layer, where, offset_deg, out, bbox=None):
    feats, start = [], 0
    while True:
        p = {'where': where, 'outFields': '*', 'outSR': 4326, 'f': 'geojson', 'returnGeometry': 'true', 'orderByFields': 'OBJECTID',
             'maxAllowableOffset': offset_deg, 'resultOffset': start, 'resultRecordCount': 500}
        if bbox: p.update({'geometry': '%s,%s,%s,%s' % bbox, 'geometryType': 'esriGeometryEnvelope', 'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects'})
        q = urllib.parse.urlencode(p)
        d = json.loads(get(GEO + str(layer) + '/query?' + q))
        if 'error' in d: raise RuntimeError(d['error'])
        feats += d.get('features', [])
        if not d.get('exceededTransferLimit') and len(d.get('features', [])) < 500: break
        start += 500; time.sleep(1)
    save(out, {'type': 'FeatureCollection', 'features': feats})
    print('  ', out, len(feats), 'features')


# Metro Vancouver's municipalities and reserves in detail; the census divisions around it (Fraser Valley,
# Squamish-Lillooet, Sunshine Coast, qathet, the east side of Vancouver Island) coarser, as land beyond the region.
# The layers carry no census-division field, so divisions are picked by the start of the subdivision's code.
step('census subdivisions', lambda: arcgis(9, "CSDUID LIKE '5915%'", 0.00005, 'csds.geojson'))
step('land around the region', lambda: arcgis(9, ' OR '.join("CSDUID LIKE '%s%%'" % cd for cd in ('5909', '5931', '5929', '5927', '5917', '5919', '5921', '5923', '5926')),
                                               0.0005, 'csds_around.geojson'))
# DAs carry no subdivision either: Metro Vancouver's (5915) inside the City's box; build.py keeps the ones in the City.
step('dissemination areas', lambda: arcgis(12, "DAUID LIKE '5915%'", 0.00002, 'das.geojson', CITY))

# ---------- Washington State (U.S. Census cartographic boundary, 1:500k) ----------
def washington():
    z = download('https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_500k.zip', os.path.join(TMP, 'us.zip'))
    shp_to_geojson(z, "STATEFP = '53'", 'washington.geojson', 'NAME')
step('washington', washington)

# The 2021 Census Profile for the City's dissemination areas: fetch_census.py (run after this one).

# ---------- OpenStreetMap ----------
SERVERS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter',
           'https://maps.mail.ru/osm/tools/overpass/api/interpreter']


def overpass(q, name):
    for i in range(6):
        url = SERVERS[i % len(SERVERS)]
        try:
            d = json.loads(get(url, urllib.parse.urlencode({'data': q}).encode(), tries=1, timeout=400))
            if d.get('remark') and 'error' in d['remark'].lower(): raise RuntimeError(d['remark'])
            save(name, d); return d
        except Exception as e:
            print('  overpass retry', i + 1, url, e); time.sleep(20 * (i + 1))
    raise RuntimeError('overpass failed: ' + name)


bb = lambda b: '%s,%s,%s,%s' % (b[1], b[0], b[3], b[2])
step('osm streets', lambda: overpass(f'[out:json][timeout:300];way["highway"~"^(trunk|primary|secondary|tertiary)$"]["name"]({bb(CITY)});out tags geom;', 'osm_streets.json'))
step('osm highways', lambda: overpass(f'[out:json][timeout:600];way["highway"~"^(motorway|trunk)$"]["ref"]({bb(REGION)});out tags geom;', 'osm_highways.json'))
step('osm places', lambda: overpass(f'[out:json][timeout:200];node["place"~"^(neighbourhood|quarter|suburb|locality|village|town|city)$"]["name"]({bb(REGION)});out tags;', 'osm_places.json'))


def landmarks():
    names = sorted({n for l in LANDMARKS for n in [l['osm'] if 'osm' in l else l['name']]} | {k['osm'] for k in KNOWN_AS if 'osm' in k})
    rx = '|'.join(re.escape(n) for n in names)
    overpass(f'[out:json][timeout:300];nwr["name"~"^({rx})$"]({bb((-123.30, 49.15, -123.00, 49.35))});out tags center;', 'osm_landmarks.json')
step('osm landmarks', landmarks)

# ---------- TransLink GTFS: SkyTrain (route_type 1), West Coast Express (2), SeaBus (4) ----------
def translink():
    z = zipfile.ZipFile(io.BytesIO(get('https://gtfs-static.translink.ca/gtfs/google_transit.zip')))
    rd = lambda n: list(csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig')))
    routes = {r['route_id']: r for r in rd('routes.txt') if r['route_type'] in ('1', '2', '4')}
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
    save('translink_rail.json', {
        'feed': feed[:1],
        'routes': {rid: {'short': r['route_short_name'], 'long': r['route_long_name'], 'type': r['route_type'], 'color': r.get('route_color', ''),
                         'shapes': {sid: [[x, y] for _, x, y in sorted(shapes[sid])] for (ri, sid) in shape_n if ri == rid},
                         'counts': {sid: c for (ri, sid), c in shape_n.items() if ri == rid}} for rid, r in routes.items()},
        'stations': [dict(s, routes=sorted(s['routes'])) for s in stations.values()]})
step('translink rail', translink)

print('done; failed:', FAILED or 'none')
