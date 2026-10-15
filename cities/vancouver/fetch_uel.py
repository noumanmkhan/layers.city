"""Nearby places and bikeways in the University Endowment Lands, which the City's open data doesn't cover, into raw/.
Run from GitHub Actions (fetch-vancouver.yml, and monthly by fetch-vancouver-places.yml); the sandbox can't reach Overpass.

From OpenStreetMap: named parks, playgrounds, dog off-leash areas, tennis courts and community centres inside the
Point Grey box, into raw/uel_osm.json (nearby.py keeps those inside the UEL itself). Private and customers-only places
are left out. Also raw/uel_bikes.geojson: OpenStreetMap's bike paths and lanes there, written with the City's own Bikeways
types so bikes.json's classes apply (engine/bikes.py reads it as bikes.json "extra", clipped to the UEL): a cycleway is an
off-street bike path (Protected Bike Lanes|OSB, OSS if signed for walking too), a path signed for bikes a shared path
(OSS), a cycle track a protected lane (SL) and a painted lane a painted lane (NB)."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_lib as F

S, W, N, E = 49.225, -123.275, 49.285, -123.19
Q = f"""[out:json][timeout:180];
(nwr["leisure"="park"]["name"]({S},{W},{N},{E});
 nwr["leisure"="playground"]({S},{W},{N},{E});
 nwr["leisure"="dog_park"]({S},{W},{N},{E});
 nwr["leisure"="pitch"]["sport"~"tennis"]({S},{W},{N},{E});
 nwr["amenity"="community_centre"]["name"]({S},{W},{N},{E}););
out tags center;"""
d = F.overpass(Q, 'uel_osm_full.json')
out = []
for el in d.get('elements', []):
    t, c = el.get('tags', {}), (el if el['type'] == 'node' else el.get('center'))
    if not c or t.get('access') in ('private', 'customers', 'members', 'no'): continue
    kind = 'tennis' if t.get('leisure') == 'pitch' else t.get('leisure') or t.get('amenity')
    out.append({'osm': el['type'][0] + str(el['id']), 'kind': kind, 'name': t.get('name', ''), 'operator': t.get('operator', ''),
                'at': [round(c['lon'], 5), round(c['lat'], 5)]})
os.remove(os.path.join(F.RAW, 'uel_osm_full.json'))
F.save('uel_osm.json', sorted(out, key=lambda x: (x['kind'], x['name'])))
for x in out: print(' ', x['kind'], '|', x['name'], '|', x['operator'], x['at'])

# ---------- Bike paths and lanes ----------
QB = f"""[out:json][timeout:180];
(way["highway"="cycleway"]({S},{W},{N},{E});
 way["highway"~"^(path|footway)$"]["bicycle"="designated"]({S},{W},{N},{E});
 way["highway"]["cycleway"~"^(lane|track)$"]({S},{W},{N},{E});
 way["highway"]["cycleway:both"~"^(lane|track)$"]({S},{W},{N},{E});
 way["highway"]["cycleway:right"~"^(lane|track)$"]({S},{W},{N},{E});
 way["highway"]["cycleway:left"~"^(lane|track)$"]({S},{W},{N},{E}););
out tags geom;"""
b = F.overpass(QB, 'uel_bikes_full.json')
feats = []
for w in b.get('elements', []):
    t, g = w.get('tags', {}), w.get('geometry') or []
    if len(g) < 2 or t.get('access') in ('private', 'no'): continue
    lanes = {t.get(k) for k in ('cycleway', 'cycleway:both', 'cycleway:right', 'cycleway:left')}
    if t['highway'] == 'cycleway': typ, sub = 'Protected Bike Lanes', 'OSB' if t.get('foot') not in ('designated', 'yes') else 'OSS'
    elif t['highway'] in ('path', 'footway'): typ, sub = 'Protected Bike Lanes', 'OSS'
    elif 'track' in lanes: typ, sub = 'Protected Bike Lanes', 'SL'
    else: typ, sub = 'Painted Lanes', 'NB'
    feats.append({'type': 'Feature', 'properties': {'bike_route_name': t.get('name') or '', 'street_name': t.get('name') or '', 'bikeway_type': typ,
                  'subtype': sub, 'status': 'Active', 'year_of_construction': None, 'source': 'OpenStreetMap'},
                  'geometry': {'type': 'LineString', 'coordinates': [[round(p['lon'], 6), round(p['lat'], 6)] for p in g]}})
os.remove(os.path.join(F.RAW, 'uel_bikes_full.json'))
F.save('uel_bikes.geojson', {'type': 'FeatureCollection', 'features': feats})
from collections import Counter
print('bike ways:', len(feats), dict(Counter((f['properties']['bikeway_type'], f['properties']['subtype']) for f in feats)))
