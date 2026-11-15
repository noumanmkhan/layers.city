"""Points for the What's here card's Nearby section beyond a city, from OpenStreetMap via Overpass, into
cities/<city>/raw/region_basemap/places.json: libraries, community centres, hospitals (with emergency=*),
playgrounds, named places of worship (religion, denomination) and named schools (isced:level, grades), one [lon, lat, name, extra] per place (areas as
their centre). The box is cities/<city>/region.json "bbox". Usage: python3 engine/region/fetch_places.py <city>
(fetch-region-basemap.yml). Each city's own script turns these into its nearby file, adding schools from its own list."""
import json, os, sys, time, urllib.parse, urllib.request

CITY = sys.argv[1]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'cities', CITY)
S, W, N, E = json.load(open(os.path.join(ROOT, 'region.json')))['bbox']
OUT = os.path.join(ROOT, 'raw', 'region_basemap')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'layers.city-pipeline (go@layers.city)'}


def get(url, data=None, tries=6, timeout=300):
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            print('  retry', a + 1, url[:90], e, flush=True)
            time.sleep(10 * (a + 1))
    raise SystemExit('failed: ' + url)


# ---------- places (OpenStreetMap) ----------
Q = """[out:json][timeout:600];
(
  nwr["amenity"="library"]({b});
  nwr["amenity"="community_centre"]({b});
  nwr["leisure"="sports_centre"]["name"~"[Cc]ommunity|[Rr]ecreation|[Cc]entre|[Cc]enter|[Cc]omplex|[Aa]rena"]({b});
  nwr["amenity"="hospital"]({b});
  nwr["leisure"="playground"]({b});
  nwr["amenity"="place_of_worship"]["name"]({b});
  nwr["amenity"="school"]["name"]({b});
);
out tags center;"""
b = '%s,%s,%s,%s' % (S, W, N, E)
res = None
for ep in ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']:
    try:
        res = json.loads(get(ep, urllib.parse.urlencode({'data': Q.format(b=b)}).encode(), tries=4, timeout=900)); break
    except SystemExit as e:
        print(e)
if res is None:
    raise SystemExit('Overpass failed')
out = {k: [] for k in ('library', 'centre', 'hospital', 'playground', 'worship', 'school')}
for el in res.get('elements', []):
    t = el.get('tags', {})
    c = (el.get('lon'), el.get('lat')) if el['type'] == 'node' else ((el.get('center') or {}).get('lon'), (el.get('center') or {}).get('lat'))
    if c[0] is None:
        continue
    p = [round(c[0], 5), round(c[1], 5), t.get('name', '')]
    if t.get('amenity') == 'library':
        out['library'].append(p)
    elif t.get('amenity') == 'community_centre' or t.get('leisure') == 'sports_centre':
        out['centre'].append(p)
    elif t.get('amenity') == 'hospital':
        out['hospital'].append(p + [{'emergency': t.get('emergency', ''), 'type': t.get('healthcare:speciality', '')}])
    elif t.get('leisure') == 'playground':
        out['playground'].append(p)
    elif t.get('amenity') == 'school':
        out['school'].append(p + [{'isced': t.get('isced:level', ''), 'grades': t.get('grades', '')}])
    elif t.get('amenity') == 'place_of_worship':
        out['worship'].append(p + [{'religion': t.get('religion', ''), 'denomination': t.get('denomination', '')}])
json.dump({'source': 'OpenStreetMap contributors (ODbL) via Overpass API', 'fetched': time.strftime('%Y-%m-%d'),
           'bbox': [S, W, N, E], 'groups': out}, open(os.path.join(OUT, 'places.json'), 'w'), separators=(',', ':'))
print('places:', {k: len(v) for k, v in out.items()})
