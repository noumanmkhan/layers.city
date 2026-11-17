"""Curated landmarks (names.py LANDMARKS): the places people give directions by. Not a points-of-interest database.
Each is placed at OpenStreetMap's point for the same name when one sits within 1.5 km of the hand position
(raw/pois.geojson, raw/places.json, raw/rail.geojson); otherwise the hand position stands, and the build says so.
Output: docs/dubai/data/landmarks.geojson"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from names import LANDMARKS, CAT_LABEL

OUT = os.path.join(HERE, '..', '..', 'docs', 'dubai', 'data', 'landmarks.geojson')
d = lambda a, b: math.hypot((a[0] - b[0]) * 101.0, (a[1] - b[1]) * 111.2)
raw = lambda f: json.load(open(os.path.join(HERE, 'raw', f), encoding='utf-8'))

osm = {}
for f in raw('pois.geojson')['features'] + [f for f in raw('rail.geojson')['features'] if f['geometry']['type'] == 'Point']:
    p = f['properties']; c = tuple(f['geometry']['coordinates'])
    rank = 0 if p.get('_km2') else 1   # an area's point beats a stray node (an entrance, a bus stop of the same name)
    for n in {p.get('name'), p.get('name:en')} - {None}: osm.setdefault(n.lower(), []).append((c, rank))
for p in raw('places.json'):
    if p.get('name'): osm.setdefault(p['name'].lower(), []).append((tuple(p['at']), 2))

feats = []
for l in LANDMARKS:
    lat, lon = l['at']
    cands = [(c, r) for c, r in osm.get(l['osm'].lower(), []) + osm.get(l['name'].lower(), []) if d(c, (lon, lat)) < 1.5]
    if cands:
        c = min(cands, key=lambda cr: (cr[1], d(cr[0], (lon, lat))))[0]
        moved = d(c, (lon, lat))
        if moved > 0.25: print('  moved %.2f km to OpenStreetMap: %s' % (moved, l['name']))
        lon, lat = c
    else:
        print('  hand position:', l['name'])
    feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(lon, 5), round(lat, 5)]},
                  'properties': {'name': l['name'], 'cat': l['cat'], 'catLabel': CAT_LABEL[l['cat']], 'tier': l['tier'], 'aliases': l['aliases']}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
print('landmarks:', len(feats))
