"""Fetch San Francisco's address points into cities/sf/raw/addresses.json, for the card's Address row (addresses.py):
where each street's numbers start and which way they rise. Runs in GitHub Actions (fetch-sf.yml).

DataSF 3mea-di5p, the Enterprise Addressing System's addresses (the City's official list): each base address's
number, street name and type, and position. Units at one address are dropped; numbers are kept as integers."""
import json, os, sys, time, urllib.parse
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, RAW

ID = '3mea-di5p'
first = json.loads(get(f'https://data.sfgov.org/resource/{ID}.json?$limit=1', tries=3))
print('fields:', sorted(first[0]) if first else None, first[:1])
f = set(first[0])
pick = lambda *c: next((x for x in c if x in f), None)
NUM, NAME, TYPE = pick('address_number', 'addr_num', 'number'), pick('street_name', 'st_name'), pick('street_type', 'st_type')
LON, LAT, PT = pick('longitude', 'lon'), pick('latitude', 'lat'), pick('point', 'the_geom', 'location')
print('using', NUM, NAME, TYPE, LON, LAT, PT)
sel = ','.join(x for x in (NUM, NAME, TYPE, LON, LAT, PT) if x)
seen, rows, off = set(), [], 0
while True:
    q = urllib.parse.urlencode({'$select': sel, '$limit': 50000, '$offset': off, '$order': ':id'})
    d = json.loads(get(f'https://data.sfgov.org/resource/{ID}.json?' + q, tries=3))
    for r in d:
        try:
            n = int(float(r.get(NUM)))
            if LON and r.get(LON): x, y = float(r[LON]), float(r[LAT])
            else: x, y = r[PT]['coordinates']
        except (TypeError, ValueError, KeyError):
            continue
        st = ' '.join(v for v in (r.get(NAME), r.get(TYPE)) if v).strip()
        k = (n, st)
        if not st or k in seen: continue
        seen.add(k); rows.append([st, n, round(x, 5), round(y, 5)])
    off += len(d); print('rows so far', len(rows), 'of', off, flush=True)
    if len(d) < 50000: break
if len(rows) < 50000: raise SystemExit(f'only {len(rows)} addresses: not saved')
json.dump({'source': f'DataSF {ID} (Enterprise Addressing System)', 'fetched': time.strftime('%Y-%m-%d'), 'rows': rows},
          open(os.path.join(RAW, 'addresses.json'), 'w'), separators=(',', ':'))
print(len(rows), 'addresses on', len({r[0] for r in rows}), 'streets;', Counter(r[0] for r in rows).most_common(5))
print('size', os.path.getsize(os.path.join(RAW, 'addresses.json')))
