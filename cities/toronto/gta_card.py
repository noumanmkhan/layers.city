"""The What's here card beyond the City of Toronto: raw/gta_card/ (fetch_gta_card.py), raw/schools/ and the region's
parks (docs/toronto/data/gta_parks.geojson, gta_basemap.py) ->

  docs/toronto/data/gta_nearby.json   {"groups": {key: [[lon, lat, name], ...]}} as nearby.json, for card.outsideNearby:
      library, centre (community and recreation centres), er (hospitals OSM marks emergency=yes), park and playground
      (one point per park or playground), school_e / school_s (the Ministry of Education's publicly funded schools,
      by level), and places of worship as mosque, gurdwara, synagogue, hindu, buddhist, church (shown only while the
      Places of worship layer and that faith's chip are on, as in the city).
  docs/toronto/data/gta_prov.geojson, gta_fed.geojson   provincial and federal ridings that reach past the city into
      Halton, Peel, York or Durham, {name}, for card.reps.outside (MPP and MP rows; representatives.py adds their members).

Only points beyond the city are kept: inside it the card uses the City's own data. Describe only, nothing ranked."""
import csv, json, os
from shapely.geometry import shape, Point, mapping
from shapely.ops import unary_union
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'gta_card')
DATA = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data')
if not os.path.isdir(RAW):
    raise SystemExit('gta_card: no raw/gta_card/ yet (fetch-gta-card.yml); skipped')
base = json.load(open(os.path.join(DATA, 'base.geojson')))['features']
CITY = unary_union([shape(f['geometry']) for f in base if f['properties']['kind'] == 'city']).buffer(0)
MUNIS = unary_union([shape(f['geometry']) for f in base if f['properties']['kind'] == 'neighbour']).buffer(0)
OUT_AREA = prep(MUNIS.buffer(0.01).difference(CITY.buffer(-0.002)))   # a little past the edges: a stop across the line still counts
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

# Parks: one point per outline (its inside point), from the Parks layer's regional file.
gp = os.path.join(DATA, 'gta_parks.geojson')
if os.path.exists(gp):
    for f in json.load(open(gp))['features']:
        p = shape(f['geometry']).representative_point()
        add('park', p.x, p.y)

# Schools: the Ministry's list beyond the city, publicly funded only (as in the city), by level.
sp = os.path.join(HERE, 'raw', 'schools', 'ontario_schools.csv')
for r in csv.DictReader(open(sp, encoding='utf-8')):
    if r['Municipality'] == 'Toronto, City of' or not r.get('Latitude') or not r.get('Longitude'):
        continue
    lvl = (r.get('School Level') or '').lower()
    k = 'school_s' if 'secondary' in lvl else 'school_e' if 'elementary' in lvl else None
    if k:
        try: add(k, float(r['Longitude']), float(r['Latitude']), r['School Name'].strip())
        except ValueError: pass
json.dump({'groups': groups}, open(os.path.join(DATA, 'gta_nearby.json'), 'w'), separators=(',', ':'))
print('gta nearby:', {k: len(v) for k, v in sorted(groups.items())})

# Ridings that reach past the city into the GTA's municipalities. RENAME: districts renamed since Represent's
# boundary set was published, so the name matches the House of Commons' list (and the riding's current name).
RENAME = {'New Tecumseth—Gwillimbury': 'York—South Simcoe'}
REACH = MUNIS.buffer(-0.002)
for src, out in (('ridings_prov', 'gta_prov'), ('ridings_fed', 'gta_fed')):
    feats = []
    for f in json.load(open(os.path.join(RAW, src + '.geojson')))['features']:
        g = shape(f['geometry']).buffer(0)
        if not g.intersects(REACH):
            continue
        g = g.intersection(MUNIS.buffer(0.01)).simplify(0.0003, preserve_topology=True)
        if g.is_empty:
            continue
        feats.append({'type': 'Feature', 'properties': {'name': RENAME.get(f['properties']['name'], f['properties']['name'])},
                      'geometry': json.loads(json.dumps(mapping(g)), parse_float=r5)})
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(DATA, out + '.geojson'), 'w'), separators=(',', ':'))
    print(out, len(feats), 'ridings')
