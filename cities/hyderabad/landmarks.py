"""Curated landmarks (names.py LANDMARKS): the places Hyderabadis give directions by. Not a points-of-interest
database. Each is placed at OpenStreetMap's point for the same name when one sits within 1.5 km of the
hand position (raw/osm_landmarks.json); otherwise the hand position stands, and the build says so.
Output: docs/hyderabad/data/landmarks.geojson"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from names import LANDMARKS, CAT_LABEL

OUT = os.path.join(HERE, '..', '..', 'docs', 'hyderabad', 'data', 'landmarks.geojson')
d = lambda a, b: math.hypot((a[0] - b[0]) * 106.2, (a[1] - b[1]) * 111.2)

osm = {}
for el in json.load(open(os.path.join(HERE, 'raw', 'osm_landmarks.json')))['elements']:
    c = (el.get('lon') or el.get('center', {}).get('lon'), el.get('lat') or el.get('center', {}).get('lat'))
    n = el.get('tags', {}).get('name')
    if n and c[0]: osm.setdefault(n, []).append((c, el['type']))

feats = []
for l in LANDMARKS:
    lat, lon = l['at']
    cands = [(c, t) for c, t in osm.get(l.get('osm', l['name']), []) if d(c, (lon, lat)) < 1.5]
    if cands:
        # A relation or way's centre beats a stray node (an entrance, a bus stop of the same name).
        c = min(cands, key=lambda ct: ({'area': 0, 'relation': 0, 'way': 1, 'node': 2}[ct[1]], d(ct[0], (lon, lat))))[0]
        moved = d(c, (lon, lat))
        if moved > 0.25: print('  moved %.2f km to OpenStreetMap: %s' % (moved, l['name']))
        lon, lat = c
    else:
        print('  hand position:', l['name'])
    feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(lon, 5), round(lat, 5)]},
                  'properties': {'name': l['name'], 'cat': l['cat'], 'catLabel': CAT_LABEL[l['cat']], 'tier': l['tier'], 'aliases': l['aliases']}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(OUT, 'w'), separators=(',', ':'))
print('landmarks:', len(feats))
