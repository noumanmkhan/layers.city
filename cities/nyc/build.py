"""Build the New York City map's layer files from cities/nyc/raw/ (see SOURCES.md).
Polygons and lines go to tmp/ and are simplified by mapshaper in run.sh; points go straight to
docs/nyc/data/. Output shapes match the other cities', so the shared engine draws all of them.

Land and water: the five boroughs come from the City's own boundaries (DCP, clipped to the shoreline); the region
around them from the Census Bureau's cartographic boundaries (also shoreline-clipped): counties, and county
subdivisions as the municipalities (New Jersey's townships, boroughs and cities; New York's towns and cities;
Connecticut's towns). Everything not land is water.

Units: the 59 community districts. The 12 joint interest areas in DCP's file (Central Park, the airports, the big
parks) become park units with no profile. 2020 NTAs are a second, finer layer."""
import json, math, os, re, sys
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping, Point, LineString, MultiLineString, box
from shapely.ops import unary_union, linemerge, polylabel
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from names import BORO, CD_NAMES, CD_INFO, BORO_INFO, KNOWN_AS, MAJOR_STREETS, HIGHWAYS, street_key, street_name

R = os.path.join(HERE, 'raw') + '/'
OUT = os.path.join(HERE, '..', '..', 'docs', 'nyc', 'data') + '/'
TMP = os.path.join(HERE, 'tmp') + '/'
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
load = lambda f: json.load(open(R + f))
fc = lambda feats: {'type': 'FeatureCollection', 'features': feats}
feat = lambda g, p: {'type': 'Feature', 'properties': p, 'geometry': mapping(g)}
KM = 84.4   # km per degree of longitude at New York's latitude (111.2 per degree of latitude)
KM2 = KM * 111.2
dist_km = lambda a, b: math.hypot((a[0] - b[0]) * KM, (a[1] - b[1]) * 111.2)
FRAME = box(-76.0, 39.6, -71.8, 42.3)
CITY_COUNTIES = ['36005', '36047', '36061', '36081', '36085']
CORE = ['36119', '36087', '36059', '36103', '36079', '36071', '36027',
        '34003', '34017', '34013', '34039', '34031', '34023', '34025', '34027', '34035', '34021',
        '09190', '09120', '09170', '09140']
ST = {'36': 'NY', '34': 'NJ', '09': 'CT'}


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


_SP = None


def geo(f):
    """A feature's shape in WGS84. A few City layers (LPC's) come in New York State Plane feet (EPSG:2263)."""
    global _SP
    g = shape(f['geometry'])
    x = g.bounds[0]
    if abs(x) > 360:
        if _SP is None:
            from pyproj import Transformer
            from shapely.ops import transform
            t = Transformer.from_crs(2263, 4326, always_xy=True)
            _SP = lambda g: transform(t.transform, g)
        g = _SP(g)
    return g.buffer(0)


way_line = lambda w: LineString([(round(p['lon'], 5), round(p['lat'], 5)) for p in w['geometry']])
prop = lambda p, *keys: next((p[k] for k in keys if p.get(k) not in (None, '')), None)

# ---------- The city and its boroughs ----------
boroughs = {}
for f in load('boroughs.geojson')['features']:
    p = f['properties']
    boroughs[str(prop(p, 'boro_name', 'boroname', 'BoroName')).replace('The Bronx', 'Bronx')] = shape(f['geometry']).buffer(0)
CITY = polys(unary_union(list(boroughs.values())).buffer(0))
inside = lambda g: polys(g.intersection(CITY))
CITY_B3 = CITY.buffer(0.0003, 4)
CITY_B5 = CITY.buffer(0.0005, 4)
CITY_B20 = CITY.buffer(0.002, 4)
_prep = {}


def clip(line, area):
    """The line inside area (None if none): whole lines inside skip the costly intersection."""
    p = _prep.setdefault(id(area), (prep(area), prep(area.boundary)))
    if not p[0].intersects(line): return None
    if not p[1].intersects(line): return line
    g = line.intersection(area)
    return None if g.is_empty else g
dump('boroughs', [feat(g, {'name': n, 'info': BORO_INFO[n], 'lp': label_pt(g)}) for n, g in sorted(boroughs.items())])
print('boroughs', sorted(boroughs))

# ---------- 2020 NTAs (the finer layer; also names the joint interest areas) ----------
ntas = []
for f in load('ntas.geojson')['features']:
    p = f['properties']
    g = inside(shape(f['geometry']).buffer(0))
    if g.is_empty: continue
    ntas.append((prop(p, 'ntaname', 'NTAName'), prop(p, 'nta2020', 'NTA2020'), str(prop(p, 'ntatype', 'NTAType') or '0'), g))
dump('ntas', [feat(g, {'name': n, 'code': c, 'kind': 'res' if t == '0' else 'other', 'lp': label_pt(g)}) for n, c, t, g in sorted(ntas, key=lambda x: x[1])])

# ---------- Units: community districts ----------
units, park_units = [], 0
for f in load('community_districts.geojson')['features']:
    code = int(float(prop(f['properties'], 'boro_cd', 'BoroCD')))
    g = inside(shape(f['geometry']).buffer(0))
    if g.is_empty: continue
    b, n = BORO[str(code)[0]], code % 100
    if code in CD_NAMES:
        p = {'name': CD_NAMES[code], 'code': code, 'label': '%s %d' % (b, n), 'boro': b}
        if code in CD_INFO: p['info'] = CD_INFO[code]
    else:   # a joint interest area: named after the NTA covering most of it (Central Park, JFK Airport...)
        best = max(ntas, key=lambda x: x[3].intersection(g).area)
        p = {'name': best[0], 'code': code, 'label': '%s %d' % (b, n), 'boro': b,
             'park': 'a park or airport, not one of the 59 community districts'}
        park_units += 1
    p['lp'] = label_pt(g)
    units.append(feat(g, p))
units.sort(key=lambda f: f['properties']['code'])
dump('districts', units)
print('community districts', len(units) - park_units, '· joint interest areas', park_units, [f['properties']['name'] for f in units if 'park' in f['properties']])

# ---------- Base: the city, the region's municipalities, land beyond ----------
counties = {f['properties']['GEOID']: (f['properties'], shape(f['geometry']).buffer(0)) for f in load('counties.geojson')['features']}
county_label = lambda gid: counties[gid][0].get('NAMELSAD', counties[gid][0]['NAME']) + ', ' + ST[gid[:2]]
REGION = unary_union([counties[c][1] for c in CORE if c in counties])
missing = [c for c in CORE if c not in counties]
if missing: print('  counties not in the Census file:', missing)
STATES = unary_union([shape(f['geometry']).buffer(0) for f in load('states.geojson')['features']]).intersection(FRAME)
# Water (raw/water.geojson, fetch_water.py): the Census boundaries run to mid-river, so the Hudson, the Harlem, the
# Hackensack and the bays and lakes beyond would be drawn as land. Cut out of everything the base draws; small ponds
# are left as land (over 1 km² in the city and the region's counties, over 8 km² beyond).
WATER = None
if os.path.exists(R + 'water.geojson'):
    parts = [g for g in (shape(f['geometry']).buffer(0) for f in load('water.geojson')['features'])
             if g.area * KM2 > (1.0 if g.intersects(REGION) or g.intersects(CITY) else 8.0)]
    WATER = unary_union(parts).buffer(0)
    print('water areas cut from the base', len(parts))
wet = lambda g: polys(g.difference(WATER)) if WATER is not None else g
base = [feat(wet(CITY), {'kind': 'city', 'name': 'City of New York'})]
cutout = CITY.buffer(0.0003)
towns = []
for f in load('cousubs.geojson')['features']:
    p = f['properties']
    gid = p['STATEFP'] + p['COUNTYFP']
    if gid in CITY_COUNTIES or gid not in CORE: continue
    if p.get('NAME', '').startswith('County subdivisions not defined') or p.get('COUSUBFP') == '00000': continue
    g = wet(polys(shape(f['geometry']).buffer(0).difference(cutout).intersection(counties[gid][1])))
    if g.is_empty or g.area * KM2 < 0.05: continue
    nm = p.get('NAMELSAD') or p['NAME']
    nm = re.sub(r' (city|town|village|CDP|borough|township)$', '', nm)
    towns.append((nm, g, gid))
# New Jersey has hundreds of small boroughs: name only the bigger towns and a few everyone knows until zoom 12.
ALWAYS = {'Hoboken', 'Weehawken', 'Fort Lee', 'Union City', 'Jersey City', 'Newark', 'Bayonne', 'Secaucus', 'Elizabeth', 'Paterson',
          'Yonkers', 'New Rochelle', 'Mount Vernon', 'White Plains', 'Long Beach', 'Hempstead', 'Stamford', 'Greenwich', 'New Haven',
          'Montclair', 'Princeton', 'Trenton', 'Morristown', 'Hackensack', 'Edgewater', 'North Bergen', 'Kearny', 'Rye', 'Scarsdale'}
by_name = Counter(n for n, _, _ in towns)
for n, g, gid in towns:
    p = {'kind': 'neighbour', 'name': n, 'region': county_label(gid), 'lp': label_pt(g)}
    if g.area * KM2 < 25 and n not in ALWAYS: p['minor'] = True
    base.append(feat(g, p))
outside = wet(polys(STATES.difference(REGION.buffer(0.0005)).difference(cutout)))
base.insert(0, feat(outside, {'kind': 'outside', 'name': ''}))
dump('base', base)
dump('region_areas', [feat(polys(counties[c][1]), {'region': county_label(c)}) for c in CORE if c in counties])
write('regions', [{'type': 'Feature', 'properties': {'name': n}, 'geometry': {'type': 'Point', 'coordinates': c}} for n, c in [
    ('Pennsylvania', [-75.45, 40.6]), ('Long Island Sound', [-73.2, 41.05]), ('Atlantic Ocean', [-73.6, 40.38]),
    ('Sussex County, NJ', [-74.7, 41.15]), ('Ulster County, NY', [-74.25, 41.85]), ('Ocean County, NJ', [-74.25, 39.95])]])
print('towns', len(towns), Counter(gid[:2] for _, _, gid in towns))

# ---------- Representation (inside the city) ----------
def districts(fname, keys, props):
    out = []
    for f in load(fname)['features']:
        if not f.get('geometry'): continue
        g = inside(shape(f['geometry']).buffer(0))
        if g.is_empty or g.area * KM2 < 0.05: continue
        num = int(float(prop(f['properties'], *keys)))
        out.append(feat(g, dict(props(num), num=num, lp=label_pt(g))))
    out.sort(key=lambda f: f['properties']['num'])
    return out

dump('council', districts('council.geojson', ['coundist', 'coun_dist', 'CounDist'], lambda n: {}))
dump('assembly', districts('assembly.geojson', ['assembly_district', 'assem_dist', 'AssemDist'], lambda n: {}))
dump('senate', districts('senate.geojson', ['st_sen_dist', 'stsendist', 'StSenDist'], lambda n: {}))
dump('congress', districts('congress.geojson', ['cong_dist', 'CongDist'], lambda n: {}))
school = districts('school_districts.geojson', ['schooldist', 'SchoolDist'], lambda n: {'board': 'csd', 'name': 'District %d' % n})
dump('school', school)

# ---------- Business improvement districts (SBS) ----------
bids = []
for f in load('bids.geojson')['features']:
    p = f['properties']
    n = prop(p, 'f_all_bi_2', 'bid_name', 'bid', 'name', 'BID')
    if not n or not f.get('geometry'): continue
    n = re.sub(r'(?i)\s*(business improvement district|\bBID)\s*$', '', str(n)).strip()
    g = inside(shape(f['geometry']).buffer(0))
    if not g.is_empty: bids.append(feat(g, {'name': n, 'lp': label_pt(g)}))
dump('bids', sorted(bids, key=lambda f: f['properties']['name']))
print('BIDs', len(bids), '· fields', sorted(load('bids.geojson')['features'][0]['properties']) if load('bids.geojson')['features'] else None)

# ---------- LPC historic districts (current, designated; extensions join their district) ----------
by = defaultdict(list); since = {}
for f in load('historic_districts.geojson')['features']:
    p = f['properties']
    if str(p.get('current_', 'Yes')).lower() not in ('yes', 'true', '1') or not f.get('geometry'): continue
    if 'DESIGNATED' not in str(p.get('status_of_', 'DESIGNATED')).upper(): continue
    n = re.sub(r'\s+(Extension|Ext\.?)(\s+\w+)?$', '', p['area_name'].strip())
    n = re.sub(r'\s+Historic District$', '', n)
    by[n].append(geo(f))
    y = str(p.get('desdate') or '')[:4]
    if y.isdigit(): since[n] = min(since.get(n, y), y)
heritage = []
for n, gs in sorted(by.items()):
    g = inside(unary_union(gs).buffer(0))
    if not g.is_empty: heritage.append(feat(g, {'name': n, 'since': since.get(n), 'lp': label_pt(g)}))
dump('heritage', heritage)
print('historic districts', len(heritage))

# ---------- Known-as names: curated, moved to OpenStreetMap's place point when one is close ----------
osm_places = defaultdict(list)
for el in load('osm_places.json')['elements']:
    n = el.get('tags', {}).get('name'); c = (el.get('lon') or el.get('center', {}).get('lon'), el.get('lat') or el.get('center', {}).get('lat'))
    if n and c[0]: osm_places[n].append(c)
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
    if re.search(r'(?i)\b(expressway|parkway|thruway|drive|highway|bridge|tunnel|ramp|exit)\b', t['name']) and street_key(t['name']) not in MAJOR_STREETS: continue
    key = street_key(t['name'])
    g = clip(way_line(w), CITY_B3)
    if g is None: continue
    segs[(key, 'major' if key in MAJOR_STREETS else 'minor')].append(g)
streets = []
for (name, cls), gs in segs.items():
    m = merged(gs, 0.15)
    if m is None or m.length * KM < (0.6 if cls == 'major' else 1.2): continue
    streets.append(feat(m, {'name': name, 'cls': cls, 'len': round(m.length * 1000, 1)}))
streets.sort(key=lambda f: (f['properties']['cls'] != 'major', -f['properties']['len']))
dump('streets', streets)

# Manhattan's East and West streets, side kept ("E 42nd St"), for How addresses work (engine/addresses.py, with
# Fifth Avenue from the main streets as the divide). Written straight to docs: the address layer reads it.
if os.path.exists(R + 'osm_manhattan_ew.json'):
    MAN = boroughs['Manhattan'].buffer(0.0003)
    ew = defaultdict(list)
    for w in load('osm_manhattan_ew.json')['elements']:
        if len(w.get('geometry', [])) < 2: continue
        n = street_name(w['tags']['name'])
        g = clip(way_line(w), MAN)
        if g is not None and re.match(r'^[EW] ', n): ew[n].append(g)
    out_ew = []
    for n, gs in sorted(ew.items()):
        m = merged(gs, 0.05)
        if m is not None: out_ew.append(feat(m, {'name': n}))
    write('streets_ew', out_ew)
    print('Manhattan East/West streets', len(out_ew))
print('main streets missing from the data:', sorted(MAJOR_STREETS - {n for n, c in segs if c == 'major'}))

# ---------- Highways: expressways and parkways inside the city by name; across the region by route ----------
def hw_name(t):
    n = t.get('name') or ''
    for frag, label, route in HIGHWAYS:
        if frag.lower() in n.lower(): return label, route
    return None


def route_of(tags):
    for r in (tags.get('ref') or '').split(';'):
        r = r.strip()
        m = re.fullmatch(r'(I|US|NY|NJ|CT|GSP|NJTP|TPK|CR)[ -]?(\w+)', r)
        if m: return m.group(1), m.group(2)
    n = tags.get('name') or ''
    if 'Garden State Parkway' in n: return 'GSP', 'GSP'
    if 'New Jersey Turnpike' in n: return 'NJTP', 'NJ Tpk'
    return None


inner = CITY.buffer(-0.0004, 4)
INNER_P = prep(inner)
in_city, outer = defaultdict(list), defaultdict(list)
for w in load('osm_highways.json')['elements']:
    t = w['tags']
    if len(w.get('geometry', [])) < 2 or 'link' in t.get('highway', ''): continue
    line = way_line(w)
    hn = hw_name(t)
    if hn:
        g = clip(line, CITY_B5)
        if g is not None: in_city[hn].append(g)
    r = route_of(t)
    if r and (t['highway'] == 'motorway' or r[0] in ('I', 'GSP', 'NJTP')):
        if not INNER_P.contains(line):
            outer[r].append(line)
hw = []
by_label = defaultdict(list)
for (label, route), gs in in_city.items(): by_label[(label, route)] += gs
for (label, route), gs in by_label.items():
    m = merged(gs, 0.3)
    if m is None: continue
    kind = 'interstate' if route in ('278', '495', '678', '95', '87', '295', '478', '78') else 'provincial' if route.isdigit() else 'city'
    hw.append(feat(m, {'route': route, 'name': label + (' (I-%s)' % route if kind == 'interstate' and 'I-' not in label else ''), 'kind': kind}))
dump('highways', hw)
REGION_BOX = REGION.buffer(0.01)
gh, shields = [], []
for (pre, num), gs in outer.items():
    m = merged(gs, 1)
    if m is None: continue
    toll = pre in ('GSP', 'NJTP')
    big = pre in ('I', 'GSP', 'NJTP')
    route = num if pre in ('I', 'US', 'NY', 'NJ', 'CT') else num
    gh.append(feat(m, {'route': route, 'name': {'I': 'I-' + num, 'US': 'US ' + num, 'GSP': 'Garden State Parkway', 'NJTP': 'New Jersey Turnpike'}.get(pre, pre + ' ' + num), 'toll': toll}))
    if not big: continue
    for p in getattr(m, 'geoms', [m]):
        km = p.length * KM
        if km < 6: continue
        for d in [x for x in range(6, int(km) - 2, 30)] or [km / 2]:
            pt = p.interpolate(d / KM)
            if not REGION_BOX.contains(pt) or CITY.buffer(0.01).contains(pt): continue
            if any(s['properties']['route'] == route and Point(s['geometry']['coordinates']).distance(pt) * KM < 18 for s in shields): continue
            shields.append({'type': 'Feature', 'properties': {'route': route, 'toll': toll},
                            'geometry': {'type': 'Point', 'coordinates': [round(pt.x, 5), round(pt.y, 5)]}})
dump('region_highways', gh)
write('region_shields', shields)
print('city highways', sorted(l for l, _ in by_label), '· region routes', len(outer), len(shields), 'shields')

# ---------- The subway (and Staten Island Railway), from MTA GTFS ----------
mta = load('mta_rail.json')
TRUNK = {'A': 'ace', 'C': 'ace', 'E': 'ace', 'B': 'bdfm', 'D': 'bdfm', 'F': 'bdfm', 'FX': 'bdfm', 'M': 'bdfm', 'G': 'g', 'J': 'jz', 'Z': 'jz',
         'L': 'l', 'N': 'nqrw', 'Q': 'nqrw', 'R': 'nqrw', 'W': 'nqrw', '1': '123', '2': '123', '3': '123', '4': '456', '5': '456', '6': '456',
         '6X': '456', '7': '7', '7X': '7', 'GS': 's', 'FS': 's', 'H': 's', 'S': 's', 'SI': 'sir', 'SIR': 'sir'}
TRUNK_NAME = {'ace': 'A C E', 'bdfm': 'B D F M', 'g': 'G', 'jz': 'J Z', 'l': 'L', 'nqrw': 'N Q R W', '123': '1 2 3', '456': '4 5 6', '7': '7',
              's': 'Shuttles (S)', 'sir': 'Staten Island Railway'}
SERVICE = lambda r: {'GS': 'S', 'FS': 'S', 'H': 'S', 'FX': 'F', '6X': '6', '7X': '7', 'SI': 'SIR'}.get(r, r)
segs = defaultdict(list); route_trunk = {}
for rid, r in mta['subway']['routes'].items():
    tr = TRUNK.get(r['short'] or rid) or TRUNK.get(rid)
    if not tr or not r['counts']: continue
    route_trunk[rid] = tr
    top = max(r['counts'].values())
    segs[tr] += [LineString(r['shapes'][s]) for s, c in r['counts'].items() if c >= top * 0.1 and len(r['shapes'][s]) > 1]
ORDER = ['sir', 's', 'g', 'l', 'jz', '7', 'nqrw', 'bdfm', 'ace', '456', '123']
sub = []
for tr in ORDER:
    if not segs[tr]: continue
    m = merged(segs[tr], 0.05)
    if m is not None: sub.append(feat(m, {'line': tr, 'name': TRUNK_NAME[tr]}))
dump('subway_lines', sub)
SVC_ORDER = ['1', '2', '3', '4', '5', '6', '7', 'A', 'C', 'E', 'B', 'D', 'F', 'M', 'G', 'J', 'Z', 'L', 'N', 'Q', 'R', 'W', 'S', 'SIR']
stations = {}
for s in mta['subway']['stations']:
    svcs = {SERVICE(mta['subway']['routes'][x]['short'] or x) for x in s['routes'] if x in route_trunk}
    if not svcs: continue
    nm = s['name'].replace(' - ', '–')
    # Complexes share a name across platforms on different lines: join stops of one name within 250 m.
    key = next((k for k, st in stations.items() if st['name'] == nm and dist_km(st['pts'][0], (s['lon'], s['lat'])) < 0.25), None) or (nm, s['id'])
    st = stations.setdefault(key, {'name': nm, 'pts': [], 'lines': set()})
    st['pts'].append((s['lon'], s['lat'])); st['lines'] |= svcs
stns = [{'type': 'Feature', 'properties': {'name': st['name'], 'lines': sorted(st['lines'], key=lambda l: SVC_ORDER.index(l) if l in SVC_ORDER else 99)},
         'geometry': {'type': 'Point', 'coordinates': [round(sum(p[0] for p in st['pts']) / len(st['pts']), 5), round(sum(p[1] for p in st['pts']) / len(st['pts']), 5)]}}
        for st in stations.values()]
write('subway_stations', stns)
print('subway trunks', [f['properties']['name'] for f in sub], '· stations', len(stns))

# ---------- Commuter rail: LIRR and Metro-North (GTFS), NJ Transit and PATH (OpenStreetMap) ----------
HUBS = {'Penn Station', 'Grand Central', 'Grand Central Madison', 'Atlantic Terminal', 'Jamaica', 'Hoboken', 'Newark Penn Station',
        'Secaucus Junction', 'Harlem-125 St', 'Long Island City', 'World Trade Center', '33rd Street', 'Newark Penn'}
rail, rail_in, rstations = [], [], {}


def add_rail(g, p):
    rail.append(feat(g, p))
    gi = clip(g, CITY_B20)
    if gi is not None: rail_in.append(feat(gi, p))


for key, agency in [('lirr', 'LIRR'), ('mnr', 'Metro-North')]:
    for rid, r in mta[key]['routes'].items():
        name = (r['long'] or r['short']).replace(' Branch', '').replace(' Service', '').strip()
        if not r['counts'] or name in ('City Terminal Zone',): continue
        top = max(r['counts'].values())
        m = merged([LineString(r['shapes'][s]) for s, c in r['counts'].items() if c >= top * 0.1 and len(r['shapes'][s]) > 1], 0.2)
        if m is None: continue
        add_rail(m, {'line': agency.lower().replace('-', '') + '-' + re.sub(r'\W+', '', name.lower()), 'name': '%s %s' % (agency, name) + (' Branch' if key == 'lirr' else ' Line'),
                     'color': '#' + (r['color'] or '6E6E6E'), 'offset': 0, 'to': name, 'agency': agency})
    names = {rid: (r['long'] or r['short']).replace(' Branch', '').strip() for rid, r in mta[key]['routes'].items()}
    for s in mta[key]['stations']:
        nm = s['name'].replace('Penn Station', 'Penn Station').strip()
        st = rstations.setdefault(nm.lower(), {'name': nm, 'pts': [], 'lines': set()})
        st['pts'].append((s['lon'], s['lat'])); st['lines'] |= {'%s %s' % (agency, names[x]) for x in s['routes'] if x in names and names[x] != 'City Terminal Zone'}

NJT_COLOR = {'Northeast Corridor': '#EF3E42', 'North Jersey Coast': '#00A4E4', 'Morris & Essex': '#00A94F', 'Montclair-Boonton': '#E66B5B',
             'Raritan Valley': '#FAA634', 'Main': '#FFCF01', 'Bergen County': '#C4D600', 'Pascack Valley': '#8E258D', 'Port Jervis': '#FF7900',
             'Gladstone': '#A2D5AE', 'Atlantic City': '#005DAA', 'Hudson-Bergen Light Rail': '#0083C1', 'Newark Light Rail': '#F7941D', 'River Line': '#00A3A7'}
seen = set()
for el in load('osm_rail.json')['elements']:
    t = el.get('tags', {})
    if el['type'] != 'relation': continue
    net = (t.get('network') or '') + ' ' + (t.get('operator') or '')
    nm = t.get('name') or t.get('ref') or ''
    if 'PATH' in net or 'Port Authority Trans-Hudson' in net:
        agency, line, color = 'PATH', 'PATH', '#' + (t.get('colour') or '004D6F').lstrip('#')
    elif re.search(r'(?i)airtrain', net + nm):
        agency, line, color = 'AirTrain', 'AirTrain JFK' if 'JFK' in net + nm else 'AirTrain Newark', '#6E6E6E'
    elif re.search(r'(?i)nj ?transit', net):
        agency = 'NJ Transit'
        norm = lambda x: x.lower().replace('&', 'and').replace('–', '-').replace('morristown', 'morris and essex')
        line = next((k for k in NJT_COLOR if norm(k) in norm(nm)), None)
        if not line: continue
        color = NJT_COLOR[line]
    else:
        continue
    key = (agency, line, nm if agency == 'PATH' else '')
    ways = [LineString([(round(p['lon'], 5), round(p['lat'], 5)) for p in m['geometry']]) for m in el.get('members', [])
            if m.get('type') == 'way' and len(m.get('geometry') or []) > 1 and m.get('role', '') in ('', 'forward', 'backward', 'main')]
    if not ways: continue
    g = merged(ways, 0.2)
    if g is None: continue
    lid = re.sub(r'\W+', '', (agency + line).lower())
    if (lid, nm) in seen: continue
    seen.add((lid, nm))
    add_rail(g, {'line': lid, 'name': (line if agency in ('PATH', 'AirTrain') or 'Light Rail' in line or line == 'River Line' else 'NJ Transit ' + line + ' Line'),
                 'color': color, 'offset': 0, 'to': nm, 'agency': agency})
# One feature per line: OpenStreetMap has a relation per direction and branch.
def one_per_line(feats):
    by = defaultdict(list); props = {}
    for f in feats:
        k = f['properties']['name']; by[k].append(shape(f['geometry'])); props.setdefault(k, f['properties'])
    out = []
    for k, gs in by.items():
        m = merged(gs, 0.1)
        if m is not None: out.append(feat(m, props[k]))
    return out
rail, rail_in = one_per_line(rail), one_per_line(rail_in)
dump('rail_lines', rail); dump('rail_lines_inner', rail_in)
for el in load('osm_stations.json')['elements']:
    t = el.get('tags', {})
    net = (t.get('network') or '') + ' ' + (t.get('operator') or '')
    if not re.search(r'(?i)nj ?transit|PATH|Port Authority', net) or not t.get('name') or 'lon' not in el: continue
    if t.get('station') == 'subway' and 'PATH' not in net: continue
    nm = t['name']
    st = rstations.setdefault(nm.lower(), {'name': nm, 'pts': [], 'lines': set()})
    st['pts'].append((el['lon'], el['lat'])); st['lines'].add('PATH' if 'PATH' in net or 'Port Authority' in net else 'NJ Transit')
write('rail_stations', [{'type': 'Feature', 'properties': {'name': st['name'], 'lines': sorted(st['lines']), **({'hub': True} if st['name'] in HUBS else {})},
                         'geometry': {'type': 'Point', 'coordinates': [round(sum(p[0] for p in st['pts']) / len(st['pts']), 5), round(sum(p[1] for p in st['pts']) / len(st['pts']), 5)]}}
                        for st in rstations.values() if st['lines']])
print('rail lines', sorted(f['properties']['name'] for f in rail), '· stations', len(rstations))

print('units', len(units), '· NTAs', len(ntas), '· known-as', len(known), '· towns', len(towns), '· streets', len(streets),
      sum(f['properties']['cls'] == 'major' for f in streets), 'major · BIDs', len(bids), '· historic districts', len(heritage))
