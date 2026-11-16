"""The tri-state region beyond New York City, for the lens, Living here and Representatives on the card beyond the City.
Run from GitHub Actions (fetch-region-basemap.yml runs a city's fetch_region.py after the shared fetches); the
sandbox can't reach census.gov or Open States. Writes raw/region/:
  acs_tracts.json   ACS 5-year, the same tables and form as fetch_acs.py, for every tract in the region's counties
                    (New York, New Jersey, and Connecticut's planning regions, which the Census uses as counties since 2022)
  tracts.geojson    those tracts' boundaries (TIGERweb Tracts_Blocks layer 0): GEOID
  congress.geojson, upper.geojson, lower.geojson   congressional, state Senate and lower-house districts in the
                    region's box (TIGERweb Legislative 0, 1, 2), STATE 09, 34 and 36, with STATE and BASENAME
  nj.csv, ct.csv    Open States' current New Jersey and Connecticut legislators (New York's ny.csv and the House
                    Clerk's list come from fetch_representatives.py)"""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, step, FAILED

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'region')
os.makedirs(OUT, exist_ok=True)
COUNTIES = {'36': ['027', '059', '071', '079', '087', '103', '119'],                  # Dutchess … Westchester
            '34': ['003', '013', '017', '021', '023', '025', '027', '031', '035', '039'],  # Bergen … Union
            '09': ['120', '140', '170', '190']}                                       # CT planning regions
S, W, N, E = json.load(open(os.path.join(HERE, 'region.json')))['bbox']
TW = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/'
GROUPS = ['B25003', 'B08301', 'B25075', 'B25063', 'B25036', 'B25032', 'C16001', 'B01001', 'B05005']
SF = 'https://www2.census.gov/programs-surveys/acs/summary_file/{y}/table-based-SF/'
PREFIXES = tuple('1400000US' + st + c for st, cs in COUNTIES.items() for c in cs)


def save(name, obj):
    json.dump(obj, open(os.path.join(OUT, name), 'w'), separators=(',', ':'))
    print('  saved', name, flush=True)


def query(path, where, fields, extra=None):
    feats, off = [], 0
    while True:
        q = dict({'where': where, 'outFields': fields, 'outSR': 4326, 'f': 'geojson', 'geometryPrecision': 5,
                  'maxAllowableOffset': 0.0001, 'resultOffset': off, 'resultRecordCount': 500}, **(extra or {}))
        d = json.loads(get(TW + path + '/query?' + urllib.parse.urlencode(q)))
        if 'error' in d: raise RuntimeError(d['error'])
        feats += d.get('features', [])
        if len(d.get('features', [])) < 500: return feats
        off += 500; time.sleep(1)


def tracts():
    feats = []
    for st, cs in COUNTIES.items():
        for c in cs:
            feats += query('Tracts_Blocks/MapServer/0', f"STATE='{st}' AND COUNTY='{c}'", 'GEOID')
            print('  tracts so far', len(feats), flush=True)
    save('tracts.geojson', {'type': 'FeatureCollection', 'features': feats})


def districts():
    box = {'geometry': f'{W},{S},{E},{N}', 'geometryType': 'esriGeometryEnvelope', 'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects'}
    for name, layer in (('congress', 0), ('upper', 1), ('lower', 2)):
        f = query(f'Legislative/MapServer/{layer}', "STATE IN ('09','34','36')", 'STATE,BASENAME,NAME', box)
        save(name + '.geojson', {'type': 'FeatureCollection', 'source': f'U.S. Census Bureau TIGERweb (Legislative/MapServer/{layer})', 'features': f})
        print(' ', name, len(f), flush=True); time.sleep(2)


def legislators():
    for st in ('nj', 'ct'):
        b = get(f'https://data.openstates.org/people/current/{st}.csv')
        open(os.path.join(OUT, st + '.csv'), 'wb').write(b); print('  saved', st + '.csv', len(b), flush=True)


def labels_for(year, g):
    d = json.loads(get(f'https://api.census.gov/data/{year}/acs/acs5/groups/{g}.json', tries=2))['variables']
    return {k[:-1].replace('_', '_E', 1): v['label'] for k, v in d.items() if k.endswith('E') and k.startswith(g + '_')}


def acs():
    for year in (2024, 2023):
        root = SF.format(y=year)
        try: get(root + 'data/5YRData/', tries=1)
        except Exception as e:
            print('ACS', year, 'not available:', e); continue
        tr, labels = {}, {}
        for g in GROUPS:
            try: labels.update(labels_for(year, g))
            except Exception as e: print('  labels for', g, 'failed:', e)
            body = get(root + f'data/5YRData/acsdt5y{year}-{g.lower()}.dat').decode('utf8', 'replace').splitlines()
            head = body[0].split('|')
            for line in body[1:]:
                if not line.startswith(PREFIXES): continue
                row = dict(zip(head, line.split('|')))
                t = tr.setdefault(row['GEO_ID'][9:], {})
                for k, v in row.items():
                    if k.startswith(g + '_E'):
                        try: t[k] = int(float(v)) if float(v) >= 0 else None
                        except ValueError: t[k] = None
            print(' ', g, 'tracts so far', len(tr), flush=True); time.sleep(2)
        save('acs_tracts.json', {'year': year, 'source': root, 'labels': labels, 'tracts': tr})
        return
    raise RuntimeError('no ACS year available')


for label, fn in [('districts', districts), ('legislators', legislators), ('tracts', tracts), ('acs', acs)]:
    print('==', label, flush=True); step(label, fn)
print('FAILED:', FAILED or 'none')
