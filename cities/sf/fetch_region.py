"""The Bay Area beyond San Francisco, for the lens, Living here and Representatives on the card beyond the City.
Run from GitHub Actions (fetch-region-basemap.yml runs a city's fetch_region.py after the shared fetches); the
sandbox can't reach census.gov. Writes raw/region/:
  acs_tracts.json   ACS 5-year, the same tables and form as fetch_acs.py, for every tract in the other eight counties
  tracts.geojson    those tracts' boundaries (TIGERweb Tracts_Blocks layer 0): GEOID
  upper.geojson, lower.geojson   State Senate and Assembly districts in the region's box (TIGERweb Legislative 1, 2)
Congressional districts and the legislators come from fetch_representatives.py (they cover the whole state)."""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, step, FAILED

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'region')
os.makedirs(OUT, exist_ok=True)
COUNTIES = ['001', '013', '041', '055', '081', '085', '095', '097']   # Alameda … Sonoma (San Francisco is 075)
S, W, N, E = json.load(open(os.path.join(HERE, 'region.json')))['bbox']
TW = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/'
GROUPS = ['B25003', 'B08301', 'B25075', 'B25063', 'B25036', 'B25032', 'C16001', 'B01001', 'B05005']
SF = 'https://www2.census.gov/programs-surveys/acs/summary_file/{y}/table-based-SF/'
PREFIXES = tuple('1400000US06' + c for c in COUNTIES)


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
    for c in COUNTIES:
        feats += query('Tracts_Blocks/MapServer/0', f"STATE='06' AND COUNTY='{c}'", 'GEOID')
        print('  tracts so far', len(feats), flush=True)
    save('tracts.geojson', {'type': 'FeatureCollection', 'features': feats})


def districts():
    box = {'geometry': f'{W},{S},{E},{N}', 'geometryType': 'esriGeometryEnvelope', 'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects'}
    for name, layer in (('upper', 1), ('lower', 2)):
        f = query(f'Legislative/MapServer/{layer}', "STATE='06'", 'BASENAME,NAME', box)
        save(name + '.geojson', {'type': 'FeatureCollection', 'features': f}); print(' ', name, len(f))


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


for label, fn in [('districts', districts), ('tracts', tracts), ('acs', acs)]:
    print('==', label, flush=True); step(label, fn)
print('FAILED:', FAILED or 'none')
