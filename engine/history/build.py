"""Build a city's transit history page, docs/<city>/<path>/index.html, from cities/<city>/history.json.

Usage: python3 engine/history/build.py <city>

The page is one SVG map (the land, the former municipalities and the main streets, from the map's published layers)
with every line in history.json drawn over it, and a timeline that sets each line's stage for the chosen year.
history.json "_about" describes the geometry recipes and stages. Everything is projected here, so the page needs
no map library and no tiles. The engine names no city; the lines, their routes and their dates are in history.json."""
import json, math, os, re, sys
from datetime import date

from shapely.geometry import shape, LineString, MultiLineString, Point, box, mapping
from shapely.ops import substring, unary_union, linemerge

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from theme import SCRIPT as THEME_SCRIPT, css as theme_css   # noqa: E402

city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: build.py <city>')
CITY = os.path.join(ROOT, 'cities', city)
DATA = os.path.join(ROOT, 'docs', city, 'data')
cfg = json.load(open(os.path.join(CITY, 'history.json'), encoding='utf-8'))
OUT = os.path.join(ROOT, 'docs', city, cfg['path'])
STAGES = {'proposed', 'approved', 'building', 'open', 'closed', 'cancelled', 'dormant', 'superseded'}
W = 1000


def load(name):
    return json.load(open(os.path.join(DATA, name), encoding='utf-8'))['features']


# ---- inputs --------------------------------------------------------------------------------------------------
stations = {}                     # name -> (lon, lat), from the map's station layer
for f in load('subway_stations.geojson'):
    stations[f['properties']['name']] = tuple(f['geometry']['coordinates'])
lines_pub = {f['properties']['line']: shape(f['geometry']) for f in load('subway_lines.geojson')}
build_lines, build_stations = {}, {}
for f in load('construction.geojson'):
    p = f['properties']
    if p.get('part') == 'station':
        build_stations[(p['id'], p['name'])] = tuple(f['geometry']['coordinates'])
    else:
        build_lines[p['id']] = shape(f['geometry'])
street_geoms = {}
streets_major = []
for f in load('streets.geojson'):
    g = shape(f['geometry'])
    street_geoms.setdefault(f['properties']['name'], []).append(g)
    if f['properties']['cls'] == 'major':
        streets_major.append(g)
boroughs = load('boroughs.geojson')
base = load('base.geojson')

LAT0 = 43.7
KX = math.cos(math.radians(LAT0))
M_PER_DEG = 111320.0


def metres(a, b):
    return math.hypot((a[0] - b[0]) * KX, a[1] - b[1]) * M_PER_DEG


def street(name):
    if name not in street_geoms:
        sys.exit(f'history.json: no street called {name!r} in streets.geojson')
    return unary_union(street_geoms[name])


def crossing(a, b, near=None):
    """Where two named streets meet: one point, the middle of the crossing (divided roads cross more than once)."""
    ga, gb = street(a), street(b)
    pts = []
    x = ga.intersection(gb)
    for g in getattr(x, 'geoms', [x]):
        if g.is_empty:
            continue
        if g.geom_type == 'Point':
            pts.append((g.x, g.y))
        else:
            c = g.centroid
            pts.append((c.x, c.y))
    if not pts:   # streets that stop short of each other (a gap in the centreline file)
        from shapely.ops import nearest_points
        pa, pb = nearest_points(ga, gb)
        if metres((pa.x, pa.y), (pb.x, pb.y)) > 200:
            sys.exit(f'history.json: {a} and {b} do not meet')
        pts = [((pa.x + pb.x) / 2, (pa.y + pb.y) / 2)]
    if near:
        ref = resolve(near)
        pts.sort(key=lambda p: metres(p, ref))
    first = pts[0]
    cluster = [p for p in pts if metres(p, first) < 120]
    if len(pts) != len(cluster) and not near:
        far = max(metres(p, first) for p in pts)
        if far > 400:
            sys.exit(f'history.json: {a} and {b} meet in more than one place ({far:.0f} m apart); give "near"')
    return (sum(p[0] for p in cluster) / len(cluster), sum(p[1] for p in cluster) / len(cluster))


def resolve(pt):
    if isinstance(pt, list):
        return tuple(pt)
    if isinstance(pt, dict):
        return crossing(*pt['x'], near=pt.get('near'))
    if pt.startswith('build:'):
        _, lid, name = pt.split(':', 2)
        return build_stations[(lid, name)]
    if pt not in stations:
        sys.exit(f'history.json: no station called {pt!r}')
    return stations[pt]


def along(names, a, b):
    """The named streets' centrelines between two points, in order. Takes every vertex near the straight line
    from a to b and sorts them along it, which suits arterials (straight, or gently curving)."""
    A, B = resolve(a), resolve(b)
    ax, ay, bx, by = A[0] * KX, A[1], B[0] * KX, B[1]
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    chord = math.sqrt(L2) * M_PER_DEG
    band = max(400.0, chord * 0.25)
    pts = []
    for n in names:
        for g in street_geoms.get(n) or sys.exit(f'history.json: no street called {n!r}'):
            for part in getattr(g, 'geoms', [g]):
                for x, y in part.coords:
                    px, py = x * KX - ax, y - ay
                    t = (px * dx + py * dy) / L2
                    if 0 < t < 1:
                        perp = abs(px * dy - py * dx) / math.sqrt(L2) * M_PER_DEG
                        if perp < band:
                            pts.append((t, (x, y)))
    pts.sort()
    line = LineString([A] + [p for _, p in pts] + [B])
    return line.simplify(0.00022)


def cut(lid, a, b):
    g = lines_pub[lid]
    if g.geom_type != 'LineString':
        g = linemerge(g)
    da, db = g.project(Point(resolve(a))), g.project(Point(resolve(b)))
    return substring(g, min(da, db), max(da, db)), (min(da, db), max(da, db), g)


def geometry(spec):
    """A recipe -> (geometry, the published line and range it was cut from, if any)."""
    if 'parts' in spec:
        parts = [geometry(s)[0] for s in spec['parts']]
        coords = []
        for p in parts:
            for seg in getattr(p, 'geoms', [p]):
                coords.append(list(seg.coords))
        return MultiLineString(coords), None
    if 'line' in spec:
        g, rng = cut(spec['line'], spec['from'], spec['to'])
        return g, (spec['line'],) + rng
    if 'build' in spec:
        return build_lines[spec['build']], None
    if 'along' in spec:
        return along(spec['along'], spec['from'], spec['to']), None
    if 'path' in spec:
        return LineString([resolve(p) for p in spec['path']]), None
    sys.exit(f'history.json: unknown geometry recipe {spec}')


def length_km(g):
    tot = 0.0
    for seg in getattr(g, 'geoms', [g]):
        c = list(seg.coords)
        tot += sum(metres(c[i], c[i + 1]) for i in range(len(c) - 1))
    return tot / 1000


# ---- lines -----------------------------------------------------------------------------------------------------
out_lines = []
all_geoms = []
for ln in cfg['lines']:
    g, rng = geometry(ln['geom'])
    all_geoms.append(g)
    sts = []
    if 'stations' in ln:
        for s in ln['stations']:
            p = resolve(s['at'])
            sts.append([p, s['n']])
    elif 'build' in ln['geom']:
        bid = ln['geom']['build']
        sts = [[p, n] for (i, n), p in build_stations.items() if i == bid]
    for e in ln['events']:
        if e['s'] not in STAGES:
            sys.exit(f'history.json: {ln["id"]}: unknown stage {e["s"]}')
        for s in e['src']:
            if s not in cfg['sources']:
                sys.exit(f'history.json: {ln["id"]}: unknown source {s}')
    out_lines.append({'ln': ln, 'g': g, 'sts': sts})

# ---- projection: the city plus every line, with a margin --------------------------------------------------------
city_poly = unary_union([shape(f['geometry']) for f in boroughs])
bx = unary_union([city_poly] + all_geoms).bounds
padx, pady = (bx[2] - bx[0]) * 0.02, (bx[3] - bx[1]) * 0.03
minx, miny, maxx, maxy = bx[0] - padx, bx[1] - pady, bx[2] + padx, bx[3] + pady
SCALE = W / ((maxx - minx) * KX)
H = round((maxy - miny) * SCALE)
frame = box(minx, miny, maxx, maxy)


def xy(p):
    return (round((p[0] - minx) * KX * SCALE, 1), round((maxy - p[1]) * SCALE, 1))


def path_lines(g):
    out = []
    for seg in getattr(g, 'geoms', [g]):
        if seg.is_empty or seg.geom_type != 'LineString':
            continue
        pts = [xy(c) for c in seg.coords]
        out.append('M' + 'L'.join(f'{x:g} {y:g}' for x, y in pts))
    return ''.join(out)


def path_polys(g, tol=0.0003):
    g = g.intersection(frame).simplify(tol, preserve_topology=True)
    out = []
    for p in getattr(g, 'geoms', [g]):
        if p.geom_type != 'Polygon' or p.is_empty:
            continue
        for ring in [p.exterior, *p.interiors]:
            pts = [xy(c) for c in ring.coords]
            out.append('M' + 'L'.join(f'{x:g} {y:g}' for x, y in pts[:-1]) + 'Z')
    return ''.join(out)


neighbours = unary_union([shape(f['geometry']) for f in base if f['properties']['kind'] == 'neighbour'])
streets = unary_union(streets_major).intersection(frame).simplify(0.0002)
basemap = {
    'w': W, 'h': H,
    'near': path_polys(neighbours),
    'boroughs': [{'d': path_polys(shape(f['geometry'])), 'n': f['properties']['name'],
                  'lp': xy(f['properties']['lp'])} for f in boroughs],
    'streets': path_lines(streets),
}


# ---- built lines' stations: every station of the published line inside the cut -----------------------------------
line_of = {}
for f in load('subway_stations.geojson'):
    line_of[f['properties']['name']] = f['properties']['lines']
for item in out_lines:
    spec = item['ln']['geom']
    if 'line' in spec and 'stations' not in item['ln']:
        g = item['g']
        item['sts'] = [[p, n] for n, p in stations.items()
                       if spec['line'] in line_of[n] and g.distance(Point(p)) < 0.0008]


def year_of(d):
    return int(str(d)[:4])


def nice_date(d):
    s = str(d)
    parts = s.split('-')
    months = ['Jan.', 'Feb.', 'Mar.', 'Apr.', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.']
    if len(parts) == 3:
        return f'{months[int(parts[1]) - 1]} {int(parts[2])}, {parts[0]}'
    if len(parts) == 2:
        return f'{months[int(parts[1]) - 1]} {parts[0]}'
    return parts[0]


today = date.today()
out = {'lines': [], 'ghosts': [], 'sources': cfg['sources'], 'start': cfg['page']['start'], 'now': today.year,
       'future': cfg['page']['future']}
for item in out_lines:
    ln, g = item['ln'], item['g']
    xs = [xy(c) for seg in getattr(g, 'geoms', [g]) for c in seg.coords]
    out['lines'].append({
        'id': ln['id'], 'name': ln['name'], 'now': ln.get('now'), 'group': ln['group'], 'mode': ln['mode'],
        'c': ln['colour'], 'approx': bool(ln.get('approx')), 'd': path_lines(g), 'km': round(length_km(g), 1),
        'bb': [min(p[0] for p in xs), min(p[1] for p in xs), max(p[0] for p in xs), max(p[1] for p in xs)],
        'st': [[*xy(p), n] for p, n in item['sts']],
        'ev': [{'y': year_of(e['d']), 'd': nice_date(e['d']), 's': e['s'], 't': e['t'], 'src': e['src'],
                'f': bool(e.get('future'))} for e in sorted(ln['events'], key=lambda e: str(e['d']))],
    })
for gh in cfg.get('ghosts', []):
    out['ghosts'].append({'n': gh['n'], 'p': xy(resolve(gh['at'])),
                          'ev': [{'y': year_of(e['d']), 'd': nice_date(e['d']), 's': e['s'], 't': e['t'], 'src': e['src']}
                                 for e in gh['events']]})

page = cfg['page']
tpl = open(os.path.join(ROOT, 'engine', 'history', 'page.html'), encoding='utf-8').read()
DARK = ['.map,.key,.idx,.evs{--water:#1B2A33;--land:#24272D;--near:#1E2126;--street:#3A3E45;--edge:#4A4F57;--case:#0E0F12;--ghost:#7D838C}']
html = (tpl.replace('{{title}}', page['title']).replace('{{city}}', page['city']).replace('{{short}}', page['short'])
        .replace('{{description}}', page['description']).replace('{{lede}}', page['lede'])
        .replace('{{note}}', page['note']).replace('{{credits}}', page['credits'])
        .replace('{{robots}}', '<meta name="robots" content="noindex">' if cfg.get('unlisted') else '')
        .replace('{{BASE}}', json.dumps(basemap, separators=(',', ':'), ensure_ascii=False))
        .replace('{{HIST}}', json.dumps(out, separators=(',', ':'), ensure_ascii=False))
        .replace('{{themeScript}}', THEME_SCRIPT).replace('{{themeCss}}', theme_css(DARK)))
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)
print(f'{city}: {len(out["lines"])} lines, {len(out["ghosts"])} ghost stations -> docs/{city}/{cfg["path"]}/index.html '
      f'({os.path.getsize(os.path.join(OUT, "index.html")) // 1024} KB)')
