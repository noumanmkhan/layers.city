"""Fetch New York City's emergency departments from the New York State Department of Health (Health Data NY, open
data): every hospital site in the five boroughs certified for the "Emergency Department" service (Health Facility
Certification Information, 2g9y-7kqm), placed and named from Health Facility General Information (vn5v-hh5r), as
raw/institutions/nys_ed.json, for the card's nearest-ER row (places.py). Site-level, so each campus of a hospital
system counts on its own (federal CMS data lists a system once). Run from GitHub Actions (*Fetch New York City data*;
the sandbox can't reach health.data.ny.gov).

Usage: python3 cities/nyc/fetch_er.py"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'institutions')
API = 'https://health.data.ny.gov/resource/'
COUNTIES = "('New York','Kings','Queens','Bronx','Richmond')"
os.makedirs(OUT, exist_ok=True)


def soql(rid, **params):
    q = urllib.parse.urlencode({**{'$' + k: v for k, v in params.items()}, '$limit': 5000})
    for attempt in range(4):
        try:
            req = urllib.request.Request(API + rid + '.json?' + q, headers={'User-Agent': 'layers.city pipeline (go@layers.city)'})
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except Exception as ex:
            print(f'{rid} try {attempt + 1} failed: {ex}', flush=True)
            if attempt == 3:
                raise
            time.sleep(30)


cert = soql('2g9y-7kqm', where=f"attribute_value = 'Emergency Department' AND county IN {COUNTIES}")
ids = sorted({r['fac_id'] for r in cert})
print(f'{len(cert)} certification rows, {len(ids)} sites with an emergency department')
info = {}
for i in range(0, len(ids), 50):
    for r in soql('vn5v-hh5r', where='fac_id IN (' + ','.join(f"'{x}'" for x in ids[i:i + 50]) + ')'):
        info[r['fac_id']] = r
sites = []
for fid in ids:
    r = info.get(fid)
    if not r or not r.get('latitude'):
        print('no location for', fid, next((c['primary_nam'] for c in cert if c['fac_id'] == fid), ''))
        continue
    sites.append({'id': fid, 'name': r['facility_name'], 'address': r.get('address1'), 'zip': r.get('fac_zip'),
                  'county': r.get('county'), 'type': r.get('description'), 'operator': r.get('operator_name'),
                  'lat': round(float(r['latitude']), 6), 'lon': round(float(r['longitude']), 6)})
json.dump({'asof': time.strftime('%Y-%m-%d'), 'source': 'New York State Department of Health, Health Data NY '
           '(Health Facility Certification Information; Health Facility General Information)', 'sites': sites},
          open(os.path.join(OUT, 'nys_ed.json'), 'w'), indent=1, ensure_ascii=False)
print(f'{len(sites)} emergency departments placed:', [s['name'] for s in sites])
