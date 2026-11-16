"""The Metroplex beyond the City of Dallas, for the ZIP lens and Living here on the card beyond the
City. Run from GitHub Actions (fetch-region-basemap.yml runs a city's fetch_region.py after the shared fetches); the
sandbox can't reach census.gov. Writes raw/region/:
  zctas.geojson     every ZIP Code Tabulation Area in the nine counties' box (2020 cartographic boundaries)
  acs_zcta.json     ACS 5-year for those ZCTAs, the same tables and form as fetch_zips.py
(The Texas House, Senate and congressional districts already cover the nine counties: fetch_representatives.py.)"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import *

OUT = os.path.join(RAW, 'region')
os.makedirs(OUT, exist_ok=True)
GROUPS = ['B25003', 'B08301', 'B25075', 'B25063', 'B25032', 'B25036', 'C16001', 'B01001', 'B05005']
SF = 'https://www2.census.gov/programs-surveys/acs/summary_file/{y}/table-based-SF/'


def zctas():
    z = download('https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_zcta520_500k.zip', os.path.join(TMP, 'zcta.zip'))
    S, W, N, E = json.load(open(os.path.join(HERE, 'region.json')))['bbox']
    shp_to_geojson(z, '1=1', os.path.join('region', 'zctas.geojson'), spat=(W, S, E, N))


def labels_for(year, g):
    d = json.loads(get(f'https://api.census.gov/data/{year}/acs/acs5/groups/{g}.json'))['variables']
    return {k[:-1].replace('_', '_E', 1): v['label'] for k, v in d.items() if k.endswith('E') and k.startswith(g + '_')}


def acs():
    want = {f['properties']['ZCTA5CE20'] for f in json.load(open(os.path.join(OUT, 'zctas.geojson')))['features']}
    print('ZCTAs wanted', len(want))
    for year in (2024, 2023):
        root = SF.format(y=year)
        try:
            get(root + 'data/5YRData/', tries=1)
        except Exception as e:
            print('ACS', year, 'not available:', e); continue
        rows, labels = {}, {}
        for g in GROUPS:
            try: labels.update(labels_for(year, g))
            except Exception as e: print('labels for', g, 'failed:', e)
            body = get(root + f'data/5YRData/acsdt5y{year}-{g.lower()}.dat').decode('utf8', 'replace').splitlines()
            head = body[0].split('|')
            for line in body[1:]:
                if not line.startswith('860Z200US'): continue
                row = dict(zip(head, line.split('|')))
                z = row['GEO_ID'][9:]
                if z not in want: continue
                t = rows.setdefault(z, {})
                for k, v in row.items():
                    if k.startswith(g + '_E'):
                        try: t[k] = int(float(v)) if float(v) >= 0 else None
                        except ValueError: t[k] = None
            print(g, 'ZCTAs so far', len(rows), flush=True)
            time.sleep(2)
        json.dump({'year': year, 'source': root, 'labels': labels, 'zctas': rows}, open(os.path.join(OUT, 'acs_zcta.json'), 'w'), separators=(',', ':'))
        return
    raise RuntimeError('no ACS year available')


for label, fn in [('zctas', zctas), ('acs', acs)]:
    print('==', label, flush=True); step(label, fn)
print('FAILED:', FAILED or 'none')
