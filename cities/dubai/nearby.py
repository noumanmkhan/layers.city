"""Points for the card's Nearby section -> docs/dubai/data/nearby.json (the shape Toronto's and Melbourne's use):
the nearest library, community centre, hospital and tagged emergency department, places of worship by faith (shown
only while their layer is on), and counts within 800 m of parks, beaches, sports places and schools. Everything comes
from the published layers (places_more.py, run first), so the card and the map always agree. Describe only: nothing
is ranked, and schools are only counted."""
import json, os
from shapely.geometry import shape

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'docs', 'dubai', 'data')


def feats(n):
    p = os.path.join(DATA, n + '.geojson')
    return json.load(open(p))['features'] if os.path.exists(p) else []


groups = {}
add = lambda k, c, name=None: groups.setdefault(k, []).append([round(c[0], 5), round(c[1], 5)] + ([name] if name else []))
for f in feats('community'):
    p = f['properties']; add(p['cat'], f['geometry']['coordinates'], p['name'])
for f in feats('institutions'):
    p = f['properties']
    if p['cat'] == 'hospital':
        add('hospital', f['geometry']['coordinates'], p['name'])
        if p.get('ed'): add('er', f['geometry']['coordinates'], p['name'])
for f in feats('parks'):
    c = shape(f['geometry']).representative_point()
    add('beach' if f['properties'].get('r') else 'park', (c.x, c.y), f['properties']['n'])
for f in feats('sports'):
    add('sports', f['geometry']['coordinates'], f['properties']['name'])
for f in feats('schools'):
    add('school', f['geometry']['coordinates'], f['properties']['name'])
for f in feats('faith'):
    p = f['properties']
    if p['cat'] != 'otherfaith': add(p['cat'], f['geometry']['coordinates'], p['name'])
json.dump({'groups': groups}, open(os.path.join(DATA, 'nearby.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('nearby:', {k: len(v) for k, v in groups.items()})
