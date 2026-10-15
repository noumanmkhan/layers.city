"""Fetch the ZIP-code areas that make up the City of Dallas, and their American Community Survey figures.
Runs in GitHub Actions (fetch-dallas.yml); the sandbox can't reach census.gov.

- ZIP Code Tabulation Areas (ZCTAs), the Census Bureau's 2020 cartographic boundaries, around the city
- ACS 5-year table-based summary file, ZCTA rows for: B25003 tenure, B08301 means of transportation to work,
  B25075 owner home values and B25063 cash rents (brackets, for medians), B25032 units in structure,
  B25036 year built, C16001 language at home, B01001 sex by age, B05005 period of entry
Writes raw/zctas.geojson and raw/acs_zcta.json: {year, source, labels: {var: label}, zctas: {ZIP: {var: count}}}.
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import *

GROUPS = ['B25003', 'B08301', 'B25075', 'B25063', 'B25032', 'B25036', 'C16001', 'B01001', 'B05005']
SF = 'https://www2.census.gov/programs-surveys/acs/summary_file/{y}/table-based-SF/'


def zctas():
    z = download('https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_zcta520_500k.zip', os.path.join(TMP, 'zcta.zip'))
    shp_to_geojson(z, '1=1', 'zctas.geojson', spat=(CITY[0] - 0.05, CITY[1] - 0.05, CITY[2] + 0.05, CITY[3] + 0.05))


def labels_for(year, g):
    d = json.loads(get(f'https://api.census.gov/data/{year}/acs/acs5/groups/{g}.json'))['variables']
    return {k[:-1].replace('_', '_E', 1): v['label'] for k, v in d.items() if k.endswith('E') and k.startswith(g + '_')}


def acs():
    want = {f['properties']['ZCTA5CE20'] for f in json.load(open(os.path.join(RAW, 'zctas.geojson')))['features']}
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
            print(g, 'ZCTAs so far', len(rows))
            time.sleep(2)
        save('acs_zcta.json', {'year': year, 'source': root, 'labels': labels, 'zctas': rows})
        return
    raise RuntimeError('no ACS year available')


for label, fn in [('zctas', zctas), ('acs', acs)]:
    print('==', label); step(label, fn)
print('FAILED:', FAILED or 'none')
