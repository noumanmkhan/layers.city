"""Melbourne's Parks and Sports & rec layers -> docs/melbourne/data/parks.geojson and sports.geojson. The same
shapes as Toronto's and Chicago's (the engine's parks and places layer kinds read them).

Parks: every named park, garden and reserve from OpenStreetMap whose middle is in the City (raw/parks/osm_parks.json,
fetch_parks.py), since the City publishes no park outlines. A garden or reserve mostly inside a bigger park isn't drawn
twice. Amenities, from a point inside the outline or within 25 m of it (toilets and barbecues often stand at the
edge): playgrounds, public toilets and barbecues from the City's own asset lists (playgrounds, public-toilets,
public-barbecues; CC BY 4.0) and OpenStreetMap; off-leash dog areas and water play from OpenStreetMap only.
Sports & rec: public pools, ovals, fields, courts and skate parks from OpenStreetMap inside a park, one point per park."""
import json, os, re
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping, Point, Polygon, LineString
from shapely.ops import unary_union, polygonize, linemerge
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(HERE, 'raw', 'parks')
DATA = os.path.join(ROOT, 'docs', 'melbourne', 'data')
CITY = unary_union([shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(DATA, 'suburbs.geojson')))['features']])


def write(name, obj):
    s = json.dumps(obj, separators=(',', ':'), ensure_ascii=False)
    open(os.path.join(DATA, name), 'w').write(s)


def outline(e):
    if e['type'] == 'way':
        cs = [(p['lon'], p['lat']) for p in e.get('geometry') or []]
        return Polygon(cs).buffer(0) if len(cs) >= 4 else None
    lines = [LineString([(p['lon'], p['lat']) for p in m['geometry']]) for m in e.get('members', [])
             if m.get('type') == 'way' and m.get('role') in ('outer', '') and len(m.get('geometry') or []) >= 2]
    if not lines: return None
    polys = [q.buffer(0) for q in polygonize(linemerge(lines))]
    polys = [q for q in polys if not q.is_empty]
    if not polys: return None
    try: return unary_union(polys).buffer(0)
    except Exception: return max(polys, key=lambda q: q.area)


osm = json.load(open(os.path.join(RAW, 'osm_parks.json')))
asof = (osm.get('osm3s') or {}).get('timestamp_osm_base', '')[:10] or None
KIND = {'park': 'Park', 'garden': 'Garden', 'nature_reserve': 'Nature reserve'}
raw = []
for e in osm['elements']:
    t = e.get('tags', {})
    if t.get('leisure') not in KIND or not t.get('name') or t.get('access') in ('private', 'no'): continue
    g = outline(e)
    if g is None or g.is_empty or g.area < 2e-8 or not CITY.contains(g.representative_point()): continue
    raw.append((t['name'].strip(), t['leisure'], g))
raw.sort(key=lambda p: (p[1] != 'park', -p[2].area))   # parks first, biggest first
kept = []
for n, kind, g in raw:
    if any(k[2].intersection(g).area > 0.5 * g.area for k in kept) and (kind != 'park' or any(k[0] == n for k in kept)):
        continue   # a garden or reserve inside a park, or the same park mapped twice
    kept.append((n, kind, g))
TREE = STRtree([g.buffer(0.00025) for *_, g in kept])


def park_of(x, y):
    p = Point(x, y); best = None
    for i in TREE.query(p):
        if kept[i][2].contains(p): return i
        if TREE.geometries[i].contains(p) and best is None: best = i
    return best


amen = defaultdict(set)
water = set()


def city_points(name, xy):
    path = os.path.join(RAW, name + '.geojson')
    if not os.path.exists(path): return 0
    n = 0
    for f in json.load(open(path))['features']:
        p = f['properties']; c = xy(p, f)
        if c and c[0] is not None:
            yield c


def gp(p, f):
    g = p.get('geo_point_2d') or {}
    if g.get('lon') is not None: return g['lon'], g['lat']
    if p.get('longitude') is not None: return float(p['longitude']), float(p['latitude'])
    if p.get('lon') is not None: return float(p['lon']), float(p['lat'])
    if f.get('geometry') and f['geometry']['type'] == 'Point': return tuple(f['geometry']['coordinates'][:2])
    return None


for name, a in (('playgrounds', 'play'), ('public-toilets', 'wc'), ('public-barbecues', 'bbq')):
    for x, y in city_points(name, gp):
        i = park_of(x, y)
        if i is not None: amen[i].add(a)

at = lambda e: (e['center']['lon'], e['center']['lat']) if 'center' in e else (e.get('lon'), e.get('lat'))
SPORT = {'swimming': ['pool'], 'australian_football': ['cricket'], 'cricket': ['cricket'], 'soccer': ['field'],
         'rugby_union': ['field'], 'rugby_league': ['field'], 'field_hockey': ['field'], 'hockey': ['field'],
         'tennis': ['tennis'], 'basketball': ['basketball'], 'netball': ['basketball'], 'skateboard': ['skatepark']}
fac = defaultdict(Counter)
am = json.load(open(os.path.join(RAW, 'osm_amenities.json')))
for e in am['elements']:
    t = e.get('tags', {}); x, y = at(e)
    if x is None: continue
    i = park_of(x, y)
    if i is None: continue   # outside every park: school ovals, apartment pools, club courts
    if t.get('leisure') == 'playground':
        amen[i].add('play')
        if re.search(r'splash|water', t.get('playground', '')): amen[i].add('water')
        continue
    if t.get('leisure') == 'water_park' or re.search(r'splash|water', t.get('playground', '')): amen[i].add('water'); continue
    if t.get('leisure') == 'dog_park': amen[i].add('dog'); continue
    if t.get('amenity') == 'toilets': amen[i].add('wc'); continue
    if t.get('amenity') == 'bbq': amen[i].add('bbq'); continue
    if t.get('amenity') == 'drinking_water': continue
    if t.get('leisure') == 'swimming_pool' or (t.get('leisure') == 'sports_centre' and 'swimming' in (t.get('sport') or '')):
        cats = ['pool']
    else:
        cats = sorted({c for s in re.split(r'[;,]\s*', t.get('sport') or '') for c in SPORT.get(s.strip(), [])})
    for c in cats: fac[i][c] += 1

rnd = lambda o: [rnd(v) for v in o] if isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]
ORDER_A = ['play', 'water', 'wc', 'bbq', 'dog']
parks = []
for i, (n, kind, g) in enumerate(kept):
    pr = {'n': n, 't': KIND[kind]}
    a = [x for x in ORDER_A if x in amen[i]]
    if a: pr['a'] = a
    gm = mapping(g.simplify(0.00002, preserve_topology=True))
    parks.append({'type': 'Feature', 'properties': pr, 'geometry': {'type': gm['type'], 'coordinates': rnd(gm['coordinates'])}})
write('parks.geojson', {'type': 'FeatureCollection', 'asof': {'parks': asof}, 'count': len(parks), 'features': parks})
print('parks:', len(parks), dict(Counter(a for f in parks for a in f['properties'].get('a', []))),
      os.path.getsize(os.path.join(DATA, 'parks.geojson')) // 1024, 'KB')

# Ovals (cricket and Australian football grounds) take the engine's cricket glyph; netball courts count with basketball.
WORD = {'pool': ('pool', 'pools'), 'cricket': ('oval', 'ovals'), 'field': ('sports field', 'sports fields'),
        'tennis': ('tennis court', 'tennis courts'), 'basketball': ('basketball or netball court', 'basketball or netball courts'),
        'skatepark': ('skate park', 'skate parks')}
ORDER = ['pool', 'cricket', 'field', 'tennis', 'basketball', 'skatepark']
sports, counts = [], Counter()
for i, c in fac.items():
    cats = [k for k in ORDER if c[k]]
    if not cats: continue
    for k in cats: counts[k] += 1
    p = kept[i][2].representative_point()
    has = ', '.join(f'{c[k]} {WORD[k][0] if c[k] == 1 else WORD[k][1]}' for k in cats)
    sports.append({'type': 'Feature', 'properties': {'name': kept[i][0], 'cat': cats[0], 'cats': cats, 'sub': 'In the park', 'has': has},
                   'geometry': {'type': 'Point', 'coordinates': [round(p.x, 5), round(p.y, 5)]}})
write('sports.geojson', {'type': 'FeatureCollection', 'asof': asof, 'count': len(sports), 'counts': dict(counts), 'features': sports})
print('sports:', len(sports), dict(counts))
