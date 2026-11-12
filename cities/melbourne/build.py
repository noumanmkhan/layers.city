"""Build the Melbourne map's layer files from cities/melbourne/raw/ (see SOURCES.md).
Polygons and lines go to tmp/ and are simplified by mapshaper in run.sh; points go straight to
docs/melbourne/data/. Output shapes match the other cities', so the shared engine draws all of them.

The San Francisco shape (decided with the user, November 12, 2026): the City of Melbourne in full detail, inside a
Greater Melbourne view. Land and water: the ABS's 2021 boundaries follow the coast, so the land is Victoria's outline;
Port Phillip and Western Port are what's left of the frame.

Units: ABS Suburbs and Localities (2021) cut to the City's boundary. The locality "Melbourne" is split at the Yarra
into the CBD (north) and St Kilda Road (south; postcode 3004). Slivers under 0.05 km² where a suburb's line and the
City's differ join their neighbour. Base: every other suburb in Greater Melbourne is a neighbour, its region the
council it sits in (the largest overlap), so "Focus on a region" picks a council."""
import json, math, os, re, sys
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping, Point, LineString, MultiLineString, box
from shapely.ops import unary_union, linemerge, polylabel, split

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from names import SIDES, SIDE_INFO, KNOWN_AS, MAJOR_STREETS, UNIT_NOTES, UNIT_AKA, CBD, ST_KILDA_RD, street_key

R = os.path.join(HERE, 'raw') + '/'
OUT = os.path.join(HERE, '..', '..', 'docs', 'melbourne', 'data') + '/'
TMP = os.path.join(HERE, 'tmp') + '/'
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
load = lambda f: json.load(open(R + f))
fc = lambda feats: {'type': 'FeatureCollection', 'features': feats}
feat = lambda g, p: {'type': 'Feature', 'properties': p, 'geometry': mapping(g)}
KM = 88.2   # km per degree of longitude at Melbourne's latitude (111.2 per degree of latitude)
KM2 = KM * 111.2
dist_km = lambda a, b: math.hypot((a[0] - b[0]) * KM, (a[1] - b[1]) * 111.2)
FRAME = box(143.6, -39.1, 146.5, -36.9)
pkey = lambda p, *frags: next(k for k in p if any(k.lower() == f or k.lower().startswith(f) for f in frags))


def label_pt(g):
    if g.geom_type == 'MultiPolygon':
        g = max(g.geoms, key=lambda p: p.area)
    try:
        p = polylabel(g, tolerance=0.0001)
    except Exception:
        p = g.representative_point()
    return [round(p.x, 5), round(p.y, 5)]


def polys(g):
    if g.geom_type in ('Polygon', 'MultiPolygon'): return g
    return unary_union([x for x in getattr(g, 'geoms', []) if x.geom_type in ('Polygon', 'MultiPolygon')])


def dump(name, feats):
    json.dump(fc(feats), open(TMP + name + '.geojson', 'w'), separators=(',', ':'))


def write(name, feats):
    json.dump(fc(feats), open(OUT + name + '.geojson', 'w'), separators=(',', ':'))


def lines_of(g):
    if g.geom_type == 'LineString': return [g]
    return [x for p in getattr(g, 'geoms', []) for x in lines_of(p)]


def merged(gs, min_km=0.3):
    u = lines_of(unary_union(gs))
    m = linemerge(u) if len(u) > 1 else (u[0] if u else LineString())
    parts = [p for p in getattr(m, 'geoms', [m]) if p.geom_type == 'LineString' and p.length * KM > min_km]
    return (MultiLineString(parts) if len(parts) > 1 else parts[0]) if parts else None


way_line = lambda w: LineString([(round(p['lon'], 5), round(p['lat'], 5)) for p in w['geometry']])

# ---------- Councils, the City, Greater Melbourne, the land ----------
lgas = load('lga.geojson')['features']
LN = pkey(lgas[0]['properties'], 'lga_name')
COUNCIL = {}
RENAMED = {'Moreland': 'Merri-bek'}   # the 2021 boundaries carry the council's old name (renamed in September 2022)
for f in lgas:
    n = re.sub(r'\s*\((Vic\.|Vic)\)$', '', str(f['properties'][LN])).strip()
    if n.lower().startswith(('unincorporated', 'no usual', 'migratory')): continue
    COUNCIL[RENAMED.get(n, n)] = shape(f['geometry']).buffer(0)
CITY = COUNCIL.pop('Melbourne')
GM = unary_union([shape(f['geometry']).buffer(0) for f in load('gccsa.geojson')['features']])
VIC = unary_union([shape(f['geometry']).buffer(0) for f in load('victoria.geojson')['features']])
print('City km²', round(CITY.area * KM2, 1), '· Greater Melbourne km²', round(GM.area * KM2), '· councils in the box', len(COUNCIL))
# Councils inside Greater Melbourne (by most of their area); the rest are land beyond the region.
# Metropolitan Melbourne's 31 councils are the City and these 30; Macedon Ranges reaches into the ABS's Greater Melbourne
# but isn't a metropolitan council, so it stays land beyond the region.
METRO = {n: g for n, g in COUNCIL.items() if g.intersection(GM).area > 0.5 * g.area and n != 'Macedon Ranges'}
assert len(METRO) == 30, sorted(METRO)
print('metropolitan councils', len(METRO), sorted(METRO))
SHIRES = {'Cardinia', 'Mornington Peninsula', 'Nillumbik', 'Yarra Ranges', 'Macedon Ranges'}
council_name = lambda n: ('Shire of ' if n in SHIRES else 'City of ') + n   # ABS names are bare ("Yarra")

# ---------- Units: the City's suburbs ----------
sal = load('sal.geojson')['features']
SN = pkey(sal[0]['properties'], 'sal_name')
clean = lambda n: re.sub(r'\s*\((Vic\.|Vic)\)$', '', str(n)).strip()
yarra = merged([way_line(w) for w in load('osm_yarra.json')['elements'] if len(w.get('geometry', [])) > 1], 0)
pieces = []
for f in sal:
    n = clean(f['properties'][SN])
    g = shape(f['geometry']).buffer(0)
    if not g.intersects(CITY): continue
    g = polys(g.intersection(CITY))
    if g.is_empty: continue
    if n == 'Melbourne':   # the CBD and St Kilda Road, split at the Yarra: each piece goes to the side of the river it's on
        river = unary_union(lines_of(yarra))
        def north_of_river(p):
            q = p.representative_point()
            return q.y > river.interpolate(river.project(q)).y
        cut = list(getattr(g.difference(river.buffer(0.0002)), 'geoms', [g.difference(river.buffer(0.0002))]))
        strip = g.difference(unary_union(cut))
        cut += list(getattr(strip, 'geoms', [strip]))
        north = unary_union([p for p in cut if p.area > 0 and north_of_river(p)])
        south = unary_union([p for p in cut if p.area > 0 and not north_of_river(p)])
        pieces += [(CBD, polys(north)), (ST_KILDA_RD, polys(south))]
        continue
    pieces.append((n, g))
big = {n: g for n, g in pieces if g.area * KM2 >= 0.05}
for n, g in pieces:
    if n in big: continue
    host = min(big, key=lambda m: big[m].distance(g))
    big[host] = big[host].union(g)
    print('  sliver of', n, round(g.area * KM2, 3), 'km² joins', host)
wanted = [n for v in SIDES.values() for n in v]
print('units', sorted(big), '· missing from SIDES', sorted(set(big) - set(wanted)), '· in SIDES, not found', sorted(set(wanted) - set(big)))
for n in set(big) - set(wanted):   # an unexpected suburb sliver: give it to its biggest neighbour
    host = max((m for m in big if m in wanted), key=lambda m: big[m].buffer(0.0003).intersection(big[n]).area)
    big[host] = big[host].union(big.pop(n))
units, by_name = [], {}
for i, n in enumerate(sorted(big), 1):
    g = polys(big[n].buffer(0.00001).buffer(-0.00001))
    by_name[n] = g
    p = {'name': n, 'code': i, 'lp': label_pt(g)}
    if n in UNIT_AKA: p['aka'] = UNIT_AKA[n]
    if n in UNIT_NOTES: p['part'] = UNIT_NOTES[n]
    units.append(feat(g, p))
dump('suburbs', units)
CODE = {f['properties']['name']: f['properties']['code'] for f in units}
json.dump(CODE, open(TMP + 'unit_codes.json', 'w'))
side_geom = {s: unary_union([by_name[n] for n in ns if n in by_name]) for s, ns in SIDES.items()}
rest = CITY.difference(unary_union(list(side_geom.values())).buffer(0.00001))
for p in [p for p in getattr(rest, 'geoms', [rest]) if p.geom_type == 'Polygon' and p.area > 1e-10]:
    s = min(side_geom, key=lambda s: side_geom[s].distance(p))
    side_geom[s] = side_geom[s].union(p)
sides = [feat(polys(g.buffer(0.00002).buffer(-0.00002)), {'name': s, 'info': SIDE_INFO[s], 'lp': label_pt(g)}) for s, g in side_geom.items()]
dump('sides', sides)

# ---------- Base: the City, Greater Melbourne's other suburbs (by council), land beyond ----------
base = [feat(CITY, {'kind': 'city', 'name': 'City of Melbourne'})]
cutout = CITY.buffer(0.0002)
council_of = lambda g: max(METRO, key=lambda c: METRO[c].intersection(g).area)
ALWAYS = {'St Kilda', 'Fitzroy', 'Richmond', 'Collingwood', 'Brunswick', 'Footscray', 'Prahran', 'Hawthorn', 'Box Hill',
          'Dandenong', 'Frankston', 'Werribee', 'Sunshine', 'Preston', 'Northcote', 'Williamstown', 'Glen Waverley',
          'Ringwood', 'Camberwell', 'Caulfield', 'Brighton', 'Toorak', 'Chadstone', 'Doncaster', 'Essendon', 'Coburg',
          'Point Cook', 'Cranbourne', 'Pakenham', 'Craigieburn', 'Mernda', 'Lilydale', 'Belgrave', 'Sorrento', 'Tullamarine',
          'Clayton', 'Springvale', 'Moonee Ponds', 'Albert Park', 'South Melbourne', 'Port Melbourne', 'South Yarra', 'Abbotsford'}
REGION_G = unary_union(list(METRO.values()))
towns = []
for f in sal:
    n = clean(f['properties'][SN])
    g = shape(f['geometry']).buffer(0)
    if not g.intersects(REGION_G): continue
    g = polys(g.difference(cutout).intersection(REGION_G.buffer(0.0003)))
    if g.is_empty or g.area * KM2 < 0.02: continue
    c = council_name(council_of(g))
    towns.append((n, g, c))
seen = Counter(n for n, _, _ in towns)
for n, g, c in towns:
    pr = {'kind': 'neighbour', 'name': n + (' (%s)' % c if seen[n] > 1 else ''), 'region': c, 'lp': label_pt(g)}
    if n not in ALWAYS: pr['minor'] = True
    base.append(feat(g, pr))
land = VIC.intersection(FRAME)
outside = polys(land.difference(REGION_G.buffer(0.0005)).difference(cutout))
base.insert(0, feat(outside, {'kind': 'outside', 'name': ''}))
dump('base', base)
dump('region_areas', [feat(polys(g), {'region': council_name(c)}) for c, g in sorted(METRO.items())])
print('suburbs around the City', len(towns), '· councils', len(METRO))
write('regions', [{'type': 'Feature', 'properties': {'name': n}, 'geometry': {'type': 'Point', 'coordinates': c}} for n, c in [
    ('Geelong', [144.36, -38.15]), ('Bass Strait', [144.75, -38.75]), ('Gippsland', [146.05, -38.10]),
    ('Ballarat', [143.85, -37.56])]])

# ---------- Known-as names ----------
osm_places = {}
for el in load('osm_places.json')['elements'] + load('osm_landmarks.json')['elements']:
    n = el.get('tags', {}).get('name'); c = (el.get('lon') or el.get('center', {}).get('lon'), el.get('lat') or el.get('center', {}).get('lat'))
    if n and c[0]: osm_places.setdefault(n, []).append(c)
known = []
for k in KNOWN_AS:
    lat, lon = k['at']
    cands = [c for c in osm_places.get(k['osm'], []) if dist_km(c, (lon, lat)) < 1.0]
    pt = min(cands, key=lambda c: dist_km(c, (lon, lat))) if cands else (lon, lat)
    if not cands: print('  known-as from hand position:', k['name'])
    known.append({'type': 'Feature', 'properties': {'name': k['name'], 'kind': k['kind']},
                  'geometry': {'type': 'Point', 'coordinates': [round(pt[0], 5), round(pt[1], 5)]}})
write('knownas', known)

# ---------- Main streets: OpenStreetMap trunk, primary and secondary roads in the City ----------
VIEW = CITY.buffer(0.0003)
segs = defaultdict(list)
for w in load('osm_streets.json')['elements']:
    t = w['tags']
    if len(w.get('geometry', [])) < 2: continue
    key = street_key(t['name'])
    if t['highway'] == 'tertiary' and key not in MAJOR_STREETS: continue
    g = way_line(w).intersection(VIEW)
    if g.is_empty: continue
    segs[(key, 'major' if key in MAJOR_STREETS else 'minor')].append(g)
streets = []
for (name, cls), gs in segs.items():
    m = merged(gs, 0.1)
    if m is None or m.length * KM < (0.4 if cls == 'major' else 0.8): continue
    streets.append(feat(m, {'name': name, 'cls': cls, 'len': round(m.length * 1000, 1)}))
streets.sort(key=lambda f: (f['properties']['cls'] != 'major', -f['properties']['len']))
dump('streets', streets)
print('main streets missing from the data:', sorted(MAJOR_STREETS - {n for n, c in segs if c == 'major'}))

# ---------- Freeways: in the City by name, across the region by route number ----------
def refs_of(tags):
    """Victorian route numbers from OpenStreetMap's ref ("M1;A1" -> ["M1", "A1"]); M and A routes only."""
    out = []
    for r in (tags.get('ref') or '').split(';'):
        r = r.strip()
        if re.fullmatch(r'[MA]\d{1,3}', r): out.append(r)
    return out


inner = CITY.buffer(-0.0003)
in_city, outer, names_of = defaultdict(list), defaultdict(list), defaultdict(Counter)
for w in load('osm_highways.json')['elements']:
    t = w['tags']
    if len(w.get('geometry', [])) < 2 or 'link' in t.get('highway', ''): continue
    line, refs = way_line(w), refs_of(t)
    if t['highway'] == 'motorway' and line.intersects(CITY.buffer(0.002)):
        g = line.intersection(CITY.buffer(0.002))
        nm = t.get('name') or (refs[0] if refs else None)
        if nm and re.search(r'(?i)ramp|\bin\b|\bout\b', nm): nm = None   # on- and off-ramps: drawn, not named
        if not g.is_empty and nm: in_city[street_key(nm)].append(g); names_of[street_key(nm)][refs[0] if refs else ''] += 1
    if refs and (t['highway'] == 'motorway' or refs[0].startswith('M')):
        g = line.difference(inner)
        if not g.is_empty: outer[refs[0]].append(g)
hw = []
for nm, gs in in_city.items():
    m = merged(gs, 0.2)
    if m is None: continue
    route = names_of[nm].most_common(1)[0][0]
    hw.append(feat(m, {'route': route, 'name': nm, 'kind': 'freeway'}))
dump('highways', hw)
TOLL = {'CityLink', 'EastLink', 'Citylink'}
REGION_BOX = REGION_G.buffer(0.02)
gh, shields = [], []
for ref, gs in outer.items():
    m = merged(gs, 1)
    if m is None: continue
    gh.append(feat(m, {'route': ref, 'name': ref, 'toll': False}))
    for p in getattr(m, 'geoms', [m]):
        km = p.length * KM
        if km < 4: continue
        for d in [x for x in range(4, int(km) - 2, 20)] or [km / 2]:
            pt = p.interpolate(d / KM)
            if not REGION_BOX.contains(pt): continue
            if any(s['properties']['route'] == ref and Point(s['geometry']['coordinates']).distance(pt) * KM < 12 for s in shields): continue
            shields.append({'type': 'Feature', 'properties': {'route': ref, 'toll': False},
                            'geometry': {'type': 'Point', 'coordinates': [round(pt.x, 5), round(pt.y, 5)]}})
dump('region_highways', gh)
write('region_shields', shields)
print('freeways in the City', {f['properties']['name']: f['properties']['route'] for f in hw}, '· region routes', sorted(outer), len(shields), 'shields')

json.dump({'units': len(units), 'sides': len(sides)}, open(TMP + 'build_summary.json', 'w'))
print('suburbs', len(units), '· sides', len(sides), '· known-as', len(known), '· neighbours', len(base) - 2, '· streets', len(streets))
