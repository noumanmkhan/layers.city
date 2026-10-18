"""ACS 5-year tables for every tract in the five boroughs, for the community district lens and the card's
"Living here" rows. Runs in GitHub Actions (fetch-nyc.yml); the sandbox can't reach census.gov.
The same tables as Chicago's (fetch_extra.py and fetch_acs_more.py), read from the Census Bureau's table-based
summary files (no API key):
- B25003 tenure, B08301 means of transportation to work, B25075 owner home value brackets, B25063 cash rent brackets
- B25036 year structure built, B25032 units in structure (occupied homes), C16001 language at home (5 and over),
  B01001 sex by age, B05005 period of entry (the foreign-born)
Writes raw/acs_tracts.json {year, source, labels, tracts: {GEOID: {var: count}}} and raw/tracts.json
{GEOID: [lon, lat]} (TIGERweb internal points), used to place each tract in a community district."""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import *

GROUPS = ['B25003', 'B08301', 'B25075', 'B25063', 'B25036', 'B25032', 'C16001', 'B01001', 'B05005']
SF = 'https://www2.census.gov/programs-surveys/acs/summary_file/{y}/table-based-SF/'
PREFIXES = tuple('1400000US' + c for c in CITY_COUNTIES)


def labels_for(year, g):
    d = json.loads(get(f'https://api.census.gov/data/{year}/acs/acs5/groups/{g}.json', tries=2))['variables']
    return {k[:-1].replace('_', '_E', 1): v['label'] for k, v in d.items() if k.endswith('E') and k.startswith(g + '_')}


def acs():
    for year in (2024, 2023):
        root = SF.format(y=year)
        try:
            get(root + 'data/5YRData/', tries=1)
        except Exception as e:
            print('ACS', year, 'not available:', e); continue
        tracts, labels = {}, {}
        for g in GROUPS:
            try: labels.update(labels_for(year, g))
            except Exception as e: print('  labels for', g, 'failed:', e)
            body = get(root + f'data/5YRData/acsdt5y{year}-{g.lower()}.dat').decode('utf8', 'replace').splitlines()
            head = body[0].split('|')
            for line in body[1:]:
                if not line.startswith(PREFIXES): continue
                row = dict(zip(head, line.split('|')))
                t = tracts.setdefault(row['GEO_ID'][9:], {})
                for k, v in row.items():
                    if k.startswith(g + '_E'):
                        try: t[k] = int(float(v)) if float(v) >= 0 else None
                        except ValueError: t[k] = None
            print(' ', g, 'tracts so far', len(tracts)); time.sleep(2)
        save('acs_tracts.json', {'year': year, 'source': root, 'labels': labels, 'tracts': tracts})
        return
    raise RuntimeError('no ACS year available')


def tracts():
    pts = {}
    for c in CITY_COUNTIES:
        q = {'where': f"STATE='36' AND COUNTY='{c[2:]}'", 'outFields': 'GEOID,INTPTLAT,INTPTLON', 'returnGeometry': 'false', 'f': 'json', 'resultRecordCount': 2000}
        off = 0
        while True:
            q['resultOffset'] = off
            d = json.loads(get('https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0/query?' + urllib.parse.urlencode(q)))
            for f in d['features']:
                a = f['attributes']; pts[a['GEOID']] = [float(a['INTPTLON']), float(a['INTPTLAT'])]
            if not d.get('exceededTransferLimit') and len(d['features']) < 2000: break
            off += len(d['features'])
    save('tracts.json', pts)


for label, fn in [('tracts', tracts), ('acs', acs)]:
    print('==', label); step(label, fn)
print('FAILED:', FAILED or 'none')
