"""Neighbourhood badges: a one-colour silhouette for a few curated places, a fitted name for the rest.

Usage: python3 engine/badges.py <city>

Reads the city's units file (the layer of kind "units"), its area fills (kind "fill", for the line under
the name) and the drawings in cities/<city>/badges/<slug>.svg (viewBox 0 0 240 120, shapes classed
m = ink, k = knockout, ms / ks = ink or knockout strokes). Writes docs/<city>/data/<file> for the layer
of kind "badges":

  {"units": [{"n": name, "b": [[s, w], [n, e]], "w": vb width, "h": vb height, "f": name font size,
              "art": true|false, "svg": inner SVG markup}]}

"b" is the largest box of the badge's shape that fits inside the unit, around the point farthest from
its edges (or a better-fitting point nearby). The page sizes the badge to that box, so it always sits
inside its own place, and hides it while its name would be too small to read."""
import json, math, os, re, sys, unicodedata
from html import escape
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
FILLS = sorted((l for l in layers if l['kind'] == 'fill'), key=lambda l: l.get('size') != 'major')
load = lambda f: json.load(open(os.path.join(DATA, f if '.' in f else f + '.geojson'), encoding='utf-8'))

def slug(s):
    s = re.sub(r"['’]", '', s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

# ---------- text measure (Archivo, capitals) ----------
# Rough advance widths in ems. The page sets each line with textLength, so a slight overestimate only
# opens the letter-spacing a little; it never squeezes letters together.
NARROW = {'I': .30, 'J': .52, ' ': .30, '.': .30, "'": .26, '’': .26, '-': .42, ',': .30}
WIDE = {'M': .92, 'W': 1.0, 'Q': .80, 'O': .78, 'G': .76, 'D': .74, 'C': .72, 'N': .75, 'H': .75, 'U': .74}
def width(s, size, track):
    return (sum(NARROW.get(c, WIDE.get(c, .66)) for c in s) * size + track * size * max(len(s) - 1, 0)) * 1.04

# ---------- layouts ----------
F = 24          # name size for text-only labels (viewBox units; only proportions matter)
TRACK = .06     # letter-spacing, in ems
SUB = .44       # sub line, as a share of the name size

def text(cls, s, x, y, size, track):
    w = width(s, size, track)
    return ('<text class="%s" x="%.1f" y="%.1f" font-size="%.1f" text-anchor="middle" textLength="%.1f" lengthAdjust="spacing">%s</text>'
            % (cls, x, y, size, w, escape(s)), w)

def lines_for(name):
    """Ways to break a name into lines, each as [(text, size share)]."""
    up = name.upper()
    parts = [p.strip() for p in up.split('-') if p.strip()]
    out = [[(up, 1)]]
    if len(parts) == 2:
        out.append([(parts[0], 1), (parts[1], .62)])
    elif len(parts) > 2:
        out.append([(parts[0], 1)] + [(p, .55) for p in parts[1:]])
    words = up.split(' ')
    if len(parts) == 1 and len(words) > 1:
        best = min(range(1, len(words)), key=lambda i: abs(len(' '.join(words[:i])) - len(' '.join(words[i:]))))
        out.append([(' '.join(words[:best]), 1), (' '.join(words[best:]), 1)])
    return out

def text_label(name, sub, layout):
    pad = .45 * F
    lead = len(layout) > 1 and layout[1][1] < 1     # a lead name, a short rule, then the rest
    rows, y, wmax, rule = [], pad, 0, None
    for i, (s, k) in enumerate(layout):
        size = F * k
        y += size * .8
        rows.append(('bd-n' if k == 1 else 'bd-n2', s, y, size, TRACK if k == 1 else .1))
        y += size * .25
        if i == 0 and lead:
            y += F * .12; rule = y; y += F * .09 + F * .3
        else:
            y += F * .12
        wmax = max(wmax, width(s, size, rows[-1][4]))
    if sub:
        size = F * SUB
        y += size * .35 + size * .8
        rows.append(('bd-s', sub.upper(), y, size, .14))
        y += size * .25
        wmax = max(wmax, width(sub.upper(), size, .14))
    W, H = wmax + 2 * pad, y + pad * .8
    body = '<rect class="bd-plate" x="0" y="0" width="%.1f" height="%.1f" rx="%.1f"/>' % (W, H, F * .35)
    if rule:
        body += '<rect class="bd-rule" x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>' % (W / 2 - F * 1.4, rule, F * 2.8, F * .09)
    for cls, s, yy, size, tr in rows:
        body += text(cls, s, W / 2, yy, size, tr)[0]
    return W, H, F, body

ART_CLASS = {'m': 'bd-m', 'k': 'bd-k', 'ms': 'bd-ms', 'ks': 'bd-ks'}
def art_badge(name, sub, art):
    art = re.sub(r'<title>.*?</title>|<desc>.*?</desc>|</?svg[^>]*>', '', art, flags=re.S)   # just the shapes
    art = re.sub(r'class="(\w+)"', lambda m: 'class="%s"' % ART_CLASS.get(m.group(1), m.group(1)), art)
    W, pad = 240, 10
    up = name.upper()
    size = min(22, (W - 2 * pad) / (width(up, 1, TRACK)))
    names = [up]
    if size < 15:    # too long for one line: break at the hyphens or the middle space
        parts = [p for p in re.split(r'(?<=-)', up) if p]
        best = min(range(1, len(parts)), key=lambda i: abs(len(''.join(parts[:i])) - len(''.join(parts[i:])))) if len(parts) > 1 else None
        if best is None:
            words = up.split(' ')
            best = min(range(1, len(words)), key=lambda i: abs(len(' '.join(words[:i])) - len(' '.join(words[i:]))))
            names = [' '.join(words[:best]), ' '.join(words[best:])]
        else:
            names = [''.join(parts[:best]).rstrip('-'), ''.join(parts[best:])]
        size = min(18, min((W - 2 * pad) / width(n, 1, TRACK) for n in names))
    y = 120 + 6
    body = '<g class="bd-art">%s</g>' % art.strip()
    for n in names:
        y += size * .82
        body += text('bd-n', n, W / 2, y, size, TRACK)[0]
        y += size * .3
    if sub:
        s = F * SUB
        y += s * .6 + 2
        body += text('bd-s', sub.upper(), W / 2, y + s * .2, s, .14)[0]
        y += s * .6
    H = y + pad
    return W, H, size, '<rect class="bd-plate" x="-6" y="-4" width="%d" height="%.1f" rx="10"/>' % (W + 12, H + 4) + body

# ---------- fitting ----------
def fit(geom, aspect, near=None):
    """Largest box of the given width/height inside geom, in degrees. Works in a local equal-scale frame.
    near [lon, lat]: keep to the part of a multi-part unit that holds this point (the mainland, say)."""
    lat0 = geom.centroid.y
    kx = math.cos(math.radians(lat0))
    g = affinity.scale(geom, xfact=kx, yfact=1, origin=(0, 0))
    pg = prep(g)
    def size_at(c):
        lo, hi = 0, max(g.bounds[2] - g.bounds[0], g.bounds[3] - g.bounds[1])
        for _ in range(22):
            h = (lo + hi) / 2
            b = box(c[0] - aspect * h / 2, c[1] - h / 2, c[0] + aspect * h / 2, c[1] + h / 2)
            lo, hi = (h, hi) if pg.contains(b) else (lo, h)
        return lo
    parts = list(g.geoms) if g.geom_type == 'MultiPolygon' else [g]
    if near:
        np_ = Point(near[0] * kx, near[1])
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
    best = max(((size_at(c), c) for c in cands))
    h, c = best
    step = h / 4
    for _ in range(3):   # nudge around the best point
        for dx, dy in ((step, 0), (-step, 0), (0, step), (0, -step)):
            c2 = (c[0] + dx, c[1] + dy); h2 = size_at(c2)
            if h2 > h: h, c = h2, c2
        step /= 2
    w = aspect * h
    s, n = c[1] - h / 2, c[1] + h / 2
    west, east = (c[0] - w / 2) / kx, (c[0] + w / 2) / kx
    return h, [[round(s, 6), round(west, 6)], [round(n, 6), round(east, 6)]]

# ---------- build ----------
units = load(UNITS['file'])
fills = [(l, [(f['properties']['name'], prep(shape(f['geometry']))) for f in load(l['file'])['features']]) for l in FILLS]
art_dir = os.path.join(CITY_DIR, BADGES.get('art', 'badges'))
arts = {f[:-4]: open(os.path.join(art_dir, f), encoding='utf-8').read() for f in os.listdir(art_dir) if f.endswith('.svg')} if os.path.isdir(art_dir) else {}
# Optional cities/<city>/badges/places.json: {"Unit name": {"near": [lon, lat]}} to pick which part of a
# multi-part unit the badge sits on.
opts_path = os.path.join(art_dir, 'places.json')
opts = json.load(open(opts_path, encoding='utf-8')) if os.path.isfile(opts_path) else {}
names = {slug(f['properties']['name']) for f in units['features']}
for a in arts:
    if a not in names:
        print('  no unit for drawing %s.svg' % a)

out = []
for f in units['features']:
    name, geom = f['properties']['name'], shape(f['geometry'])
    pt = polylabel(max(geom.geoms, key=lambda p: p.area) if geom.geom_type == 'MultiPolygon' else geom, tolerance=.0005)
    sub = ' · '.join(n for l, polys in fills for n, pg in polys if pg.contains(pt))
    art = arts.get(slug(name))
    if art:
        W, H, fs, body = art_badge(name, sub, art)
        h, b = fit(geom, W / H, opts.get(name, {}).get('near'))
        out.append({'n': name, 'b': b, 'w': round(W, 1), 'h': round(H, 1), 'f': round(fs, 1), 'art': True, 'svg': body})
        continue
    # Text only: try each way of breaking the name and keep the one that comes out largest.
    best = None
    for layout in lines_for(name):
        W, H, fs, body = text_label(name, sub, layout)
        h, b = fit(geom, W / H, opts.get(name, {}).get('near'))
        px = h / H * fs     # name size in degrees: what decides when it becomes readable
        if not best or px > best[0]:
            best = (px, {'n': name, 'b': b, 'w': round(W, 1), 'h': round(H, 1), 'f': fs, 'art': False, 'svg': body})
    out.append(best[1])

path = os.path.join(DATA, BADGES['file'])
json.dump({'units': out}, open(path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('%s: %d badges (%d drawn) -> %s (%d KB)' % (city, len(out), sum(u['art'] for u in out), os.path.relpath(path, ROOT), os.path.getsize(path) // 1024))
