"""Build the Hyderabad map's layer files from cities/hyderabad/raw/ (see SOURCES.md).
Polygons and lines go to tmp/ and are simplified by mapshaper in run.sh; points go straight to docs/hyderabad/data/.

The revenue track only. Hyderabad has two parallel systems of boundaries: the revenue one (districts, mandals,
villages: land records, certificates, law and order) and the civic one (municipal corporations, zones, circles,
wards: roads, drains, property tax). The civic boundaries were redrawn in December 2025 and February 2026 and are
published only as images, so this map shows the revenue track, which the 2027 census has frozen until March 31, 2027.

"The city" here: every mandal mostly inside the Outer Ring Road (more than half its land). The regional view: every
other mandal of the four districts the city spans. Constituencies and PIN codes are drawn across the whole region."""
import json, math, os, re, sys
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping, Point, LineString, MultiLineString, box
from shapely.ops import unary_union, linemerge, polylabel, polygonize
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from names import DISTRICTS, DISTRICT_INFO, KNOWN_AS, BEYOND, BUSINESS_PARKS

R = os.path.join(HERE, 'raw') + '/'
OUT = os.path.join(HERE, '..', '..', 'docs', 'hyderabad', 'data') + '/'
TMP = os.path.join(HERE, 'tmp') + '/'
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
load = lambda f: json.load(open(R + f))
fc = lambda feats: {'type': 'FeatureCollection', 'features': feats}
feat = lambda g, p: {'type': 'Feature', 'properties': p, 'geometry': mapping(g)}
KM = 106.2   # km per degree of longitude at Hyderabad's latitude (111.2 per degree of latitude)
KM2 = KM * 111.2
dist_km = lambda a, b: math.hypot((a[0] - b[0]) * KM, (a[1] - b[1]) * 111.2)
FRAME = box(75.5, 15.0, 81.0, 20.0)   # well past view.max, so the land never runs out when zoomed out or panned


def label_pt(g):
    if g.geom_type == 'MultiPolygon': g = max(g.geoms, key=lambda p: p.area)
    try: p = polylabel(g, tolerance=0.0005)
    except Exception: p = g.representative_point()
    return [round(p.x, 5), round(p.y, 5)]


def polys(g):
    if g.geom_type in ('Polygon', 'MultiPolygon'): return g
    return unary_union([x for x in getattr(g, 'geoms', []) if x.geom_type in ('Polygon', 'MultiPolygon')])


def dump(name, feats): json.dump(fc(feats), open(TMP + name + '.geojson', 'w'), separators=(',', ':'))
def write(name, feats): json.dump(fc(feats), open(OUT + name + '.geojson', 'w'), separators=(',', ':'))


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


norm = lambda s: re.sub(r'[^a-z]', '', (s or '').lower().replace('rangareddy', 'rangareddy').replace('rangareddi', 'rangareddy'))

# ---------- Districts and mandals (OpenStreetMap, from the Telangana government's shapefiles) ----------
admin = load('admin.geojson')['features']
dists = {}
for f in admin:
    p = f['properties']
    if p['level'] != 5: continue
    n = re.sub(r'(?i)\s+district$', '', p['official'] or p['name'] or '').strip()
    dists[n] = shape(f['geometry']).buffer(0)
print('districts in frame', sorted(dists))
DKEY = {norm(d): d for d in DISTRICTS}
D = {}
for n, g in dists.items():
    k = DKEY.get(norm(n)) or DKEY.get(norm(n.replace(' ', '')))
    if k: D[k] = g
assert sorted(D) == sorted(DISTRICTS), ('districts not found', set(DISTRICTS) - set(D))
REGION = unary_union(list(D.values()))
print('region km²', round(REGION.area * KM2))

mandals = []
for f in admin:
    p = f['properties']
    if p['level'] != 6: continue
    g = shape(f['geometry']).buffer(0)
    pt = g.representative_point()
    d = next((k for k, dg in D.items() if dg.contains(pt)), None)
    if not d: continue
    n = re.sub(r'(?i)\s+(mandal|urban mandal)$', '', (p['name'] or '').strip()).strip()
    mandals.append({'name': n, 'district': d, 'g': g, 'osm': p['osm']})
dup = [n for n, c in Counter((m['name'], m['district']) for m in mandals).items() if c > 1]
if dup: print('  same-name mandals in one district:', dup)
print('mandals by district', Counter(m['district'] for m in mandals))
# Gaps: district land no mandal covers (a mandal missing in OpenStreetMap).
for d, dg in D.items():
    gap = dg.difference(unary_union([m['g'] for m in mandals if m['district'] == d]).buffer(0.0003))
    big = [x for x in getattr(gap, 'geoms', [gap]) if x.geom_type == 'Polygon' and x.area * KM2 > 1]
    if big: print('  %s: %.1f km² not in any mandal (%d pieces)' % (d, sum(x.area for x in big) * KM2, len(big)))

# ---------- Lakes: cut out of the land so they read as water ----------
lakes = [shape(f['geometry']).buffer(0) for f in load('lakes.geojson')['features']]
LAKES = unary_union([g for g in lakes if g.area * KM2 >= 0.4])
print('lakes kept', sum(1 for g in lakes if g.area * KM2 >= 0.4), 'of', len(lakes))

# ---------- The Outer Ring Road, and the city: the mandals mostly inside it ----------
roads = load('roads.geojson')['features']
orr_lines = [shape(f['geometry']) for f in roads if re.search(r'(?i)outer ring road', f['properties'].get('name') or '') or (f['properties'].get('ref') or '').upper() == 'ORR']
orr_u = unary_union(orr_lines)
ring = [p for p in polygonize(orr_u.buffer(0.0015).boundary)] if orr_lines else []
ORR = max(ring, key=lambda p: p.area) if ring else None
if ORR is None or ORR.area * KM2 < 600:   # gaps in the mapped road: fall back to the hull of its lines
    print('  ORR polygonize gave', ORR and round(ORR.area * KM2), 'km²: using the convex hull')
    ORR = orr_u.convex_hull
ORR = ORR.buffer(0.002)
print('inside the ORR km²', round(ORR.area * KM2))
for m in mandals:
    m['share'] = m['g'].intersection(ORR).area / m['g'].area
core = [m for m in mandals if m['share'] > 0.5]
for m in sorted(mandals, key=lambda m: -m['share']):
    if 0.25 < m['share'] <= 0.75: print('  borderline %-22s %-20s %.0f%% inside the ORR %s' % (m['name'], m['district'], m['share'] * 100, '(in)' if m in core else '(out)'))
CITY = polys(unary_union([m['g'] for m in core]).buffer(0.00002).buffer(-0.00002).difference(LAKES))
print('city: %d mandals, %.0f km²' % (len(core), CITY.area * KM2))

# ---------- Units: the city's mandals; and its districts as the big fill ----------
core.sort(key=lambda m: (DISTRICTS.index(m['district']), m['name']))
units = []
for i, m in enumerate(core, 1):
    g = polys(m['g'].difference(LAKES))
    units.append(feat(g, {'name': m['name'], 'code': i, 'district': m['district'], 'lp': label_pt(g)}))
dump('mandals', units)
dfill = []
for d in DISTRICTS:
    gs = [m['g'] for m in core if m['district'] == d]
    if not gs: continue
    g = polys(unary_union(gs).buffer(0.00002).buffer(-0.00002).difference(LAKES))
    dfill.append(feat(g, {'name': d, 'info': DISTRICT_INFO[d], 'lp': label_pt(g)}))
dump('districts', dfill)

# ---------- Base: the city, the other mandals of the four districts, land beyond ----------
ALWAYS = {'Shamshabad', 'Medchal', 'Patancheru', 'Sangareddy', 'Ibrahimpatnam', 'Ghatkesar', 'Shamirpet', 'Moinabad', 'Chevella',
          'Shankarpalle', 'Shankarpally', 'Maheshwaram', 'Keesara', 'Kandukur', 'Zahirabad', 'Narayankhed', 'Sadashivpet',
          'Amangal', 'Shadnagar', 'Farooqnagar', 'Kadthal', 'Yacharam', 'Andole', 'Jogipet', 'Gajwel', 'Ameenpur', 'Bachupally', 'Dundigal'}
base = [feat(CITY, {'kind': 'city', 'name': 'Hyderabad'})]
cutout = CITY.buffer(0.0003)
outer_m = []
for m in mandals:
    if m in core: continue
    g = polys(m['g'].difference(cutout).difference(LAKES))
    if g.is_empty: continue
    pr = {'kind': 'neighbour', 'name': m['name'], 'region': m['district'], 'lp': label_pt(g)}
    if m['name'] not in ALWAYS: pr['minor'] = True
    base.append(feat(g, pr)); outer_m.append(m)
outside = polys(FRAME.difference(REGION.buffer(0.0005)).difference(LAKES))
base.insert(0, feat(outside, {'kind': 'outside', 'name': ''}))
dump('base', base)
dump('region_areas', [feat(polys(D[d].difference(LAKES)), {'region': d}) for d in DISTRICTS if d != 'Hyderabad'])
beyond = []
for n, g in dists.items():
    if n in D or any(norm(n) == norm(d) for d in DISTRICTS): continue
    part = g.intersection(FRAME)
    if part.area * KM2 > 400: beyond.append((n + ' district', label_pt(polys(part))))
REG_PREP = prep(REGION.buffer(0.02))
beyond += [(n, c) for n, c in BEYOND if not REG_PREP.contains(Point(c)) and n not in [b[0] for b in beyond]]
write('regions', [{'type': 'Feature', 'properties': {'name': n}, 'geometry': {'type': 'Point', 'coordinates': c}} for n, c in beyond])
print('mandals beyond the city', len(outer_m), '· districts labelled beyond', [n for n, _ in beyond])

# ---------- Constituencies: not drawn ----------
# The open constituency maps (DataMeet's 2008 lines, OpenCity's 2018 map) put well-known places in the wrong seat and
# split most of the old city wards between seats (scouting/hyderabad/FINDINGS.md). representatives.json is kept ready
# for when accurate lines are available.
REG_B = REGION.buffer(0.0005)
inreg = lambda g: polys(g.intersection(REG_B).difference(LAKES))

# ---------- PIN codes (Department of Posts via OpenCity, 2025) ----------
pins = load('pincodes.geojson')
src_rank = {s['name']: i for i, s in enumerate(pins.get('sources', []))}
by_pin = defaultdict(list)
for f in pins['features']:
    p = f['properties']
    pin = next((str(v) for k, v in p.items() if re.fullmatch(r'\d{6}', str(v or '').strip())), None)
    if not pin: continue
    office = next((v for k, v in p.items() if re.search(r'(?i)office|^name$|po_name|officename', k) and not re.fullmatch(r'\d{6}', str(v))), None)
    by_pin[pin].append((src_rank.get(p.get('_src'), 9), shape(f['geometry']).buffer(0), office))
pinf = []
for pin, xs in by_pin.items():
    best = min(x[0] for x in xs)   # one source per PIN: the city file over the all-India one
    g = inreg(unary_union([x[1] for x in xs if x[0] == best]))
    if g.is_empty or g.area * KM2 < 0.05: continue
    office = next((x[2] for x in xs if x[0] == best and x[2]), None)
    pinf.append(feat(g, {'pin': pin, 'office': re.sub(r'(?i)\s+(s\.?o|b\.?o|h\.?o|g\.?p\.?o)\.?$', '', office or '').strip().title() or None, 'lp': label_pt(g)}))
pinf.sort(key=lambda f: f['properties']['pin'])
dump('pincodes', pinf)
print('PIN codes', len(pinf), '· sources', pins.get('sources'))

# ---------- Known-as names ----------
osm_places = defaultdict(list)
places_raw = load('osm_places.json')['elements']
for el in places_raw + load('osm_landmarks.json')['elements']:
    t = el.get('tags', {}); c = (el.get('lon'), el.get('lat'))
    for n in {t.get('name'), t.get('name:en'), t.get('alt_name')} - {None}:
        if c[0]: osm_places[n.lower()].append(c)
known = []
for k in KNOWN_AS:
    lat, lon = k['at']
    cands = [c for c in osm_places.get(k['osm'].lower(), []) + osm_places.get(k['name'].lower(), []) if dist_km(c, (lon, lat)) < 1.2]
    pt = min(cands, key=lambda c: dist_km(c, (lon, lat))) if cands else (lon, lat)
    if not cands: print('  known-as from hand position:', k['name'])
    known.append({'type': 'Feature', 'properties': {'name': k['name'], 'kind': k['kind']},
                  'geometry': {'type': 'Point', 'coordinates': [round(pt[0], 5), round(pt[1], 5)]}})
write('knownas', known)

# ---------- Business parks (names.py), placed at OpenStreetMap's site of the same name ----------
biz_osm = defaultdict(list)
for b in load('osm_bizparks.json')['elements']:
    biz_osm[b['name'].lower()].append(((b['lon'], b['lat']), b['km2']))
bizf = []
for b in BUSINESS_PARKS:
    lat, lon = b['at']
    cands = [c for c in biz_osm.get(b['osm'].lower(), []) if dist_km(c[0], (lon, lat)) < 1.0]
    pt = max(cands, key=lambda c: c[1])[0] if cands else (lon, lat)   # the largest mapped site of that name
    if not cands: print('  business park from hand position:', b['name'])
    bizf.append({'type': 'Feature', 'properties': {'name': b['name'], 'cat': 'tw-com', 'sub': b['area']},
                 'geometry': {'type': 'Point', 'coordinates': [round(pt[0], 5), round(pt[1], 5)]}})
write('bizparks', bizf)
print('business parks', len(bizf))

# ---------- Places beyond the city, for search ("Near Patancheru") ----------
KIND = {'town': 'Town', 'village': 'Village', 'suburb': 'Suburb', 'quarter': 'Neighbourhood', 'neighbourhood': 'Neighbourhood',
        'locality': 'Locality', 'hamlet': 'Hamlet', 'city': 'Town'}
CITY_P = prep(CITY.buffer(0.001))
om_prep = [(m, prep(m['g'])) for m in outer_m]
rp, seen = [], set()
for el in places_raw:
    t = el['tags']; n = t.get('name:en') or t.get('name')
    if not n or not re.search(r'[A-Za-z]', n): continue
    pt = Point(el['lon'], el['lat'])
    if CITY_P.contains(pt): continue
    m = next((m for m, pp in om_prep if pp.contains(pt)), None)
    if not m or (n, m['name']) in seen: continue
    seen.add((n, m['name']))
    rp.append({'name': n, 'muni': m['name'], 'region': m['district'], 'kind': KIND[t['place']], 'at': [el['lon'], el['lat']]})
rp.sort(key=lambda p: p['name'])
json.dump(rp, open(OUT + 'region_places.json', 'w'), separators=(',', ':'), ensure_ascii=False)
print('places beyond the city', len(rp), Counter(p['kind'] for p in rp))

# ---------- Highways: the ORR, the PVNR Expressway and the national highways ----------
def hw_of(p):
    n, ref = p.get('name') or '', (p.get('ref') or '') + ';' + (p.get('nat') or '')
    if re.search(r'(?i)outer ring road', n) or re.search(r'(?i)\bORR\b', ref): return ('ORR', 'Outer Ring Road', 'interstate')
    if re.search(r'(?i)p\.?\s*v\.?\s*narasimha rao|pvnr', n): return ('PVNR', 'PVNR Expressway', 'interstate')
    m = re.search(r'(?i)\bNH\s*-?\s*(\d+[A-Z]?)', ref)
    if m: return (m.group(1), 'NH ' + m.group(1), 'provincial')
    return None


in_city, outer = defaultdict(list), defaultdict(list)
CITY_B5 = CITY.buffer(0.0005); INNER_P = prep(CITY.buffer(-0.0004))
for f in roads:
    p = f['properties']
    if p['hw'] not in ('motorway', 'trunk'): continue
    h = hw_of(p)
    if not h: continue
    line = shape(f['geometry'])
    g = line if h[0] == 'ORR' else clip(line, CITY_B5)   # the ORR whole: it leaves the city's mandals and comes back
    if g is not None: in_city[h].append(g)
    if not INNER_P.contains(line): outer[h].append(line)
hw = []
for (route, name, kind), gs in in_city.items():
    m = merged(gs, 0.3)
    if m is not None: hw.append(feat(m, dict({'route': route, 'name': name, 'kind': kind}, **({'over': True} if route == 'ORR' else {}))))
dump('highways', hw)

# ---------- Main streets and collectors (OpenStreetMap, inside the city) ----------
# Main: trunk roads that aren't the ORR, PVNR or a national highway, and primary roads (major); secondary (minor).
# Collectors: tertiary. Unnamed stretches are kept so the network doesn't break off; they draw without a label.
CITY_B3 = CITY.buffer(0.0003)
CLS = {'trunk': 'major', 'primary': 'major', 'secondary': 'minor', 'tertiary': 'coll'}
segs = defaultdict(list)
for f in roads:
    p = f['properties']
    if p['hw'] not in CLS or (p['hw'] == 'trunk' and hw_of(p)): continue
    n = (p.get('name') or '').strip() or None
    if n and re.search(r'(?i)\b(ramp|exit|entry|slip road|service road|u-?turn)\b', n): n = None
    g = clip(shape(f['geometry']), CITY_B3)
    if g is None: continue
    segs[(n, CLS[p['hw']])].append(g)
streets, colls = [], []
for (n, cls), gs in segs.items():
    m = merged(gs, 0.05)
    if m is None or (n and m.length * KM < 0.3): continue
    (colls if cls == 'coll' else streets).append(feat(m, {'name': n, 'cls': cls, 'len': round(m.length * 1000, 1)}))
for L in (streets, colls): L.sort(key=lambda f: (f['properties']['name'] is None, f['properties']['cls'] != 'major', -f['properties']['len']))
dump('streets', streets); dump('collectors', colls)
print('main streets', len(streets), sum(f['properties']['cls'] == 'major' for f in streets), 'major,',
      round(sum(f['properties']['len'] for f in streets) / 1000 * KM), 'km · collectors', len(colls), round(sum(f['properties']['len'] for f in colls) / 1000 * KM), 'km')
REG_P = prep(REGION.buffer(0.01))
gh, shields = [], []
for (route, name, kind), gs in outer.items():
    m = merged(gs, 1)
    if m is None: continue
    gh.append(feat(m, {'route': route, 'name': name, 'toll': False}))
    for part in getattr(m, 'geoms', [m]):
        km = part.length * KM
        if km < 8: continue
        for d in [x for x in range(8, int(km) - 2, 35)] or [km / 2]:
            pt = part.interpolate(d / KM)
            if not REG_P.contains(pt) or CITY.buffer(0.01).contains(pt): continue
            if any(s['properties']['route'] == route and Point(s['geometry']['coordinates']).distance(pt) * KM < 20 for s in shields): continue
            shields.append({'type': 'Feature', 'properties': {'route': route, 'toll': False}, 'geometry': {'type': 'Point', 'coordinates': [round(pt.x, 5), round(pt.y, 5)]}})
dump('region_highways', gh)
write('region_shields', shields)
print('highways in the city', sorted(n for _, n, _ in in_city), '· beyond', sorted(n for _, n, _ in outer), len(shields), 'shields')

# ---------- Hyderabad Metro and MMTS (OpenStreetMap route relations) ----------
rail = load('osm_rail.json')
stops = {int(k): v for k, v in rail['stops'].items()}
METRO = [('red', 'Red', r'(?i)red|corridor\s*(i|1)\b|miyapur|lb nagar|l\.?b\.? nagar'), ('blue', 'Blue', r'(?i)blue|corridor\s*(iii|3)\b|nagole|raidurg|raidurgam'),
         ('green', 'Green', r'(?i)green|corridor\s*(ii|2)\b|jbs|jubilee bus|mgbs|mahatma gandhi bus')]
COLOUR = {'red': 'Red', 'blue': 'Blue', 'green': 'Green'}
mlines, mstn = defaultdict(list), {}
clean = lambda n: re.sub(r'(?i)\s+(metro\s+)?(station|metro|mmts)$', '', (n or '').strip()).strip()
for r in rail['routes']:
    if r['route'] not in ('subway', 'light_rail'): continue
    blob = ' '.join(str(r.get(k) or '') for k in ('name', 'ref', 'colour', 'from', 'to'))
    line = next((l for l, _, rx in METRO if re.search(r'(?i)\b' + l + r'\b', blob)), None) or next((l for l, _, rx in METRO if re.search(rx, blob)), None)
    if not line: print('  metro route not placed:', blob); continue
    mlines[line].extend(lines_of(shape(r['geometry'])))
    for s in r['stops']:
        n = stops.get(int(s))
        if not n or not n.get('name'): continue
        nm = clean(n['name'])
        v = mstn.setdefault(nm.lower(), {'name': nm, 'pts': [], 'lines': set()})
        v['pts'].append((n['lon'], n['lat'])); v['lines'].add(COLOUR[line])
pt_of = lambda v: [round(sum(p[0] for p in v['pts']) / len(v['pts']), 5), round(sum(p[1] for p in v['pts']) / len(v['pts']), 5)]
metro = [feat(merged(gs, 0.05), {'line': l, 'name': COLOUR[l] + ' Line'}) for l, gs in mlines.items() if merged(gs, 0.05) is not None]
dump('metro_lines', metro)
ORDER_L = ['Red', 'Blue', 'Green']
ends = set()
for l, gs in mlines.items():
    m = merged(gs, 0.05)
    for part in getattr(m, 'geoms', [m]):
        ends.add(part.coords[0]); ends.add(part.coords[-1])
mfeat = []
for v in mstn.values():
    c = pt_of(v)
    p = {'name': v['name'], 'lines': sorted(v['lines'], key=ORDER_L.index)}
    if any(dist_km(c, e) < 0.5 for e in ends) and len(v['lines']) == 1: p['terminus'] = True
    mfeat.append({'type': 'Feature', 'properties': p, 'geometry': {'type': 'Point', 'coordinates': c}})
write('metro_stations', mfeat)
print('metro lines', sorted(mlines), '· stations', len(mfeat))

mm, mmst = [], {}
for r in rail['routes']:
    if r['route'] != 'train': continue
    mm.extend(lines_of(shape(r['geometry'])))
    for s in r['stops']:
        n = stops.get(int(s))
        if not n or not n.get('name'): continue
        nm = clean(n['name'])
        v = mmst.setdefault(nm.lower(), {'name': nm, 'pts': [], 'lines': {'MMTS'}})
        v['pts'].append((n['lon'], n['lat']))
mmg = merged(mm, 0.2)
rail_l = [feat(mmg, {'line': 'mmts', 'name': 'MMTS', 'color': '#7A4E9E', 'offset': 0, 'to': 'Lingampalli, Falaknuma, Medchal, Ghatkesar and Umdanagar', 'agency': 'South Central Railway'})] if mmg is not None else []
rail_in = [feat(g, f['properties']) for f in rail_l for g in [clip(shape(f['geometry']), CITY.buffer(0.002))] if g is not None]
dump('rail_lines', rail_l); dump('rail_lines_inner', rail_in)
HUBS = {'Secunderabad', 'Hyderabad', 'Kacheguda', 'Lingampalli', 'Falaknuma', 'Begumpet'}
write('rail_stations', [{'type': 'Feature', 'properties': {'name': v['name'], 'lines': ['MMTS'], **({'hub': True} if v['name'] in HUBS else {})},
                         'geometry': {'type': 'Point', 'coordinates': pt_of(v)}} for v in mmst.values()])
print('MMTS routes', sum(1 for r in rail['routes'] if r['route'] == 'train'), '· stations', len(mmst))

# ---------- An empty profile file: the map has no neighbourhood lens (see city.json "lens") ----------
json.dump({}, open(OUT + 'profiles.json', 'w'))
print('units', len(units), '· known-as', len(known), '· PIN codes', len(pinf))

# The page asks for a representatives file even with no offices on the card: publish an empty one (no 404).
json.dump({'updated': '2026-10-30'}, open(OUT + 'representatives.json', 'w'))
