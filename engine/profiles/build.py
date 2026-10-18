"""Fact sheets: neighbourhood profiles, printable, one page each.

One small JSON file per neighbourhood with everything a one-page profile shows, so the page itself
only reads and draws, every visitor sees the same numbers, and a printed copy matches the screen.

Usage:  python3 engine/profiles/build.py toronto
Reads:  cities/<city>/factsheet.json (the city's settings and wording) and factsheet.css (its badge colours)
        docs/<city>/data/*  (the same published files the map uses, so the two never disagree)
Writes: docs/<city>/profiles/index.html             the page (engine/profiles/page.html with the city's settings)
Writes: docs/<city>/profiles/data/index.json        {asof, places: [{slug, name}]}, for the picker
        docs/<city>/profiles/data/<slug>.json       one profile each

Rules carried over from the map:
- Facilities, never people: no language, origin or other demographic rows. Census figures used here
  (commuting, canopy) keep their year.
- Counts are of what's on the map, inside the neighbourhood's boundary (the City's official one,
  which can be bigger than the name's everyday use). Stations, libraries and campuses also count
  when they sit just outside it (within NEAR_KM): one across the street still serves the area.
- Times are the map's own: transit to the city's hub ("hub" in factsheet.json) from its profiles file. Drive times come from
  cities/<city>/raw/drive_profiles.json (fetch_drive.py: free-flow, from each neighbourhood); without it,
  drive rows are left out rather than guessed.
  Walks to the nearest station are straight-line distance x 1.3 at 4.8 km/h, shown as "about".

Needs: pip install shapely  (already needed by cities/<city>/run.sh)
"""
import heapq, html, json, math, os, re, sys, unicodedata
from datetime import date
import shapely
from shapely.geometry import shape, Point, box
from shapely import clip_by_rect, make_valid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import settings, units_file, station_keys, Units

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: build.py <city>')
D = os.path.join(ROOT, 'docs', city, 'data')
OUT = os.path.join(ROOT, 'docs', city, 'profiles', 'data')
NEAR_KM = 0.15        # a station or library this close to the boundary counts (stations on a
                      # boundary street, such as Bloor, sit just outside the line)
MIN_ROUTE_KM = 0.2    # a streetcar route counts only if this much of it runs inside
WALK_MAX_KM = 2.5     # beyond this, give the nearest station's distance rather than a walk time
PAD = 0.14            # map frame: margin around the neighbourhood, as a share of its size
VIEW_W = 600          # map viewBox width; height follows the neighbourhood's shape
CFG = settings(city)
LBL = CFG.get('labels', {})
U = Units(CFG.get('distance', 'km'))
HUB = CFG.get('hub', {})
RAIL = CFG.get('rail', {})


def lbl(key, default):
    return LBL.get(key, default)


def load(name):
    with open(os.path.join(D, name)) as f:
        return json.load(f)


def opt(name, default):
    return load(name) if os.path.exists(os.path.join(D, name)) else default


def slug(s):
    s = re.sub(r"['’]", '', s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# ---- one flat projection in km for the whole city (good to well under 1% across a city) --------
hood_feats = opt(units_file(CFG), {'features': []})['features']
if not hood_feats:
    sys.exit(f'{city}: no {units_file(CFG)}')
LAT0 = sum(shape(f['geometry']).centroid.y for f in hood_feats) / len(hood_feats)
KX, KY = 111.32 * math.cos(math.radians(LAT0)), 110.574


def km(g):
    return shapely.transform(g, lambda c: c * [KX, KY])


def layer(name):
    """[(geometry in km, properties)] for a published layer; empty if the city doesn't have it."""
    return [(km(make_valid(shape(f['geometry']))), f['properties'])
            for f in opt(name + '.geojson', {'features': []})['features']]


census = opt(CFG.get('census', 'nbhd_profiles.json'), {})
nearby = opt('nearby.json', {'groups': {}})['groups']

stations = layer('subway_stations')
subway_lines = layer('subway_lines')
streetcars = layer('streetcars')
HAS = lambda name: os.path.exists(os.path.join(D, name + '.geojson'))
bikes = layer('bikes')
bikeshare = layer('bikeshare')
go = layer(RAIL['file']) if RAIL.get('file') else []
heritage = layer('heritage_buildings')
landmarks = layer('landmarks')
institutions = layer('institutions')
french = layer('french_schools')
bus_routes = [(g, m) for g, m in layer('transit_routes') if m.get('m') == 'bus' and 'night' not in m.get('f', [])]


RAW = os.path.join(ROOT, 'cities', city, 'raw')


def raw(name):
    p = os.path.join(RAW, name)
    return json.load(open(p)) if os.path.exists(p) else None


def group(name):
    """A nearby.json group as [(point in km, label or None)]."""
    return [(km(Point(p[0], p[1])), p[2] if len(p) > 2 else None) for p in nearby.get(name, [])]


G = {k: group(k) for k in nearby}
FAITH = [k for k in G if k in ('church', 'mosque', 'synagogue', 'hindu', 'gurdwara', 'buddhist')
         or k.startswith('church:')]


# ---- transit: routes and stops (transit.json), the station graph, the walk grid -----------------
transit = opt('transit.json', {'routes': [], 'stops': []})
ROUTES = transit['routes']
STOPS = [(km(Point(s[0], s[1])), s[3] if len(s) > 3 else []) for s in transit['stops']]
WALK_GRID = os.path.join(OUT, 'walk_grid.json')
wgrid = json.load(open(WALK_GRID)) if os.path.exists(WALK_GRID) else None
HUBS = CFG.get('hubs', [])
LONG_WALK_MIN = 30   # past this, a walk time stops being useful: give the distance instead
TRANSFER = CFG.get('transferStops', 3)   # a change of line "costs" this many stops when choosing the best way to a hub


SNAME = station_keys([{'properties': m} for _, m in stations])   # unique in the city (see common.station_keys)
for (_, m), key in zip(stations, SNAME):
    m['key'] = key
WALK = '~walk'   # an edge between two stations of one name a short walk apart (New York's Fulton St): a change


def station_graph():
    """Stations in order along each line: {station index: [(neighbour index, line)]}.

    With cities/<city>/raw/subway_patterns.json (lists of station points in the order one service calls at
    them, such as the A train to Far Rockaway, and pairs of points with a free transfer between them), each
    service's stops in that order; otherwise each line's
    stations in order along its drawn line, which suits lines without branches or express runs."""
    adj = {k: [] for k in range(len(stations))}
    pat = raw('subway_patterns.json')
    if pat:
        at = {(round(g.x / KX, 5), round(g.y / KY, 5)): k for k, (g, _) in enumerate(stations)}
        for p in pat['patterns']:
            ks = [at.get((round(x, 5), round(y, 5))) for x, y in p['stops']]
            ks = [k for k in ks if k is not None]
            for a, b in zip(ks, ks[1:]):
                if a != b and (b, p['line']) not in adj[a]:
                    adj[a].append((b, p['line'])); adj[b].append((a, p['line']))
        for x, y in pat.get('transfers', []):   # free transfers between stations mapped apart
            a, b = at.get(tuple(round(v, 5) for v in x)), at.get(tuple(round(v, 5) for v in y))
            if a is not None and b is not None and (b, WALK) not in adj[a]:
                adj[a].append((b, WALK)); adj[b].append((a, WALK))
    else:
        for g, m in subway_lines:
            line = m.get('line')
            on = sorted((g.project(sg), k) for k, (sg, sm) in enumerate(stations) if line in sm.get('lines', []))
            for (_, a), (_, b) in zip(on, on[1:]):
                adj[a].append((b, line)); adj[b].append((a, line))
    # Platforms of one station complex mapped as separate stations (New York's two Fulton Sts): one name within
    # 350 m, or any two within 200 m, are a walk apart (the patterns file can also list transfers).
    for i in range(len(stations)):
        for j in range(i + 1, len(stations)):
            d = stations[i][0].distance(stations[j][0])
            if (d < 0.2 or (d < 0.35 and stations[i][1]['name'] == stations[j][1]['name'])) and (j, WALK) not in adj[i]:
                adj[i].append((j, WALK)); adj[j].append((i, WALK))
    return adj


SADJ = station_graph()


def to_hubs(k):
    """[[stops, changes] or None per hub] from station k, fewest stops with changes weighed in."""
    best = {}
    heap = [(0, 0, 0, k, l) for l in stations[k][1].get('lines', [])]
    seen = set()
    while heap:
        cost, n, ch, i, line = heapq.heappop(heap)
        if (i, line) in seen:
            continue
        seen.add((i, line))
        if SNAME[i] not in best:
            best[SNAME[i]] = [n, ch]
        for j, l in SADJ[i]:
            if l == WALK:   # walk to the other platforms and board any of their lines: a change, no stop
                for l2 in stations[j][1].get('lines', []):
                    heapq.heappush(heap, (cost + TRANSFER, n, ch + 1, j, l2))
                continue
            extra = 0 if l == line else TRANSFER
            heapq.heappush(heap, (cost + 1 + extra, n + 1, ch + (l != line), j, l))
    return [best.get(h) for h in HUBS]


HUB_TABLE = {SNAME[k]: to_hubs(k) for k in range(len(stations))} if stations else {}


def hub_text(v):
    if v is None:
        return 'Not on the subway'
    n, ch = v
    if n == 0:
        return 'You’re there'
    return f"{n} stop{'s' if n != 1 else ''}" + (f" · {ch} change{'s' if ch != 1 else ''}" if ch else '')


def grid_cell(lon, lat):
    if not wgrid:
        return None
    c = int((lon - wgrid['lon0']) / wgrid['dlon']); r = int((lat - wgrid['lat0']) / wgrid['dlat'])
    if 0 <= c < wgrid['cols'] and 0 <= r < wgrid['rows']:
        return r * wgrid['cols'] + c
    return None


def grid_share(poly_ll, layer, minutes):
    """Share of the walk grid's squares inside the (lon/lat) polygon within `minutes` of `layer`."""
    if not wgrid or layer not in wgrid['layers']:
        return None
    L = wgrid['layers'][layer]['min']
    w, s, e, n = poly_ll.bounds
    c0, c1 = int((w - wgrid['lon0']) / wgrid['dlon']), int((e - wgrid['lon0']) / wgrid['dlon'])
    r0, r1 = int((s - wgrid['lat0']) / wgrid['dlat']), int((n - wgrid['lat0']) / wgrid['dlat'])
    from shapely.prepared import prep
    pp = prep(poly_ll)
    have = near = 0
    for r in range(max(0, r0), min(wgrid['rows'], r1 + 1)):
        for c in range(max(0, c0), min(wgrid['cols'], c1 + 1)):
            lon = wgrid['lon0'] + (c + 0.5) * wgrid['dlon']; lat = wgrid['lat0'] + (r + 0.5) * wgrid['dlat']
            if pp.contains(Point(lon, lat)):
                v = L[r * wgrid['cols'] + c]
                have += 1
                near += v is not None and v <= minutes
    return round(100 * near / have) if have else None


def listing(items, keep=3):
    items = list(items)
    if not items:
        return 'None'
    return ', '.join(items[:keep]) + (f' +{len(items) - keep} more' if len(items) > keep else '')


HAS_TRAMS = any(r.get('m') == 'tram' for r in ROUTES)


def transit_sections(P, poly_ll, ll, lp, c, st_names, shares, docks, bike_km, name):
    lines_at = {m['key']: m.get('lines', []) for _, m in stations}
    # 01 subway and LRT
    spot = {m['key']: g for g, m in stations}
    ranked = sorted(st_names, key=lambda n: (-len(lines_at[n]), lp.distance(spot[n])))   # interchanges first, then nearest
    sub = [[n, {'lines': lines_at[n]}] for n in ranked]   # the page draws each line's coloured bullet
    origin, origin_walk = None, None
    if st_names:
        origin = ranked[0]
    else:
        k = grid_cell(ll.x, ll.y)
        L = wgrid['layers'].get('subway') if wgrid else None
        if L and k is not None and L['min'][k] is not None and L['min'][k] <= LONG_WALK_MIN:
            origin, origin_walk = L['names'][L['src'][k]], f"about {L['min'][k]} min walk"
        elif stations:
            d, _, m = nearest(lp, stations)
            origin = m['key']
            origin_walk = f'about {walk_min(d)} min walk' if walk_min(d) <= LONG_WALK_MIN else f'{fmt_km(d)} away'
    rows1 = sub[:4] + ([['More stations', f'+{len(sub) - 4}']] if len(sub) > 4 else [])
    if not sub and origin:
        rows1.append(['Nearest station', f'{origin} · {origin_walk}', {'lines': lines_at.get(origin, [])}])
    share = grid_share(poly_ll, 'subway', 10)
    if share is not None:
        rows1.append(['Area within a 10-min walk of a station', f'{share}%'])
    if not rows1:
        rows1 = [['Stations', 'None']]

    # 02 buses and streetcars: every route stopping inside the boundary
    served = sorted({i for g, rs in STOPS if P.contains(g) for i in rs}, key=lambda i: route_key(ROUTES[i]['r']))
    # route badges, styled on the page like the map's (TTC conventions): {r: number, n: name, m: mode, f: families}
    badge = lambda r: {'r': r['r'], 'n': r['n'], 'm': r.get('m'), 'f': r.get('f', [])}
    badges = lambda rs_: {'routes': [badge(r) for r in rs_]} if rs_ else 'None'
    rs = [ROUTES[i] for i in served if ROUTES[i].get('m') != 'go']
    cars = [r for r in rs if r.get('m') == 'tram' and 'night' not in r.get('f', [])]
    freq = [r for r in rs if r.get('m') == 'bus' and 'freq' in r.get('f', [])]
    exp = [r for r in rs if r.get('m') == 'bus' and 'exp' in r.get('f', []) and 'freq' not in r.get('f', [])]
    night = [r for r in rs if 'night' in r.get('f', [])]
    other = [r for r in rs if r.get('m') == 'bus' and not set(r.get('f', [])) & {'freq', 'exp', 'night'}]
    gobus = [r for r in (ROUTES[i] for i in served) if r.get('m') == 'go']
    rows2 = [['Streetcars', badges(cars)]] if HAS_TRAMS else []
    rows2.append(['Frequent buses (10 min or better)', badges(freq)])
    if exp:
        rows2.append(['Express buses', badges(exp)])
    rows2 += [['Other daytime buses', badges(other)], [lbl('overnight', 'Overnight'), badges(night)]]
    if gobus:
        rows2.append([lbl('railRoutes', 'Regional buses and trains stopping here'), badges(gobus)])
    share = grid_share(poly_ll, 'stop', 5)
    if share is not None:
        rows2.append(['Area within a 5-min walk of a stop', f'{share}%'])

    # 03 to the hubs, from the neighbourhood's best-connected station (or the nearest one)
    rows3 = [[h, hub_text(v), *([{'lines': lines_at.get(h, [])}] if CFG.get('hubBullets', True) else [])]
             for h, v in zip(HUBS, HUB_TABLE.get(origin, [None] * len(HUBS)))] if origin else []
    if HUB.get('field') and c.get(HUB['field']) is not None:
        rows3.append([f"Door to door to {HUB['name']}, typical", f"about {c[HUB['field']]} min"])
    title3 = f'From {origin} to the hubs' + (f' ({origin_walk})' if origin_walk else '') if origin else 'To the hubs'

    # 04 GO, cycling and driving
    rows4 = []
    k = grid_cell(ll.x, ll.y)
    G_ = wgrid['layers'].get('go') if wgrid else None
    rail_meta = [{'go': True}] if RAIL.get('badge') else []
    if G_ and k is not None and G_['min'][k] is not None and G_['min'][k] <= LONG_WALK_MIN:
        rows4.append([RAIL['nearest'], f"{G_['names'][G_['src'][k]]} · about {G_['min'][k]} min walk", *rail_meta])
    elif go:
        d, _, m = nearest(lp, go)
        if d <= U.radius_km(RAIL.get('within', 1e9)):   # "within": past this (city's unit), no nearest station row
            rows4.append([RAIL['nearest'], f"{m['name']} · {fmt_km(d)}", *rail_meta])
    if bikeshare:
        rows4.append([lbl('bikeshare', 'Bike share stations'), f'{len(shares)} · {docks} docks' if shares else 'None'])
    rows4.append([lbl('bikeLanes', 'Bike lanes and trails'), U.length(bike_km)])
    if drive_to(name, 0) is not None:
        rows4.append([f'Drive to {DRIVE_DEST[0]}', f'about {drive_to(name, 0)} min'])

    return {'origin': origin, 'sections': [
        {'title': lbl('subwaySection', 'Subway'), 'rows': rows1},
        {'title': lbl('busSection', 'Buses'), 'rows': rows2},
        {'title': title3, 'rows': rows3},
        {'title': lbl('railSection', 'Rail, cycling and driving'), 'rows': rows4},
    ]}


# ---- driving: highways, arterials, on-ramps (raw/ramps.json) and drive times (raw/drive_profiles.json)
highways = layer('highways') + [(g, m) for g, m in layer(CFG.get('regionHighways', 'region_highways'))]   # the city's own, then the region's
drive_prof = raw('drive_profiles.json')
# A station destination is named without "Station" ("Union"), unless "drive.keepStation" (New York's "Penn Station")
dest_name = lambda n: n if CFG.get('drive', {}).get('keepStation') else n.replace(' Station', '')
DRIVE_DEST = [dest_name(d['name']) for d in drive_prof['destinations']] if drive_prof else []


def drive_to(name, k):
    if not drive_prof:
        return None
    row = drive_prof['hoods'].get(name)
    return row[k] if row and k < len(row) else None


# Main roads: a raw file of the city's road classes ({class: FeatureCollection}, "arterials.raw"), or published
# layers whose every street is one class ("arterials.layers": {"streets": "major", "collectors": "collector"}).
ART = CFG.get('arterials', {})
if ART.get('raw'):
    streets_raw = raw(ART['raw']) or {}
    arterials = [(km(make_valid(shape(f['geometry']))), ART['classes'][cls], (f['properties'].get(ART.get('name', 'name')) or '').strip())
                 for cls, fc in streets_raw.items() if cls in ART['classes'] for f in fc.get('features', []) if f.get('geometry')]
else:
    arterials = [(g, cls, (m.get('name') or '').strip()) for lname, cls in ART.get('layers', {}).items() for g, m in layer(lname)]


# The map frames draw arterials as a few long merged lines rather than thousands of block-length pieces.
from shapely.ops import linemerge, unary_union as _union
ART_DRAW = linemerge(_union([g for g, cls, _ in arterials if cls != 'collector'])) if arterials else None


def hwy_near(pt, limit):
    """(route, km) of the closest highway within limit km of pt, else None."""
    best = None
    for g, m in highways:
        d = g.distance(pt)
        if d <= limit and (best is None or d < best[1]):
            best = (m.get('route'), d)
    return best


def street_near(pt, limit=0.25):
    best = None
    for g, cls, nm in arterials:
        if not nm or cls == 'collector':
            continue
        d = g.distance(pt)
        if d <= limit and (best is None or d < best[1]):
            best = (nm, d)
    return best[0] if best else None


def find_onramps():
    """On-ramps, from OSM's slip roads (raw/ramps.json).

    OSM draws one ramp as several connected pieces, and the map's highway lines are simplified
    centrelines (the 401's collector lanes run 100-150 m off them), so "which end is on the highway"
    can't be judged by distance. What can: a ramp chain starts or ends exactly on a street. So pieces
    are joined into chains by shared ends; a chain end within STREET_M of an arterial or collector is
    its street end; the piece touching it says the direction (it leaves the street: on-ramp; it
    arrives: off-ramp); the highway is the one nearest the chain's other ends. One access point per
    highway and street: [(point in km, route, street)]."""
    data = raw('ramps.json')
    if not data:
        return []
    STREET_KM, HWY_KM = 0.03, 0.4
    key = lambda c: (round(c[0], 6), round(c[1], 6))
    ways = []
    for link in data['links']:
        cs = link['coords'][::-1] if link.get('oneway') == '-1' else link['coords']
        if len(cs) >= 2:
            ways.append((cs, link.get('oneway') != 'no'))
    # chains: union-find over pieces that share an end
    parent = list(range(len(ways)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    at = {}
    for i, (cs, _) in enumerate(ways):
        for c in (cs[0], cs[-1]):
            at.setdefault(key(c), []).append(i)
    for idx in at.values():
        for j in idx[1:]:
            parent[find(j)] = find(idx[0])
    chains = {}
    for i in range(len(ways)):
        chains.setdefault(find(i), []).append(i)
    groups = {}
    for members in chains.values():
        ends = {}
        for i in members:
            cs, _ = ways[i]
            for c, first in ((cs[0], True), (cs[-1], False)):
                ends.setdefault(key(c), []).append((i, first))
        loose = [(k, v) for k, v in ends.items() if len(v) == 1]            # the chain's own ends
        pts = {k: km(Point(*k)) for k, _ in loose}
        street_ends = [(k, v[0]) for k, v in loose if street_near(pts[k], STREET_KM)]
        other = [pts[k] for k, _ in loose if k not in dict(street_ends)]
        if street_ends and not other and len(loose) > 1:
            # every end is near a street (the Gardiner over Lake Shore, a highway beside an arterial):
            # the end closest to a highway is the highway end
            dist = {k: (hwy_near(pts[k], HWY_KM) or (None, 9))[1] for k, _ in loose}
            h = min(dist, key=dist.get)
            street_ends = [(k, v) for k, v in street_ends if k != h]
            other = [pts[h]]
        if not street_ends or not other:
            continue
        hwy = min((h for h in (hwy_near(q, HWY_KM) for q in other) if h), key=lambda h: h[1], default=None)
        if not hwy:
            continue
        for k, (i, first) in street_ends:
            if ways[i][1] and first:                                        # the piece leaves the street
                street = street_near(pts[k], STREET_KM)
                groups.setdefault((hwy[0], street), []).append(pts[k])
    out = []
    for (route, street), ps in groups.items():
        x = sum(p.x for p in ps) / len(ps); y = sum(p.y for p in ps) / len(ps)
        out.append((Point(x, y), route, street))
    return out


ONRAMPS = find_onramps()
HWY_NAME = {m.get('route'): m.get('name') for g, m in highways}


def hwy_kind(m):
    """Shield style, as on the map: provincial (yellow), city expressway (green) or toll (blue)."""
    return 'toll' if m.get('toll') is True or 'toll' in (m.get('name') or '').lower() else 'city' if m.get('kind') == 'city' else 'prov'


HWY_KIND = {m.get('route'): hwy_kind(m) for g, m in highways}
RAMP_R = CFG.get('drive', {}).get('rampRadius', 8)   # list a highway only if one of its on-ramps is this close (city's unit)
RAMP_KM = U.radius_km(RAMP_R)

# Parking and charging: the map's own layers (cities/<city>/parking.py)
parking = layer('parking')
greenp = [(g, m) for g, m in parking if m.get('c') == 'gp']
chargers = [(g, m) for g, m in parking if m.get('c') == 'ev' and not m.get('off')]   # leave out "temporarily unavailable"
permit_areas = layer('permit_areas')


def driving_sections(P, lp, name, c):
    # 01 highway access: the nearest on-ramp to each highway, closest first
    best = {}
    for pt, route, street in ONRAMPS:
        d = lp.distance(pt)
        if d <= RAMP_KM and (route not in best or d < best[route][0]):
            best[route] = (d, street)
    rows1 = [[f'at {street}', fmt_km(d), {'hwy': route}] for route, (d, street) in sorted(best.items(), key=lambda kv: kv[1][0])[:5]]
    if not rows1:
        rows1 = [['Highway on-ramps', 'Not built yet (run fetch_drive.py)' if not ONRAMPS else f'None within {U.radius(RAMP_R)}']]
    through = sorted({m.get('route') for g, m in highways if g.intersection(P).length > 0.2})
    if through:
        rows1.append([f"Highways through the {CFG.get('page', {}).get('unit', 'neighbourhood')}", {'hwys': through}])

    # 02 drive times to the destinations
    rows2 = [[d, f'about {drive_to(name, k)} min'] for k, d in enumerate(DRIVE_DEST) if drive_to(name, k) is not None]
    if not rows2:
        rows2 = [['Drive times', 'Not built yet (run fetch_drive.py)']]

    # 03 parking and charging, from the map's parking layers
    rows3 = []
    if greenp:
        lots = [m for g, m in greenp if P.contains(g)]
        if lots:
            garages = sum(m.get('t') == 'g' for m in lots)
            rows3.append([lbl('parkingLots', 'City car parks'), f"{len(lots)} · {sum(m.get('cap') or 0 for m in lots):,} spaces",
                          {'gp': True}])
            if garages:
                rows3.append(['Of those, garages', str(garages)])
            ttc = [m for m in lots if m.get('ttc')]
            if ttc:
                rows3.append([lbl('commuterLots', 'Commuter lots'), str(len(ttc))])
        else:
            d, _, m = nearest(lp, greenp)
            rows3.append([lbl('parkingNearest', 'Nearest city car park'), f"{m['n']} · {fmt_km(d)}", {'gp': True}])
    if c.get('permit') is not None:
        codes = sorted({m.get('name') for g, m in permit_areas if g.intersection(P).area > 0.01 * P.area})
        share = c['permit']
        rows3.append(['Permit parking', 'None of the area' if not share else
                      f"{share}% of the area" + (f" · {listing(codes, 3)}" if codes else '')])
    if chargers:
        here = [m for g, m in chargers if P.contains(g)]
        l2 = sum(m.get('l2') or 0 for m in here)
        fast = [m for m in here if m.get('dc')]
        rows3.append(['EV charging sites', f'{len(here)} · {l2} Level 2 ports' if here else 'None', {'ev': True}])
        if fast:
            rows3.append(['DC fast charging', f"{len(fast)} site{'s' if len(fast) != 1 else ''} · {sum(m['dc'] for m in fast)} ports"])
        else:
            fc = [(g, m) for g, m in chargers if m.get('dc')]
            if fc:
                d, _, m = nearest(lp, fc)
                rows3.append(['Nearest DC fast charger', f"{m.get('a') or m.get('n')} · {fmt_km(d)}"])
    # (a city with no parking layers gets no parking section)

    # 04 roads: arterial and collector length inside the boundary, and the longest arterials
    length = {'major': 0.0, 'minor': 0.0, 'collector': 0.0}
    by_name = {}
    for g, cls, nm in arterials:
        if not g.intersects(P):
            continue
        l = g.intersection(P).length
        length[cls] += l
        if nm and cls != 'collector':
            by_name[nm] = by_name.get(nm, 0) + l
    main = [nm for nm, l in sorted(by_name.items(), key=lambda kv: -kv[1]) if l > 0.3][:3]
    present = {cls for _, cls, _ in arterials}
    rows4 = [[lbl('mainRoads', 'Main roads'), ', '.join(main) if main else 'None']]
    rows4 += [[label, U.length(length[cls])] for cls, label in lbl('roads', [['major', 'Major arterials'], ['minor', 'Minor arterials'],
                                                                          ['collector', 'Collector streets']]) if cls in present]
    for z in CFG.get('drive', {}).get('zones', []):   # a toll or charge zone: how much of the place is in it
        inside = sum(g.intersection(P).area for g, _ in layer(z['file'])) / P.area if P.area else 0
        rows4.append([z['label'], 'All of it' if inside > 0.97 else 'None of it' if inside < 0.01 else f'{round(100 * inside)}% of the area'])
    out = [{'title': 'Highway access', 'rows': rows1}, {'title': 'Drive times, empty roads', 'rows': rows2}]
    if rows3:
        out.append({'title': 'Parking and charging', 'rows': rows3})
    out.append({'title': 'Roads', 'rows': rows4})
    return out


def line_color(m):
    return m.get('color') or CFG.get('lineColors', {}).get(m.get('line'))


def walk_min(d_km):   # 1.3 x straight line at 4.8 km/h (3 mph)
    return max(1, round(d_km * 1.3 / 4.8 * 60))


def fmt_km(d):
    return U.dist(d)


def nearest(pt, items):
    return min(((pt.distance(g), g, m) for g, m in items), key=lambda t: t[0]) if items else None


def route_key(s):
    m = re.match(r'\d+', s)
    return int(m.group()) if m else 0


# ---- one profile --------------------------------------------------------------------------------
def build(feat):
    props = feat['properties']
    name = props['name']
    ll = Point(*props['lp']) if props.get('lp') else shape(feat['geometry']).representative_point()
    P = km(make_valid(shape(feat['geometry'])))
    lp = km(ll)
    near = P.buffer(NEAR_KM)
    count = lambda items: sum(1 for g, _ in items if P.contains(g))
    c = census.get(str(props.get('code')), {})

    # Getting around
    st = [m for g, m in stations if near.contains(g)]
    st_names = sorted({m['key'] for m in st})
    lines = sorted({l for m in st for l in m.get('lines', [])})
    cars = sorted({f"{m['r']} {m['n']}" for g, m in streetcars if g.intersection(P).length > MIN_ROUTE_KM},
                  key=route_key)
    bike_km = sum(g.intersection(P).length for g, _ in bikes)
    shares = [m for g, m in bikeshare if P.contains(g)]
    docks = sum(m.get('d') or 0 for m in shares)
    go_in = sorted({m['name'] for g, m in go if near.contains(g)})

    around = []
    if st_names:
        around.append([lbl('subwayStations', 'Subway stations'),
                       f"{len(st_names)} · Line{'s' if len(lines) > 1 else ''} {', '.join(lines)}"])
    elif stations:
        d, _, m = nearest(lp, stations)
        around.append([lbl('nearestSubway', 'Nearest subway'), f"{m['key']} · about {walk_min(d)} min walk" if d <= WALK_MAX_KM
                       else f"{m['key']} · {fmt_km(d)} away"])
    if go_in:
        around.append([RAIL['in'], ', '.join(go_in)])
    if HAS('streetcars'):
        around.append([lbl('streetcarRoutes', 'Streetcar routes'), ', '.join(cars) if cars else 'None'])
    if bikeshare:
        around.append([lbl('bikeshare', 'Bike share stations'), f'{len(shares)} · {docks} docks' if shares else 'None'])
    around.append([lbl('bikeLanes', 'Bike lanes and trails'), U.length(bike_km)])
    if HUB.get('field') and c.get(HUB['field']) is not None:
        around.append([f"Transit to {HUB['name']}", f"about {c[HUB['field']]} min"])
    if drive_to(name, 0) is not None:
        around.append([f'Drive to {DRIVE_DEST[0]}', f'about {drive_to(name, 0)} min'])

    # Parks and nature: the first row counts parks (also drawn on the map and counted at a glance)
    parks = [g for g, _ in G.get('park', []) if P.contains(g)]
    nature = [[label, str(len(parks)) if grp == 'park' else str(count(G.get(grp, [])))]
              for label, grp in lbl('nature', [['Parks', 'park'], ['Playgrounds', 'playground']])]
    if c.get('canopy') is not None:
        nature.append(['Tree canopy', f"{c['canopy']}%"])

    # Learning and community
    libs = sorted(n.replace(' branch', '') for g, n in G.get('library', []) if near.contains(g))
    learning = [
        [lbl('libraries', 'Library branches'), ', '.join(libs) if libs else 'None'],
        [lbl('centres', 'Community and rec centres'), str(count(G.get('centre', [])))],
    ]
    if HAS('french_schools'):
        learning.append([lbl('french', 'French-language schools'), str(count(french))])
    unis = sorted({m['name'] for g, m in institutions
                   if m.get('cat') in ('university', 'college') and near.contains(g)})
    if unis:
        learning.append(['Universities and colleges', ', '.join(unis)])
    er = nearest(lp, G.get('er', []))
    if er:
        learning.append(['Nearest emergency department', f'{er[2]} · {fmt_km(er[0])}'])

    # Daily life
    n_heritage = count(heritage)
    daily = [
        [lbl('heritage', 'Heritage buildings'), str(n_heritage)],
        ['Places of worship', str(sum(count(G[k]) for k in FAITH))],
    ]
    if 'halal' in G or 'kosher' in G:
        daily.append([lbl('grocers', 'Halal and kosher grocers'), str(count(G.get('halal', [])) + count(G.get('kosher', [])))])
    lm = sorted(m['name'] for g, m in landmarks if P.contains(g))
    if lm:
        daily.append(['Landmarks', ', '.join(lm)])
    if c.get('walkBikePct') is not None:
        daily.append([lbl('walkBike', 'Commute on foot or by bike'), f"{c['walkBikePct']}%"])

    tr = transit_sections(P, make_valid(shape(feat['geometry'])), ll, lp, c, st_names, shares, docks, bike_km, name)
    dr = driving_sections(P, lp, name, c)

    glance = [
        [U.area(P.area), 'area'],
        [str(len(st_names)), 'subway station' if len(st_names) == 1 else 'subway stations'],
        [str(len(parks)), 'park' if len(parks) == 1 else 'parks'],
        *([[str(len(shares)), lbl('glanceBikeshare', 'bike share stations')]] if bikeshare else []),
        [str(n_heritage), lbl('glanceHeritage', 'heritage buildings')],
    ]
    if c.get('canopy') is not None:
        glance.append([f"{c['canopy']}%", 'tree canopy'])

    return {
        'slug': slug(name), 'name': name, 'asof': date.today().isoformat(),
        'map': frame(P, parks),
        'glance': glance,
        'sections': [
            {'title': 'Getting around', 'rows': around},
            {'title': 'Parks and nature', 'rows': nature},
            {'title': 'Learning and community', 'rows': learning},
            {'title': 'Daily life', 'rows': daily},
        ],
        'transit': {'origin': tr['origin'], 'sections': tr['sections'],
                    'system': system_outline(P)},
        'driving': {'sections': dr, 'region': region_outline(P)},
    }


# ---- the map: the neighbourhood and what's around it, as coordinates in an SVG viewBox ---------
def frame(P, parks):
    x0, y0, x1, y1 = P.bounds
    pad = max(x1 - x0, y1 - y0) * PAD
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    s = VIEW_W / (x1 - x0)
    view = box(x0, y0, x1, y1)

    def xy(x, y):
        return [round((x - x0) * s, 1), round((y1 - y) * s, 1)]   # SVG's y runs down

    # "stationLabels": past this many stations in the frame, the page names only those with three lines or more
    BUSY = CFG.get('stationLabels') and sum(view.contains(g) for g, _ in stations) > CFG['stationLabels']

    def paths(g, tol=0.01):
        g = clip_by_rect(g, x0, y0, x1, y1)
        out = []
        for part in getattr(g, 'geoms', [g]):
            if part.is_empty:
                continue
            ring = part.exterior if part.geom_type == 'Polygon' else part
            if ring.geom_type == 'LineString':
                out.append([xy(*c) for c in ring.simplify(tol).coords])
        return [o for o in out if len(o) > 1]

    return {
        'w': VIEW_W, 'h': round((y1 - y0) * s),
        # to turn a spot on the drawing back into lon/lat (and back): lon = (x / s + x0) / kx
        'geo': {'x0': round(x0, 5), 'y1': round(y1, 5), 's': round(s, 5), 'kx': round(KX, 5), 'ky': KY},
        'outline': [[xy(*c) for c in part.exterior.simplify(0.008).coords]
                    for part in getattr(P, 'geoms', [P]) if part.geom_type == 'Polygon'],
        'subway': [{'line': m.get('line'), 'color': line_color(m), 'paths': p}
                   for g, m in subway_lines if (p := paths(g))],
        'streetcar': [p for g, _ in streetcars for p in paths(g)],
        'bike': [p for g, _ in bikes for p in paths(g)],
        # for the Driving lens: highways (with their route), arterials, on-ramps
        'hwy': [{'route': m.get('route'), 'kind': hwy_kind(m), 'paths': p} for g, m in highways if (p := paths(g))],
        'arterial': paths(ART_DRAW) if ART_DRAW is not None else [],
        'ramps': [xy(pt.x, pt.y) + [route] for pt, route, _ in ONRAMPS if view.contains(pt)],
        'greenp': [xy(g.x, g.y) + [m.get('t')] for g, m in greenp if view.contains(g)],     # t: g garage, s surface
        'ev': [xy(g.x, g.y) + [1 if m.get('dc') else 0] for g, m in chargers if view.contains(g)],   # 1: DC fast
        # daytime buses, for the Transit lens: frequent ones (every 10 min or better) drawn bolder
        'busFreq': [p for g, m in bus_routes if 'freq' in m.get('f', []) for p in paths(g)],
        'bus': [p for g, m in bus_routes if 'freq' not in m.get('f', []) for p in paths(g)],
        'stations': [dict({'x': xy(g.x, g.y)[0], 'y': xy(g.x, g.y)[1], 'name': m['name']},
                          **({'big': True} if BUSY and len(m.get('lines', [])) >= 3 else {}))
                     for g, m in stations if view.contains(g)],
        'parks': [xy(g.x, g.y) for g in parks],
        'bikeshare': [xy(g.x, g.y) for g, _ in bikeshare if P.contains(g)],
    }


# ---- the system map: every line in the city, drawn once; each profile adds its own outline -------
SYS = None
if hood_feats:
    from shapely.ops import unary_union
    CITY = km(make_valid(unary_union([make_valid(shape(f['geometry'])) for f in hood_feats])))
    cx0, cy0, cx1, cy1 = CITY.bounds
    pad = (cx1 - cx0) * 0.03
    cx0, cy0, cx1, cy1 = cx0 - pad, cy0 - pad, cx1 + pad, cy1 + pad
    cs = VIEW_W / (cx1 - cx0)
    sxy = lambda x, y: [round((x - cx0) * cs, 1), round((cy1 - y) * cs, 1)]
    TERMINI = {m['name'] for _, m in stations if m.get('terminus')}

    def sys_line(g, m):
        """A line on the system map: its longest piece as `path`, any branches as `more`."""
        parts = sorted(getattr(g, 'geoms', [g]), key=lambda p: -p.length)
        out = {'line': m.get('line'), 'name': m.get('name'), 'color': line_color(m),
               'path': [sxy(*c) for c in parts[0].simplify(0.05).coords]}
        if len(parts) > 1:
            out['more'] = [[sxy(*c) for c in p.simplify(0.05).coords] for p in parts[1:] if p.length > 0.3]
        return out
    SYS = {
        'w': VIEW_W, 'h': round((cy1 - cy0) * cs), 'hubs': HUBS,
        'outline': [[sxy(*c) for c in part.exterior.simplify(0.15).coords]
                    for part in getattr(CITY, 'geoms', [CITY]) if part.geom_type == 'Polygon' and part.area > 1],
        'lines': [sys_line(g, m) for g, m in subway_lines if g.geom_type in ('LineString', 'MultiLineString')],
        'stations': [{'x': sxy(g.x, g.y)[0], 'y': sxy(g.x, g.y)[1], 'name': m['key'], 'lines': m.get('lines', []),
                      'label': m['key'] in HUBS or m['name'] in TERMINI} for g, m in stations],
        'toHubs': HUB_TABLE,
    }


def system_outline(P):
    if not SYS:
        return []
    return [[sxy(*c) for c in part.exterior.simplify(0.05).coords]
            for part in getattr(P, 'geoms', [P]) if part.geom_type == 'Polygon']


# ---- the regional map for the Driving lens: the GTA's highways, the city, the drive destinations ---
REGION = None
if highways:
    rx0, ry0, rx1, ry1 = CITY.bounds
    padx, pady = (rx1 - rx0) * 0.35, (ry1 - ry0) * 0.45
    rx0, ry0, rx1, ry1 = rx0 - padx, ry0 - pady, rx1 + padx, ry1 + pady
    rs_ = VIEW_W / (rx1 - rx0)
    rxy = lambda x, y: [round((x - rx0) * rs_, 1), round((ry1 - y) * rs_, 1)]

    def rpaths(g):
        g = clip_by_rect(g, rx0, ry0, rx1, ry1)
        return [[rxy(*c) for c in part.simplify(0.1).coords] for part in getattr(g, 'geoms', [g])
                if not part.is_empty and part.geom_type == 'LineString']
    REGION = {
        'w': VIEW_W, 'h': round((ry1 - ry0) * rs_),
        'city': [[rxy(*c) for c in part.exterior.simplify(0.2).coords]
                 for part in getattr(CITY, 'geoms', [CITY]) if part.geom_type == 'Polygon' and part.area > 1],
        'hwy': [{'route': m.get('route'), 'kind': hwy_kind(m), 'paths': p} for g, m in highways if (p := rpaths(g))],
        'dest': [dict(zip(('x', 'y'), rxy(*km(Point(*d['at'])).coords[0])), name=dest_name(d['name']))
                 for d in (drive_prof or {}).get('destinations', [])],
    }


def region_outline(P):
    if not REGION:
        return []
    return [[rxy(*c) for c in part.exterior.simplify(0.1).coords] for part in getattr(P, 'geoms', [P]) if part.geom_type == 'Polygon']


# ---- drive.json: what a pin needs (on-ramps and the 1 km drive-time grid) -------------------------
DRIVE_JSON = {
    'destinations': DRIVE_DEST,
    'asof': (drive_prof or {}).get('asof'),
    'ramps': [[round(pt.x / KX, 5), round(pt.y / KY, 5), route, street] for pt, route, street in ONRAMPS],
    'grid': (drive_prof or {}).get('grid'),
    'names': HWY_NAME,
    'kinds': HWY_KIND,
}


# ---- write --------------------------------------------------------------------------------------
os.makedirs(OUT, exist_ok=True)
index = []
for feat in hood_feats:
    prof = build(feat)
    index.append({'slug': prof['slug'], 'name': prof['name']})
    with open(os.path.join(OUT, prof['slug'] + '.json'), 'w') as f:
        json.dump(prof, f, ensure_ascii=False, separators=(',', ':'))
if SYS:
    SYS['region'] = REGION
    with open(os.path.join(OUT, 'system.json'), 'w') as f:
        json.dump(SYS, f, ensure_ascii=False, separators=(',', ':'))
with open(os.path.join(OUT, 'drive.json'), 'w') as f:
    json.dump(DRIVE_JSON, f, ensure_ascii=False, separators=(',', ':'))
index.sort(key=lambda r: r['name'])
with open(os.path.join(OUT, 'index.json'), 'w') as f:
    json.dump({'asof': date.today().isoformat(), 'places': index}, f, ensure_ascii=False, separators=(',', ':'))

# ---- the page: engine/profiles/page.html with this city's wording, settings and badge colours ------------
PG = CFG.get('page', {})
FS = dict(PG, unitsFile=units_file(CFG), stationLabels=CFG.get('stationLabels'), hubBullets=CFG.get('hubBullets', True),
          lineOrder=CFG.get('lineOrder'), parking=HAS('parking'), distance=CFG.get('distance', 'km'), rampKm=round(RAMP_KM, 3), rampText=U.radius(RAMP_R),
          hub=HUB.get('name', ''), nearestRail=RAIL.get('nearest', 'Nearest train station'), railBadge=RAIL.get('badge'))
FS.pop('description', None)
page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'page.html'), encoding='utf-8').read()
css_path = os.path.join(ROOT, 'cities', city, 'factsheet.css')
fill = {k: html.escape(PG.get(k, ''), quote=True) for k in ('description', 'city', 'Unit', 'placeholder', 'kind', 'boundary', 'sysNote')}
fill['css'] = open(css_path, encoding='utf-8').read() if os.path.exists(css_path) else ''
fill['FS'] = json.dumps(FS, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
page = re.sub(r'\{\{(\w+)\}\}', lambda m: fill[m.group(1)], page)
with open(os.path.join(OUT, '..', 'index.html'), 'w', encoding='utf-8') as f:
    f.write(page)
print(f'{city}: {len(index)} profiles -> {os.path.relpath(OUT, ROOT)}, and the page')
