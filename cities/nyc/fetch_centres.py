"""Fetch NYC Parks' recreation centers into raw/places/rec_centers.json. Run from GitHub Actions (fetch-nyc.yml).

Source: NYC Parks Structures (data.cityofnewyork.us n8q6-i44s, updated monthly), every building on parkland with
its functions. The Facilities Database names only a handful of Parks recreation centers, so this is where the
full list comes from. Keeps the structures whose function includes "recreation center", with every column, and
writes the dataset's column names so places.py can be checked against them."""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'places'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'city-layers-pipeline (layers.city; go@layers.city)'}
BASE = 'https://data.cityofnewyork.us/resource/n8q6-i44s.json'


def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r: return json.load(r)
        except Exception as e:
            print('  retry', i + 1, e); time.sleep(10 * (i + 1))
    raise SystemExit('failed: ' + url)


rows, off = [], 0
while True:
    page = get(BASE + '?' + urllib.parse.urlencode({'$limit': 50000, '$offset': off}))
    rows += page; off += len(page)
    if len(page) < 50000: break
cols = sorted({k for r in rows for k in r})
rec = [r for r in rows if any(isinstance(v, str) and 'recreation center' in v.lower() for v in r.values())]
json.dump({'source': 'NYC Parks Structures (NYC Open Data n8q6-i44s)', 'fetched': time.strftime('%Y-%m-%d'),
           'columns': cols, 'structures': len(rows), 'records': rec},
          open(os.path.join(OUT, 'rec_centers.json'), 'w'), ensure_ascii=False, indent=1)
print(len(rows), 'structures;', len(rec), 'with a recreation center function; columns:', ', '.join(cols))
for r in rec[:5]: print('  e.g.', {k: v for k, v in r.items() if k != 'the_geom' and k != 'multipolygon'})
