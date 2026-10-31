"""Collector streets for their own layer: OpenStreetMap's tertiary roads inside the city that aren't drawn as main
streets (raw/osm_streets.json, fetched by fetch_streets.py; build.py keeps only the tertiary roads on names.py
MAJOR_STREETS), merged per name -> tmp/collectors.geojson. Stretches within ~12 m of a drawn main street are left out
(OpenStreetMap can tag parts of one street differently). Run after the main streets are built and simplified (needs
docs/sf/data/streets.geojson and base.geojson). New York's collectors.py, with San Francisco's names."""
import json, os, re
from shapely.geometry import LineString, shape, mapping
from shapely.ops import linemerge, unary_union
from names import MAJOR_STREETS, street_key

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'docs', 'sf', 'data')
city = unary_union([shape(f['geometry']) for f in json.load(open(os.path.join(DATA, 'base.geojson')))['features'] if f['properties']['kind'] == 'city'])
drawn = json.load(open(os.path.join(DATA, 'streets.geojson')))['features']
mains = unary_union([shape(f['geometry']) for f in drawn]).buffer(0.00013)
skip = MAJOR_STREETS | {f['properties']['name'] for f in drawn} | {'The Embarcadero'}
by = {}
for w in json.load(open(os.path.join(HERE, 'raw', 'osm_streets.json')))['elements']:
    t = w['tags']
    if t.get('highway') != 'tertiary' or len(w.get('geometry', [])) < 2 or not t.get('name'): continue
    key = re.sub(r'\bJunior\b', 'Jr', street_key(t['name']))
    if key in skip or re.search(r'(?i)\b(freeway|bridge|tunnel|ramp|exit)\b', key): continue
    by.setdefault(key, []).append(LineString([(p['lon'], p['lat']) for p in w['geometry']]))
feats = []
for name, gs in by.items():
    u = unary_union(gs).intersection(city).difference(mains)
    if u.is_empty: continue
    u = unary_union([p for p in getattr(u, 'geoms', [u]) if p.geom_type == 'LineString'])
    if u.is_empty: continue
    m = linemerge(u) if u.geom_type == 'MultiLineString' else u
    parts = [p for p in getattr(m, 'geoms', [m]) if p.length > 0.001]   # ~90 m
    if not parts: continue
    g = parts[0] if len(parts) == 1 else {'type': 'MultiLineString', 'coordinates': [list(p.coords) for p in parts]}
    feats.append({'type': 'Feature', 'properties': {'name': name, 'cls': 'coll', 'len': round(sum(p.length for p in parts) * 1000, 1)},
                  'geometry': g if isinstance(g, dict) else mapping(g)})
feats.sort(key=lambda f: -f['properties']['len'])
os.makedirs(os.path.join(HERE, 'tmp'), exist_ok=True)
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(HERE, 'tmp', 'collectors.geojson'), 'w'))
print('collectors', len(feats), 'streets:', ', '.join(f['properties']['name'] for f in feats[:25]))
