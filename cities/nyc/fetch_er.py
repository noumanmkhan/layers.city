"""Fetch CMS Hospital General Information (data.cms.gov provider data, xubh-q36u, a federal public file) and keep the
New York City rows (the five boroughs' counties) as raw/institutions/cms_hospitals.csv. places.py matches them to the
Facilities Database's hospitals by ZIP and street address, then by name, to say which have an emergency department
("Emergency Services: Yes"), for the card's nearest-ER row; Chicago's map uses the same file. Run from GitHub Actions
(*Fetch New York City data*; the sandbox can't reach data.cms.gov).

Usage: python3 cities/nyc/fetch_er.py"""
import csv, io, os, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'institutions')
URL = 'https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0/download?format=csv'
COUNTIES = {'NEW YORK', 'KINGS', 'QUEENS', 'BRONX', 'RICHMOND'}
os.makedirs(OUT, exist_ok=True)

raw = None
for attempt in range(4):
    try:
        req = urllib.request.Request(URL, headers={'User-Agent': 'layers.city pipeline (go@layers.city)'})
        with urllib.request.urlopen(req, timeout=300) as r:
            raw = r.read()
        break
    except Exception as ex:
        print(f'try {attempt + 1} failed: {ex}', flush=True)
        time.sleep(30)
if not raw:
    raise SystemExit('CMS hospital file not found')
rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
print('columns:', list(rows[0].keys()))
nyc = [r for r in rows if r.get('State') == 'NY' and (r.get('County/Parish') or r.get('County Name') or '').upper() in COUNTIES]
with open(os.path.join(OUT, 'cms_hospitals.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(nyc)
print(f'CMS: {len(rows)} hospitals, {len(nyc)} in the five boroughs, '
      f'{sum(r.get("Emergency Services") == "Yes" for r in nyc)} with emergency services')
