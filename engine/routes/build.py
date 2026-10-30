"""Build a city's Routes page: "what buses stop near me, and where do they go?"

Reads the schedule the map already fetched (cities/<city>/raw/surface/: routes.json with each route's patterns
and stops.json) and the map's published layers (neighbourhoods, regions, streets, stations, landmarks), and
writes docs/<city>/routes/:
  - index.html, from engine/routes/page.html and the city's cities/<city>/routes.json "page" wording;
  - data/stops.json: every stop of the included modes, with the routes and directions that serve it and the
    side of the street it's on;
  - data/sched/<bucket>.json, when the schedule fetch wrote raw/surface/sched.json: when each route runs at each
    stop, for "next bus at 5:42 am" when there are no live times;
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
# Stop names as the map writes them (engine/surface.py stop_name, from surface.json "stopNames"): an agency that
# writes them in capitals ("1 AV/E 14 ST") reads "1 Av/E 14 St". Kept in step with surface.py by hand.
SN = json.load(open(os.path.join(ROOT, 'cities', city, 'surface.json'))).get('stopNames') or {}
def stop_name(n):
    while SN.get('strip'):
        m_ = re.sub(SN['strip'], '', n.strip()).strip()
        if m_ == n: break
        n = m_
    if SN.get('title') and n.isupper():
        n = re.sub(r"\b([A-Za-z])([A-Za-z']*)", lambda m_: m_.group(1).upper() + m_.group(2).lower(), n)
        n = re.sub(r'\b(\d+)(st|nd|rd|th)\b', lambda m_: m_.group(1) + m_.group(2).lower(), n, flags=re.I)
        for w in SN.get('keep', []): n = re.sub(r'\b' + re.escape(w) + r'\b', w, n, flags=re.I)
    if SN.get('at'): n = re.sub(r'\s*@\s*', SN['at'], n)
    return n
for s_ in RAW_S['stops']: s_[1] = stop_name(s_[1])
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
if ST.get('osm'):   # OpenStreetMap ways from Overpass ("out tags geom"): the class is the way's highway tag
    by_cls = {}
    for e in raw_streets['elements']:
        t = e.get('tags', {})
        if e.get('type') != 'way' or len(e.get('geometry') or []) < 2: continue
        by_cls.setdefault(t.get('highway'), []).append({'properties': {ST['name']: t.get('name')},
            'geometry': {'type': 'LineString', 'coordinates': [[p['lon'], p['lat']] for p in e['geometry']]}})
    raw_streets = {c: {'features': fs} for c, fs in by_cls.items()}
streets = []   # (name, is_cross_class, geometry)
for cls in ST['along']:
    for f in raw_streets.get(cls, {'features': []})['features']:
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
        if src.get('sub') and p.get('sub') and re.search(src['sub'], p['sub']): name = f"{name} ({p['sub']})"
        name = CFG.get('poiNames', {}).get(name, name)   # a name that needs a word of context (History, the music venue)
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
# One file, or several (a city with two rapid agencies: BART's stations and Muni Metro's). A station of the same
# name in two files within 300 m is one station with both sets of lines (Montgomery Street: BART and Muni).
stations = []
for fn in SC.get('files') or [SC['file']]:
    for f in layer(fn):
        if SC.get('skip') and re.search(SC['skip'], f['properties']['name']): continue   # a file's street stops, not stations
        n, lines, g = f['properties']['name'] + SC.get('suffix', ''), list(f['properties'].get('lines', [])), proj(shape(f['geometry']))
        same = next((x for x in stations if x[0] == n and x[2].distance(g) < 300), None)
        if same: same[1].extend(l for l in lines if l not in same[1])
        else: stations.append((n, lines, g))
STATION_NAMES = {n for n, _, _ in stations}

# ---- routes ----
meta = {r['r']: r for r in TRANSIT['routes']}
# The map's route list goes by the number riders see (engine/surface.py: surface.json "rename" and "stripZeros"),
# which can differ from the feed's route id (the MTA's Q06 is the Q6, Muni's LOWL the L Owl): match on that.
_SC = json.load(open(os.path.join(ROOT, 'cities', city, 'surface.json')))
def _num(s):
    s2 = (s.lstrip('0') or s) if _SC.get('stripZeros') else s
    return _SC.get('rename', {}).get(s, s2)
for r in RAW_R['routes']:
    if r['id'] not in meta and _num(r['short']) in meta: meta[r['id']] = meta[_num(r['short'])]
routes = [r for r in RAW_R['routes'] if r['mode'] in MODES and r['id'] in meta]
SHORT = {r['id']: r['short'] for r in RAW_R['routes']}   # the schedule (sched.json) goes by the feed's short name
stops = {s[0]: s for s in RAW_S['stops']}

# Rapid transit (subway, LRT) from raw/surface/rapid_*.json (engine/fetch_surface.py, surface.json "rapid"): each
# shape lists its platforms in order, so they're placed exactly rather than matched to the line by distance. The
# map's transit.json doesn't list these lines, so their entry (name, frequency) is made here from the schedule.
RAPID_MODES = {'subway', 'lrt'} & MODES
STREET_STOPS = []   # stops of street lines from the rapid files (below)
# A platform's direction from its name: "Eastbound Platform", or the agency's own words (routes.json "platformDirs":
# Muni's "Metro Castro Station/Outbound" and ".../Downtown" are outbound and inbound).
PDIRS = CFG.get('platformDirs', {})
# (the agency's own words count only at the end of a name: "Metro Castro Station/Outbound", not BART's "Downtown Berkeley")
DIRWORD = re.compile(r'\b(?:(North|South|East|West)bound\b' + ''.join('|(' + re.escape(k) + r')\s*$' for k in PDIRS) + r')', re.I)
COMPASS = ('north', 'south', 'east', 'west')
def pdir(name):
    w = DIRWORD.search(name)
    if not w: return None
    if w.group(1): return w.group(1).lower()
    return next(v for k, v in PDIRS.items() if k.lower() == w.group(0).lower())
PL_ = CFG.get('platformLabels')
PLABELS = None
if PL_ and os.path.exists(os.path.join(RAW, PL_['raw'])):
    PLABELS = {'suffix': PL_.get('suffix', ['N', 'S']), 'skip': PL_.get('skip', []), 'labels': json.load(open(os.path.join(RAW, PL_['raw'])))['stations']}
def dir_label(w): return f'{w.capitalize()}bound' if w in COMPASS else w.capitalize()
def station_of(name):
    return re.sub(r'\s*-?\s*\b((North|South|East|West)bound|Subway|LRT)\b.*$', '', name).strip()
rapid_ids = set()
# Rapid lines from the city's main feed and from any other agency's (routes.json "rapidFeeds": San Francisco's BART,
# fetched into raw/surface/bart/ by fetch_surface.py), whose route ids are already their own (BART-Yellow).
RR, RS_ = [], []
for fd in [''] + CFG.get('rapidFeeds', []):
    rp = os.path.join(RAW, 'surface', fd, 'rapid_routes.json')
    if not os.path.exists(rp): continue
    RR += json.load(open(rp))['routes']
    RS_ += json.load(open(os.path.join(RAW, 'surface', fd, 'rapid_stops.json')))['stops']
if RR:
    for s_ in RS_: stops[s_[0]] = s_
    for r in RR:
        if r['mode'] in MODES and r['mode'] not in RAPID_MODES:
            # A street-running line kept apart only so the map doesn't draw it twice (San Francisco's F streetcar
            # and cable cars, surface.json "rapid" with mode "tram" or "cable"): a route like the buses, its stops
            # matched to its line by side of the street, its entry made here from the schedule.
            ds_ = [v for v in r.get('wk', {}).values() if sum(v[10:15])]
            n_ = max((sum(v[10:15]) for v in ds_), default=0)
            h_ = round(300 / n_) if n_ >= 5 else None
            meta[r['id']] = {'r': r['short'], 'n': r['long'].title() if r['long'].isupper() else r['long'], 'm': r['mode'],
                             'f': ['freq'] if h_ and h_ <= 10 else ['reg'], 'h': h_}
            routes.append(r)
            STREET_STOPS.extend(x for x in RS_ if r['id'] in x[4] or r['short'] in x[4])
            continue
        if r['mode'] not in RAPID_MODES: continue
        ds_ = [v for v in r.get('wk', {}).values() if sum(v[10:15])]
        n_ = max((sum(v[10:15]) for v in ds_), default=0)
        meta[r['id']] = {'r': r['short'], 'n': r['long'].title() if r['long'].isupper() else r['long'], 'm': r['mode'], 'f': ['freq'], 'h': round(300 / n_) if n_ >= 5 else None}
        # The same platforms in the same order are one pattern, however many shapes the schedule draws for it.
        seen = {}
        for sh in sorted(r['shapes'], key=lambda x: -x['trips']):
            key = (sh['dir'], tuple(sh.get('stops', [])))
            if key in seen: seen[key]['trips'] += sh['trips']
            else: seen[key] = dict(sh)
        routes.append(dict(r, shapes=list(seen.values())))
        rapid_ids.add(r['id']); SHORT[r['id']] = r['short']


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


def story(line, tol=18):
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
        for j in S_TREE.query(p.buffer(tol)):
            n, _, g = streets[j]
            dist = g.distance(p)
            if dist > tol: continue
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
        if n in {x[1] for x in stn}: continue   # Union Station is a landmark and a station: say it once, as the station
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
LAST_STOPS = set()  # stops where a pattern ends
stop_side = {}      # stop id -> {direction word: count}
route_index = {}
for r in routes:
    rid = r['id']
    mt = meta[rid]
    on_route = [s for s in RAW_S['stops'] + STREET_STOPS if rid in s[4] or r['short'] in s[4]]   # stops list routes by short name
    total = sum(s['trips'] for s in r['shapes']) or 1
    pats = []
    # First every pattern's candidate stops, with which side of the line each is on. Streetcar tracks (and some
    # bus shapes) run down the middle of the street, so a stop can sit within a few metres of the line both
    # ways; where a stop matches the route in both directions, it keeps only the direction whose side of the
    # street it's on (keep right), unless it's at an end of the line, where buses loop through.
    keepR = CFG.get('keepRight', True)
    cands = []
    for k, sh in enumerate(sorted(r['shapes'], key=lambda s: -s['trips'])):
        if sh['trips'] / total < 0.03 and k: continue   # a handful of trips a day (garage runs, detours)
        line = LineString([m(*c) for c in sh['coords']])
        if line.length < 200: continue
        L = line.length
        cs = []
        if r['id'] in rapid_ids:   # platforms in order, from the schedule; each serves one direction
            for sid in sh.get('stops', []):
                if sid not in stops: continue
                p = Point(*m(stops[sid][2], stops[sid][3]))
                cs.append([round(line.project(p)), sid, True, False, None])
            cands.append((sh, line, cs))
            continue
        for s in on_route:
            p = Point(*m(s[2], s[3]))
            dist = line.distance(p)
            end = line.project(p) < 120 or line.project(p) > L - 120
            if dist > (70 if end else 25): continue
            off, d, (dx, dy) = side_of(line, p)
            right = off < 0 if keepR else off > 0
            if not (end or abs(off) <= 6 or right): continue
            cs.append([round(d), s[0], right, end, turn(dx, dy)])
        cands.append((sh, line, cs))
    dirs_right = {}   # stop -> directions it's on the right-hand side for
    dirs_any = {}
    for sh, line, cs in cands:
        for d, sid, right, end, w in cs:
            dirs_any.setdefault(sid, set()).add(sh['dir'])
            if right and not end: dirs_right.setdefault(sid, set()).add(sh['dir'])
    for sh, line, cs in cands:
        L = line.length
        seq = []
        for d, sid, right, end, w in cs:
            if len(dirs_any[sid]) > 1 and not end and dirs_right.get(sid) and sh['dir'] not in dirs_right[sid]: continue
            seq.append([d, sid])
            if w is None: continue
            stop_side.setdefault(sid, {}).setdefault(w, 0)
            stop_side[sid][w] += sh['trips']
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
        p.update(story(line, 110 if r['id'] in rapid_ids else 18))   # a tunnel's drawn line strays further from the street above
        # A route that ends at a station connects there, even when its loop sits a little off the platform.
        if st_end and not any(n == st_end[0] for _, n, _ in p['stations']):
            p['stations'].append([seq[-1][0], st_end[0], st_end[1]])
        if r['id'] in rapid_ids:
            # A line's own stations are its stops ("calls"); its connections are the stations where other lines meet.
            # Main streets it crosses don't apply underground. Direction: the platforms' own word (Eastbound).
            p['calls'] = []
            for d, sid in seq:
                q = Point(*m(stops[sid][2], stops[sid][3]))
                near_st = min(stations, key=lambda x: x[2].distance(q))
                name = near_st[0] if near_st[2].distance(q) < NEAR.get('platform', 300) else station_of(stops[sid][1])
                p['calls'].append([d, name])
            # A line's own system isn't a connection: the line itself, and the lines grouped with it (routes.json page
            # "lineGroups": on BART's Yellow, Red and Green at Daly City are the same platforms, not a change).
            own = {r['short']}
            for grp in (CFG.get('page', {}).get('lineGroups') or {}).values():
                if r['short'] in grp: own |= set(grp)
            p['stations'] = [[d, n, [l for l in lines if l not in own]] for d, n, lines in p['stations'] if [l for l in lines if l not in own]]
            p['cross'] = []
            words = [w for _, sid in seq for w in [pdir(stops[sid][1])] if w]
            if words: p['head'] = max(set(words), key=words.count); p['_w'] = 1
        pats.append(p)
        LAST_STOPS.add(seq[-1][1])
        for d, sid in seq:
            stop_routes.setdefault(sid, {}).setdefault(rid, []).append([p['k'], d])
    if not pats: continue
    # A rapid pattern whose platforms carry no direction word (the J's short run on Church St) takes the word of
    # the line's pattern in the same direction that has one (outbound, not "south").
    for p in pats:
        if r['id'] in rapid_ids and not p.get('_w'):
            q = next((q for q in pats if q.get('_w') and q['dir'] == p['dir']), None)
            if q: p['head'] = q['head']
    for p in pats: p.pop('_w', None)
    # Loops: a pattern that ends away from a station, where a pattern the other way starts (the same stop or
    # within ~150 m), carries on as that pattern: the 88 ends its eastbound trip inside Thorncliffe Park and
    # leaves again westbound for St Clair. The page lets a rider near the end of the first ride on through.
    for p in pats:
        if p['to'] in STATION_NAMES: continue   # ends at a station: everyone gets off there
        if r['id'] in rapid_ids: continue        # a train's last stop is the end of the ride (the N at Ocean Beach)
        e = stops[p['stops'][-1][1]]
        best = None
        for q in pats:
            if q['dir'] == p['dir']: continue
            f = stops[q['stops'][0][1]]
            gap = math.hypot((e[2] - f[2]) * KX, (e[3] - f[3]) * KY)
            if gap <= 150 and (best is None or q['trips'] > best['trips']): best = q
        if best: p['next'] = best['k']
    doc = {'r': mt['r'], 'n': mt['n'], 'm': r['mode'], 'f': mt.get('f', []), 'h': mt.get('h'),
           'stops': {sid: stops[sid][1] for p in pats for _, sid in p['stops']},
           'patterns': pats}
    json.dump(doc, open(os.path.join(OUT, 'data', 'r', rid + '.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
    # For the list of stops near someone: each pattern's direction, end, length, share of trips, the regions it
    # passes through and its subway connections (both with distances, so the page can start them at a stop).
    route_index[rid] = [mt['r'], mt['n'], r['mode'], mt.get('f', []), mt.get('h'),
                        [[p['head'], p['to'], round(p['km'] * 1000), p['share'], p['regions'],
                          [[d, n, lines] for d, n, lines in p['stations']], p.get('next'), p['dir']] for p in pats]]

# The stops list: [id, name, lon, lat, side ("East side"...), {route: [patterns]}]
out_stops = []
for sid, rs in stop_routes.items():
    s = stops[sid]
    sides = stop_side.get(sid, {})
    w = max(sides, key=sides.get) if sides else None
    # [id, name, lon, lat, side, travel direction, {route: [[pattern, d]...]}, code on the pole ('' if none)]
    # A platform: a stop only rapid lines use, or one at a station. A street stop a bus shares with a Muni Metro
    # line (Ocean Ave & Lee St: the K and the 29) is a bus stop, with its side of the street.
    plat = any(k in rapid_ids for k in rs) and (all(k in rapid_ids for k in rs) or pdir(s[1]) is not None or
           min(x[2].distance(Point(*m(s[2], s[3]))) for x in stations) < NEAR.get('platform', 300))
    if plat:   # a platform: its direction from its own name (Eastbound Platform), or the line it starts
        w = wm = pdir(s[1])
        if not wm:   # a terminal's platform ("Kennedy Station - Subway Platform"): the way the line leaves it
            k0 = next(((rid_, pk) for rid_, v in rs.items() for pk, d in v if d < 50), None)
            w = route_index[k0[0]][5][k0[1]][0] if k0 and k0[0] in route_index else None
        if not w and sid not in LAST_STOPS:
            # A stop along a line with no word in its name (a Muni Metro stop on Judah St, Glen Park's platform):
            # its patterns' way, if they agree. Not where a pattern ends: a terminal's arrival platform has no way.
            heads = {route_index[rid_][5][pk][0] for rid_, v in rs.items() if rid_ in route_index and rid_ in rapid_ids for pk, d in v}
            w = heads.pop() if len(heads) == 1 else None
        side = f'{dir_label(w)} platform' if w else 'Platform'
        # The agency's own words for a platform's direction, as its signs say them (routes.json "platformLabels":
        # New York's "Uptown & The Bronx", from the MTA's stations list, keyed by the stop id without its N or S).
        # A platform numbered in its stop id (routes.json "platformNumber", a pattern: BART's M20-1 is Montgomery's
        # Platform 1), as the agency's signs number them, where its lines go different ways.
        if CFG.get('platformNumber') and side == 'Platform':
            pn = re.search(CFG['platformNumber'], sid)
            if pn: side = f'Platform {pn.group(1)}'
        if PLABELS and sid[-1:] in PLABELS['suffix'] and PLABELS['labels'].get(sid[:-1], {}).get(sid[-1]) not in (None, '', *PLABELS['skip']):
            lab = PLABELS['labels'][sid[:-1]][sid[-1]]
            # "Uptown platform"; a place reads as where the trains are bound: "Manhattan-bound platform"
            side = f'{lab} platform' if re.search(r'(?i)(town|bound)$', lab) else f'{lab}-bound platform'
    else:
        side = SIDE.get(w, '')
    name = s[1]
    if plat:   # a platform goes by its station's name on the map (Bloor-Yonge, not "Bloor" and "Yonge" for its two lines)
        q = Point(*m(s[2], s[3]))
        st = min(stations, key=lambda x: x[2].distance(q))
        if st[2].distance(q) < NEAR.get('platform', 300): name = st[0] + (f' - {dir_label(wm)} Platform' if wm else ' - Platform')
    # [id, name, lon, lat, side, travel direction, {route: [[pattern, d]...]}, code on the pole ('' if none), platform 1/0]
    out_stops.append([sid, name, s[2], s[3], side, w or '', {k: sorted(v) for k, v in rs.items()}, s[5] if len(s) > 5 and not plat else '', 1 if plat else 0])
json.dump({'asof': TRANSIT.get('asof'), 'week': TRANSIT.get('week'), 'routes': route_index, 'stops': out_stops},
          open(os.path.join(OUT, 'data', 'stops.json'), 'w'), separators=(',', ':'), ensure_ascii=False)

# When each route runs at each stop (raw/surface/sched.json, written by fetch_surface.py when surface.json has
# "sched"), for "next bus at 5:42 am" when there are no live times: only the stops and routes on this page. Split
# into SCHED_N files by stop id (data/sched/<bucket>.json, each with the span lists its stops use), so the page
# fetches a few kilobytes for the stops on screen rather than the whole city's timetable.
SCHED_N = 128
def bucket(sid):   # the same in the page and in apps (DATA_CONTRACT.md section 15)
    h = 0
    for ch in sid: h = (h * 31 + ord(ch)) % SCHED_N
    return h
SCHED = None
sp = os.path.join(RAW, 'surface', 'sched.json')
sd = os.path.join(OUT, 'data', 'sched')
if os.path.isdir(sd):
    for f in os.listdir(sd): os.remove(os.path.join(sd, f))
if os.path.exists(sp):
    sc = json.load(open(sp))
    head = {k: sc[k] for k in ('fetched', 'feed', 'tz', 'gap', 'days', 'week')}
    parts = [({}, {}, []) for _ in range(SCHED_N)]   # stops, span remap, span lists
    for st in out_stops:
        keep, remap, spans = parts[bucket(st[0])]
        row = {}
        for rid in st[6]:
            v = sc['stops'].get(st[0], {}).get(rid)
            if v is None: v = sc['stops'].get(st[0], {}).get(SHORT.get(rid, rid))
            if v is None: continue
            for i in v:
                if i not in remap: remap[i] = len(spans); spans.append(sc['spans'][i])
            row[rid] = [remap[i] for i in v]
        if row: keep[st[0]] = row
    os.makedirs(sd, exist_ok=True)
    for b, (keep, _, spans) in enumerate(parts):
        json.dump(dict(head, spans=spans, stops=keep), open(os.path.join(sd, f'{b}.json'), 'w'), separators=(',', ':'))
    SCHED = {'url': 'data/sched/{b}.json', 'n': SCHED_N}
    sizes = sorted(os.path.getsize(os.path.join(sd, f)) for f in os.listdir(sd))
    print(f'sched: {sum(len(p[0]) for p in parts)} stops in {SCHED_N} files, {sizes[0]}-{sizes[-1]} bytes each')

# An agency whose live trip updates name trips, not routes (BART): its trip -> route table, for the arrivals function
# (functions/api/arrivals.js "tripRoutes"), at data/<feed>_trips.json.
for fd in CFG.get('rapidFeeds', []):
    tp = os.path.join(RAW, 'surface', fd, 'trip_routes.json')
    if os.path.exists(tp):
        tr = json.load(open(tp))['trips']
        json.dump({'routes': sorted(set(tr.values())), 'trips': tr}, open(os.path.join(OUT, 'data', fd + '_trips.json'), 'w'), separators=(',', ':'))
        print(f'{fd}_trips.json: {len(tr)} trips')

# ---- the page ----
if not os.path.exists(os.path.join(ROOT, 'engine', 'routes', 'page.html')): sys.exit(print(f'{city}: {len(route_index)} routes, {len(out_stops)} stops (no page template yet)'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from theme import SCRIPT as THEME_SCRIPT, css as theme_css   # dark theme, as the guides and venue pages have
DARK_MAP = ['body{--m-t0:#40262B;--m-t1:#3B3326;--m-t2:#28362A;--m-t3:#253140;--water:#18232B;--m-city:#24272D;--m-out:#1C1F24;--m-edge:#3A3E45;--m-hood:#3A2328;--m-hoodline:#4A3A3E;'
            '--m-major:#4A4E56;--m-minor:#363A41;--m-halo:#15171B;--pill-line:#373B42;--sub:#9AA0A8}',
            '.rb:not(.tram):not(.exp):not(.cable){background:var(--card)}', '.row:hover{background:#262A30}', '.tl li.on{background:#262A30}']
tpl = open(os.path.join(ROOT, 'engine', 'routes', 'page.html'), encoding='utf-8').read()
css_p = os.path.join(ROOT, 'cities', city, 'factsheet.css')
page = dict(CFG['page'])
cfg_out = {k: v for k, v in page.items()}
cfg_out['known'] = CFG.get('known')
cfg_out['live'] = CFG.get('live')   # live arrivals: {api}, served by functions/api/arrivals.js
cfg_out['sched'] = SCHED   # scheduled times, when there are no live ones: {url, n}
cfg_out['the'] = CFG.get('regionsWithThe', [])
cfg_out['theKnown'] = CFG.get('knownWithThe')   # a pattern: known-as names that take "the"
html = (tpl.replace('{{RS}}', json.dumps(cfg_out, ensure_ascii=False))
        .replace('{{css}}', open(css_p, encoding='utf-8').read() if os.path.exists(css_p) else '')
        .replace('{{title}}', page['title']).replace('{{city}}', page['city'])
        .replace('{{description}}', page['description']).replace('{{lede}}', page['lede'])
        .replace('{{placeholder}}', page['placeholder']).replace('{{credits}}', page['credits'])
        .replace('{{mapLink}}', page.get('mapLink', 'Open on the map'))
        .replace('{{themeScript}}', THEME_SCRIPT).replace('{{themeCss}}', theme_css(DARK_MAP)))
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)
print(f'{city} routes page: {len(route_index)} routes, {len(out_stops)} stops')
