"""The What's here card beyond the City and County of San Francisco: raw/region_basemap/places.json (engine/region/fetch_places.py),
OpenStreetMap's schools and the region's parks
(docs/sf/data/region_parks.geojson, engine/region/basemap.py) ->

  docs/sf/data/region_nearby.json   {"groups": {key: [[lon, lat, name], ...]}} as nearby.json, for
      card.outsideNearby: library, centre, er (hospitals OSM marks emergency=yes), park and playground (one point
      each), school_e / school_s (elementary and middle; high schools), and places of worship by faith (shown only while the
      Places of worship layer and that faith's chip are on, as in the City).

Only points beyond the City are kept: inside it the card uses the City's own data. Describe only, nothing ranked."""
import json, os
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'region_basemap')
DATA = os.path.join(HERE, '..', '..', 'docs', 'sf', 'data')
if not os.path.exists(os.path.join(RAW, 'places.json')):
    raise SystemExit('region_card: no raw/region_basemap/places.json yet (fetch-region-basemap.yml); skipped')
base = json.load(open(os.path.join(DATA, 'base.geojson')))['features']
CITY = unary_union([shape(f['geometry']).buffer(0) for f in base if f['properties']['kind'] == 'city']).buffer(0)
REGION = unary_union([shape(f['geometry']).buffer(0) for f in base if f['properties']['kind'] == 'neighbour']).buffer(0)
OUT_AREA = prep(REGION.buffer(0.01).difference(CITY.buffer(-0.002)))
r5 = lambda v: round(float(v), 5)
groups = {}


def add(k, lon, lat, name=None):
    if OUT_AREA.contains(Point(lon, lat)):
        groups.setdefault(k, []).append([r5(lon), r5(lat)] + ([name] if name is not None else []))


P = json.load(open(os.path.join(RAW, 'places.json')))['groups']
for lon, lat, name in P['library']:
    if name: add('library', lon, lat, name)
for lon, lat, name in P['centre']:
    if name: add('centre', lon, lat, name)
for lon, lat, name, t in P['hospital']:
    if name and t.get('emergency') == 'yes': add('er', lon, lat, name)
for lon, lat, name in P['playground']:
    add('playground', lon, lat)
FAITH = {'muslim': 'mosque', 'sikh': 'gurdwara', 'jewish': 'synagogue', 'hindu': 'hindu', 'buddhist': 'buddhist', 'christian': 'church'}
for lon, lat, name, t in P['worship']:
    k = FAITH.get(t.get('religion'))
    if k: add(k, lon, lat, name)

rp = os.path.join(DATA, 'region_parks.geojson')
if os.path.exists(rp):
    for f in json.load(open(rp))['features']:
        p = shape(f['geometry']).representative_point()
        add('park', p.x, p.y)

# Schools: OpenStreetMap's named schools (California’s school directory is not fetched here yet), by name: high schools
# and secondary schools as secondary, everything else (elementary, middle, junior high, K-8) as elementary. Colleges,
# preschools and driving or trade schools are left out.
import re
HIGH = re.compile(r'(?i)\b(high school|secondary|senior high|hs)\b')
SKIP = re.compile(r'(?i)\b(college|university|preschool|pre-school|nursery|daycare|day care|montessori|driving|beauty|cosmetology|barber|academy of hair|learning center|tutoring)\b')
for lon, lat, name, t in P.get('school', []):
    if not name or SKIP.search(name): continue
    add('school_s' if HIGH.search(name) or t.get('isced') in ('3', '2;3') else 'school_e', lon, lat, name)
json.dump({'groups': groups}, open(os.path.join(DATA, 'region_nearby.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('region nearby:', {k: len(v) for k, v in sorted(groups.items())})
