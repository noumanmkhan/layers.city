"""Fetch the inputs for the Faith & Community layers into raw/faith/. Run from GitHub Actions (fetch-chicago.yml); the sandbox can't reach Overpass or Nominatim.

  worship_osm.json  Every named place of worship in and around Chicago, plus those of other faiths than
                    Christianity across Chicagoland, from OpenStreetMap (Overpass API):
                    OSM id, centre, name, religion, denomination and address tags.
  geocode.json      Positions for the street addresses in faith_shops.csv and the "add" rows of
                    faith_overrides.csv that don't give their own lat/lon, from OpenStreetMap Nominatim, or the US Census
                    geocoder where Nominatim has no match.
                    A cache: addresses already placed are kept and not looked up again, so a run only
                    asks Nominatim about new rows (one request a second, as its usage policy asks)."""
import csv, json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'faith'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'city-layers-pipeline (layers.city; go@layers.city)'}
BBOX = (41.62, -87.96, 42.05, -87.50)   # the City of Chicago (O'Hare included) plus a margin
# Other faiths across the six counties: most of Chicagoland's gurdwaras and Hindu temples (and many mosques)
# are in the suburbs, so inside the city alone the Gurdwaras toggle would be empty. Churches stay city-only:
# there are some 2,300 inside it already.
WIDE = (41.10, -88.70, 42.55, -87.50)
REGION = '-88.7,42.55,-87.5,41.1'       # Nominatim viewbox (left,top,right,bottom): the shops across Chicagoland
ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
QUERY = f"""
[out:json][timeout:240];
(nwr["amenity"="place_of_worship"]["name"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
 nwr["amenity"="place_of_worship"]["name"]["religion"]["religion"!="christian"]({WIDE[0]},{WIDE[1]},{WIDE[2]},{WIDE[3]}););
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
        {'q': q, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'us', 'viewbox': REGION, 'bounded': 1, 'addressdetails': 0})
    time.sleep(1.2)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        hits = json.load(r)
    return hits[0] if hits else None


def census(q):
    # US Census geocoder (public domain), for street addresses Nominatim doesn't know.
    url = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?' + urllib.parse.urlencode(
        {'address': q, 'benchmark': 'Public_AR_Current', 'format': 'json'})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        m = json.load(r)['result']['addressMatches']
    return {'lon': m[0]['coordinates']['x'], 'lat': m[0]['coordinates']['y'], 'display_name': m[0]['matchedAddress'] + ' (Census)',
            'type': 'census'} if m else None


def exact(hit, a):
    # Nominatim often settles for the street when it doesn't know the building: that can be miles off
    # (Lee St in Des Plaines placed at O'Hare). Keep a hit only if it names the house number and the town.
    num, town = a.split(' ')[0], a.split(', ')[-1]
    d = hit.get('display_name', '')
    return bool(re.search(r'(^|, )(\d+-)?' + re.escape(num) + r'(-\d+)?,', d)) and town.lower() in d.lower()


for a in dict.fromkeys(want):
    if a in cache and cache[a].get('at') and cache[a].get('type') != 'street': continue
    hit, street = None, None
    for q in (a + ', Illinois, USA', a.split(', ')[0] + ', Illinois, USA'):
        try: h = nominatim(q)
        except Exception as e: print('  error', q, e); h = None
        if h and exact(h, a): hit = h; break
        street = street or h
    if not hit:   # the Census geocoder interpolates along the block from the address ranges
        try: hit = census(a + ', IL')
        except Exception as e: print('  census error', a, e)
    if not hit and street: hit = dict(street, type='street')
    cache[a] = ({'at': [round(float(hit['lon']), 5), round(float(hit['lat']), 5)], 'match': hit.get('display_name', ''),
                 'type': hit.get('type', '')} if hit else {'at': None})
    print(('  placed  ' if hit else '  MISSING ') + a + ('  ->  ' + hit['display_name'] if hit else ''))
json.dump(dict(sorted(cache.items())), open(path, 'w'), ensure_ascii=False, indent=1)
missing = [a for a in dict.fromkeys(want) if not cache.get(a, {}).get('at')]
rough = [a for a in dict.fromkeys(want) if cache.get(a, {}).get('type') == 'street']
if rough: print('  ONLY THE STREET FOUND (give lat/lon in the CSV):', '; '.join(rough))
print(len(want), 'addresses,', len(missing), 'not found' + (': ' + '; '.join(missing) if missing else ''))
