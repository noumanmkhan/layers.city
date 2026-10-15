"""Build the Vancouver map's layer files from cities/vancouver/raw/ (see SOURCES.md).
Polygons and lines go to tmp/ and are simplified by mapshaper in run.sh; points go straight to
docs/vancouver/data/. Output shapes match Toronto's and Chicago's, so the shared engine draws all three.

Land and water: Statistics Canada's cartographic boundaries are clipped to the shoreline, so the land is the
union of the census subdivisions around the Lower Mainland (and Washington State's outline south of the
border); everything else in the frame is water. The City of Vancouver is its own census subdivision, which
leaves out the Musqueam reserve (Musqueam 2), a First Nation's land rather than the City's."""
import json, math, os, re, sys
from collections import defaultdict
from shapely.geometry import shape, mapping, Point, LineString, MultiLineString, box
from shapely.ops import unary_union, linemerge, polylabel

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from names import SIDES, SIDE_INFO, KNOWN_AS, street_name, street_key, MAJOR_STREETS

R = os.path.join(HERE, 'raw') + '/'
OUT = os.path.join(HERE, '..', '..', 'docs', 'vancouver', 'data') + '/'
TMP = os.path.join(HERE, 'tmp') + '/'
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
load = lambda f: json.load(open(R + f))
fc = lambda feats: {'type': 'FeatureCollection', 'features': feats}
feat = lambda g, p: {'type': 'Feature', 'properties': p, 'geometry': mapping(g)}
KM = 72.6   # km per degree of longitude at Vancouver's latitude (111 per degree of latitude)
dist_km = lambda a, b: math.hypot((a[0] - b[0]) * KM, (a[1] - b[1]) * 111.2)


def label_pt(g):
    if g.geom_type == 'MultiPolygon':
        g = max(g.geoms, key=lambda p: p.area)
    try:
        p = polylabel(g, tolerance=0.0002)
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

# ---------- Land: municipalities and reserves (Statistics Canada), Washington State ----------
FRAME = box(-125.0, 48.2, -121.0, 50.2)
csds = [(f['properties'], shape(f['geometry']).buffer(0)) for f in load('csds.geojson')['features']]
# The census divisions around Metro Vancouver (fetch_land.py), only as land shown beyond the region.
AROUND = [shape(f['geometry']).buffer(0) for f in load('cds_around.geojson')['features']] if os.path.exists(R + 'cds_around.geojson') else []
WA = unary_union([shape(f['geometry']).buffer(0) for f in load('washington.geojson')['features']])
CITY = next(g for p, g in csds if p['CSDUID'] == '5915022')
inside = lambda g: polys(g.intersection(CITY))
# The University Endowment Lands: the Point Grey piece of Electoral Area A (UBC's campus, Pacific Spirit Regional Park and the
# UEL neighbourhoods). Not part of the City, but the map shows it with the city (decided with the user, October 16, 2026):
# an "annex" in base (shaded and outlined apart, never masked), a unit of its own (24) with Living here figures, and the
# main streets, transit and landmarks drawn there as in the city. The rest of Electoral Area A stays a neighbour.
POINT_GREY = box(-123.30, 49.20, -123.19, 49.30)
AREA_A = next(g for p, g in csds if p['CSDTYPE'] == 'RDA' and p['CSDNAME'].endswith(' A'))
UEL = polys(AREA_A.intersection(POINT_GREY).difference(CITY.buffer(0.0002)))
VIEW = unary_union([CITY, UEL])
UEL_PROPS = {'name': 'University Endowment Lands', 'park': 'beside the City of Vancouver, not part of it',
             'aka': ['UEL', 'UBC Endowment Lands', 'Endowment Lands', 'UBC lands'],
             'gov': 'The Province of BC (the UEL), UBC (its campus) and Metro Vancouver (Pacific Spirit Park)',
             'votes': 'Metro Vancouver Electoral Area A, not the City'}

# ---------- Local areas (the units) and the three sides ----------
las = sorted(((f['properties']['name'].strip(), shape(f['geometry']).buffer(0)) for f in load('local_areas.geojson')['features']))
assert len(las) == 22, len(las)
units = []
for i, (name, g) in enumerate(las, 1):
    g = inside(g)
    units.append((i, name, g))
by_name = {n: g for _, n, g in units}
assert sorted(by_name) == sorted(n for v in SIDES.values() for n in v), set(by_name) ^ {n for v in SIDES.values() for n in v}
side_geom = {s: unary_union([by_name[n] for n in ns]) for s, ns in SIDES.items()}
# The City's land that no local area covers: Stanley Park, and slivers where the City's shoreline and
# Statistics Canada's differ. Each piece joins the side it's nearest, so the sides cover the whole city.
rest = CITY.difference(unary_union(list(side_geom.values())).buffer(0.00001))
pieces = [p for p in getattr(rest, 'geoms', [rest]) if p.geom_type == 'Polygon' and p.area > 1e-9]
for p in pieces:
    s = min(side_geom, key=lambda s: side_geom[s].distance(p))
    side_geom[s] = side_geom[s].union(p)
big = max(pieces, key=lambda p: p.area) if pieces else None
print('land outside the local areas:', len(pieces), 'pieces; largest', round(big.area * KM * 111.2, 2) if big else 0, 'km² at', label_pt(big) if big else None)
# Stanley Park belongs to none of the 22 local areas. It joins the units file as its own shape (code 23,
# park note), so a tap there is named for the park; it has no census figures, so it never takes a lens tier.
assert big is not None and big.area * KM * 111.2 > 3.5 and big.contains(Point(-123.1417, 49.3017)), 'Stanley Park not found'
units_out = [feat(g, {'name': n, 'code': i, 'lp': label_pt(g)}) for i, n, g in units] + \
    [feat(big, {'name': 'Stanley Park', 'code': 23, 'park': 'a park, not one of the 22', 'lp': label_pt(big)})] + \
    [feat(UEL, dict(UEL_PROPS, code=24, lp=label_pt(UEL)))]
dump('local_areas', units_out)
sides = []
for s, g in side_geom.items():
    g = polys(g.buffer(0.00002).buffer(-0.00002))
    sides.append(feat(g, {'name': s, 'info': SIDE_INFO[s], 'lp': label_pt(g)}))
dump('sides', sides)

# ---------- Base: the city, Metro Vancouver's other municipalities, and land beyond ----------
TYPE_NAME = {'CY': 'City of {n}', 'DM': 'District of {n}', 'TP': 'Township of {n}', 'VL': 'Village of {n}', 'IM': '{n}'}
METRO = [(p, g) for p, g in csds if p['CSDUID'][:4] == '5915' and p['CSDUID'] != '5915022']
dup = {p['CSDNAME'] for p, _ in METRO if sum(q['CSDNAME'] == p['CSDNAME'] for q, _ in METRO) > 1}


def muni_name(p):
    n, t = p['CSDNAME'], p['CSDTYPE']
    if t == 'IRI': return n + ' (reserve)'
    if t == 'RDA': return 'Electoral Area A' if n.endswith(' A') else n   # its Point Grey piece is the annex below
    if t == 'TWL': return n
    return TYPE_NAME.get(t, '{n}').format(n=n) if n in dup else n


base, cutout = [feat(CITY, {'kind': 'city', 'name': 'City of Vancouver'})], CITY.buffer(0.0002)
for p, g in METRO:
    g = polys(g.difference(cutout))
    if g.is_empty: continue
    if p['CSDTYPE'] == 'RDA' and p['CSDNAME'].endswith(' A'):
        g = polys(g.difference(POINT_GREY))
        base.append(feat(UEL, {'kind': 'annex', 'name': UEL_PROPS['name'], 'region': 'Metro Vancouver', 'lp': label_pt(UEL)}))
    pr = {'kind': 'neighbour', 'name': muni_name(p), 'region': 'Metro Vancouver', 'lp': label_pt(g), 'type': p['CSDTYPE']}
    if p['CSDTYPE'] in ('IRI', 'RDA', 'TWL'): pr['rest'] = True   # not a town to colour in the drive lens
    base.append(feat(g, pr))
REGION = unary_union([g for p, g in csds if p['CSDUID'][:4] == '5915'])
land = unary_union([g for p, g in csds] + AROUND + [WA]).intersection(FRAME)
outside = polys(land.difference(REGION.buffer(0.0005)))
base.insert(0, feat(outside, {'kind': 'outside', 'name': ''}))
dump('base', base)
write('regions', [{'type': 'Feature', 'properties': {'name': n}, 'geometry': {'type': 'Point', 'coordinates': c}} for n, c in [
    ('Fraser Valley', [-122.05, 49.12]), ('Sunshine Coast', [-123.72, 49.55]), ('Vancouver Island', [-123.95, 49.05]),
    ('Washington, USA', [-122.55, 48.85]), ('Squamish-Lillooet', [-123.10, 49.75])]])

# ---------- Known-as names: curated, moved to OpenStreetMap's place point when one is close ----------
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

# ---------- Main streets: OpenStreetMap trunk, primary and secondary roads inside the city ----------
segs = defaultdict(list)
for w in load('osm_streets.json')['elements']:
    t = w['tags']
    if len(w.get('geometry', [])) < 2: continue
    key = street_key(t['name'])
    # OpenStreetMap files a few of the city's arterials (25th, 33rd, 57th, Mackenzie, Renfrew) as tertiary:
    # a tertiary road is a main street only when it's on the hand-kept list; the rest wait for a collectors layer.
    if t['highway'] == 'tertiary' and key not in MAJOR_STREETS: continue
    g = way_line(w).intersection(VIEW.buffer(0.0003))   # the University Endowment Lands' roads too
    if g.is_empty: continue
    segs[(key, 'major' if key in MAJOR_STREETS else 'minor')].append(g)
streets = []
for (name, cls), gs in segs.items():
    m = merged(gs, 0.15)
    if m is None or m.length * KM < (0.6 if cls == 'major' else 1.0): continue
    streets.append(feat(m, {'name': name, 'cls': cls, 'len': round(m.length * 1000, 1)}))
streets.sort(key=lambda f: (f['properties']['cls'] != 'major', -f['properties']['len']))
dump('streets', streets)
print('main streets missing from the data:', sorted(MAJOR_STREETS - {n for n, c in segs if c == 'major'}))

# ---------- Highways: freeways inside the city by name, BC highways across the region by number ----------
def refs_of(tags):
    """BC highway numbers from OpenStreetMap's ref ("TCH 1;BC 99" -> ["1", "99"]); Washington's routes are left out."""
    out = []
    for r in (tags.get('ref') or '').split(';'):
        m = re.fullmatch(r'(?:BC |TCH )?(\d{1,3}[A-Z]?)', r.strip())
        if m: out.append(m.group(1))
    return out


inner = CITY.buffer(-0.0004)
in_city, outer = defaultdict(list), defaultdict(list)
for w in load('osm_highways.json')['elements']:
    t = w['tags']
    if len(w.get('geometry', [])) < 2 or 'link' in t.get('highway', ''): continue
    line, refs = way_line(w), refs_of(t)
    if t['highway'] == 'motorway' and line.intersects(CITY):
        g = line.intersection(CITY.buffer(0.0005))
        if not g.is_empty and refs: in_city[refs[0]].append(g)
    if refs:
        g = line.difference(inner)
        if not g.is_empty: outer[refs[0]].append(g)
HWY_NAME = {'1': 'Trans-Canada Highway (Hwy 1)'}
hw = []
for ref, gs in in_city.items():
    m = merged(gs, 0.2)
    if m is None: continue
    hw.append(feat(m, {'route': ref, 'name': HWY_NAME.get(ref, 'Highway ' + ref), 'kind': 'provincial'}))
dump('highways', hw)
REGION_BOX = REGION.buffer(0.01)
gh, shields = [], []
for ref, gs in outer.items():
    m = merged(gs, 1)
    if m is None: continue
    gh.append(feat(m, {'route': ref, 'name': 'Highway ' + ref, 'toll': False}))
    for p in getattr(m, 'geoms', [m]):
        km = p.length * KM
        if km < 5: continue
        for d in [x for x in range(5, int(km) - 2, 25)] or [km / 2]:
            pt = p.interpolate(d / KM)
            if not REGION_BOX.contains(pt): continue
            if any(s['properties']['route'] == ref and Point(s['geometry']['coordinates']).distance(pt) * KM < 15 for s in shields): continue
            shields.append({'type': 'Feature', 'properties': {'route': ref, 'toll': False},
                            'geometry': {'type': 'Point', 'coordinates': [round(pt.x, 5), round(pt.y, 5)]}})
dump('region_highways', gh)
write('region_shields', shields)

# ---------- SkyTrain and SeaBus (metro), West Coast Express (rail), from TransLink's GTFS ----------
tl = load('translink_rail.json')

def reach_stations(m):
    """Extend a line whose end stops within 350 m of a station point that it doesn't touch (the Canada Line ends at
    its own Waterfront platform, west of the station point TransLink gives for Waterfront), so it meets the dot."""
    pts = [(s['lon'], s['lat']) for s in tl['stations']]
    parts = []
    for p in getattr(m, 'geoms', [m]):
        c = list(p.coords)
        for i in (0, -1):
            near = min(pts, key=lambda q: dist_km(q, c[i]))
            if 0.02 < dist_km(near, c[i]) < 0.35 and not any(dist_km(near, x) < 0.02 for x in c):
                c = [near] + c if i == 0 else c + [near]
        parts.append(LineString(c))
    return MultiLineString(parts) if len(parts) > 1 else parts[0]


LINE_ID = lambda r: 'seabus' if r['type'] == '4' else 'wce' if r['type'] == '2' else re.sub(r'\W', '', r['long'].lower().replace(' line', '').replace('skytrain', '').strip())
metro, metro_names = [], {}
for rid, r in tl['routes'].items():
    lid = LINE_ID(r)
    if lid == 'wce': continue
    top = max(r['counts'].values())
    shp = [LineString(r['shapes'][s]) for s, c in r['counts'].items() if c >= top * 0.15 and len(r['shapes'][s]) > 1]
    m = merged(shp, 0.1)
    m = reach_stations(m)
    name = 'SeaBus' if lid == 'seabus' else r['long'] if 'Line' in r['long'] else r['long'] + ' Line'
    metro_names[rid] = {'seabus': 'SeaBus'}.get(lid, name.replace(' Line', ''))
    metro.append(feat(m, {'line': lid, 'name': name}))
ORDER = ['seabus', 'canada', 'millennium', 'expo']
dump('skytrain_lines', sorted(metro, key=lambda f: ORDER.index(f['properties']['line']) if f['properties']['line'] in ORDER else 0))
TERMINI = {'Waterfront', 'King George', 'Production Way-University', 'Production Way–University', 'VCC-Clark', 'Lafarge Lake-Douglas',
           'YVR-Airport', 'Richmond-Brighouse', 'Lonsdale Quay'}
stations, seen = [], {}
for s in tl['stations']:
    rs = [x for x in s['routes'] if x in metro_names]
    if not rs: continue
    name = re.sub(r'\s+(Station|SkyTrain Station)$', '', s['name']).replace(' @ ', ' ')
    name = re.sub(r'\s*(Northbound|Southbound|Eastbound|Westbound|Platform \d+|Bay \d+).*$', '', name).strip()
    key = name.lower()
    if key in seen:   # one point per station: platforms of the same station merge
        st = seen[key]; st['pts'].append((s['lon'], s['lat'])); st['lines'] |= {metro_names[x] for x in rs}; continue
    seen[key] = {'name': name, 'pts': [(s['lon'], s['lat'])], 'lines': {metro_names[x] for x in rs}}
LORD = ['Expo', 'Millennium', 'Canada', 'SeaBus']
write('skytrain_stations', [{'type': 'Feature', 'properties': {'name': st['name'], 'lines': sorted(st['lines'], key=lambda l: LORD.index(l) if l in LORD else 9),
                                                               'terminus': st['name'] in TERMINI},
                             'geometry': {'type': 'Point', 'coordinates': [round(sum(p[0] for p in st['pts']) / len(st['pts']), 5),
                                                                           round(sum(p[1] for p in st['pts']) / len(st['pts']), 5)]}}
                            for st in seen.values()])
wce_lines, wce_in, wce_stn = [], [], []
for rid, r in tl['routes'].items():
    if LINE_ID(r) != 'wce': continue
    top = max(r['counts'].values())
    s = max((s for s, c in r['counts'].items() if c >= top * 0.5), key=lambda s: len(r['shapes'][s]))
    g = LineString(r['shapes'][s])
    p = {'line': 'WCE', 'name': 'West Coast Express', 'color': '#' + (r['color'] or '6B2C91'), 'offset': 0, 'to': 'Mission City'}
    wce_lines.append(feat(g, p))
    gi = g.intersection(CITY.buffer(0.002))
    if not gi.is_empty: wce_in.append(feat(gi, p))
    seen_wce = {}
    for st in tl['stations']:
        if rid in st['routes']:   # platforms filed as "X Station @ West Coast Express" merge into X
            nm = re.sub(r'\s+Station$', '', st['name'].split(' @ ')[0]).strip()
            seen_wce.setdefault(nm, []).append((st['lon'], st['lat']))
    metro_at = {st['name']: (sum(p[0] for p in st['pts']) / len(st['pts']), sum(p[1] for p in st['pts']) / len(st['pts'])) for st in seen.values()}
    for nm, pts in seen_wce.items():
        if nm in metro_at: pts = [metro_at[nm]]   # Waterfront: one dot shared with SkyTrain and SeaBus
        wce_stn.append({'type': 'Feature', 'properties': {'name': nm, 'lines': ['West Coast Express'], **({'hub': True} if nm == 'Waterfront' else {})},
                        'geometry': {'type': 'Point', 'coordinates': [round(sum(p[0] for p in pts) / len(pts), 5), round(sum(p[1] for p in pts) / len(pts), 5)]}})
dump('wce_lines', wce_lines); dump('wce_lines_inner', wce_in); write('wce_stations', wce_stn)

print('local areas', len(units), '· sides', len(sides), '· known-as', len(known), '· neighbours', len(base) - 2,
      '· streets', len(streets), sum(f['properties']['cls'] == 'major' for f in streets), 'major',
      '· city freeways', sorted(in_city), '· region routes', sorted(outer), len(shields), 'shields',
      '· metro lines', [f['properties']['name'] for f in metro], '· stations', len(seen), '· WCE stations', len(wce_stn))
