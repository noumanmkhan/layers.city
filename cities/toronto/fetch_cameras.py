"""Fetch Toronto's red light camera and former speed camera (ASE) data into raw/cameras/.
Runs in GitHub Actions (.github/workflows/fetch-cameras.yml); needs openpyxl and pyproj.

Sources, all City of Toronto Open Data (Transportation Services; Open Government Licence – Toronto):
  red-light-cameras                       current camera points (WGS84 GeoJSON), refreshed daily
  red-light-camera-annual-charges         charges per camera per year (XLSX), refreshed about twice a year
  automated-speed-enforcement-locations   ASE points: the final file plus the two older snapshots the package
                                          still holds (2022, EPSG:2945; March 2025, EPSG:2952), which carry
                                          site codes and earlier sites. No longer refreshed (program ended).
  automated-speed-enforcement-ase-charges charges per site per month (XLSX), no longer refreshed
  toronto-centreline-tcl                  street centreline (CSV), only the segments of streets the camera
                                          texts name, to place retired cameras and sites without a point
The spreadsheets are written out as JSON rows (dates as ISO text) so the build (cameras.py) needs only the
standard library. The log lists the packages, resources and anything unexpected."""
import csv, datetime, io, json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'cameras')
sys.path.insert(0, HERE)
from cameras import snorm, bare, wanted_streets   # noqa: E402

API = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show?id='
UA = {'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)'}
csv.field_size_limit(1 << 30)


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, e)
            time.sleep(5 * (i + 1))
    raise SystemExit('failed: ' + url)


def package(pid):
    p = json.loads(get(API + pid))['result']
    print(f"Package {pid}: {p['title']} · refresh {p.get('refresh_rate')} · last refreshed {p.get('last_refreshed')} · {p.get('license_title')}")
    for r in p['resources']:
        print('   ', r['id'], r['name'], r.get('format'), r.get('last_modified'))
    return p


def resource(p, test):
    rs = [r for r in p['resources'] if test(r)]
    if not rs:
        raise SystemExit(f"{p['name']}: no resource matched")
    return rs[0]


def cell(v):
    if isinstance(v, datetime.datetime):
        return v.date().isoformat() if v.time() == datetime.time() else v.isoformat()
    if isinstance(v, str):
        return v.strip()
    return v


def sheet(blob):
    import openpyxl
    ws = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True).worksheets[0]
    rows = [[cell(v) for v in r] for r in ws.iter_rows(values_only=True)]
    rows = [r[:max((i for i, v in enumerate(r) if v not in (None, '')), default=-1) + 1] for r in rows]
    rows = [r for r in rows if r]
    return rows[0], rows[1:]


def info(p, r):
    return {'package': p['name'], 'title': p['title'], 'refreshed': p.get('last_refreshed'), 'refresh': p.get('refresh_rate'),
            'resource': r['name'], 'resourceId': r['id'], 'modified': r.get('last_modified'), 'licence': p.get('license_title'),
            'page': 'https://open.toronto.ca/dataset/' + p['name'] + '/'}


os.makedirs(RAW, exist_ok=True)
sources = {'fetched': datetime.date.today().isoformat()}

# Red light camera points.
p = package('red-light-cameras')
r = resource(p, lambda r: '4326' in r['name'] and (r.get('format') or '').lower() == 'geojson')
fc = json.loads(get(r['url']))
keep = ('RLC', 'NAME', 'MAIN', 'SIDE1', 'ADDITIONAL_INFO', 'MID_BLOCK', 'WARD_1', 'ACTIVATION_DATE', 'INTERSECTION_ID')
for f in fc['features']:
    f['properties'] = {k: f['properties'].get(k) for k in keep}
    g = f['geometry']
    g['coordinates'] = [[round(x, 6) for x in c] for c in g['coordinates']] if g['type'] == 'MultiPoint' else [round(x, 6) for x in g['coordinates']]
fc.pop('crs', None)
json.dump(fc, open(os.path.join(RAW, 'rlc_locations.geojson'), 'w'), separators=(',', ':'))
print(len(fc['features']), 'red light camera points')
rlc_info = [info(p, r)]

# Red light camera charges by year.
p = package('red-light-camera-annual-charges')
r = resource(p, lambda r: (r.get('format') or '').upper() == 'XLSX')
hdr, rows = sheet(get(r['url']))
notes = [row[0] for row in rows if isinstance(row[0], str)]
print('Header:', hdr[:6], '…', hdr[-1]); print('Notes:', notes)
partial = None
for n in notes:   # "2026 data is from January 1, 2026 to Jun 30, 2026."
    m = re.match(r'^(\d{4}) data is from (.+?) to (.+?)\.?$', n)
    if m:
        try:
            to = datetime.datetime.strptime(m.group(3).replace('.', ''), '%b %d, %Y').date()
        except ValueError:
            to = datetime.datetime.strptime(m.group(3), '%B %d, %Y').date()
        partial = {'year': int(m.group(1)), 'to': to.isoformat()}
json.dump({'header': hdr, 'rows': rows, 'notes': notes, 'partial': partial}, open(os.path.join(RAW, 'rlc_charges.json'), 'w'), separators=(',', ':'), default=str)
print(sum(1 for x in rows if isinstance(x[0], (int, float))), 'cameras in the charges file; partial year:', partial)
rlc_info.append(info(p, r))
sources['rlc'] = rlc_info
rlc_texts = [str(x[2]) for x in rows if isinstance(x[0], (int, float))]

# ASE points: every GeoJSON snapshot in the package, oldest first, in WGS84.
from pyproj import Transformer   # noqa: E402
p = package('automated-speed-enforcement-locations')
snaps = []
for r in p['resources']:
    if (r.get('format') or '').lower() != 'geojson' or 'download' not in (r.get('url') or ''):
        continue
    m = re.search(r'(\d{4})\.geojson$', r['url'])
    epsg = int(m.group(1)) if m else 4326
    g = json.loads(get(r['url']))
    t = Transformer.from_crs(epsg, 4326, always_xy=True) if epsg != 4326 else None
    pts = []
    for f in g['features']:
        c = f['geometry']['coordinates']
        c = c[0] if f['geometry']['type'] == 'MultiPoint' else c
        x, y = t.transform(*c) if t else c
        q = f['properties']; code = q.get('Location_Code')
        pts.append([None if code in (None, 'None') else code, q.get('location'), q.get('Status'), round(x, 6), round(y, 6)])
    snaps.append({'resource': r['name'], 'id': r['id'], 'modified': r.get('last_modified'), 'epsg': epsg, 'points': pts})
    print(f"  snapshot {r['name']} ({r.get('last_modified')}, EPSG:{epsg}): {len(pts)} points")
snaps.sort(key=lambda s: s['modified'] or '')
json.dump(snaps, open(os.path.join(RAW, 'ase_locations.json'), 'w'), separators=(',', ':'))
ase_info = [dict(info(p, {'name': ', '.join(s['resource'] for s in snaps), 'id': ', '.join(s['id'] for s in snaps), 'last_modified': snaps[-1]['modified']}))]

# ASE charges by month.
p = package('automated-speed-enforcement-ase-charges')
r = resource(p, lambda r: (r.get('format') or '').upper() == 'XLSX')
hdr, rows = sheet(get(r['url']))
notes = [x[1] for x in rows if not x[0] and len(x) > 1 and x[1]]
print('Header:', hdr[:6], '…', hdr[-1]); print('Notes:', notes)
json.dump({'header': hdr, 'rows': rows, 'notes': notes}, open(os.path.join(RAW, 'ase_charges.json'), 'w'), separators=(',', ':'), default=str)
print(sum(1 for x in rows if isinstance(x[0], str) and re.match(r'^[A-Z]\d+', x[0])), 'ASE site rows')
ase_info.append(info(p, r))
sources['ase'] = ase_info
ase_texts = [str(x[1]) for x in rows if isinstance(x[0], str) and re.match(r'^[A-Z]\d+', x[0])]

# Centreline segments of the named streets.
want = wanted_streets(ase_texts, rlc_texts)
p = package('toronto-centreline-tcl')
r = resource(p, lambda r: '4326' in r['name'] and (r.get('format') or '').upper() == 'CSV')
SKIP = {'Trail', 'Walkway', 'Ferry Route', 'River', 'Creek/Tributary', 'Hydro Line', 'Major Railway', 'Minor Railway',
        'Geostatistical line', 'Major Shoreline', 'Minor Shoreline (Land locked)', 'Busway'}
ival = lambda v: int(float(v)) if v not in (None, '', 'None') else None
segs = []
for row in csv.DictReader(io.StringIO(get(r['url']).decode('utf-8-sig'))):
    if row['FEATURE_CODE_DESC'] in SKIP or bare(snorm(row['LINEAR_NAME_FULL'])) not in want:
        continue
    g = json.loads(row['geometry'])
    lines = g['coordinates'] if g['type'] == 'MultiLineString' else [g['coordinates']]
    coords = [[round(x, 6), round(y, 6)] for ln in lines for x, y in ln]
    segs.append([int(row['CENTRELINE_ID']), row['LINEAR_NAME_FULL'], ival(row['FROM_INTERSECTION_ID']), ival(row['TO_INTERSECTION_ID']),
                 ival(row['LO_NUM_L']), ival(row['HI_NUM_L']), ival(row['LO_NUM_R']), ival(row['HI_NUM_R']), coords])
json.dump(segs, open(os.path.join(RAW, 'centreline.json'), 'w'), separators=(',', ':'))
sources['centreline'] = info(p, r)
print(len(segs), 'centreline segments for', len(want), 'street names')
json.dump(sources, open(os.path.join(RAW, 'sources.json'), 'w'), indent=1)
