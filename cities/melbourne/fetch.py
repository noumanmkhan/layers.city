"""Fetch Melbourne's raw inputs into cities/melbourne/raw/. Runs in GitHub Actions
(.github/workflows/fetch-melbourne.yml); the sandbox can't reach these hosts.

- Australian Bureau of Statistics, ASGS Edition 3 (2021) boundaries from its ArcGIS service (CC BY 4.0): Suburbs and
  Localities across Greater Melbourne, Local Government Areas, the Greater Melbourne GCCSA, Victoria (the land), and the
  SA1s inside the City of Melbourne
- ABS 2021 Census General Community Profile DataPack, SA1s in Victoria (CC BY 4.0): the City's SA1 rows only
- OpenStreetMap via Overpass (ODbL): main streets and collectors in the City, freeways across the region, the Yarra,
  place points and the curated landmarks
- Transport Victoria GTFS Schedule (CC BY 4.0): metropolitan trains, trams and V/Line trains
Each step logs its own failure and the rest carry on.
"""
import csv, io, json, os, re, sys, time, urllib.parse, zipfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_lib import RAW, TMP, FRAME, REGION, CITY, FAILED, get, download, step, save, overpass
from names import LANDMARKS, KNOWN_AS

# ---------- ABS boundaries ----------
ABS = 'https://geo.abs.gov.au/arcgis/rest/services/'


def services():
    d = json.loads(get(ABS + 'ASGS2021?f=json'))
    print('  ABS ASGS2021 services:', [s['name'] for s in d.get('services', [])])


def abs_layer(service):
    d = json.loads(get(ABS + 'ASGS2021/%s/MapServer?f=json' % service))
    lay = d['layers'][0]
    info = json.loads(get(ABS + 'ASGS2021/%s/MapServer/%d?f=json' % (service, lay['id'])))
    print('  %s layer %d %s · max records %s · fields %s' % (service, lay['id'], lay['name'], info.get('maxRecordCount'),
                                                           [f['name'] for f in info.get('fields', [])]))
    return lay['id'], info.get('maxRecordCount') or 1000


def abs_query(service, where, offset_deg, out, bbox=None):
    lid, page = abs_layer(service)
    page = min(page, 1000)
    feats, start = [], 0
    while True:
        p = {'where': where, 'outFields': '*', 'outSR': 4326, 'f': 'geojson', 'returnGeometry': 'true',
             'maxAllowableOffset': offset_deg, 'resultOffset': start, 'resultRecordCount': page}
        if bbox: p.update({'geometry': '%s,%s,%s,%s' % bbox, 'geometryType': 'esriGeometryEnvelope', 'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects'})
        d = json.loads(get(ABS + 'ASGS2021/%s/MapServer/%d/query?%s' % (service, lid, urllib.parse.urlencode(p))))
        if 'error' in d: raise RuntimeError(d['error'])
        got = d.get('features', [])
        feats += got
        if not (d.get('exceededTransferLimit') or (d.get('properties') or {}).get('exceededTransferLimit')) and len(got) < page: break
        start += page; time.sleep(1)
    save(out, {'type': 'FeatureCollection', 'features': feats})
    print('  ', out, len(feats), 'features')


step('abs services', services)
step('suburbs', lambda: abs_query('SAL', "1=1", 0.00004, 'sal.geojson', REGION))
step('councils', lambda: abs_query('LGA', "1=1", 0.00006, 'lga.geojson', REGION))
step('greater melbourne', lambda: abs_query('GCCSA', "GCCSA_CODE_2021 = '2GMEL'", 0.0001, 'gccsa.geojson'))
step('victoria', lambda: abs_query('STE', "STATE_CODE_2021 = '2'", 0.0008, 'victoria.geojson'))
step('sa1s', lambda: abs_query('SA1', "1=1", 0.00002, 'sa1.geojson', CITY))


# ---------- 2021 Census General Community Profile, SA1s (the City's rows only) ----------
# Only the columns profiles.py reads are kept (the whole DataPack's SA1 rows for the City come to ~70 MB).
CENSUS_KEEP = {
    'G01': ['Tot_P_P', 'Age_0_4_yr_P', 'Age_5_14_yr_P', 'Age_15_19_yr_P', 'Age_20_24_yr_P', 'Age_25_34_yr_P', 'Age_35_44_yr_P', 'Age_45_54_yr_P',
            'Age_55_64_yr_P', 'Age_65_74_yr_P', 'Age_75_84_yr_P', 'Age_85ov_P', 'Birthplace_Elsewhere_P', 'Count_psns_occ_priv_dwgs_P'],
    'G02': None, 'G36': None,
    'G37': ['O_OR_Total', 'O_MTG_Total', 'R_Tot_Total', 'R_ST_h_auth_Total', 'R_Com_Hp_Total', 'Oth_ten_type_Total', 'Ten_type_NS_Total', 'Total_Total'],
    'G10C': ['Tot_2016', 'Tot_2017', 'Tot_2018', 'Tot_2019', 'Tot_2020', 'Tot_2021', 'Tot_Tot'],
}


def census():
    sa1 = json.load(open(os.path.join(RAW, 'sa1.geojson')))['features']
    want = {str(f['properties']['sa1_code_2021']) for f in sa1}
    print('  SA1s in the City box:', len(want))
    z = zipfile.ZipFile(download('https://www.abs.gov.au/census/find-census-data/datapacks/download/2021_GCP_SA1_for_VIC_short-header.zip',
                                 os.path.join(TMP, 'gcp.zip')))
    tables = {}
    for n in z.namelist():
        m = re.search(r'2021Census_(G\d+[A-Z]?)_VIC_SA1\.csv$', n)
        if m and (m.group(1) in CENSUS_KEEP or m.group(1).startswith('G13')):
            rows = list(csv.reader(io.TextIOWrapper(z.open(n), 'utf-8-sig')))
            tables[m.group(1)] = (rows[0], [r for r in rows[1:] if r[0] in want])
    out = {}
    for t, cols in CENSUS_KEEP.items():
        h, body = tables[t]
        idx = [0] + ([h.index(c) for c in cols] if cols else list(range(1, len(h))))
        out[t] = {'cols': [h[i] for i in idx], 'rows': [[r[i] for i in idx] for r in body]}
    # Language used at home (G13A-E): persons, all levels of English (POL_<language>_Tot, PSEO_Tot), one row per SA1.
    lc, rows = ['P_Tot_Tot'], {}
    for t in sorted(k for k in tables if k.startswith('G13')):
        h, body = tables[t]
        lc += [c for c in h if re.fullmatch(r'(PSEO|POL_.+)_Tot', c) and '_UOLSE_' not in c and c not in lc]
        for r in body: rows.setdefault(r[0], {}).update(zip(h, r))
    out['G13'] = {'cols': ['SA1_CODE_2021'] + lc, 'rows': [[k] + [d.get(c, '0') for c in lc] for k, d in rows.items()]}
    out['_about'] = ('ABS 2021 Census GCP DataPack, SA1s in the City of Melbourne box (fetch.py), trimmed to the columns profiles.py reads: '
                     'G01 ages and birthplace, G02 medians, G36 dwelling structure, G37 tenure, G10C year of arrival totals, '
                     'G13 language used at home (persons, all proficiencies).')
    save('census_sa1.json', out)
step('census', census)

# ---------- OpenStreetMap ----------
bb = lambda b: '%s,%s,%s,%s' % (b[1], b[0], b[3], b[2])
step('osm streets', lambda: overpass(f'[out:json][timeout:300];way["highway"~"^(trunk|primary|secondary|tertiary)$"]["name"]({bb(CITY)});out tags geom;', 'osm_streets.json'))
step('osm highways', lambda: overpass(f'[out:json][timeout:600];way["highway"~"^(motorway|trunk)$"]({bb(REGION)});out tags geom;', 'osm_highways.json'))
step('osm yarra', lambda: overpass(f'[out:json][timeout:200];way["waterway"="river"]["name"~"Yarra|Birrarung"]({bb(CITY)});out tags geom;', 'osm_yarra.json'))
step('osm places', lambda: overpass(f'[out:json][timeout:200];node["place"~"^(neighbourhood|quarter|suburb|locality|village|town|city)$"]["name"]({bb(REGION)});out tags;', 'osm_places.json'))


def landmarks():
    names = sorted({l.get('osm', l['name']) for l in LANDMARKS} | {l['name'] for l in LANDMARKS} | {k['osm'] for k in KNOWN_AS})
    rx = '|'.join(re.escape(n) for n in names)
    overpass(f'[out:json][timeout:300];nwr["name"~"^({rx})$"]({bb((144.40, -38.10, 145.10, -37.60))});out tags center;', 'osm_landmarks.json')
step('osm landmarks', landmarks)


# ---------- Transport Victoria GTFS Schedule: 1 V/Line trains, 2 metropolitan trains, 3 metropolitan trams ----------
def gtfs_url():
    for api in ('https://opendata.transport.vic.gov.au/api/3/action/package_show?id=gtfs-schedule',
                'https://discover.data.vic.gov.au/api/3/action/package_show?id=gtfs-schedule'):
        try:
            d = json.loads(get(api, tries=2))
            res = d['result']['resources']
            print('  GTFS resources:', [(r.get('name'), r.get('format'), r.get('url')) for r in res])
            z = [r['url'] for r in res if (r.get('format') or '').lower() == 'zip' or r.get('url', '').lower().endswith('.zip')]
            if z: return z[0]
        except Exception as e:
            print('  ', api, e)
    return 'https://data.ptv.vic.gov.au/downloads/gtfs.zip'


def ptv():
    url = gtfs_url(); print('  GTFS from', url)
    outer = zipfile.ZipFile(download(url, os.path.join(TMP, 'gtfs.zip')))
    print('  GTFS folders:', [n for n in outer.namelist() if n.endswith('.zip')][:20])
    out = {}
    for mode in ('1', '2', '3'):
        n = next((n for n in outer.namelist() if re.fullmatch(r'(?:[^/]*/)?%s/google_transit\.zip' % mode, n)), None)
        if not n: print('  no folder', mode); continue
        z = zipfile.ZipFile(io.BytesIO(outer.read(n)))
        rd = lambda f: list(csv.DictReader(io.TextIOWrapper(z.open(f), 'utf-8-sig')))
        routes = {r['route_id']: r for r in rd('routes.txt') if r['route_short_name'] != 'Replacement Bus'}
        trips = [t for t in rd('trips.txt') if t['route_id'] in routes]
        shape_n = Counter((t['route_id'], t['shape_id']) for t in trips)
        top = Counter()
        for (r, s), c in shape_n.items(): top[r] = max(top[r], c)
        share = 0.5 if mode == '1' else 0.1   # V/Line: only its main patterns; trains and trams: drop rare variants (depot runs)
        shape_n = Counter({k: c for k, c in shape_n.items() if c >= top[k[0]] * share})
        want = {s for _, s in shape_n}
        shapes = defaultdict(list)
        for p in rd('shapes.txt'):
            if p['shape_id'] in want:
                shapes[p['shape_id']].append((int(p['shape_pt_sequence']), round(float(p['shape_pt_lon']), 5), round(float(p['shape_pt_lat']), 5)))
        trip_route = {t['trip_id']: t['route_id'] for t in trips}
        stop_routes = defaultdict(set)
        for st in rd('stop_times.txt'):
            r = trip_route.get(st['trip_id'])
            if r: stop_routes[st['stop_id']].add(r)
        stops = {s['stop_id']: s for s in rd('stops.txt')}
        stations = {}
        for sid, rs in stop_routes.items():
            s = stops[sid]; key = s.get('parent_station') or sid
            p = stops.get(key, s)
            st = stations.setdefault(key, {'id': key, 'name': p['stop_name'], 'lon': float(p['stop_lon']), 'lat': float(p['stop_lat']), 'routes': set()})
            st['routes'] |= rs
        print('  mode', mode, len(routes), 'routes ·', len(stations), 'stops · e.g.', [(r['route_short_name'], r['route_long_name'], r['route_type'], r.get('route_color')) for r in list(routes.values())[:30]])
        out[mode] = {
            'feed': (rd('feed_info.txt')[:1] if 'feed_info.txt' in z.namelist() else []),
            'routes': {rid: {'short': r['route_short_name'], 'long': r['route_long_name'], 'type': r['route_type'], 'color': r.get('route_color', ''),
                             'shapes': {sid: [[x, y] for _, x, y in sorted(shapes[sid])] for (ri, sid) in shape_n if ri == rid},
                             'counts': {sid: c for (ri, sid), c in shape_n.items() if ri == rid}} for rid, r in routes.items()},
            'stations': [dict(s, routes=sorted(s['routes'])) for s in stations.values()]}
        out[mode]['routes'] = {k: v for k, v in out[mode]['routes'].items() if v['counts']}
    save('ptv_rail.json', out)
step('ptv gtfs', ptv)

print('done; failed:', FAILED or 'none')
