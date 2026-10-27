"""Build a city's Routes page: "what buses stop near me, and where do they go?"

Reads the schedule the map already fetched (cities/<city>/raw/surface/: routes.json with each route's patterns
and stops.json) and the map's published layers (neighbourhoods, regions, streets, stations, landmarks), and
writes docs/<city>/routes/:
  - index.html, from engine/routes/page.html and the city's cities/<city>/routes.json "page" wording;
  - data/stops.json: every stop of the included modes, with the routes and directions that serve it and the
    side of the street it's on;
  - data/r/<route>.json, one per route: each pattern's line (with distance along it), its stops in order, and
    its "story" measured along the line: the regions and neighbourhoods it passes through, the streets it
    runs along, the main streets it crosses, its subway connections and the landmarks it passes.
The page slices a pattern's story from the stop someone picked, so it always reads "from here".

Patterns are the agency's own (GTFS shapes, busiest first). A stop belongs to a pattern when it's within a
few metres of the line on the side traffic keeps to (or anywhere near the line's ends, where buses loop
into stations). Every distance is in metres along the pattern.

Usage: python3 engine/routes/build.py <city>
"""
import json, math, os, re, sys
from shapely.geometry import shape, LineString, Point
from shapely.strtree import STRtree

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
city = sys.argv[1]
CFG = json.load(open(os.path.join(ROOT, 'cities', city, 'routes.json'), encoding='utf-8'))
RAW = os.path.join(ROOT, 'cities', city, 'raw')
DATA = os.path.join(ROOT, 'docs', city, 'data')
OUT = os.path.join(ROOT, 'docs', city, 'routes')
os.makedirs(os.path.join(OUT, 'data', 'r'), exist_ok=True)

RAW_R = json.load(open(os.path.join(RAW, 'surface', 'routes.json')))
RAW_S = json.load(open(os.path.join(RAW, 'surface', 'stops.json')))
TRANSIT = json.load(open(os.path.join(DATA, 'transit.json')))
MODES = set(CFG.get('modes', ['bus']))
NEAR = CFG.get('near', {})
FIX = CFG.get('nameFix', {})
BRIDGES = set(CFG.get('bridges', []))

# ---- a flat metric projection around the city (plenty for distances of a few km) ----
lat0 = sum(s[3] for s in RAW_S['stops']) / len(RAW_S['stops'])
KX, KY = 111320 * math.cos(math.radians(lat0)), 110574


def m(lon, lat): return (lon * KX, lat * KY)


def ll(x, y): return (round(x / KX, 5), round(y / KY, 5))


def proj(g):
    import shapely
    return shapely.transform(g, lambda a: a * [KX, KY])


def layer(name):
    p = os.path.join(DATA, name + '.geojson')
    return json.load(open(p))['features'] if os.path.exists(p) else []


def polys(name, skip=()):
    out = [(f['properties']['name'], proj(shape(f['geometry']))) for f in layer(name)
           if f['properties'].get('name') not in skip]
    return out, STRtree([g for _, g in out])


def where(index, p):
    feats, tree = index
    for i in tree.query(p):
        if feats[i][1].contains(p): return feats[i][0]
    return None


HOODS = polys(CFG.get('units', 'neighbourhoods'))
REGIONS = [polys(n, CFG.get('regionSkip', [])) for n in CFG.get('regions', [])]


def region(p):
    for r in REGIONS:
        n = where(r, p)
        if n: return n
    return None


# ---- streets: every named segment of the classes buses run along, with its name tidied ----
ST = CFG['streets']
raw_streets = json.load(open(os.path.join(RAW, ST['raw'])))
streets = []   # (name, is_cross_class, geometry)
for cls in ST['along']:
    for f in raw_streets[cls]['features']:
        n = (f['properties'].get(ST['name']) or '').strip()
        if not n or 'ramp' in n.lower() or not f.get('geometry'): continue
        streets.append((FIX.get(n, n), cls in ST['cross'], proj(shape(f['geometry']))))
S_TREE = STRtree([g for *_, g in streets])
CROSS = [s for s in streets if s[1]]
C_TREE = STRtree([g for *_, g in CROSS])


def axis(dx, dy):
    """Bearing 0-180 of a direction, ignoring which way along it (for "is the bus on this street?")."""
    return math.degrees(math.atan2(dx, dy)) % 180


def adiff(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)


# ---- points of interest: the map's landmarks and institutions, plus this page's extra list ----
pois = []   # (name, kind label, point)
for src in CFG.get('pois', []):
    for f in layer(src['file']):
        p = f['properties']
        if 'cats' in src:
            if p.get('cat') not in src['cats']: continue
            kind = src['cats'][p['cat']]
        else:
            kind = p.get(src.get('cat', 'cat')) or ''
        name = p['name']
        # A campus by its own name (Centennial College, Story Arts Centre), when the layer's note is one.
        if src.get('sub') and p.get('sub') and re.search(src['sub'], p['sub']): name = f"{name}, {p['sub']}"
        pois.append((name, kind, proj(shape(f['geometry']))))
stop_by_name = {}
for s in RAW_S['stops']:
    stop_by_name.setdefault(s[1], []).append(s)
for x in CFG.get('extras', []):
    hits = [s for want in x['stops'] for n, ss in stop_by_name.items() if n.startswith(want) for s in ss]
    if not hits:
        print(f'  extra landmark "{x["name"]}": no stop named like {x["stops"]}; skipped')
        continue
    lon = sum(s[2] for s in hits) / len(hits); lat = sum(s[3] for s in hits) / len(hits)
    pois.append((x['name'], x['cat'], Point(*m(lon, lat))))
known = [(f['properties']['name'], proj(shape(f['geometry']))) for f in layer(CFG['known'])] if CFG.get('known') else []

SC = CFG['stations']
stations = [(f['properties']['name'] + SC.get('suffix', ''), f['properties'].get('lines', []), proj(shape(f['geometry'])))
            for f in layer(SC['file'])]

# ---- routes ----
meta = {r['r']: r for r in TRANSIT['routes']}
routes = [r for r in RAW_R['routes'] if r['mode'] in MODES and r['id'] in meta]
stops = {s[0]: s for s in RAW_S['stops']}


def runs(seq, step):
    """[(value, start index, end index)] for consecutive equal values."""
    out = []
    for i, v in enumerate(seq):
        if out and out[-1][0] == v: out[-1][2] = i
        else: out.append([v, i, i])
    return out


def turn(a, b):
    """Grid-relative direction word for a travel bearing (degrees from true north)."""
    g = (math.degrees(math.atan2(a, b)) + CFG.get('gridTilt', 0)) % 360
    return ['north', 'east', 'south', 'west'][int(((g + 45) % 360) // 90)]


SIDE = {'north': 'East side', 'south': 'West side', 'east': 'South side', 'west': 'North side'}
if not CFG.get('keepRight', True):
    SIDE = {k: {'East side': 'West side', 'West side': 'East side', 'South side': 'North side', 'North side': 'South side'}[v] for k, v in SIDE.items()}

STEP = 30


def story(line):
    """Everything along one pattern, measured in metres from its start."""
    L = line.length
    ds = list(range(0, int(L), STEP)) + [int(L)]
    pts = [line.interpolate(d) for d in ds]
    out = {}

    # Regions and neighbourhoods. A street that is itself the boundary (Pape Ave between two neighbourhoods)
    # reads "between A and B": look a little to each side of the line.
    hood, reg = [], []
    for i, p in enumerate(pts):
        a = pts[max(i - 1, 0)]; b = pts[min(i + 1, len(pts) - 1)]
        dx, dy = b.x - a.x, b.y - a.y; n = math.hypot(dx, dy) or 1
        ox, oy = -dy / n * 35, dx / n * 35
        left, right = where(HOODS, Point(p.x + ox, p.y + oy)), where(HOODS, Point(p.x - ox, p.y - oy))
        on = where(HOODS, p)
        if left and right and left != right: hood.append(tuple(sorted((left, right))))
        else: hood.append(on or left or right)
        reg.append(region(p))

    def spans(seq, least):
        rs = [r for r in runs(seq, STEP) if r[0] and (ds[r[2]] - ds[r[1]] >= least)]
        merged = []
        for v, i, j in rs:
            if merged and merged[-1][0] == v: merged[-1][2] = j
            else: merged.append([v, i, j])
        return [[ds[i], ds[j], v if isinstance(v, str) else list(v)] for v, i, j in merged]

    hs = spans(hood, 150)
    # A "between" stretch that's short and sits beside one of its own neighbourhoods just reads as that one.
    out['hoods'] = hs
    out['regions'] = spans(reg, 300)

    # Streets it runs along: the nearest named street within 18 m running the same way as the bus.
    along = []
    for i, p in enumerate(pts):
        a = pts[max(i - 1, 0)]; b = pts[min(i + 1, len(pts) - 1)]
        if a.equals(b): along.append(None); continue
        brg = axis(b.x - a.x, b.y - a.y)
        best = None
        for j in S_TREE.query(p.buffer(18)):
            n, _, g = streets[j]
            dist = g.distance(p)
            if dist > 18: continue
            s0 = g.project(p); q0 = g.interpolate(max(s0 - 12, 0)); q1 = g.interpolate(min(s0 + 12, g.length))
            if q0.equals(q1) or adiff(axis(q1.x - q0.x, q1.y - q0.y), brg) > 25: continue
            if best is None or dist < best[0]: best = (dist, n)
        along.append(best[1] if best else None)
    # Fill short gaps (an intersection, a jog) between the same street; drop short stretches, except bridges.
    rs = runs(along, STEP)
    st = []
    for v, i, j in rs:
        if not v: continue
        if ds[j] - ds[i] < (60 if v in BRIDGES else 220): continue
        if st and st[-1][2] == v and ds[i] - st[-1][1] < 400: st[-1][1] = ds[j]
        else: st.append([ds[i], ds[j], v])
    out['streets'] = st

    # Main streets it crosses (not the ones it's running along at that point).
    cross = []
    for j in C_TREE.query(line.buffer(1)):
        n, _, g = CROSS[j]
        x = line.intersection(g)
        for p in getattr(x, 'geoms', [x]):
            if p.is_empty or p.geom_type != 'Point': continue
            d = line.project(p)
            if any(a - 300 <= d <= b + 300 and s == n for a, b, s in st): continue   # running along it here (or turning onto it)
            if n in BRIDGES or re.search(CFG.get('notCrossed', r'(?!)'), n): continue   # on a bridge you go over, not across
            if d < 40 or d > L - 40: continue
            cross.append([round(d), n])
    cross.sort()
    kept = []
    for d, n in cross:
        if kept and any(k[1] == n and d - k[0] < 600 for k in kept): continue
        kept.append([d, n])
    out['cross'] = kept

    # Subway connections and landmarks near the line, in order.
    stn = []
    for n, lines, g in stations:
        if line.distance(g) <= NEAR.get('station', 150): stn.append([round(line.project(g)), n, lines])
    out['stations'] = sorted(stn)
    pp = []
    for n, kind, g in pois:
        if line.distance(g) <= NEAR.get('poi', 200): pp.append([round(line.project(g)), n, kind])
    for n in BRIDGES:   # bridges come from the streets themselves
        for a, b, s in st:
            if s == n: pp.append([round((a + b) / 2), n, 'Bridge'])
    out['pois'] = sorted(pp)
    kn = []
    for n, g in known:
        if line.distance(g) <= NEAR.get('known', 250): kn.append([round(line.project(g)), n])
    out['known'] = sorted(kn)
    return out


def side_of(line, p):
    """Signed offset of p from the line (left positive), and the line's travel direction there."""
    d = line.project(p)
    a = line.interpolate(max(d - 15, 0)); b = line.interpolate(min(d + 15, line.length))
    dx, dy = b.x - a.x, b.y - a.y; n = math.hypot(dx, dy) or 1
    q = line.interpolate(d)
    return ((p.x - q.x) * -dy + (p.y - q.y) * dx) / n, d, (dx, dy)


stop_routes = {}    # stop id -> {route id: set of dirs}
stop_side = {}      # stop id -> {direction word: count}
route_index = {}
for r in routes:
    rid = r['id']
    mt = meta[rid]
    on_route = [s for s in RAW_S['stops'] if rid in s[4]]
    total = sum(s['trips'] for s in r['shapes']) or 1
    pats = []
    for k, sh in enumerate(sorted(r['shapes'], key=lambda s: -s['trips'])):
        if sh['trips'] / total < 0.03 and k: continue   # a handful of trips a day (garage runs, detours)
        line = LineString([m(*c) for c in sh['coords']])
        if line.length < 200: continue
        L = line.length
        seq = []
        for s in on_route:
            p = Point(*m(s[2], s[3]))
            dist = line.distance(p)
            end = line.project(p) < 120 or line.project(p) > L - 120
            if dist > (70 if end else 25): continue
            off, d, (dx, dy) = side_of(line, p)
            right = off < 0 if CFG.get('keepRight', True) else off > 0
            if not (end or abs(off) <= 6 or right): continue
            seq.append([round(d), s[0]])
            w = turn(dx, dy)
            stop_side.setdefault(s[0], {}).setdefault(w, 0)
            stop_side[s[0]][w] += sh['trips']
        seq.sort()
        if len(seq) < 2: continue
        sx, sy = line.coords[0]; ex, ey = line.coords[-1]
        head = turn(ex - sx, ey - sy)
        # The line itself, to draw, with each vertex's distance along it (simplified to ~6 m).
        simp = line.simplify(6)
        coords = []
        for x, y in simp.coords:
            coords.append([*ll(x, y), round(line.project(Point(x, y)))])
        last = stops[seq[-1][1]]
        st_end = next(((n, lines) for n, lines, g in stations if g.distance(Point(*m(last[2], last[3]))) < 300), None)
        p = {'k': len(pats), 'dir': sh['dir'], 'trips': sh['trips'], 'share': round(sh['trips'] / total, 2),
             'head': head, 'km': round(L / 1000, 1), 'to': st_end[0] if st_end else last[1], 'line': coords,
             'stops': seq}
        p.update(story(line))
        # A route that ends at a station connects there, even when its loop sits a little off the platform.
        if st_end and not any(n == st_end[0] for _, n, _ in p['stations']):
            p['stations'].append([seq[-1][0], st_end[0], st_end[1]])
        pats.append(p)
        for d, sid in seq:
            stop_routes.setdefault(sid, {}).setdefault(rid, []).append([p['k'], d])
    if not pats: continue
    doc = {'r': mt['r'], 'n': mt['n'], 'm': r['mode'], 'f': mt.get('f', []), 'h': mt.get('h'),
           'stops': {sid: stops[sid][1] for p in pats for _, sid in p['stops']},
           'patterns': pats}
    json.dump(doc, open(os.path.join(OUT, 'data', 'r', rid + '.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
    # For the list of stops near someone: each pattern's direction, end, length, share of trips, the regions it
    # passes through and its subway connections (both with distances, so the page can start them at a stop).
    route_index[rid] = [mt['r'], mt['n'], r['mode'], mt.get('f', []), mt.get('h'),
                        [[p['head'], p['to'], round(p['km'] * 1000), p['share'], p['regions'],
                          [[d, n, lines] for d, n, lines in p['stations']]] for p in pats]]

# The stops list: [id, name, lon, lat, side ("East side"...), {route: [patterns]}]
out_stops = []
for sid, rs in stop_routes.items():
    s = stops[sid]
    sides = stop_side.get(sid, {})
    w = max(sides, key=sides.get) if sides else None
    # [id, name, lon, lat, side, travel direction, {route: [[pattern, d]...]}, code on the pole ('' if none)]
    out_stops.append([sid, s[1], s[2], s[3], SIDE.get(w, ''), w or '', {k: sorted(v) for k, v in rs.items()}, s[5] if len(s) > 5 else ''])
json.dump({'asof': TRANSIT.get('asof'), 'week': TRANSIT.get('week'), 'routes': route_index, 'stops': out_stops},
          open(os.path.join(OUT, 'data', 'stops.json'), 'w'), separators=(',', ':'), ensure_ascii=False)

# ---- the page ----
if not os.path.exists(os.path.join(ROOT, 'engine', 'routes', 'page.html')): sys.exit(print(f'{city}: {len(route_index)} routes, {len(out_stops)} stops (no page template yet)'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from theme import SCRIPT as THEME_SCRIPT, css as theme_css   # dark theme, as the guides and venue pages have
DARK_MAP = ['body{--water:#18232B;--m-city:#24272D;--m-out:#1C1F24;--m-edge:#3A3E45;--m-hood:#3A2328;--m-hoodline:#4A3A3E;'
            '--m-major:#4A4E56;--m-minor:#363A41;--m-halo:#15171B;--pill-line:#373B42;--sub:#9AA0A8}',
            '.rb:not(.tram):not(.exp){background:var(--card)}', '.row:hover{background:#262A30}', '.tl li.on{background:#262A30}']
tpl = open(os.path.join(ROOT, 'engine', 'routes', 'page.html'), encoding='utf-8').read()
css_p = os.path.join(ROOT, 'cities', city, 'factsheet.css')
page = dict(CFG['page'])
cfg_out = {k: v for k, v in page.items()}
html = (tpl.replace('{{RS}}', json.dumps(cfg_out, ensure_ascii=False))
        .replace('{{css}}', open(css_p, encoding='utf-8').read() if os.path.exists(css_p) else '')
        .replace('{{title}}', page['title']).replace('{{city}}', page['city'])
        .replace('{{description}}', page['description']).replace('{{lede}}', page['lede'])
        .replace('{{placeholder}}', page['placeholder']).replace('{{credits}}', page['credits'])
        .replace('{{mapLink}}', page.get('mapLink', 'Open on the map'))
        .replace('{{themeScript}}', THEME_SCRIPT).replace('{{themeCss}}', theme_css(DARK_MAP)))
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)
print(f'{city} routes page: {len(route_index)} routes, {len(out_stops)} stops')
