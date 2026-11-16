"""A city's region beyond the city, filled in from OpenStreetMap (cities/<city>/raw/region_basemap/, from
engine/region/fetch_basemap.py). Usage: python3 engine/region/basemap.py <city>. The first city to have this kept its own copy;
this one serves any city, set by cities/<city>/region.json:
  "parkNames": {"park": "Park", "reserve": "Nature reserve"}   names for unnamed parks
  "parkMaxKm2": 120     planning overlays tagged protected_area that cover whole districts are left out
  "parksInCity": true   for a city with no parks file of its own: region_parks also holds OpenStreetMap's parks inside
                        the city (still o: 1, so they read as OSM outlines)

  roads   arterials and collectors outside the city -> tmp/region_streets.geojson (trunk and primary: major,
          secondary: minor) and tmp/region_collectors.geojson (tertiary), drawn with the Main streets and Collector
          streets layers (city.json "more"), each with o: 1 so the page names them in the regional view only. A
          stretch within ~15 m of one of the city's own streets is dropped so nothing draws twice.
  parks   parks and reserves outside the city -> docs/<city>/data/region_parks.geojson, each with o: 1 (r: 1 for a
          reserve, s: 1 under 3 ha), drawn with the Parks layer (city.json "more").
  land    land use across the whole region, the city included -> tmp/landuse.geojson, one feature per class per
          ~5 km cell (dissolved), for the Land use layer: k = res, com, ind, farm, wood, cem, quarry.

Run after the city's base (tmp/base.geojson: kind city and neighbour) and its streets and collectors are published;
run.sh simplifies the tmp files afterwards."""
import json, math, os, re, sys
from collections import defaultdict
from shapely.geometry import shape, mapping, LineString, MultiLineString, Polygon, MultiPolygon
from shapely.ops import unary_union, linemerge

CITY_ID = sys.argv[1]
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'cities', CITY_ID)
DATA = os.path.join(HERE, '..', '..', 'docs', CITY_ID, 'data')
CFG = json.load(open(os.path.join(HERE, 'region.json')))
RAW = os.path.join(HERE, 'raw', 'region_basemap')
TMP = os.path.join(HERE, 'tmp')
PARKS = os.path.join(DATA, 'region_parks.geojson')
if not os.path.isdir(RAW):
    raise SystemExit('region basemap: no raw/region_basemap/ yet (fetch-region-basemap.yml); skipped')
S, W, N, E = CFG['bbox']
COS = math.cos(math.radians((S + N) / 2))
KM = 111.32 * COS      # km per degree of longitude here, roughly, for lengths of lines
M2 = 111_320 ** 2 * COS

base = json.load(open(os.path.join(TMP, 'base.geojson')))['features']
base = [f for f in base if f.get('geometry')]
CITY = unary_union([shape(f['geometry']).buffer(0) for f in base if f['properties']['kind'] in ('city', 'annex')]).buffer(0)
MUNIS = unary_union([shape(f['geometry']).buffer(0) for f in base if f['properties']['kind'] == 'neighbour']).buffer(0)
REGION = unary_union([CITY, MUNIS]).buffer(0)
OUTSIDE = MUNIS.buffer(0.002).difference(CITY.buffer(-0.0004))
R5 = lambda x: round(float(x), 5)


def geom_json(g):
    return json.loads(json.dumps(mapping(g)), parse_float=R5)


def lines_of(g):
    return [p for p in getattr(g, 'geoms', [g]) if p.geom_type == 'LineString' and not p.is_empty]


# ---------- roads ----------
CLS = {'trunk': 'major', 'primary': 'major', 'secondary': 'minor', 'tertiary': 'coll'}
JUNK = re.compile(r'(?i)\b(ramp|exit|entry|on-ramp|off-ramp|slip road|u-?turn)\b')
city_lines = unary_union([shape(f['geometry']) for n in ('streets', 'collectors') if os.path.exists(os.path.join(DATA, n + '.geojson'))
                          for f in json.load(open(os.path.join(DATA, n + '.geojson')))['features']]).buffer(0.00018)
streets, colls = {'type': 'FeatureCollection', 'features': []}, {'type': 'FeatureCollection', 'features': []}
segs = defaultdict(list)
for w in json.load(open(os.path.join(RAW, 'roads.json')))['items']:
    if w['hw'] not in CLS or len(w['c']) < 2:
        continue
    n = (w['name'] or '').strip() or None
    if n and JUNK.search(n):
        n = None
    g = LineString(w['c'])
    if not g.intersects(OUTSIDE):
        continue
    g = g.intersection(OUTSIDE).difference(city_lines)
    if g.is_empty:
        continue
    segs[(n, CLS[w['hw']])].extend(lines_of(g))
added = defaultdict(int)
for (n, cls), gs in segs.items():
    u = unary_union(gs)
    m = linemerge(u) if u.geom_type == 'MultiLineString' else u
    parts = [p for p in lines_of(m) if p.length * KM > (0.05 if n is None else 0.08)]
    if not parts:
        continue
    m = parts[0] if len(parts) == 1 else MultiLineString(parts)
    f = {'type': 'Feature', 'properties': {'name': n, 'cls': cls, 'len': round(m.length * 1000, 1), 'o': 1}, 'geometry': geom_json(m)}
    (colls if cls == 'coll' else streets)['features'].append(f)
    added[cls] += 1
# The page labels streets in file order: named before unnamed, majors first, longest first.
for c in (streets, colls):
    c['features'].sort(key=lambda f: (f['properties']['name'] is None, f['properties']['cls'] != 'major', -f['properties']['len']))
json.dump(streets, open(os.path.join(TMP, 'region_streets.geojson'), 'w'), separators=(',', ':'))
json.dump(colls, open(os.path.join(TMP, 'region_collectors.geojson'), 'w'), separators=(',', ':'))
print('region roads added:', dict(added))

# ---------- parks ----------
P = {'type': 'FeatureCollection', 'features': []}
kept, skipped = 0, []
NAMES = dict({'park': 'Park', 'reserve': 'Reserve'}, **CFG.get('parkNames', {}))
for it in json.load(open(os.path.join(RAW, 'parks.json')))['items']:
    g = MultiPolygon([Polygon(p[0], p[1:]) for p in it['poly']]).buffer(0)
    a_km2 = g.area * M2 / 1e6
    # Planning overlays (the Greenbelt, the Oak Ridges Moraine plan area) are tagged protected_area too: they
    # cover whole townships, not places you'd visit, so anything that large is left out.
    if a_km2 > CFG.get('parkMaxKm2', 120) or (it['name'] or '').upper() == 'RESTRICTED AREA':
        skipped.append((it['name'], round(a_km2)))
        continue
    # A city with no parks file of its own (region.json "parksInCity": true) takes OpenStreetMap's inside the city too.
    g = g.intersection(OUTSIDE.union(CITY) if CFG.get('parksInCity') else OUTSIDE.difference(CITY))
    if g.is_empty or g.area * M2 < 3000:
        continue
    g = g.simplify(0.00003, preserve_topology=True)
    # s: a small park (under 3 ha), left off the zoomed-out regional view so the suburbs don't read as confetti.
    P['features'].append({'type': 'Feature', 'properties': {'n': it['name'] or NAMES[it['k']], 'o': 1, **({'r': 1} if it['k'] == 'reserve' else {}),
                                                            **({'s': 1} if g.area * M2 < 30000 else {})},
                          'geometry': geom_json(g)})
    kept += 1
json.dump(P, open(PARKS, 'w'), separators=(',', ':'))
print('region parks added:', kept, '· left out (too large):', skipped[:8])

# ---------- land use ----------
ORDER = ['farm', 'res', 'com', 'ind', 'cem', 'quarry', 'wood']   # later classes draw on top
CELL = 0.05
cells = defaultdict(list)
for it in json.load(open(os.path.join(RAW, 'landuse.json')))['items']:
    for p in it['poly']:
        g = Polygon(p[0], p[1:])
        if not g.is_valid:
            g = g.buffer(0)
        if g.is_empty:
            continue
        x0, y0, x1, y1 = g.bounds
        cells[(it['k'], int(((x0 + x1) / 2) // CELL), int(((y0 + y1) / 2) // CELL))].append(g)
LAND = REGION.buffer(0)
feats, tally = [], defaultdict(float)
for (k, i, j), gs in sorted(cells.items(), key=lambda kv: (ORDER.index(kv[0][0]), kv[0][1], kv[0][2])):
    u = unary_union(gs).intersection(LAND)
    if u.is_empty:
        continue
    u = u.simplify(0.00008, preserve_topology=True)
    polys = [p for p in getattr(u, 'geoms', [u]) if p.geom_type == 'Polygon' and p.area * M2 > 15000]
    if not polys:
        continue
    g = polys[0] if len(polys) == 1 else MultiPolygon(polys)
    tally[k] += g.area * M2 / 1e6
    feats.append({'type': 'Feature', 'properties': {'k': k}, 'geometry': geom_json(g)})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(TMP, 'landuse.geojson'), 'w'), separators=(',', ':'))
print('land use:', len(feats), 'features;', {k: round(v) for k, v in sorted(tally.items(), key=lambda kv: -kv[1])}, 'km²')
