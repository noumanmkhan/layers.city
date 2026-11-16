"""The What's here card's Nearby section beyond a city, for cities with no school list of their own for the region.
Usage: python3 engine/region/card.py <city>. Inputs: cities/<city>/raw/region_basemap/places.json (fetch_places.py)
and docs/<city>/data/region_parks.geojson (basemap.py). Output: docs/<city>/data/region_nearby.json
{"groups": {key: [[lon, lat, name], ...]}}, the shape of nearby.json, for card.outsideNearby:

  library, centre        named libraries and community centres
  er                     hospitals OpenStreetMap marks emergency=yes
  park, playground       one point each, counted within the card's radius
  school_e, school_s     OpenStreetMap's named schools sorted by name: high and secondary schools as school_s,
                         everything else (elementary, middle, junior high) as school_e; colleges, preschools and
                         driving, beauty or trade schools are left out
  mosque, gurdwara, synagogue, hindu, buddhist, church   places of worship by faith (shown only while the Places of
                         worship layer and that faith's chip are on, as in the city)

Only points beyond the city are kept: inside it the card uses the city's own data. Describe only, nothing ranked.
Some cities keep their own copy (cities/<city>/region_card.py) because they have an official school list."""
import json, os, re, sys
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep

CITY_ID = sys.argv[1]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
RAW = os.path.join(ROOT, 'cities', CITY_ID, 'raw', 'region_basemap')
DATA = os.path.join(ROOT, 'docs', CITY_ID, 'data')
if not os.path.exists(os.path.join(RAW, 'places.json')):
    raise SystemExit('region card: no raw/region_basemap/places.json yet (fetch-region-basemap.yml); skipped')
base = [f for f in json.load(open(os.path.join(DATA, 'base.geojson')))['features'] if f['geometry']]
CITY = unary_union([shape(f['geometry']).buffer(0) for f in base if f['properties']['kind'] in ('city', 'annex')]).buffer(0)
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
HIGH = re.compile(r'(?i)\b(high school|secondary|senior high|hs)\b')
SKIP = re.compile(r'(?i)\b(college|university|preschool|pre-school|nursery|daycare|day care|montessori|driving|beauty|cosmetology|barber|academy of hair|learning cent(er|re)|tutoring)\b')
for lon, lat, name, t in P.get('school', []):
    if not name or SKIP.search(name): continue
    add('school_s' if HIGH.search(name) or t.get('isced') in ('3', '2;3') else 'school_e', lon, lat, name)
json.dump({'groups': groups}, open(os.path.join(DATA, 'region_nearby.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('region nearby:', {k: len(v) for k, v in sorted(groups.items())})
