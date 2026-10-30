"""Build the San Francisco map's layer files from cities/sf/raw/ (see SOURCES.md).
Polygons and lines go to tmp/ and are simplified by mapshaper in run.sh; points go straight to
docs/sf/data/. Output shapes match the other cities', so the shared engine draws all of them.

Land and water: MTC's city and county boundaries are clipped to the shoreline, so the land is the union of the
nine Bay Area counties (and the Census Bureau's shoreline-clipped counties and states beyond them); everything
else in the frame is water. San Francisco is MTC's "San Francisco" city cut to the mainland, Treasure Island and
Yerba Buena Island: the Farallon Islands (also in the City and County) are left off the map.

Units: the City's 41 Analysis Neighborhoods (Census tracts grouped by Planning). Golden Gate Park, McLaren Park and
Lincoln Park are among them; they become park units with no profile. SF Find's 117 neighbourhoods are a second,
finer layer. The "parts of the city" fill groups the 41 (names.py SIDES)."""
import json, math, os, re, sys
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping, Point, LineString, MultiLineString, box
from shapely.ops import unary_union, linemerge, polylabel
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from names import SIDES, SIDE_INFO, KNOWN_AS, MAJOR_STREETS, HIGHWAYS, street_key

R = os.path.join(HERE, 'raw') + '/'
OUT = os.path.join(HERE, '..', '..', 'docs', 'sf', 'data') + '/'
TMP = os.path.join(HERE, 'tmp') + '/'
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
load = lambda f: json.load(open(R + f))
fc = lambda feats: {'type': 'FeatureCollection', 'features': feats}
feat = lambda g, p: {'type': 'Feature', 'properties': p, 'geometry': mapping(g)}
KM = 88.0   # km per degree of longitude at San Francisco's latitude (111.2 per degree of latitude)
KM2 = KM * 111.2
dist_km = lambda a, b: math.hypot((a[0] - b[0]) * KM, (a[1] - b[1]) * 111.2)
FRAME = box(-124.4, 36.3, -120.4, 39.5)
CITY_BOX = box(-122.53, 37.70, -122.35, 37.84)
PARKS = {'Golden Gate Park', 'McLaren Park', 'Lincoln Park'}


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
prop = lambda p, *keys: next((p[k] for k in keys if p.get(k) not in (None, '')), None)
pkey = lambda p, *frags: next((k for k in p if any(f in k.lower() for f in frags)), None)
fields = lambda f: sorted(load(f)['features'][0]['properties']) if load(f)['features'] else []

# ---------- The city (MTC's shoreline-clipped San Francisco, without the Farallones) ----------
cities = load('cities.geojson')['features']
print('MTC city fields', fields('cities.geojson'))
cname = lambda p: str(prop(p, 'jurname', 'name', 'NAME') or '').strip()
CO_FIPS = {f['properties']['fipco']: f['properties']['coname'] for f in load('bay_counties.geojson')['features']}
ccounty = lambda p: CO_FIPS.get(p.get('fipco'), '')
sf_city = [shape(f['geometry']).buffer(0) for f in cities if cname(f['properties']).lower() in ('san francisco', 'city of san francisco')]
assert sf_city, 'San Francisco not in MTC cities'
CITY = polys(unary_union(sf_city).intersection(CITY_BOX))
inside = lambda g: polys(g.intersection(CITY))
CITY_B3 = CITY.buffer(0.0003, 4); CITY_B5 = CITY.buffer(0.0005, 4); CITY_B20 = CITY.buffer(0.002, 4)
_prep = {}


def clip(line, area):
    p = _prep.setdefault(id(area), (prep(area), prep(area.boundary)))
    if not p[0].intersects(line): return None
    if not p[1].intersects(line): return line
    g = line.intersection(area)
    return None if g.is_empty else g


print('city area km²', round(CITY.area * KM2, 1))

# ---------- Units: the 41 Analysis Neighborhoods, and the five parts of the city ----------
ans = []
if os.path.exists(R + 'analysis_neighborhoods.geojson'):
    for f in load('analysis_neighborhoods.geojson')['features']:
        p = f['properties']
        n = prop(p, 'nhood', 'NHOOD', 'name', 'neighborhood')
        g = inside(shape(f['geometry']).buffer(0))
        if not g.is_empty: ans.append((n.strip(), g))
else:   # rebuilt the City's way: 2020 tracts dissolved by DataSF's crosswalk (fetch.py tracts_an)
    xw = load('an_tracts.json')
    print('  41 rebuilt from tracts · crosswalk fields', sorted(xw[0]))
    gk = next(k for k in xw[0] if 'geoid' in k.lower() or 'tract' in k.lower())
    nk = next(k for k in xw[0] if 'nhood' in k.lower() or 'neighborhood' in k.lower())
    t2n = {str(r[gk])[-11:]: r[nk].strip() for r in xw if r.get(gk) and r.get(nk)}
    by = defaultdict(list)
    for f in load('tracts_2020.geojson')['features']:
        n = t2n.get(f['properties']['GEOID'])
        if n: by[n].append(shape(f['geometry']).buffer(0))
    ans = [(n, inside(unary_union(gs).buffer(0.00001).buffer(-0.00001))) for n, gs in by.items()]
    ans = [(n, g) for n, g in ans if not g.is_empty]
ans.sort()
by_name = {n: g for n, g in ans}
assert len(by_name) == 41, (len(by_name), sorted(by_name))
assert sorted(by_name) == sorted(n for v in SIDES.values() for n in v), set(by_name) ^ {n for v in SIDES.values() for n in v}
units = []
for i, (n, g) in enumerate(ans, 1):
    p = {'name': n, 'code': i, 'lp': label_pt(g)}
    if n in PARKS: p['park'] = 'a park, counted as one of the 41 for planning but with few residents'
    units.append(feat(g, p))
dump('neighbourhoods', units)
side_geom = {s: unary_union([by_name[n] for n in ns]) for s, ns in SIDES.items()}
rest = CITY.difference(unary_union(list(side_geom.values())).buffer(0.00001))
pieces = [p for p in getattr(rest, 'geoms', [rest]) if p.geom_type == 'Polygon' and p.area > 1e-9]
for p in pieces:
    s = min(side_geom, key=lambda s: side_geom[s].distance(p))
    side_geom[s] = side_geom[s].union(p)
print('city land outside the 41:', len(pieces), 'pieces,', round(sum(p.area for p in pieces) * KM2, 2), 'km²')
sides = [feat(polys(g.buffer(0.00002).buffer(-0.00002)), {'name': s, 'info': SIDE_INFO[s], 'lp': label_pt(g)}) for s, g in side_geom.items()]
dump('sides', sides)

# ---------- SF Find neighbourhoods (117): the finer layer ----------
finds = []
for f in load('sffind.geojson')['features']:
    n = prop(f['properties'], 'name', 'NAME', 'nhood')
    g = inside(shape(f['geometry']).buffer(0))
    if n and not g.is_empty: finds.append(feat(g, {'name': n.strip(), 'lp': label_pt(g)}))
dump('sffind', sorted(finds, key=lambda f: f['properties']['name']))
print('SF Find neighbourhoods', len(finds))

# ---------- Base: the city, the region's 100 other cities and towns, unincorporated land, land beyond ----------
counties_bay = {}
for f in load('bay_counties.geojson')['features']:
    p = f['properties']
    n = str(prop(p, 'coname', 'county', 'COUNTY', 'name', 'NAME', 'countyname') or '').strip()
    n = re.sub(r'(?i)\s+county$', '', n)
    counties_bay[n] = shape(f['geometry']).buffer(0)
print('Bay Area counties', sorted(counties_bay), '· fields', fields('bay_counties.geojson'))
county_of = lambda g: max(counties_bay, key=lambda c: counties_bay[c].intersection(g).area)
county_label = lambda c: 'San Francisco' if c == 'San Francisco' else c + ' County'
REGION = unary_union(list(counties_bay.values()))
ca = [shape(f['geometry']).buffer(0) for f in load('counties.geojson')['features']]
STATES = [shape(f['geometry']).buffer(0) for f in load('states.geojson')['features'] if f['properties'].get('STUSPS') != 'CA']
base = [feat(CITY, {'kind': 'city', 'name': 'City of San Francisco'})]
cutout = CITY.buffer(0.0003)
ALWAYS = {'Oakland', 'San Jose', 'Berkeley', 'Daly City', 'Sausalito', 'Palo Alto', 'Fremont', 'Santa Rosa', 'Napa', 'Vallejo',
          'Walnut Creek', 'San Mateo', 'Redwood City', 'Mountain View', 'Sunnyvale', 'Santa Clara', 'Richmond', 'Hayward', 'Concord',
          'San Rafael', 'Alameda', 'South San Francisco', 'Emeryville', 'Petaluma', 'Fairfield', 'Livermore', 'Pleasanton', 'Half Moon Bay'}
towns = []
for f in cities:
    p = f['properties']; n = cname(p)
    if n.lower() == 'san francisco': continue
    g = polys(shape(f['geometry']).buffer(0).difference(cutout))
    if g.is_empty: continue
    towns.append((n, g, ccounty(p) and re.sub(r'(?i)\s+county$', '', ccounty(p)) or county_of(g)))
for n, g, c in towns:
    pr = {'kind': 'neighbour', 'name': n, 'region': county_label(c), 'lp': label_pt(g)}
    if g.area * KM2 < 20 and n not in ALWAYS: pr['minor'] = True
    base.append(feat(g, pr))
TOWNS = unary_union([g for _, g, _ in towns] + [CITY]).buffer(0.0002)
for c, cg in sorted(counties_bay.items()):
    if c == 'San Francisco': continue   # the Farallones: left off
    u = polys(cg.difference(TOWNS))
    u = unary_union([p for p in getattr(u, 'geoms', [u]) if p.area * KM2 > 0.5]) if not u.is_empty else u
    if u.is_empty: continue
    base.append(feat(u, {'kind': 'neighbour', 'name': 'Unincorporated ' + c + ' County', 'region': county_label(c),
                         'lp': label_pt(u), 'rest': True, 'minor': True}))
land = unary_union(ca + STATES).intersection(FRAME)
outside = polys(land.difference(REGION.buffer(0.0005)).difference(cutout))
base.insert(0, feat(outside, {'kind': 'outside', 'name': ''}))
dump('base', base)
dump('region_areas', [feat(polys(g), {'region': county_label(c)}) for c, g in sorted(counties_bay.items()) if c != 'San Francisco'])
write('regions', [{'type': 'Feature', 'properties': {'name': n}, 'geometry': {'type': 'Point', 'coordinates': c}} for n, c in [
    ('Pacific Ocean', [-122.85, 37.55]), ('Santa Cruz County', [-122.05, 37.06]), ('Sacramento', [-121.5, 38.55]),
    ('San Joaquin County', [-121.3, 37.95]), ('Lake County', [-122.75, 38.95]), ('Mendocino County', [-123.4, 38.95]),
    ('Merced & Stanislaus', [-121.0, 37.4])]])
print('cities and towns', len(towns), Counter(c for _, _, c in towns))

# ---------- Representation (inside the city) ----------
def districts(fname, keys, props, frag=None):
    out = []
    feats = load(fname)['features']
    if feats: print(' ', fname, 'fields', sorted(feats[0]['properties']))
    for f in feats:
        if not f.get('geometry'): continue
        g = inside(shape(f['geometry']).buffer(0))
        if g.is_empty or g.area * KM2 < 0.05: continue
        p = f['properties']
        v = prop(p, *keys)
        if v is None and frag: v = p.get(pkey(p, *frag))
        m = re.search(r'\d+(\.\d+)?', str(v))
        num = int(float(m.group(0))) if m else 0
        out.append(feat(g, dict(props(num), num=num, lp=label_pt(g))))
    out.sort(key=lambda f: f['properties']['num'])
    return out


dump('supervisors', districts('supervisors.geojson', ['sup_dist_num', 'sup_dist'], lambda n: {}))
dump('assembly', districts('assembly.geojson', ['SLDLST', 'sldlst'], lambda n: {}))
dump('senate', districts('senate.geojson', ['SLDUST', 'sldust'], lambda n: {}))
dump('congress', districts('congress.geojson', ['DISTRICT', 'District', 'district', 'CD', 'cd', 'ID', 'NAME', 'Name'], lambda n: {}, ['dist']))

# ---------- Historic districts (Planning Code Articles 10 and 11) ----------
hd = load('historic_districts.geojson')['features']
print('historic district fields', fields('historic_districts.geojson'))
heritage, kinds = [], Counter()
for f in hd:
    p = f['properties']
    if not f.get('geometry'): continue
    kinds[(p.get('a10'), p.get('a11'))] += 1
    art = 'Article 10' if p.get('a10') == 'Listed' else 'Article 11' if p.get('a11') == 'Listed' else None
    if not art: continue
    n = str(prop(p, 'name_1', 'docname') or '').strip()
    n = re.sub(r'(?i)\s+(landmark|historic|conservation)\s+district$', '', n)
    g = inside(shape(f['geometry']).buffer(0))
    if n and not g.is_empty:
        heritage.append(feat(g, {'name': n, 'kind': 'Landmark district (Article 10)' if art == 'Article 10' else 'Conservation district (Article 11)', 'lp': label_pt(g)}))
dump('heritage', sorted(heritage, key=lambda f: f['properties']['name']))
print('historic districts kept', len(heritage), 'of', len(hd), '· by type', kinds.most_common(8))

# ---------- Cultural districts (the City's ten) ----------
cult = []
for f in load('cultural_districts.geojson')['features']:
    p = f['properties']
    n = str(prop(p, 'district_name', 'name', 'cultural_district', 'district') or '').strip()
    n = re.sub(r'(?i)\s+(and|&)?\s*cultural district$', '', n)
    n = {'African American Arts': 'African American Arts & Culture'}.get(n, n)
    g = inside(shape(f['geometry']).buffer(0))
    if n and not g.is_empty: cult.append(feat(g, {'name': n, 'lp': label_pt(g)}))
dump('cultural', sorted(cult, key=lambda f: f['properties']['name']))
print('cultural districts', [f['properties']['name'] for f in cult], '· fields', fields('cultural_districts.geojson'))

# ---------- Known-as names ----------
osm_places = defaultdict(list)
for el in load('osm_places.json')['elements'] + load('osm_landmarks.json')['elements']:
    n = el.get('tags', {}).get('name'); c = (el.get('lon') or el.get('center', {}).get('lon'), el.get('lat') or el.get('center', {}).get('lat'))
    if n and c[0]: osm_places[n].append(c)
known = []
for k in KNOWN_AS:
    lat, lon = k['at']
    cands = [c for c in osm_places.get(k['osm'], []) + osm_places.get(k['name'], []) if dist_km(c, (lon, lat)) < 1.0]
    pt = min(cands, key=lambda c: dist_km(c, (lon, lat))) if cands else (lon, lat)
    if not cands: print('  known-as from hand position:', k['name'])
    known.append({'type': 'Feature', 'properties': {'name': k['name'], 'kind': k['kind']},
                  'geometry': {'type': 'Point', 'coordinates': [round(pt[0], 5), round(pt[1], 5)]}})
write('knownas', known)

# ---------- Main streets ----------
segs = defaultdict(list)
for w in load('osm_streets.json')['elements']:
    t = w['tags']
    if len(w.get('geometry', [])) < 2: continue
    key = street_key(t['name'])
    if re.search(r'(?i)\b(freeway|bridge|tunnel|ramp|exit|on-ramp|off-ramp)\b', key): continue
    if t['highway'] == 'tertiary' and key not in MAJOR_STREETS and key != 'The Embarcadero': continue   # fetch_streets.py
    g = clip(way_line(w), CITY_B3)
    if g is None: continue
    segs[(key, 'major' if key in MAJOR_STREETS else 'minor')].append(g)
streets = []
for (name, cls), gs in segs.items():
    m = merged(gs, 0.15)
    if m is None or m.length * KM < (0.5 if cls == 'major' else 1.0): continue
    streets.append(feat(m, {'name': name, 'cls': cls, 'len': round(m.length * 1000, 1)}))
streets.sort(key=lambda f: (f['properties']['cls'] != 'major', -f['properties']['len']))
dump('streets', streets)
print('main streets missing from the data:', sorted(MAJOR_STREETS - {n for n, c in segs if c == 'major'}))

# ---------- Highways: freeways in the city by name or route; across the region by route ----------
def route_of(tags):
    for r in (tags.get('ref') or '').split(';'):
        m = re.fullmatch(r'(I|US|CA|SR)[ -]?(\d+)', r.strip())
        if m: return ('CA' if m.group(1) == 'SR' else m.group(1)), m.group(2)
    return None


def hw_name(t):
    n = t.get('name') or ''
    for frag, label, route in HIGHWAYS:
        if frag.lower() in n.lower(): return label, route
    r = route_of(t)
    if r: return {'I': 'I-', 'US': 'US ', 'CA': 'CA '}[r[0]] + r[1], r[1]
    return None


inner = CITY.buffer(-0.0004, 4)
INNER_P = prep(inner)
in_city, outer = defaultdict(list), defaultdict(list)
for w in load('osm_highways.json')['elements']:
    t = w['tags']
    if len(w.get('geometry', [])) < 2 or 'link' in t.get('highway', ''): continue
    line = way_line(w)
    if t['highway'] == 'motorway' or route_of(t):
        hn = hw_name(t)
        if hn:
            g = clip(line, CITY_B5)
            if g is not None: in_city[hn].append(g)
    r = route_of(t)
    if r and (t['highway'] == 'motorway' or r[0] in ('I', 'US')) and not INNER_P.contains(line):
        outer[r].append(line)
hw = []
for (label, route), gs in in_city.items():
    m = merged(gs, 0.2)
    if m is None: continue
    kind = 'interstate' if label.startswith('I-') or '(I-' in label or label.startswith('Bay Bridge') or route in ('80', '280', '380') else 'provincial'
    hw.append(feat(m, {'route': route, 'name': label, 'kind': kind}))
dump('highways', hw)
REGION_BOX = REGION.buffer(0.01)
gh, shields = [], []
for (pre, num), gs in outer.items():
    m = merged(gs, 1)
    if m is None: continue
    gh.append(feat(m, {'route': num, 'name': {'I': 'I-', 'US': 'US ', 'CA': 'CA '}[pre] + num, 'toll': False}))
    if pre == 'CA' and num not in ('1', '4', '17', '24', '85', '87', '92', '237', '238', '242', '580'): continue
    for p in getattr(m, 'geoms', [m]):
        km = p.length * KM
        if km < 6: continue
        for d in [x for x in range(6, int(km) - 2, 30)] or [km / 2]:
            pt = p.interpolate(d / KM)
            if not REGION_BOX.contains(pt) or CITY.buffer(0.01).contains(pt): continue
            if any(s['properties']['route'] == num and Point(s['geometry']['coordinates']).distance(pt) * KM < 18 for s in shields): continue
            shields.append({'type': 'Feature', 'properties': {'route': num, 'toll': False},
                            'geometry': {'type': 'Point', 'coordinates': [round(pt.x, 5), round(pt.y, 5)]}})
dump('region_highways', gh)
write('region_shields', shields)
print('city highways', sorted(l for l, _ in in_city), '· region routes', len(outer), len(shields), 'shields')

# ---------- BART, and Muni Metro, streetcars and cable cars (GTFS) ----------
gt = load('gtfs_rail.json')


def route_lines(r, share=0.1):
    if not r['counts']: return None
    top = max(r['counts'].values())
    return merged([LineString(r['shapes'][s]) for s, c in r['counts'].items() if c >= top * share and len(r['shapes'][s]) > 1], 0.05)


def stations_of(key, lines_of_route, rename=lambda n: n, near=0.15):
    st = {}
    for s in gt[key]['stations']:
        ls = {lines_of_route[x] for x in s['routes'] if x in lines_of_route}
        if not ls: continue
        nm = rename(s['name'])
        k = next((k for k, v in st.items() if v['name'] == nm and dist_km(v['pts'][0], (s['lon'], s['lat'])) < near), None) or (nm, s['id'])
        v = st.setdefault(k, {'name': nm, 'pts': [], 'lines': set()})
        v['pts'].append((s['lon'], s['lat'])); v['lines'] |= ls
    return st


pt_of = lambda v: [round(sum(p[0] for p in v['pts']) / len(v['pts']), 5), round(sum(p[1] for p in v['pts']) / len(v['pts']), 5)]
BART_COLOR = {'FFFF33': 'yellow', 'FFE800': 'yellow', 'FF9933': 'orange', 'F9A11B': 'orange', 'FF0000': 'red', 'ED1C24': 'red',
              '339933': 'green', '4DB848': 'green', '0099CC': 'blue', '00AEEF': 'blue', 'D5CFA3': 'beige', 'B0BEC7': 'beige'}
BART_NAME = {'yellow': 'Yellow', 'orange': 'Orange', 'red': 'Red', 'green': 'Green', 'blue': 'Blue', 'beige': 'Oakland Airport'}   # beige: the Grey Line connector


def bart_line(r):
    c = (r['color'] or '').upper()
    if c in BART_COLOR: return BART_COLOR[c]
    t = (r['short'] + ' ' + r['long']).lower()
    for k in ('yellow', 'orange', 'red', 'green', 'blue'):
        if t.startswith(k): return k
    return 'beige' if t.startswith('grey') or t.startswith('gray') or 'oakland int' in t else None


blines = defaultdict(list); bline_of = {}
for rid, r in gt['bart']['routes'].items():
    if r['type'] != '1': continue   # bus bridges
    l = bart_line(r)
    if not l: print('  BART route not placed', rid, r['short'], r['long'], r['color']); continue
    bline_of[rid] = BART_NAME[l]
    m = route_lines(r)
    if m is not None: blines[l].append(m)
bart = [feat(merged(gs, 0.05), {'line': l, 'name': 'BART ' + BART_NAME[l] + (' Line' if l != 'beige' else ' connector')}) for l, gs in blines.items()]
BORDER = ['beige', 'green', 'orange', 'blue', 'red', 'yellow']
dump('bart_lines', sorted(bart, key=lambda f: BORDER.index(f['properties']['line'])))
bst = stations_of('bart', bline_of, lambda n: re.sub(r'\s+(BART\s+)?Station$', '', n).replace(' / ', '/'), 0.3)
LORD = ['Yellow', 'Orange', 'Red', 'Green', 'Blue', 'Oakland Airport']
write('bart_stations', [{'type': 'Feature', 'properties': {'name': v['name'], 'lines': sorted(v['lines'], key=LORD.index)},
                         'geometry': {'type': 'Point', 'coordinates': pt_of(v)}} for v in bst.values()])
print('BART lines', sorted(blines), '· stations', len(bst))

# Muni: the Metro lines (J K L M N T, and the S shuttle), the F and E streetcars, and the three cable car lines.
mlines, mline_of = [], {}
for rid, r in gt['muni']['routes'].items():
    s = (r['short'] or rid).strip().upper()
    if r['type'] == '5' or 'CABLE' in r['long'].upper() or s in ('PM', 'PH', 'C', 'CA'):
        lid, name = 'cable', {'PM': 'Powell–Mason', 'PH': 'Powell–Hyde', 'C': 'California Street', 'CA': 'California Street'}.get(s, r['long'].title()) + ' cable car'
    elif s in ('F', 'E'):
        lid, name = 'hist', '%s %s streetcar' % (s, 'Market & Wharves' if s == 'F' else 'Embarcadero')
    elif re.fullmatch(r'[JKLMNTS]', s) or re.fullmatch(r'[JKLMNTS] ?(OWL|BUS)?', s):
        if 'BUS' in s or 'OWL' in s: continue
        lid, name = s.lower(), '%s %s' % (s, re.sub(r'(?i)\s+(line|metro)$', '', r['long']).title())
    else:
        continue
    m = route_lines(r)
    if m is None: continue
    mline_of[rid] = s if lid not in ('cable',) else 'Cable car'
    mlines.append(feat(m, {'line': lid, 'name': name}))
MORD = ['cable', 'hist', 's', 'e', 'f', 'j', 'k', 'l', 'm', 'n', 't']
dump('muni_lines', sorted(mlines, key=lambda f: MORD.index(f['properties']['line']) if f['properties']['line'] in MORD else 5))
def muni_name(n):
    """One name per Muni Metro station, as riders say it: the GTFS names each platform ("Metro Montgomery
    Station/Outbound", "Yerba Buena/Moscone Station Northbound", "Balboa Park BART/Mezzanine Level")."""
    n = re.sub(r'^Metro\s+', '', n.strip())
    n = re.sub(r'/(Outbound|Outbd|Inbound|Downtown|Downtn|Mezzanine Level)$', '', n)
    n = re.sub(r'\s+(Station\s+)?(North|South|East|West|Out|In)bound$', '', n)
    n = re.sub(r'\s+(BART|Platform.*)$', '', n)
    n = re.sub(r'\s+Station$', '', n)
    return n.replace('(16th Street)', '(16th St)').replace(' - ', ' – ').strip()


mst = stations_of('muni', {rid: l for rid, l in mline_of.items() if l != 'Cable car' and l not in ('F', 'E')},
                  lambda n: muni_name(n), 0.25)
# Surface stops of the Metro lines are many: keep the subway stations and the named surface hubs only.
SUB = re.compile(r'(?i)^(embarcadero|montgomery|powell|civic center|van ness|church|castro|forest hill|west portal|chinatown|union square|yerba buena|4th|st\.? francis|sunnydale|balboa park|ucsf|chase center|ocean beach|stonestown|sf state)')
MLORD = ['J', 'K', 'L', 'M', 'N', 'T', 'S']
write('muni_stations', [{'type': 'Feature', 'properties': {'name': v['name'], 'lines': sorted(v['lines'], key=lambda l: MLORD.index(l) if l in MLORD else 9)},
                         'geometry': {'type': 'Point', 'coordinates': pt_of(v)}} for v in mst.values() if SUB.match(v['name']) or len(v['lines']) >= 3])
print('Muni lines', [f['properties']['name'] for f in mlines], '· stations kept', sum(1 for v in mst.values() if SUB.match(v['name']) or len(v['lines']) >= 3), 'of', len(mst))

# ---------- Regional trains: Caltrain (GTFS); SMART, ACE, Capitol Corridor, VTA light rail (OpenStreetMap) ----------
rail, rail_in, rst = [], [], {}


def add_rail(g, p):
    rail.append(feat(g, p))
    gi = clip(g, CITY_B20)
    if gi is not None: rail_in.append(feat(gi, p))


for rid, r in gt['caltrain']['routes'].items():
    m = route_lines(r, 0.05)
    if m is not None and r['type'] == '2':
        add_rail(m, {'line': 'caltrain', 'name': 'Caltrain', 'color': '#E31837', 'offset': 0, 'to': 'San José / Gilroy', 'agency': 'Caltrain'})
for s in gt['caltrain']['stations']:
    nm = re.sub(r'\s+(Caltrain\s+)?Station$', '', s['name']).strip()
    v = rst.setdefault(nm.lower(), {'name': nm, 'pts': [], 'lines': set()})
    v['pts'].append((s['lon'], s['lat'])); v['lines'].add('Caltrain')
OSM_LINES = [('SMART', r'(?i)smart|sonoma.marin', '#0E5B39', 'SMART', 'Larkspur – Windsor'),
             ('ACE', r'(?i)\bace\b|altamont', '#7A3E97', 'ACE', 'San José – Stockton'),
             ('Capitol Corridor', r'(?i)capitol corridor', '#00577C', 'Capitol Corridor', 'San José – Sacramento'),
             ('VTA light rail', r'(?i)\bvta\b|santa clara valley', '#2A8DD1', 'VTA', 'San José and Silicon Valley')]
seen = set()
for el in load('osm_rail.json')['elements']:
    t = el.get('tags', {})
    if el['type'] != 'relation': continue
    blob = ' '.join(str(t.get(k, '')) for k in ('network', 'operator', 'name', 'ref'))
    hit = next((x for x in OSM_LINES if re.search(x[1], blob)), None)
    if not hit: continue
    ways = [LineString([(round(p['lon'], 5), round(p['lat'], 5)) for p in m['geometry']]) for m in el.get('members', [])
            if m.get('type') == 'way' and len(m.get('geometry') or []) > 1 and m.get('role', '') in ('', 'forward', 'backward', 'main')]
    if not ways: continue
    g = merged(ways, 0.2)
    if g is None: continue
    add_rail(g, {'line': re.sub(r'\W+', '', hit[0].lower()), 'name': hit[0], 'color': hit[2], 'offset': 0, 'to': hit[4], 'agency': hit[3]})


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
    blob = ' '.join(str(t.get(k, '')) for k in ('network', 'operator', 'name'))
    hit = next((x for x in OSM_LINES if re.search(x[1], blob)), None)
    if not hit or not t.get('name') or 'lon' not in el or hit[0] == 'VTA light rail': continue
    nm = re.sub(r'\s+(Station|SMART Station|ACE Station)$', '', t['name']).strip()
    v = rst.setdefault(nm.lower(), {'name': nm, 'pts': [], 'lines': set()})
    v['pts'].append((el['lon'], el['lat'])); v['lines'].add(hit[0])
HUBS = {'San Francisco', '4th & King', 'Millbrae', 'San Jose Diridon', 'San José Diridon', 'Oakland Coliseum', 'Richmond', 'Larkspur'}
write('rail_stations', [{'type': 'Feature', 'properties': {'name': v['name'], 'lines': sorted(v['lines']), **({'hub': True} if v['name'] in HUBS else {})},
                         'geometry': {'type': 'Point', 'coordinates': pt_of(v)}} for v in rst.values() if v['lines']])
print('regional rail', sorted(f['properties']['name'] for f in rail), '· stations', len(rst))

print('units', len(units), '· SF Find', len(finds), '· known-as', len(known), '· towns', len(towns), '· streets', len(streets),
      sum(f['properties']['cls'] == 'major' for f in streets), 'major · historic districts', len(heritage), '· cultural', len(cult))
