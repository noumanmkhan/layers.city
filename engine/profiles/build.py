"""Neighbourhood profiles (unreleased: lives only on the `profiles` branch).

One small JSON file per neighbourhood with everything a one-page profile shows, so the page itself
only reads and draws, every visitor sees the same numbers, and a printed copy matches the screen.

Usage:  python3 engine/profiles/build.py toronto
Reads:  docs/<city>/data/*  (the same published files the map uses, so the two never disagree)
Writes: docs/<city>/profiles/data/index.json        {asof, places: [{slug, name}]}, for the picker
        docs/<city>/profiles/data/<slug>.json       one profile each

Rules carried over from the map:
- Facilities, never people: no language, origin or other demographic rows. Census figures used here
  (commuting, canopy) keep their year.
- Counts are of what's on the map, inside the neighbourhood's boundary (the City's official one,
  which can be bigger than the name's everyday use). Stations, libraries and campuses also count
  when they sit just outside it (within NEAR_KM): one across the street still serves the area.
- Times are the map's own: transit to Union from nbhd_profiles.json, driving from drive_grid.json.
  Walks to the nearest station are straight-line distance x 1.3 at 4.8 km/h, shown as "about".

Needs: pip install shapely  (already needed by cities/<city>/run.sh)
"""
import json, math, os, re, sys, unicodedata
from datetime import date
import shapely
from shapely.geometry import shape, Point, box
from shapely import clip_by_rect, make_valid

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
hood_feats = opt('neighbourhoods.geojson', {'features': []})['features']
if not hood_feats:
    sys.exit(f'{city}: no neighbourhoods.geojson')
LAT0 = sum(shape(f['geometry']).centroid.y for f in hood_feats) / len(hood_feats)
KX, KY = 111.32 * math.cos(math.radians(LAT0)), 110.574


def km(g):
    return shapely.transform(g, lambda c: c * [KX, KY])


def layer(name):
    """[(geometry in km, properties)] for a published layer; empty if the city doesn't have it."""
    return [(km(make_valid(shape(f['geometry']))), f['properties'])
            for f in opt(name + '.geojson', {'features': []})['features']]


census = opt('nbhd_profiles.json', {})
nearby = opt('nearby.json', {'groups': {}})['groups']
grid = opt('drive_grid.json', None)

stations = layer('subway_stations')
subway_lines = layer('subway_lines')
streetcars = layer('streetcars')
bikes = layer('bikes')
bikeshare = layer('bikeshare')
go = layer('go_stations')
heritage = layer('heritage_buildings')
landmarks = layer('landmarks')
institutions = layer('institutions')
french = layer('french_schools')


def group(name):
    """A nearby.json group as [(point in km, label or None)]."""
    return [(km(Point(p[0], p[1])), p[2] if len(p) > 2 else None) for p in nearby.get(name, [])]


G = {k: group(k) for k in nearby}
FAITH = [k for k in G if k in ('church', 'mosque', 'synagogue', 'hindu', 'gurdwara', 'buddhist')
         or k.startswith('church:')]


def walk_min(d_km):
    return max(1, round(d_km * 1.3 / 4.8 * 60))


def fmt_km(d):
    return f'{d * 1000:.0f} m' if d < 1 else f'{d:.1f} km'


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
    st_names = sorted({m['name'] for m in st})
    lines = sorted({l for m in st for l in m.get('lines', [])})
    cars = sorted({f"{m['r']} {m['n']}" for g, m in streetcars if g.intersection(P).length > MIN_ROUTE_KM},
                  key=route_key)
    bike_km = sum(g.intersection(P).length for g, _ in bikes)
    shares = [m for g, m in bikeshare if P.contains(g)]
    docks = sum(m.get('d') or 0 for m in shares)
    go_in = sorted({m['name'] for g, m in go if near.contains(g)})

    around = []
    if st_names:
        around.append(['Subway stations',
                       f"{len(st_names)} · Line{'s' if len(lines) > 1 else ''} {', '.join(lines)}"])
    elif stations:
        d, _, m = nearest(lp, stations)
        around.append(['Nearest subway', f"{m['name']} · about {walk_min(d)} min walk" if d <= WALK_MAX_KM
                       else f"{m['name']} · {fmt_km(d)} away"])
    if go_in:
        around.append(['GO stations', ', '.join(go_in)])
    around.append(['Streetcar routes', ', '.join(cars) if cars else 'None'])
    around.append(['Bike Share stations', f'{len(shares)} · {docks} docks' if shares else 'None'])
    around.append(['Bike lanes and trails', f'{bike_km:.1f} km'])
    if c.get('union') is not None:
        around.append(['Transit to Union', f"about {c['union']} min"])
    if grid:
        g = min(grid['points'], key=lambda p: (p[0] - ll.x) ** 2 + (p[1] - ll.y) ** 2)
        around.append([f"Drive to {grid['hub'].replace(' Station', '')}", f'about {g[2]} min'])

    # Parks and nature
    parks = [g for g, _ in G.get('park', []) if P.contains(g)]
    nature = [
        ['Parks', str(len(parks))],
        ['Playgrounds', str(count(G.get('playground', [])))],
        ['Off-leash areas', str(count(G.get('offleash', [])))],
        ['Tennis courts', str(count(G.get('tennis', [])))],
    ]
    if c.get('canopy') is not None:
        nature.append(['Tree canopy', f"{c['canopy']}%"])

    # Learning and community
    libs = sorted(n.replace(' branch', '') for g, n in G.get('library', []) if near.contains(g))
    learning = [
        ['Library branches', ', '.join(libs) if libs else 'None'],
        ['Community and rec centres', str(count(G.get('centre', [])))],
        ['French-language and immersion schools', str(count(french))],
    ]
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
        ['Heritage buildings', str(n_heritage)],
        ['Places of worship', str(sum(count(G[k]) for k in FAITH))],
        ['Halal and kosher grocers', str(count(G.get('halal', [])) + count(G.get('kosher', [])))],
    ]
    lm = sorted(m['name'] for g, m in landmarks if P.contains(g))
    if lm:
        daily.append(['Landmarks', ', '.join(lm)])
    if c.get('walkBikePct') is not None:
        daily.append(['Commute on foot or by bike (2021)', f"{c['walkBikePct']}%"])

    glance = [
        [f'{P.area:.1f} km²', 'area'],
        [str(len(st_names)), 'subway station' if len(st_names) == 1 else 'subway stations'],
        [str(len(parks)), 'park' if len(parks) == 1 else 'parks'],
        [str(len(shares)), 'Bike Share stations'],
        [str(n_heritage), 'heritage buildings'],
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
        'outline': [[xy(*c) for c in part.exterior.simplify(0.008).coords]
                    for part in getattr(P, 'geoms', [P]) if part.geom_type == 'Polygon'],
        'subway': [{'line': m.get('line'), 'color': m.get('color'), 'paths': p}
                   for g, m in subway_lines if (p := paths(g))],
        'streetcar': [p for g, _ in streetcars for p in paths(g)],
        'bike': [p for g, _ in bikes for p in paths(g)],
        'stations': [{'x': xy(g.x, g.y)[0], 'y': xy(g.x, g.y)[1], 'name': m['name']}
                     for g, m in stations if view.contains(g)],
        'parks': [xy(g.x, g.y) for g in parks],
        'bikeshare': [xy(g.x, g.y) for g, _ in bikeshare if P.contains(g)],
    }


# ---- write --------------------------------------------------------------------------------------
os.makedirs(OUT, exist_ok=True)
index = []
for feat in hood_feats:
    prof = build(feat)
    index.append({'slug': prof['slug'], 'name': prof['name']})
    with open(os.path.join(OUT, prof['slug'] + '.json'), 'w') as f:
        json.dump(prof, f, ensure_ascii=False, separators=(',', ':'))
index.sort(key=lambda r: r['name'])
with open(os.path.join(OUT, 'index.json'), 'w') as f:
    json.dump({'asof': date.today().isoformat(), 'places': index}, f, ensure_ascii=False, separators=(',', ':'))
print(f'{city}: {len(index)} profiles -> {os.path.relpath(OUT, ROOT)}')
