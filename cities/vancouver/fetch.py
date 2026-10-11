"""Fetch Vancouver's raw inputs into cities/vancouver/raw/. Runs in GitHub Actions
(.github/workflows/fetch-vancouver.yml); the sandbox can't reach these hosts.

- City of Vancouver Open Data (Opendatasoft): the 22 local areas (OGL – Vancouver)
- Statistics Canada 2021 cartographic boundary files (land-clipped): census subdivisions (municipalities
  and reserves) around the Lower Mainland, and dissemination areas inside the City of Vancouver
- Statistics Canada 2021 Census Profile for dissemination areas (British Columbia), cut down to the City's
  DAs and the profile sections the map uses (Statistics Canada Open Licence)
- U.S. Census Bureau cartographic boundary: Washington State, so the land south of the border shows
- OpenStreetMap via Overpass (ODbL): main streets and collectors in the city, highways across the region,
  neighbourhood place points and the curated landmarks
- TransLink GTFS: SkyTrain, SeaBus and West Coast Express lines and stations
Each step logs its own failure and the rest carry on. Needs gdal-bin (ogr2ogr) for the shapefiles.
"""
import csv, io, json, os, re, subprocess, sys, tempfile, time, urllib.parse, urllib.request, zipfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
os.makedirs(RAW, exist_ok=True)
sys.path.insert(0, HERE)
from names import LANDMARKS, KNOWN_AS

UA = {'User-Agent': 'city-layers/1.0 (https://maps.noumankhan.ca)'}
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
GEO = 'https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/'


def csds():
    z = download(GEO + 'lcsd000b21a_e.zip', os.path.join(TMP, 'csd.zip'))
    # Every BC subdivision whose census division touches the frame: Metro Vancouver (5915), Fraser Valley (5909),
    # Squamish-Lillooet (5931), Sunshine Coast (5929), and the east side of Vancouver Island (5917, 5919, 5921, 5923, 5926).
    shp_to_geojson(z, "CDUID IN ('5915','5909','5931','5929','5917','5919','5921','5923','5926','5927')", 'csds.geojson',
                   'CSDUID,CSDNAME,CSDTYPE,CDUID')
step('census subdivisions', csds)


def das():
    z = download(GEO + 'lda_000b21a_e.zip', os.path.join(TMP, 'da.zip'))
    shp_to_geojson(z, "CSDUID = '5915022'", 'das.geojson', 'DAUID,CSDUID')
step('dissemination areas', das)

# ---------- Washington State (U.S. Census cartographic boundary, 1:500k) ----------
def washington():
    z = download('https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_500k.zip', os.path.join(TMP, 'us.zip'))
    shp_to_geojson(z, "STATEFP = '53'", 'washington.geojson', 'NAME')
step('washington', washington)

# ---------- 2021 Census Profile: dissemination areas in the City of Vancouver ----------
# The profile sections the map reads (by the "Total - ..." row that opens each); every row up to the next
# "Total - " row is kept. Plus the two medians, which sit outside those sections.
SECTIONS = [
    'Total - Age groups of the population - 25% sample data',
    'Total - Private households by tenure - 25% sample data',
    'Total - Occupied private dwellings by structural type of dwelling - 25% sample data',
    'Total - Occupied private dwellings by period of construction - 25% sample data',
    'Total - Language spoken most often at home for the population in private households - 25% sample data',
    'Total - Immigrant status and period of immigration for the population in private households - 25% sample data',
    'Total - Main mode of commuting for the employed labour force aged 15 years and over with a usual place of work or no fixed workplace address - 25% sample data',
    'Total - Owner households in non-farm, non-reserve private dwellings - 25% sample data',
    'Total - Tenant households in non-farm, non-reserve private dwellings - 25% sample data',
]
SINGLE = ['Population, 2021', 'Median value of dwellings ($)', 'Median monthly shelter costs for rented dwellings ($)',
          'Median monthly shelter costs for owned dwellings ($)', 'Private households by household size']
PROFILE_URLS = [
    'https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm?Lang=E&FILETYPE=CSV&GEONO=006_BC',
    'https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm?Lang=E&FILETYPE=CSV&GEONO=006',
]


def profile():
    das = {f['properties']['DAUID'] for f in json.load(open(os.path.join(RAW, 'das.geojson')))['features']}
    z = None
    for u in PROFILE_URLS:
        try:
            z = download(u, os.path.join(TMP, 'profile.zip'), tries=2)
            zipfile.ZipFile(z)
            break
        except Exception as e:
            print('  profile source failed', u, e); z = None
    if not z: raise RuntimeError('no census profile download worked')
    zf = zipfile.ZipFile(z)
    print('  zip members:', zf.namelist())
    member = next(n for n in zf.namelist() if n.lower().endswith('.csv') and 'data' in n.lower()
                  and ('british' in n.lower() or '_bc' in n.lower() or len([m for m in zf.namelist() if m.lower().endswith('.csv')]) <= 2))
    print('  reading', member)
    keep, labels, out, city = set(), {}, defaultdict(dict), {}
    in_sec = False
    with zf.open(member) as fh:
        rdr = csv.reader(io.TextIOWrapper(fh, 'latin-1'))
        head = next(rdr)
        col = {h.strip().lstrip('﻿'): i for i, h in enumerate(head)}
        print('  columns:', head[:14])
        iD, iL, iN, iC, iV = col['DGUID'], col['GEO_LEVEL'], col['CHARACTERISTIC_NAME'], col['CHARACTERISTIC_ID'], col['C1_COUNT_TOTAL']
        iG = col['ALT_GEO_CODE']
        first_geo, n = None, 0
        for r in rdr:
            n += 1
            g = r[iG]
            cid = int(r[iC]); name = r[iN]
            # Work out which characteristic ids to keep from the first geography (they repeat in the same order).
            if first_geo is None: first_geo = g
            if g == first_geo:
                s = name.strip()
                if s.startswith('Total - '): in_sec = s in SECTIONS
                if in_sec or s in SINGLE:
                    keep.add(cid); labels[cid] = name
            if cid not in keep: continue
            v = r[iV].strip()
            val = float(v) if re.fullmatch(r'-?[\d.]+', v) else None
            if r[iL] == 'Dissemination area' and g in das:
                out[g][cid] = val
            elif g == '5915022':   # the City of Vancouver as a whole, for checks
                city[cid] = val
            if n % 5_000_000 == 0: print('   ', n, 'rows')
    print('  rows read', n, '· DAs kept', len(out), 'of', len(das), '· characteristics', len(keep))
    save('census_da.json', {'source': 'Statistics Canada, 2021 Census of Population, Census Profile (98-401-X2021006)',
                            'labels': {str(k): labels[k] for k in sorted(labels)},
                            'city': {str(k): v for k, v in city.items()},
                            'das': {g: {str(k): v for k, v in d.items()} for g, d in out.items()}})
step('census profile', profile)

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
step('osm highways', lambda: overpass(f'[out:json][timeout:300];way["highway"~"^(motorway|trunk)$"]({bb(REGION)});out tags geom;', 'osm_highways.json'))
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
