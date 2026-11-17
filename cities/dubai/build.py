"""Build the Dubai map's base layers from cities/dubai/raw/ (see SOURCES.md and scouting/dubai/FINDINGS.md).
Polygons and lines go to tmp/ and are simplified by mapshaper in run.sh; points go straight to docs/dubai/data/.

"The city": Dubai's urban area from Jebel Ali to the Sharjah border (names.py CITY_OUTLINE cut to the emirate's land).
Units: OpenStreetMap's community polygons, which leave gaps (Dubai Marina, JLT, Al Barsha, the Palm...): the gaps stay
empty and the known-as names carry those places. Dubai Municipality's 224 communities replace them once its GeoDubai
approval comes through. Sides: Deira, Bur Dubai and New Dubai (names.py). The regional view: the rest of Dubai's land
in the frame, Sharjah's areas (OpenStreetMap) and Ajman's districts (Ajman Open Data, CC BY 4.0)."""
import json, math, os, re, sys
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping, Point, Polygon, LineString, MultiLineString, box
from shapely.ops import unary_union, linemerge, polylabel
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from names import CITY_OUTLINE, SIDE_LINES, SIDES, SIDE_INFO, HIGHWAYS, KNOWN_AS, BEYOND

R = os.path.join(HERE, 'raw') + '/'
OUT = os.path.join(HERE, '..', '..', 'docs', 'dubai', 'data') + '/'
TMP = os.path.join(HERE, 'tmp') + '/'
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
load = lambda f: json.load(open(R + f, encoding='utf-8'))
fc = lambda feats: {'type': 'FeatureCollection', 'features': feats}
feat = lambda g, p: {'type': 'Feature', 'properties': p, 'geometry': mapping(g)}
KM = 101.0   # km per degree of longitude at Dubai's latitude (111.2 per degree of latitude)
KM2 = KM * 111.2
dist_km = lambda a, b: math.hypot((a[0] - b[0]) * KM, (a[1] - b[1]) * 111.2)
FRAME = box(54.85, 24.70, 55.80, 25.55)   # the extract's frame (extract_osm.py): land is closed against it


def label_pt(g):
    if g.geom_type == 'MultiPolygon': g = max(g.geoms, key=lambda p: p.area)
    try: p = polylabel(g, tolerance=0.0003)
    except Exception: p = g.representative_point()
    return [round(p.x, 5), round(p.y, 5)]


def polys(g):
    if g.geom_type in ('Polygon', 'MultiPolygon'): return g
    return unary_union([x for x in getattr(g, 'geoms', []) if x.geom_type in ('Polygon', 'MultiPolygon')])


def dump(name, feats): json.dump(fc(feats), open(TMP + name + '.geojson', 'w'), separators=(',', ':'), ensure_ascii=False)
def write(name, feats): json.dump(fc(feats), open(OUT + name + '.geojson', 'w'), separators=(',', ':'), ensure_ascii=False)


def lines_of(g):
    if g.geom_type == 'LineString': return [g]
    return [x for p in getattr(g, 'geoms', []) for x in lines_of(p)]


def merged(gs, min_km=0.3):
    u = lines_of(unary_union(gs))
    m = linemerge(u) if len(u) > 1 else (u[0] if u else LineString())
    parts = [p for p in getattr(m, 'geoms', [m]) if p.geom_type == 'LineString' and p.length * KM > min_km]
    return (MultiLineString(parts) if len(parts) > 1 else parts[0]) if parts else None


_prep = {}
def clip(line, area):
    p = _prep.setdefault(id(area), (prep(area), prep(area.boundary)))
    if not p[0].intersects(line): return None
    if not p[1].intersects(line): return line
    g = line.intersection(area)
    return None if g.is_empty else g


nm = lambda p: (p.get('name:en') or p.get('name') or '').strip()

# ---------- Emirates and land ----------
admin = load('admin.geojson')['features']
LAND = unary_union([shape(f['geometry']).buffer(0) for f in load('land.geojson')['features']])
EM = {}
for f in admin:
    p = f['properties']
    if p.get('admin_level') == '4': EM[p['ISO3166-2']] = shape(f['geometry']).buffer(0).intersection(FRAME).intersection(LAND)
REGIONS = {'AE-DU': 'Dubai', 'AE-SH': 'Sharjah', 'AE-AJ': 'Ajman'}
D = {name: polys(EM[iso]) for iso, name in REGIONS.items()}
REGION = unary_union(list(D.values()))
print('region km²', {k: round(g.area * KM2) for k, g in D.items()})

CITY = polys(Polygon(CITY_OUTLINE).intersection(D['Dubai']))
print('city km²', round(CITY.area * KM2))

# ---------- Units: OSM communities (admin_level 10, and the named level-8 areas that hold no level-10 ones) ----------
du_p = prep(D['Dubai'])
L10 = [(p, shape(f['geometry']).buffer(0)) for f in admin for p in [f['properties']] if p.get('admin_level') == '10']
L8 = [(p, shape(f['geometry']).buffer(0)) for f in admin for p in [f['properties']] if p.get('admin_level') == '8']
cands = [(nm(p), g) for p, g in L10 if du_p.contains(g.representative_point())]
for p, g in L8:
    if not nm(p) or not du_p.contains(g.representative_point()): continue
    inside = [n for n, h in cands if h.intersection(g).area > 0.9 * h.area]
    cands = [(n, h) for n, h in cands if n not in inside]   # The Meadows over "Meadows 9"
    cands.append((nm(p), g))
CITY_P = prep(CITY)

# ---------- Sides: the big fill (the whole city, gaps included) ----------
# The Creek itself splits Deira from Bur Dubai: cut the city along the Creek's water and names.py's lines, then give
# each piece to the side whose rough outline (names.py SIDE_LINES) holds most of it.
side_poly = {s: Polygon(SIDE_LINES[s]).buffer(0) for s in SIDE_LINES}
creek = polys(box(55.27, 25.17, 55.37, 25.285).difference(LAND))
cuts = unary_union([creek.buffer(0.0002)] + [Polygon(SIDE_LINES[s]).exterior.buffer(0.0002) for s in SIDE_LINES])
pieces = list(getattr(polys(CITY.difference(cuts)), 'geoms', [polys(CITY.difference(cuts))]))
def side_of(g):
    best = max(side_poly, key=lambda s: side_poly[s].intersection(g).area)
    return best if side_poly[best].intersection(g).area > 0.5 * g.area else 'New Dubai'
by_side = defaultdict(list)
for pc in pieces: by_side[side_of(pc)].append(pc)
sidef, done = [], Point(0, 0).buffer(0)
for s in SIDES:
    g = polys(unary_union(by_side[s]).buffer(0.0004).intersection(CITY).difference(done))
    done = done.union(g)
    sidef.append(feat(g, {'name': s, 'info': SIDE_INFO[s], 'lp': label_pt(g)}))
    print('  side %-10s %4.0f km²' % (s, g.area * KM2))
leftover = CITY.difference(done)
if leftover.area * KM2 > 0.05: print('  %.2f km² of the city in no side' % (leftover.area * KM2))
dump('sides', sidef)
SIDE_G = {f['properties']['name']: shape(f['geometry']) for f in sidef}

units, outer_units = [], []
for n, g in cands:
    g = polys(g.intersection(LAND))
    if g.is_empty: continue
    share = g.intersection(CITY).area / g.area
    (units if share > 0.5 else outer_units).append((n, g))
units.sort(key=lambda u: u[0])
uf = []
for i, (n, g) in enumerate(units, 1):
    g = polys(g.intersection(CITY))
    side = max(SIDE_G, key=lambda s: SIDE_G[s].intersection(g).area)
    uf.append(feat(g, {'name': n, 'code': i, 'side': side, 'lp': label_pt(g)}))
dump('communities', uf)
covered = unary_union([shape(f['geometry']) for f in uf])
print('communities in the city', len(uf), Counter(f['properties']['side'] for f in uf),
      '· %.0f of %.0f km² covered' % (covered.area * KM2, CITY.area * KM2))

# ---------- Base: the city, the areas around it by emirate, land beyond ----------
base = [feat(CITY, {'kind': 'city', 'name': 'Dubai'})]
cutout = CITY.buffer(0.0003)
neigh = []   # (name, region, geometry)
for n, g in outer_units: neigh.append((n, 'Dubai', g))
sh_p = prep(D['Sharjah'])
for p, g in L8:
    if nm(p) and sh_p.contains(g.representative_point()): neigh.append((nm(p), 'Sharjah', g))
aj_p = prep(D['Ajman'])
for f in load('ajman/districts-area.geojson')['features']:
    g = shape(f['geometry']).buffer(0)
    n = (f['properties'].get('englishnam') or '').strip()
    if n and aj_p.contains(g.representative_point()): neigh.append((n.title() if n.isupper() else n, 'Ajman', g))
taken = {r: [] for r in D}
ALWAYS = {'Al Majaz', 'Al Nahda', 'Al Qasimia', 'Al Khan', 'Muwailih Commercial', 'Al Rashidiya', 'Al Nuaimiya', 'Al Jurf'}
for n, r, g in neigh:
    g = polys(g.intersection(D[r]).difference(cutout))
    if g.is_empty or g.area * KM2 < 0.05: continue
    for t in taken[r]: g = polys(g.difference(t))
    if g.is_empty: continue
    taken[r].append(g)
    pr = {'kind': 'neighbour', 'name': n, 'region': r, 'lp': label_pt(g)}
    if n not in ALWAYS: pr['minor'] = True
    base.append(feat(g, pr))
# Land of each emirate no area covers (Dubai's desert, Sharjah's inland): one piece per emirate, so a click there
# still says which emirate it is.
for r, dg in D.items():
    left = polys(dg.difference(cutout).difference(unary_union(taken[r]).buffer(0.0002) if taken[r] else Point(0, 0)))
    left = polys(unary_union([x for x in getattr(left, 'geoms', [left]) if x.area * KM2 > 0.5]))
    if not left.is_empty:
        base.append(feat(left, {'kind': 'neighbour', 'name': r if r != 'Dubai' else 'Dubai (outside the city)', 'region': r, 'minor': True, 'rest': True, 'lp': label_pt(left)}))
outside = polys(LAND.difference(REGION.buffer(0.0005)))
base.insert(0, feat(outside, {'kind': 'outside', 'name': ''}))
dump('base', base)
dump('region_areas', [feat(D[r], {'region': r}) for r in D])
REG_PREP = prep(REGION.buffer(0.01))
write('regions', [{'type': 'Feature', 'properties': {'name': n}, 'geometry': {'type': 'Point', 'coordinates': list(c)}}
                  for n, c in BEYOND if not REG_PREP.contains(Point(c)) or n in ('Sharjah', 'Ajman')])
print('areas beyond the city', Counter(f['properties']['region'] for f in base if f['properties']['kind'] == 'neighbour'))

# ---------- Known-as names ----------
places = load('places.json')
pois = load('pois.geojson')['features']
osm_names = defaultdict(list)
for p in places:
    for n in (p.get('name'), p.get('alt')):
        if n: osm_names[n.lower()].append(tuple(p['at']))
for f in pois:
    for n in (f['properties'].get('name:en'), f['properties'].get('name')):
        if n: osm_names[n.lower()].append(tuple(f['geometry']['coordinates']))
known = []
for k in KNOWN_AS:
    lat, lon = k['at']
    c = [c for c in osm_names.get(k['osm'].lower(), []) + osm_names.get(k['name'].lower(), []) if dist_km(c, (lon, lat)) < 1.5]
    pt = min(c, key=lambda c: dist_km(c, (lon, lat))) if c else (lon, lat)
    if not c: print('  known-as from hand position:', k['name'])
    known.append({'type': 'Feature', 'properties': {'name': k['name'], 'kind': k['kind']},
                  'geometry': {'type': 'Point', 'coordinates': [round(pt[0], 5), round(pt[1], 5)]}})
write('knownas', known)

# ---------- Places beyond the city, for search ("Near Al Nahda, Sharjah") ----------
KIND = {'town': 'Town', 'village': 'Village', 'suburb': 'Suburb', 'quarter': 'Neighbourhood', 'neighbourhood': 'Neighbourhood',
        'locality': 'Locality', 'hamlet': 'Hamlet', 'city': 'Town'}
CITY_PB = prep(CITY.buffer(0.001))
nb = [(f['properties'], prep(shape(f['geometry']))) for f in base if f['properties']['kind'] == 'neighbour']
rp, seen = [], set()
for p in places:
    n = p.get('name')
    if not n or p.get('place') not in KIND or not re.search(r'[A-Za-z]', n): continue
    pt = Point(p['at'])
    if CITY_PB.contains(pt): continue
    m = next((q for q, pp in nb if pp.contains(pt)), None)
    if not m or (n, m['name']) in seen: continue
    seen.add((n, m['name']))
    rp.append({'name': n, 'muni': m['name'], 'region': m['region'], 'kind': KIND[p['place']], 'at': p['at']})
rp.sort(key=lambda p: p['name'])
json.dump(rp, open(OUT + 'region_places.json', 'w'), separators=(',', ':'), ensure_ascii=False)
print('places beyond the city', len(rp), Counter(p['region'] for p in rp))

# ---------- Highways (federal E roads and Al Khail Road), main streets and collectors ----------
roads = load('roads.geojson')['features']
def hw_of(p):
    for r in re.split(r'[;,/ ]+', (p.get('ref') or '').upper()):
        r = r.replace('-', '')
        if r in HIGHWAYS: return (r, HIGHWAYS[r])
    return None

in_city, outer = defaultdict(list), defaultdict(list)
CITY_B5 = CITY.buffer(0.0005); INNER_P = prep(CITY.buffer(-0.0004))
for f in roads:
    p = f['properties']
    if p.get('highway') not in ('motorway', 'trunk', 'primary'): continue
    h = hw_of(p)
    if not h: continue
    line = shape(f['geometry'])
    g = clip(line, CITY_B5)
    if g is not None: in_city[h].append(g)
    if not INNER_P.contains(line): outer[h].append(line)
hw = []
for (route, name), gs in in_city.items():
    m = merged(gs, 0.5)
    if m is not None: hw.append(feat(m, {'route': route, 'name': name, 'kind': 'provincial'}))
dump('highways', hw)

CITY_B3 = CITY.buffer(0.0003)
CLS = {'motorway': 'major', 'trunk': 'major', 'primary': 'major', 'secondary': 'minor', 'tertiary': 'coll'}
segs = defaultdict(list)
for f in roads:
    p = f['properties']
    if p.get('highway') not in CLS or hw_of(p): continue
    n = nm(p) or None
    if n and (re.search(r'(?i)\b(ramp|exit|entry|slip|service road|u-?turn|interchange|link)\b', n) or not re.search(r'[A-Za-z]', n)): n = None
    g = clip(shape(f['geometry']), CITY_B3)
    if g is None: continue
    segs[(n, CLS[p['highway']])].append(g)
streets, colls = [], []
for (n, cls), gs in segs.items():
    m = merged(gs, 0.05)
    if m is None or (n and m.length * KM < 0.3): continue
    (colls if cls == 'coll' else streets).append(feat(m, {'name': n, 'cls': cls, 'len': round(m.length * 1000, 1)}))
for L in (streets, colls): L.sort(key=lambda f: (f['properties']['name'] is None, f['properties']['cls'] != 'major', -f['properties']['len']))
dump('streets', streets); dump('collectors', colls)
print('main streets', len(streets), '· collectors', len(colls))
REG_P = prep(REGION.buffer(0.01))
gh, shields = [], []
for (route, name), gs in outer.items():
    m = merged(gs, 1)
    if m is None: continue
    gh.append(feat(m, {'route': route, 'name': name, 'toll': False}))
    for part in getattr(m, 'geoms', [m]):
        km = part.length * KM
        if km < 6: continue
        for d in [x for x in range(6, int(km) - 2, 25)] or [km / 2]:
            pt = part.interpolate(d / KM)
            if not REG_P.contains(pt) or CITY.buffer(0.005).contains(pt): continue
            if any(s['properties']['route'] == route and Point(s['geometry']['coordinates']).distance(pt) * KM < 15 for s in shields): continue
            shields.append({'type': 'Feature', 'properties': {'route': route, 'toll': False}, 'geometry': {'type': 'Point', 'coordinates': [round(pt.x, 5), round(pt.y, 5)]}})
dump('region_highways', gh)
write('region_shields', shields)
print('highways in the city', sorted(r for r, _ in in_city), '· beyond', sorted(r for r, _ in outer), len(shields), 'shields')

# ---------- No neighbourhood lens yet (needs DM communities), no elected offices ----------
json.dump({}, open(OUT + 'profiles.json', 'w'))
json.dump({'updated': '2026-11-17'}, open(OUT + 'representatives.json', 'w'))
print('units', len(uf), '· known-as', len(known))
