"""Bike lanes: fetch a city's bike network into cities/<city>/raw/bikes.geojson for engine/bikes.py.
Runs in GitHub Actions (fetch-bikes.yml); the sandbox can't reach these servers. The source is set in
cities/<city>/bikes.json "source":

  - "ckan_geojson" (Toronto): the City's Cycling Network package; the newest GeoJSON resource in WGS84
    (its name has "4326").
  - "socrata_geojson" (Chicago): the City's Bike Routes (hvv9-38ut) as GeoJSON.

Keeps only the fields listed in "fields", rounds coordinates to 6 decimals, and adds "fetched" and "source" at
the top. The log lists how many segments carry each value of the type field ("typeField").
Usage: python3 engine/fetch_bikes.py <city>
"""
import collections, datetime as dt, json, os, sys, time, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
city = sys.argv[1]
CFG = json.load(open(os.path.join(ROOT, 'cities', city, 'bikes.json')))
OUT = os.path.join(ROOT, 'cities', city, 'raw', 'bikes.geojson')
UA = {'User-Agent': 'city-layers-pipeline (layers.city)'}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r: return r.read()
        except Exception as e:
            print('  retry', i + 1, url[:140], e); time.sleep(15 * (i + 1))
    raise RuntimeError('failed: ' + url)


def rnd(c):
    return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 6), round(c[1], 6)]


S = CFG['source']
if S['type'] == 'ckan_geojson':
    pkg = json.loads(get(S['ckan']))['result']
    res = [r for r in pkg['resources'] if (r.get('format') or '').lower() == 'geojson' and S.get('match', '') in r['name']]
    res.sort(key=lambda r: r.get('last_modified') or r.get('created') or '', reverse=True)
    r0 = res[0]
    print('resource:', r0['name'], r0['url'], 'modified', r0.get('last_modified'))
    url, updated = r0['url'], (r0.get('last_modified') or pkg.get('last_refreshed') or '')[:10]
else:
    url, updated = S['url'], None
    try:   # Socrata's view metadata carries the data's last update
        meta = json.loads(get(S['meta']))
        updated = dt.datetime.fromtimestamp(meta.get('rowsUpdatedAt') or meta.get('viewLastModified'), dt.timezone.utc).date().isoformat()
    except Exception as e:
        print('  no metadata:', e)
fc = json.loads(get(url))
keep = CFG['fields']
feats = []
for f in fc['features']:
    if not f.get('geometry'): continue
    feats.append({'type': 'Feature', 'properties': {k: f['properties'].get(k) for k in keep},
                  'geometry': {'type': f['geometry']['type'], 'coordinates': rnd(f['geometry']['coordinates'])}})
print('segments:', len(feats), 'of', len(fc['features']))
seen = {k for f in fc['features'][:200] for k in (f.get('properties') or {})}
print('fields in source:', sorted(seen))
for k in keep:
    if k not in seen: print('  missing field:', k)
print('types:', json.dumps(collections.Counter(f['properties'].get(CFG['typeField']) for f in feats).most_common(), indent=0))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({'type': 'FeatureCollection', 'fetched': dt.date.today().isoformat(), 'updated': updated, 'source': url, 'features': feats},
          open(OUT, 'w'), separators=(',', ':'))
print('wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')
