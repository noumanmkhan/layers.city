"""Fetch the inputs for the Faith & Community layers into raw/faith/. Run from GitHub Actions (the
*Fetch faith and community places* workflow); the sandbox can't reach Overpass or Nominatim.

  worship_osm.json  Every named place of worship in and around Toronto from OpenStreetMap (Overpass API):
                    OSM id, centre, name, religion, denomination and address tags.
  geocode.json      Positions for the street addresses in faith_shops.csv and the "add" rows of
                    faith_overrides.csv that don't give their own lat/lon, from OpenStreetMap Nominatim.
                    A cache: addresses already placed are kept and not looked up again, so a run only
                    asks Nominatim about new rows (one request a second, as its usage policy asks)."""
import csv, json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'faith'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'city-layers-pipeline (layers.city; go@layers.city)'}
BBOX = (43.57, -79.65, 43.87, -79.10)   # the City of Toronto plus a margin, as for institutions
GTA = '-80.0,44.1,-78.8,43.4'           # Nominatim viewbox (left,top,right,bottom) for the shops across the GTA
ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
QUERY = f"""
[out:json][timeout:240];
nwr["amenity"="place_of_worship"]["name"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
out tags center;
"""
KEEP = ('name', 'alt_name', 'religion', 'denomination', 'addr:housenumber', 'addr:street', 'building')


def overpass():
    data = urllib.parse.urlencode({'data': QUERY}).encode()
    for attempt in range(6):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=300) as r:
                return json.load(r)
        except Exception as e:
            print('  retry', attempt + 1, url, e); time.sleep(20 * (attempt + 1))
    raise SystemExit('Overpass request failed')


els = []
for el in overpass().get('elements', []):
    t, c = el.get('tags', {}), (el if el.get('type') == 'node' else el.get('center'))
    if not c or 'lat' not in c: continue
    els.append({'osm': el['type'][0] + str(el['id']), 'at': [round(c['lon'], 5), round(c['lat'], 5)],
                **{k: t[k] for k in KEEP if k in t}})
els.sort(key=lambda e: (e.get('religion', '~'), e['name']))
json.dump({'source': 'OpenStreetMap contributors (ODbL) via Overpass API', 'bbox': BBOX, 'elements': els},
          open(os.path.join(OUT, 'worship_osm.json'), 'w'), ensure_ascii=False, indent=0)
by = {}
for e in els: by[e.get('religion', '(none)')] = by.get(e.get('religion', '(none)'), 0) + 1
print(len(els), 'named places of worship:', sorted(by.items(), key=lambda kv: -kv[1]))

# Geocoding: every address the curated lists need that has no lat/lon of its own.
want = []
for f, keep in (('faith_shops.csv', lambda r: True), ('faith_overrides.csv', lambda r: r['action'] == 'add')):
    for r in csv.DictReader(open(os.path.join(HERE, f), encoding='utf-8')):
        if keep(r) and r.get('address') and not (r.get('lat') and r.get('lon')):
            want.append(r['address'] + ', ' + r['locality'])
path = os.path.join(OUT, 'geocode.json')
cache = json.load(open(path)) if os.path.exists(path) else {}


def nominatim(q):
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(
        {'q': q, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'ca', 'viewbox': GTA, 'bounded': 1, 'addressdetails': 0})
    time.sleep(1.2)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        hits = json.load(r)
    return hits[0] if hits else None


for a in dict.fromkeys(want):
    if a in cache and cache[a].get('at'): continue
    hit = None
    for q in (a + ', Ontario, Canada', a.split(', ')[0] + ', Ontario, Canada'):
        try: hit = nominatim(q)
        except Exception as e: print('  error', q, e)
        if hit: break
    cache[a] = ({'at': [round(float(hit['lon']), 5), round(float(hit['lat']), 5)], 'match': hit.get('display_name', ''),
                 'type': hit.get('type', '')} if hit else {'at': None})
    print(('  placed  ' if hit else '  MISSING ') + a + ('  ->  ' + hit['display_name'] if hit else ''))
json.dump(dict(sorted(cache.items())), open(path, 'w'), ensure_ascii=False, indent=1)
missing = [a for a in dict.fromkeys(want) if not cache.get(a, {}).get('at')]
print(len(want), 'addresses,', len(missing), 'not found' + (': ' + '; '.join(missing) if missing else ''))
