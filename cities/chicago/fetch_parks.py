"""Parks with their outlines, and the courts, fields, pools, skate parks, playgrounds and dog areas in them, from
OpenStreetMap (Overpass) -> raw/parks/osm_parks.json, for parks.py (the Parks and Sports & rec layers).

Why OpenStreetMap: the Chicago Park District's boundary and facility files on the City portal are from November 2016
and haven't been updated since; OSM is current and is what the card's Nearby counts already use. Parks: every
named leisure=park and nature_reserve with an outline in the city's box (parks.py keeps those inside the city).
Facilities: public pitches by sport, skate parks, swimming pools, playgrounds and dog parks; anything tagged
private, customers- or members-only is left out. Run by *Fetch Chicago data* when this script changes, or by hand.
"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'parks'); os.makedirs(OUT, exist_ok=True)
BBOX = '41.64,-87.95,42.03,-87.52'
PRIV = '["access"!~"private|customers|members|no"]'
Q = f"""
[out:json][timeout:600];
(
  way["leisure"~"^(park|nature_reserve)$"]["name"]({BBOX});
  relation["leisure"~"^(park|nature_reserve)$"]["name"]({BBOX});
);
out tags geom;
(
  nwr["leisure"="pitch"]{PRIV}({BBOX});
  nwr["leisure"="playground"]{PRIV}({BBOX});
  nwr["leisure"="dog_park"]{PRIV}({BBOX});
  nwr["leisure"="swimming_pool"]{PRIV}({BBOX});
  nwr["leisure"="sports_centre"]["sport"~"swimming"]{PRIV}({BBOX});
  nwr["sport"="skateboard"]{PRIV}({BBOX});
);
out tags center;
"""
for host in ('https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter', 'https://overpass.private.coffee/api/interpreter'):
    for i in range(3):
        try:
            req = urllib.request.Request(host, data=urllib.parse.urlencode({'data': Q}).encode(), headers={'User-Agent': 'layers.city data fetch'})
            res = json.load(urllib.request.urlopen(req, timeout=700))
            break
        except Exception as e:
            print('  ', host, 'try', i + 1, e); res = None; time.sleep(30)
    if res and res.get('elements'):
        break
else:
    raise SystemExit('Overpass failed; the last files stay')
json.dump({'fetched': time.strftime('%Y-%m-%d'), 'elements': res['elements']}, open(os.path.join(OUT, 'osm_parks.json'), 'w'), separators=(',', ':'))
from collections import Counter
print(len(res['elements']), 'elements', Counter(e['tags'].get('leisure') or e['tags'].get('sport') for e in res['elements']).most_common(12))
