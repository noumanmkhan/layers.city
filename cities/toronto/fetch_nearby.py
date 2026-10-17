"""Fetch the City's parks and recreation facilities and Toronto Public Library branches for the card's
Nearby section, into raw/nearby/. Run from GitHub Actions (the *Fetch nearby places* workflow); the
sandbox can't download from Toronto Open Data.

  parks_rec.geojson   "Parks and Recreation Facilities" (Parks, Forestry & Recreation; refreshed monthly):
                      every City park and community recreation centre, with up to 20 listed amenities
                      (pools, rinks, tennis, playgrounds...) in one comma-separated AMENITIES field.
  tpl_branches.json   "Library Branch General Information" (Toronto Public Library): the 100-odd
                      branches with name, address, position and whether it's a physical branch.
  green_spaces.geojson  "Green Spaces" (Geospatial Competency Centre with Parks, Forestry & Recreation):
                      park and open-space outlines, every AREA_CLASS, trimmed to name, class and id with
                      positions rounded to 6 decimals (about 10 cm). parks.py keeps the City parks.
  water_play_osm.json Splash pads and wading pools from OpenStreetMap (Overpass API): the City's parks list
                      doesn't name them. Optional: if Overpass is down the rest is still written."""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'nearby'); os.makedirs(OUT, exist_ok=True)
CKAN = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/'
UA = {'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)'}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, url, e); time.sleep(10 * (i + 1))
    raise SystemExit('failed: ' + url)


def resource(package, want):
    pkg = json.loads(get(CKAN + 'package_show?id=' + package))['result']
    for r in pkg['resources']:
        if want(r): return r['url'], pkg.get('last_refreshed')
    raise SystemExit(f'{package}: no matching resource')


url, refreshed = resource('parks-and-recreation-facilities', lambda r: r['name'].endswith('4326.geojson'))
open(os.path.join(OUT, 'parks_rec.geojson'), 'wb').write(get(url))
fc = json.load(open(os.path.join(OUT, 'parks_rec.geojson')))
am = {}
for f in fc['features']:
    for a in (f['properties'].get('AMENITIES') or '').split(', '):
        am[a] = am.get(a, 0) + 1
print('parks and recreation:', len(fc['features']), 'locations, refreshed', refreshed)
print('  amenities:', sorted(am.items(), key=lambda kv: -kv[1]))
print('  types:', sorted({f['properties'].get('TYPE') for f in fc['features']}))

url, refreshed = resource('library-branch-general-information', lambda r: r.get('datastore_active'))
rows = json.loads(get(CKAN + 'datastore_search?resource_id=' + url.rstrip('/').split('/')[-1] + '&limit=1000'))['result']['records']
json.dump(rows, open(os.path.join(OUT, 'tpl_branches.json'), 'w'), ensure_ascii=False, indent=0)
print('library branches:', len(rows), 'refreshed', refreshed)

# Park outlines. The file is large, so only what the map needs is kept.
url, refreshed = resource('green-spaces', lambda r: r['name'].endswith('4326.geojson'))
gs = json.loads(get(url))
rnd = lambda c: [round(c[0], 6), round(c[1], 6)] if isinstance(c[0], (int, float)) else [rnd(x) for x in c]
keep, cls = [], {}
for f in gs['features']:
    p, g = f['properties'], f.get('geometry')
    if not g: continue
    cls[p.get('AREA_CLASS')] = cls.get(p.get('AREA_CLASS'), 0) + 1
    keep.append({'type': 'Feature', 'properties': {'id': p.get('AREA_ID'), 'name': p.get('AREA_NAME'), 'class': p.get('AREA_CLASS')},
                 'geometry': {'type': g['type'], 'coordinates': rnd(g['coordinates'])}})
json.dump({'type': 'FeatureCollection', 'refreshed': refreshed, 'features': keep},
          open(os.path.join(OUT, 'green_spaces.geojson'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('green spaces:', len(keep), 'areas, refreshed', refreshed)
print('  classes:', sorted(cls.items(), key=lambda kv: -kv[1]))

# Splash pads and wading pools (OpenStreetMap). Points or outlines, kept as a centre each.
BBOX = (43.57, -79.65, 43.87, -79.10)
Q = f"""[out:json][timeout:180];
(nwr["leisure"="splash_pad"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
 nwr["playground"="splash_pad"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
 nwr["leisure"="swimming_pool"]["swimming_pool"="wading"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
 nwr["leisure"="swimming_pool"]["name"~"[Ww]ading"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}););
out tags center;"""
res = None
for attempt in range(6):
    ep = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'][attempt % 2]
    try:
        with urllib.request.urlopen(urllib.request.Request(ep, data=urllib.parse.urlencode({'data': Q}).encode(), headers={'User-Agent': 'city-layers-pipeline (layers.city; go@layers.city)'}), timeout=240) as r:
            res = json.load(r); break
    except Exception as e:
        print('  overpass retry', attempt + 1, ep, e); time.sleep(20 * (attempt + 1))
if res is None:
    print('water play: Overpass unavailable, kept the previous file')
else:
    els = []
    for el in res.get('elements', []):
        t, c = el.get('tags', {}), (el if el.get('type') == 'node' else el.get('center'))
        if not c or 'lat' not in c or t.get('access') in ('private', 'no'): continue
        kind = 'wading' if t.get('leisure') == 'swimming_pool' else 'splash'
        els.append({'osm': el['type'][0] + str(el['id']), 'at': [round(c['lon'], 6), round(c['lat'], 6)], 'kind': kind, 'name': t.get('name', '')})
    json.dump({'source': 'OpenStreetMap contributors (ODbL) via Overpass API', 'fetched': time.strftime('%Y-%m-%d'), 'elements': els},
              open(os.path.join(OUT, 'water_play_osm.json'), 'w'), ensure_ascii=False, indent=0)
    print('water play:', sum(e['kind'] == 'splash' for e in els), 'splash pads,', sum(e['kind'] == 'wading' for e in els), 'wading pools')
