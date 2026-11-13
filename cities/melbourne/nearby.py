"""Points for the card's Nearby section -> docs/melbourne/data/nearby.json (the shape Toronto's and Chicago's use):
the nearest library, community centre and ER, places of worship by faith (shown only while their layer is on), and
counts within 800 m of parks, playgrounds, tennis and basketball, and primary and secondary schools. Everything
comes from the published layers (parks.py, places_more.py, run first) and the City's playground list, so the card
and the map always agree. Describe only: nothing is ranked."""
import json, os
from shapely.geometry import shape, Point
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'docs', 'melbourne', 'data')
RAW = os.path.join(HERE, 'raw', 'parks')
CITY = unary_union([shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(DATA, 'suburbs.geojson')))['features']]).buffer(0.003)


def feats(n):
    p = os.path.join(DATA, n + '.geojson')
    return json.load(open(p))['features'] if os.path.exists(p) else []


groups = {}
add = lambda k, c, name=None: groups.setdefault(k, []).append([round(c[0], 5), round(c[1], 5)] + ([name] if name else []))
for f in feats('community'):
    p = f['properties']; add(p['cat'], f['geometry']['coordinates'], p['name'])
    if p['cat'] == 'library' and 'Community Centre' in p['name']: add('centre', f['geometry']['coordinates'], p['name'])   # both in one building
for f in feats('institutions'):
    if f['properties'].get('ed'): add('er', f['geometry']['coordinates'], f['properties']['name'])
for f in feats('parks'):
    c = shape(f['geometry']).representative_point(); add('park', (c.x, c.y), f['properties']['n'])
for f in json.load(open(os.path.join(RAW, 'playgrounds.geojson')))['features']:
    g = f['properties'].get('geo_point_2d') or {}
    if g.get('lon') is not None and CITY.contains(Point(g['lon'], g['lat'])): add('playground', (g['lon'], g['lat']))
for f in feats('sports'):
    for k in ('tennis', 'basketball'):
        if k in f['properties']['cats']: add(k, f['geometry']['coordinates'], f['properties']['name'])
for f in feats('schools'):
    add('school_e' if f['properties']['cat'] == 'elementary' else 'school_s', f['geometry']['coordinates'], f['properties']['name'])
for f in feats('faith'):
    p = f['properties']
    if p['cat'] != 'otherfaith': add(p['cat'], f['geometry']['coordinates'], p['name'])
    if p.get('grp'): add(p['cat'] + ':' + p['grp'], f['geometry']['coordinates'], p['name'])
json.dump({'groups': groups}, open(os.path.join(DATA, 'nearby.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('nearby:', {k: len(v) for k, v in groups.items()})
