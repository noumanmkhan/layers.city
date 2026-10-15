"""Neighbourhood badges: a one-colour drawing for a few curated places, laid on the map like a watermark.

Usage: python3 engine/badges.py <city>

Reads the drawings in cities/<city>/badges/<slug>.svg (viewBox 0 0 240 120; shapes classed m = ink,
k = knockout, ms / ks = ink or knockout strokes), the city's units file (the layer of kind "units") and,
when the badges layer names one in "align", that street in the streets file. Writes docs/<city>/data/<file>
for the layer of kind "badges":

  {"angle": degrees, "units": [{"n": name, "c": [lat, lon], "wm": metres, "w": 240, "h": 120, "svg": markup}]}

"angle" is how far the drawings turn to run parallel to the "align" street (positive = counter-clockwise;
0 without one). "c" and "wm" are the centre and width of the largest box of the drawing's shape, turned by
that angle, that fits inside the unit around the point farthest from its edges (or a better-fitting point
nearby). The page draws each drawing at a share of that width, so it always sits inside its own place.
Knockouts are cut out with a mask, so the map shows through them. No text: the name comes from the units
layer's own label."""
import json, math, os, re, sys, unicodedata
from shapely.geometry import shape, box, Point
from shapely.ops import polylabel
from shapely.prepared import prep
from shapely import affinity

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: badges.py <city>')
CITY_DIR = os.path.join(ROOT, 'cities', city)
DATA = os.path.join(ROOT, 'docs', city, 'data')
cfg = json.load(open(os.path.join(CITY_DIR, 'city.json'), encoding='utf-8'))
layers = [l for g in cfg['groups'] for l in g[1]]
BADGES = next((l for l in layers if l['kind'] == 'badges'), None)
if not BADGES:
    sys.exit('no layer of kind "badges" in %s/city.json' % city)
UNITS = next(l for l in layers if l['kind'] == 'units')
load = lambda f: json.load(open(os.path.join(DATA, f if '.' in f else f + '.geojson'), encoding='utf-8'))

def slug(s):
    s = re.sub(r"['’]", '', s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def street_angle(prefix):
    """Least-squares direction of every main-street line whose name starts with prefix, in degrees."""
    streets = next(l for l in layers if l['kind'] == 'streets' and not l.get('under'))
    pts = []
    for f in load(streets['file'])['features']:
        if f['properties'].get('name', '').startswith(prefix):
            g = f['geometry']
            for line in (g['coordinates'] if g['type'] == 'MultiLineString' else [g['coordinates']]):
                pts += line
    if len(pts) < 2:
        sys.exit('align: no street named %s' % prefix)
    k = math.cos(math.radians(sum(p[1] for p in pts) / len(pts)))
    xs, ys = [p[0] * k for p in pts], [p[1] for p in pts]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    return math.degrees(math.atan2(sum((x - mx) * (y - my) for x, y in zip(xs, ys)), sum((x - mx) ** 2 for x in xs)))

def fit(geom, aspect, angle, near=None):
    """Largest box of the given width/height, turned by angle, inside geom. Returns (centre lon/lat, width in m).
    Works in a local equal-scale frame turned the other way, so the box is upright there.
    near [lon, lat]: keep to the part of a multi-part unit that holds this point (the mainland, say)."""
    lat0 = geom.centroid.y
    kx = math.cos(math.radians(lat0))
    g0 = affinity.scale(geom, xfact=kx, yfact=1, origin=(0, 0))
    o = g0.centroid
    g = affinity.rotate(g0, -angle, origin=o)
    pg = prep(g)
    def size_at(c):
        lo, hi = 0, max(g.bounds[2] - g.bounds[0], g.bounds[3] - g.bounds[1])
        for _ in range(22):
            h = (lo + hi) / 2
            lo, hi = (h, hi) if pg.contains(box(c[0] - aspect * h / 2, c[1] - h / 2, c[0] + aspect * h / 2, c[1] + h / 2)) else (lo, h)
        return lo
    parts = list(g.geoms) if g.geom_type == 'MultiPolygon' else [g]
    if near:
        np_ = affinity.rotate(Point(near[0] * kx, near[1]), -angle, origin=o)
        parts = [min(parts, key=lambda p: p.distance(np_))]
    cands = []
    for p in parts:
        if p.area < g.area * .05 and not near:
            continue
        pl = polylabel(p, tolerance=(p.bounds[2] - p.bounds[0]) / 200)
        cands.append((pl.x, pl.y))
        x0, y0, x1, y1 = p.bounds
        for i in range(1, 12):
            for j in range(1, 12):
                pt = (x0 + (x1 - x0) * i / 12, y0 + (y1 - y0) * j / 12)
                if pg.contains(Point(pt)):
                    cands.append(pt)
    h, c = max((size_at(c), c) for c in cands)
    step = h / 4
    for _ in range(3):   # nudge around the best point
        for dx, dy in ((step, 0), (-step, 0), (0, step), (0, -step)):
            c2 = (c[0] + dx, c[1] + dy); h2 = size_at(c2)
            if h2 > h: h, c = h2, c2
        step /= 2
    back = affinity.rotate(Point(c), angle, origin=o)
    width_m = aspect * h * 111320   # degrees of latitude to metres; x was scaled to the same units
    return [round(back.y, 6), round(back.x / kx, 6)], round(width_m)

def badge_svg(sl, art):
    """The drawing's shapes, ink in a group masked by its knockouts (so the map shows through them)."""
    art = re.sub(r'<title>.*?</title>|<desc>.*?</desc>|</?svg[^>]*>', '', art, flags=re.S).strip()
    # A drawing wrapped whole in one <g transform>: keep the transform for its mask too.
    tf = re.fullmatch(r'<g transform="([^"]+)">(.*)</g>', art, flags=re.S)
    if tf:
        art = tf.group(2)
    # Knockouts come out of the drawing and into the mask, painted black there (black = cut away).
    mask = []
    def take(m):
        el = m.group(0)
        if re.search(r'class="ks"', el):
            mask.append(el.replace('class="ks"', 'stroke="#000" fill="none"'))
        else:
            mask.append(el.replace('class="k"', 'fill="#000"'))
        return ''
    # A group of knockouts: <g class="k">…</g> or <g class="ks" …>…</g>; then single knockout shapes.
    art = re.sub(r'<g class="ks?"[^>]*>.*?</g>', lambda m: take(m), art, flags=re.S)
    art = re.sub(r'<(?:rect|circle|path|polygon|ellipse|line)\b[^>]*class="ks?"[^>]*/>', lambda m: take(m), art)
    art = re.sub(r'class="(ms|m)"', lambda m: 'class="bd-' + m.group(1) + '"', art)
    mid = 'bdm-' + sl
    if tf:
        art = '<g transform="%s">%s</g>' % (tf.group(1), art)
        mask = ['<g transform="%s">%s</g>' % (tf.group(1), ''.join(mask))]
    return ('<defs><mask id="%s" maskUnits="userSpaceOnUse" x="-20" y="-20" width="280" height="160">'
            '<rect x="-20" y="-20" width="280" height="160" fill="#fff"/>%s</mask></defs>'
            '<g mask="url(#%s)">%s</g>') % (mid, ''.join(mask), mid, art.strip())

# ---------- build ----------
angle = round(street_angle(BADGES['align']), 2) if BADGES.get('align') else 0
units = {f['properties']['name']: shape(f['geometry']) for f in load(UNITS['file'])['features']}
by_slug = {slug(n): n for n in units}
art_dir = os.path.join(CITY_DIR, BADGES.get('art', 'badges'))
opts_path = os.path.join(art_dir, 'places.json')   # {"Unit name": {"near": [lon, lat]}}: which part of a multi-part unit
opts = json.load(open(opts_path, encoding='utf-8')) if os.path.isfile(opts_path) else {}

out = []
for fn in sorted(os.listdir(art_dir)):
    if not fn.endswith('.svg'):
        continue
    sl = fn[:-4]
    name = by_slug.get(sl)
    if not name:
        print('  no unit for drawing %s' % fn)
        continue
    c, wm = fit(units[name], 240 / 120, angle, opts.get(name, {}).get('near'))
    out.append({'n': name, 'c': c, 'wm': wm, 'w': 240, 'h': 120, 'svg': badge_svg(sl, open(os.path.join(art_dir, fn), encoding='utf-8').read())})

path = os.path.join(DATA, BADGES['file'])
json.dump({'angle': angle, 'units': out}, open(path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('%s: %d badges, turned %.1f° -> %s (%d KB)' % (city, len(out), angle, os.path.relpath(path, ROOT), os.path.getsize(path) // 1024))
