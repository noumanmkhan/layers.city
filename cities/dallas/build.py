"""Build the Dallas map's layer files from cities/dallas/raw/ (see SOURCES.md).
Polygons and lines go to tmp/ and are simplified by mapshaper in run.sh; points go straight to
docs/dallas/data/. Output shapes match the other cities', so the shared engine draws all of them.

Land and water: the Census Bureau's cartographic boundaries (Texas and Oklahoma) are the land, less the lakes
from its hydrography (Lake Ray Hubbard, Lewisville, Grapevine, Joe Pool, White Rock...). The City of Dallas is
its Census place, which includes the water of Lake Ray Hubbard and its other city-owned lakes; those show as
water and belong to no area. Highland Park, University Park and Cockrell Hill are their own towns inside it.

The map's units are ZIP Code Tabulation Areas clipped to the city (Dallas has no official neighbourhoods);
the areas (sides) group them (names.py)."""
import json, math, os, re, sys
from collections import defaultdict
from shapely.geometry import shape, mapping, Point, LineString, MultiLineString, box
from shapely.ops import unary_union, linemerge, polylabel

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from names import SIDES, SIDE_INFO, SIDE_OF, KNOWN_AS, MAJOR_STREETS, street_name, street_key

R = os.path.join(HERE, 'raw') + '/'
OUT = os.path.join(HERE, '..', '..', 'docs', 'dallas', 'data') + '/'
TMP = os.path.join(HERE, 'tmp') + '/'
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
load = lambda f: json.load(open(R + f))
fc = lambda feats: {'type': 'FeatureCollection', 'features': feats}
feat = lambda g, p: {'type': 'Feature', 'properties': p, 'geometry': mapping(g)}
KM = 93.6   # km per degree of longitude at Dallas's latitude (111.2 per degree of latitude)
KM2 = KM * 111.2
dist_km = lambda a, b: math.hypot((a[0] - b[0]) * KM, (a[1] - b[1]) * 111.2)
FRAME = box(-98.7, 31.55, -95.3, 33.85)
CORE = ['Dallas', 'Tarrant', 'Collin', 'Denton', 'Rockwall', 'Ellis', 'Johnson', 'Kaufman', 'Parker']


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

# ---------- Land, lakes, counties ----------
STATES = unary_union([shape(f['geometry']).buffer(0) for f in load('states.geojson')['features']]).intersection(FRAME)
counties = {f['properties']['NAME']: shape(f['geometry']).buffer(0) for f in load('counties.geojson')['features']}
REGION = unary_union([counties[c] for c in CORE])
lake_parts = []
for f in load('lakes.geojson')['features']:
    g = shape(f['geometry']).buffer(0)
    km2 = g.area * KM2
    if km2 > (1.0 if g.intersects(REGION) else 8.0):
        lake_parts.append(g)
LAKES = unary_union(lake_parts)
LAND = polys(STATES.difference(LAKES))
dry = lambda g: polys(g.difference(LAKES))
print('lakes kept', len(lake_parts))

places = [(f['properties'], shape(f['geometry']).buffer(0)) for f in load('places.geojson')['features']]
CITY_FULL = next(g for p, g in places if p['NAME'] == 'Dallas' and p['LSAD'] == '25')
CITY = dry(CITY_FULL)
inside = lambda g: polys(g.intersection(CITY))

# ---------- Units: ZIP codes inside the city; sides group them ----------
acs = load('acs_zcta.json')['zctas'] if os.path.exists(R + 'acs_zcta.json') else {}
units, no_profile = [], {}
for f in load('zctas.geojson')['features']:
    z, g = f['properties']['ZCTA5CE20'], shape(f['geometry']).buffer(0)
    gi = inside(g)
    if gi.is_empty or gi.area * KM2 < 0.8: continue
    if z not in SIDE_OF:
        print('  ZIP with no area in names.py:', z, round(gi.area * KM2, 1), 'km²'); continue
    share = gi.area / dry(g).area if not dry(g).is_empty else 1
    units.append((z, gi, share))
units.sort()
# Land the units leave out (slivers along the city limits, bits of ZIPs too small to keep) joins the nearest side.
side_geom = {s: unary_union([g for z, g, _ in units if SIDE_OF[z] == s]) for s in SIDES}
rest = CITY.difference(unary_union([g for _, g, _ in units]).buffer(0.00001))
for p in [p for p in getattr(rest, 'geoms', [rest]) if p.geom_type == 'Polygon' and p.area > 1e-9]:
    s = min(side_geom, key=lambda s: side_geom[s].distance(p))
    side_geom[s] = side_geom[s].union(p)
units_out = []
for z, g, share in units:
    p = {'name': z, 'code': z, 'lp': label_pt(g)}
    # A ZIP mostly in another town: its Census figures describe that town, so it carries none here.
    if share < 0.45 or z not in acs: p['part'] = round(share * 100); no_profile[z] = round(share * 100)
    units_out.append(feat(g, p))
dump('zips', units_out)
sides = []
for s, g in side_geom.items():
    g = polys(g.buffer(0.00002).buffer(-0.00002))
    sides.append(feat(g, {'name': s, 'info': SIDE_INFO[s], 'lp': label_pt(g)}))
dump('sides', sides)
json.dump(no_profile, open(TMP + 'zip_partial.json', 'w'))
print('units', len(units_out), '· partial ZIPs (no figures):', no_profile)

# ---------- Base: the city, the Metroplex's other towns, land beyond ----------
TOWN_TYPES = {'25': 'city', '43': 'town', '47': 'village', '57': 'CDP'}
base = [feat(CITY, {'kind': 'city', 'name': 'City of Dallas'})]
cutout = CITY_FULL.buffer(0.0002)
county_of = lambda g: max(CORE, key=lambda c: counties[c].intersection(g).area)
towns = []
for p, g in places:
    if p['NAME'] == 'Dallas' and p['LSAD'] == '25': continue
    if not g.intersects(REGION) or p['LSAD'] == '57': continue   # census-designated places aren't towns
    g = dry(g.difference(cutout).intersection(REGION))
    if g.is_empty or g.area * KM2 < 0.3: continue
    c = county_of(g)
    towns.append((p['NAME'], g, c))
names_n = defaultdict(int)
for n, _, _ in towns: names_n[n] += 1
for n, g, c in towns:
    base.append(feat(g, {'kind': 'neighbour', 'name': n, 'region': c + ' County', 'lp': label_pt(g)}))
# Unincorporated land in each county: named for the county, so a tap there still says where it is.
towns_u = unary_union([g for _, g, _ in towns] + [CITY_FULL])
for c in CORE:
    g = dry(counties[c].difference(towns_u.buffer(0.0003)))
    if g.is_empty: continue
    base.append(feat(g, {'kind': 'neighbour', 'name': 'Unincorporated ' + c + ' County', 'region': c + ' County', 'lp': label_pt(g), 'rest': True}))
outside = polys(LAND.difference(REGION.buffer(0.0005)))
base.insert(0, feat(outside, {'kind': 'outside', 'name': ''}))
dump('base', base)
dump('region_areas', [feat(dry(counties[c]), {'region': c + ' County'}) for c in CORE])
write('regions', [{'type': 'Feature', 'properties': {'name': n}, 'geometry': {'type': 'Point', 'coordinates': c}} for n, c in [
    ('Oklahoma', [-97.2, 33.78]), ('Grayson County', [-96.65, 33.62]), ('Hunt County', [-96.08, 33.15]), ('Wise County', [-97.65, 33.22]),
    ('Hood County', [-97.83, 32.43]), ('Navarro County', [-96.45, 32.05]), ('Henderson County', [-95.85, 32.2]), ('Hill County', [-97.1, 32.0])]])
print('towns', len(towns))

# ---------- Counties (the city reaches into five) ----------
dump('counties', [feat(dry(counties[c]), {'name': c + ' County', 'lp': label_pt(dry(counties[c]))}) for c in CORE])

# ---------- Representation: council districts (inside the city); Texas House and Senate, U.S. House (the nine counties) ----------
council = []
for f in load('dallas_council.geojson')['features']:
    g = inside(shape(f['geometry']).buffer(0))
    if g.is_empty: continue
    council.append(feat(g, {'num': int(f['properties']['COUNCIL']), 'lp': label_pt(g)}))
dump('council', sorted(council, key=lambda f: f['properties']['num']))
for src, out in [('tx_house', 'tx_house'), ('tx_senate', 'tx_senate'), ('us_house', 'us_house')]:
    feats = []
    for f in load(src + '.geojson')['features']:
        g = polys(shape(f['geometry']).buffer(0).intersection(REGION))
        if g.is_empty or g.area * KM2 < 0.05: continue
        feats.append(feat(g, {'num': int(f['properties']['District']), 'lp': label_pt(g)}))
    dump(out, sorted(feats, key=lambda f: f['properties']['num']))
    print(out, [f['properties']['num'] for f in feats])

# ---------- Known-as names: curated, moved to OpenStreetMap's place point when one is close ----------
osm_places = defaultdict(list)
for el in load('osm_places.json')['elements']:
    n = el.get('tags', {}).get('name'); c = (el.get('lon') or el.get('center', {}).get('lon'), el.get('lat') or el.get('center', {}).get('lat'))
    if n and c[0]: osm_places[n].append(c)
known = []
for k in KNOWN_AS:
    lat, lon = k['at']
    cands = [c for c in osm_places.get(k['osm'], []) if dist_km(c, (lon, lat)) < 1.2]
    pt = min(cands, key=lambda c: dist_km(c, (lon, lat))) if cands else (lon, lat)
    if not cands: print('  known-as from hand position:', k['name'])
    known.append({'type': 'Feature', 'properties': {'name': k['name'], 'kind': k['kind']},
                  'geometry': {'type': 'Point', 'coordinates': [round(pt[0], 5), round(pt[1], 5)]}})
write('knownas', known)

# ---------- Main streets: OpenStreetMap trunk, primary and secondary roads inside the city ----------
segs = defaultdict(list)
for w in load('osm_streets.json')['elements']:
    t = w['tags']
    if len(w.get('geometry', [])) < 2 or t.get('highway') not in ('trunk', 'primary', 'secondary', 'tertiary'): continue
    if re.search(r'(?i)\b(freeway|expressway|tollway|turnpike|service road|frontage)\b', t['name']): continue
    key = street_key(t['name'])
    if t['highway'] == 'tertiary' and key not in MAJOR_STREETS: continue
    g = way_line(w).intersection(CITY_FULL.buffer(0.0003))
    if g.is_empty: continue
    segs[(key, 'major' if key in MAJOR_STREETS else 'minor')].append(g)
streets = []
for (name, cls), gs in segs.items():
    m = merged(gs, 0.15)
    if m is None or m.length * KM < (0.8 if cls == 'major' else 1.5): continue
    streets.append(feat(m, {'name': name, 'cls': cls, 'len': round(m.length * 1000, 1)}))
streets.sort(key=lambda f: (f['properties']['cls'] != 'major', -f['properties']['len']))
dump('streets', streets)
print('main streets missing from the data:', sorted(MAJOR_STREETS - {n for n, c in segs if c == 'major'}))

# ---------- Highways: freeways and tollways by route, across the region ----------
def route_of(tags):
    for r in (tags.get('ref') or '').split(';'):
        r = r.strip()
        m = re.fullmatch(r'(I|US|SH|TX|Loop|Spur|PGBT|SRT|DNT|Toll)[ -]?(\w+)?', r)
        if m: return r.replace('TX ', 'SH ')
    n = tags.get('name') or ''
    for k, v in [('Dallas North Tollway', 'DNT'), ('President George Bush Turnpike', 'PGBT'), ('Sam Rayburn Tollway', 'SRT'), ('Woodall Rodgers', 'Spur 366')]:
        if k in n: return v
    return None


NAMES = {'I 35E': 'I-35E (Stemmons / R.L. Thornton)', 'I 30': 'I-30 (Tom Landry)', 'I 45': 'I-45 (Julius Schepps)', 'I 635': 'I-635 (LBJ)',
         'I 20': 'I-20', 'US 75': 'US 75 (Central Expressway)', 'DNT': 'Dallas North Tollway', 'US 67': 'US 67 (Marvin D. Love)',
         'Loop 12': 'Loop 12', 'SH 183': 'SH 183 (Airport Freeway)', 'SH 114': 'SH 114', 'SH 190': 'President George Bush Turnpike',
         'PGBT': 'President George Bush Turnpike', 'Spur 366': 'Woodall Rodgers Freeway', 'US 80': 'US 80', 'US 175': 'US 175 (C.F. Hawn)',
         'SH 12': 'Loop 12'}
inner = CITY_FULL.buffer(-0.0004)
in_city, outer = defaultdict(list), defaultdict(list)
for w in load('osm_highways.json')['elements']:
    t = w['tags']
    if len(w.get('geometry', [])) < 2 or 'link' in t.get('highway', ''): continue
    r = route_of(t)
    if not r: continue
    r = re.sub(r'[ -]+', ' ', r).replace('I ', 'I ', 1)
    line = way_line(w)
    if line.intersects(CITY_FULL) and t['highway'] in ('motorway', 'trunk'):
        g = line.intersection(CITY_FULL.buffer(0.0005))
        if not g.is_empty: in_city[r].append(g)
    if t['highway'] == 'motorway':
        g = line.difference(inner)
        if not g.is_empty: outer[r].append(g)
shield = lambda r: r if r in ('DNT', 'PGBT', 'SRT') else re.sub(r'^(I|US|SH|Loop|Spur) ', '', r)   # the number, as on the sign
hw = []
for r, gs in in_city.items():
    m = merged(gs, 0.4)
    if m is None: continue
    hw.append(feat(m, {'route': shield(r), 'name': NAMES.get(r, r.replace('I ', 'I-')), 'kind': 'interstate' if r.startswith('I ') else 'provincial'}))
dump('highways', hw)
REGION_BOX = REGION.buffer(0.01)
gh, shields = [], []
for r, gs in outer.items():
    m = merged(gs, 1)
    if m is None: continue
    toll = r in ('DNT', 'PGBT', 'SRT') or 'Toll' in r
    big = r.startswith(('I ', 'US ')) or toll   # across the region, shields only for interstates, US routes and tollways
    gh.append(feat(m, {'route': shield(r), 'name': NAMES.get(r, r.replace('I ', 'I-')), 'toll': toll}))
    if not big: continue
    r = shield(r)
    for p in getattr(m, 'geoms', [m]):
        km = p.length * KM
        if km < 5: continue
        for d in [x for x in range(5, int(km) - 2, 25)] or [km / 2]:
            pt = p.interpolate(d / KM)
            if not REGION_BOX.contains(pt): continue
            if any(s['properties']['route'] == r and Point(s['geometry']['coordinates']).distance(pt) * KM < 15 for s in shields): continue
            shields.append({'type': 'Feature', 'properties': {'route': r, 'toll': toll},
                            'geometry': {'type': 'Point', 'coordinates': [round(pt.x, 5), round(pt.y, 5)]}})
dump('region_highways', gh)
write('region_shields', shields)
print('city highways', sorted(in_city), '· region routes', len(outer), len(shields), 'shields')

# ---------- DART light rail (metro), and the Silver Line and TRE (rail), from DART's GTFS ----------
dart = load('dart_rail.json')
LINE = {'RED': 'red', 'BLUE': 'blue', 'GREEN': 'green', 'ORANGE': 'orange', 'SILVER': 'silver', 'TRE': 'tre'}
metro, rail, rail_in, routes_of = [], [], [], {}
for rid, r in dart['routes'].items():
    lid = LINE.get(r['short'].upper())
    if not lid: continue
    top = max(r['counts'].values())
    shp = [LineString(r['shapes'][s]) for s, c in r['counts'].items() if c >= top * 0.15 and len(r['shapes'][s]) > 1]
    m = merged(shp, 0.1)
    if m is None: continue
    routes_of[rid] = lid
    if r['type'] == '0':
        metro.append(feat(m, {'line': lid, 'name': lid.title() + ' Line'}))
    else:
        p = {'line': lid, 'name': 'Silver Line' if lid == 'silver' else 'Trinity Railway Express', 'color': {'silver': '#8C96A3', 'tre': '#112458'}[lid],
             'offset': 0, 'to': 'DFW Airport' if lid == 'silver' else 'Fort Worth'}
        rail.append(feat(m, p))
        gi = m.intersection(CITY_FULL.buffer(0.002))
        if not gi.is_empty: rail_in.append(feat(gi, p))
ORDER = ['orange', 'green', 'blue', 'red']
dump('dart_lines', sorted(metro, key=lambda f: ORDER.index(f['properties']['line'])))
dump('rail_lines', rail); dump('rail_lines_inner', rail_in)
TERMINI = {'Parker Road', 'Westmoreland', 'Downtown Rowlett', 'UNT Dallas', 'North Carrollton/Frankford', 'Buckner', 'DFW Airport Terminal A',
           'DFW Airport Terminal B', 'Shiloh Road', 'Fort Worth T&P', 'Ledbetter', '8th & Corinth'}
stations, rstations, seen = [], [], {}
LORD = ['Red', 'Blue', 'Green', 'Orange', 'Silver', 'TRE']
for s in dart['stations']:
    ls = sorted({routes_of[x] for x in s['routes'] if x in routes_of})
    if not ls: continue
    name = re.sub(r'(?i)\s+(station|rail station|lrt station|stn)$', '', s['name']).strip()
    name = re.sub(r'(?i)\s*\b(?:SB|NB|EB|WB|platform \w+)\b.*$', '', name).strip()
    key = name.lower()
    st = seen.setdefault(key, {'name': name, 'pts': [], 'lines': set()})
    st['pts'].append((s['lon'], s['lat'])); st['lines'] |= set(ls)
for st in seen.values():
    x = round(sum(p[0] for p in st['pts']) / len(st['pts']), 5); y = round(sum(p[1] for p in st['pts']) / len(st['pts']), 5)
    lr = [l for l in st['lines'] if l in ORDER]
    names_ = sorted([('TRE' if l == 'tre' else l.title()) for l in st['lines']], key=lambda l: LORD.index(l))
    if lr:
        stations.append({'type': 'Feature', 'properties': {'name': st['name'], 'lines': [l for l in names_ if l not in ('Silver', 'TRE')], 'terminus': st['name'] in TERMINI},
                         'geometry': {'type': 'Point', 'coordinates': [x, y]}})
    if set(st['lines']) & {'silver', 'tre'}:
        rstations.append({'type': 'Feature', 'properties': {'name': st['name'], 'lines': [{'silver': 'Silver Line', 'tre': 'Trinity Railway Express'}[l] for l in sorted(st['lines'] & {'silver', 'tre'})],
                                                             **({'hub': True} if st['name'] in ('Union Station', 'EBJ Union Station') else {})},
                          'geometry': {'type': 'Point', 'coordinates': [x, y]}})
write('dart_stations', stations); write('rail_stations', rstations)

print('units', len(units_out), '· sides', len(sides), '· known-as', len(known), '· towns', len(towns), '· streets', len(streets),
      sum(f['properties']['cls'] == 'major' for f in streets), 'major · light rail', [f['properties']['name'] for f in metro],
      '· stations', len(stations), '· rail', [f['properties']['name'] for f in rail], len(rstations), 'stations')
