"""Venues pages: Toronto's big live venues, what's on at each this week, and how to get there.

Usage:  python3 engine/venues.py toronto          (refresh-venues.yml runs it nightly after the events fetch)
Reads:  cities/<city>/venues.json                  the curated venues, GTA origins and fare figures
        cities/<city>/raw/venue_events.json        this fortnight's events (fetch_venue_events.py; optional)
        cities/<city>/raw/venue_drives.json        best-case drive minutes and km from each origin (optional)
        docs/<city>/data/*                         the map's published files: stations, lines, stops, streets,
                                                   Green P, permit areas, Bike Share, neighbourhoods
        docs/<city>/profiles/data/walk_grid.json   walk minutes to the nearest station, stop and dock
Writes: docs/<city>/venues/index.html, og.png      the list: every venue, this week's events, a "busy nights"
                                                   strip, sort and filter controls, a "From …" picker
        docs/<city>/venues/<slug>/index.html, og.png   one page per venue: map, events, getting there, parking,
                                                   arrival notes, every GTA origin

The rules: facts only. An event is a name, a date, a time, what kind of thing it is and a link to its own
page at the source; no images, prices or copy. Venues are the stable unit (a page each, so the address lives
on); the week rotates inside them. Capacity is the venue's usual figure and only sorts the list. Drive
times are best case (OSRM, empty roads), the taxi figure is the City's meter rate applied to the road
distance, and both say so. Nothing here promotes an event or sells a ticket.

Pages render without the events file (every venue still shows how to get there) and without drive times
(the picker then shows transit only), so a feed outage degrades to a useful page instead of a stale one.
Needs: pip install shapely pillow fonttools brotli
"""
import html, io, json, math, os, re, sys, unicodedata
from datetime import date, datetime, timedelta
from shapely.geometry import shape, Point, box
from shapely.ops import unary_union
from shapely import make_valid, clip_by_rect
from urllib.parse import quote
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DOCS = os.path.join(ROOT, 'docs')
SITE = 'https://layers.city'
city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: venues.py <city>')
D = os.path.join(DOCS, city, 'data')
CITY_DIR = os.path.join(ROOT, 'cities', city)
OUT = os.path.join(DOCS, city, 'venues')
cfg = json.load(open(os.path.join(D, 'city.json')))
V = json.load(open(os.path.join(CITY_DIR, 'venues.json')))
CITY = V.get('city') or cfg.get('heading') or cfg['title'].split(' · ')[0]
esc = lambda s: html.escape(str(s), quote=True)
CA = cfg.get('search', {}).get('country') == 'ca'
BIG = 8000            # a venue this size or more counts towards a "busy night"
NEAR_GP_KM = 0.65     # straight-line; about a ten-minute walk once streets are allowed for


def opt_json(p, default=None):
    return json.load(open(p)) if os.path.exists(p) else default


EV = opt_json(os.path.join(CITY_DIR, 'raw', 'venue_events.json'), {})
DR = opt_json(os.path.join(CITY_DIR, 'raw', 'venue_drives.json'))
WG = opt_json(os.path.join(DOCS, city, 'profiles', 'data', 'walk_grid.json'))


def gj(name):
    p = os.path.join(D, name + '.geojson')
    return json.load(open(p))['features'] if os.path.exists(p) else []


# ---- a flat projection in km, as in engine/profiles/build.py ------------------------------------------------
hoods = gj('neighbourhoods')
LAT0 = sum(shape(f['geometry']).centroid.y for f in hoods) / len(hoods)
KX, KY = 111.32 * math.cos(math.radians(LAT0)), 110.574
km = lambda lon, lat: (lon * KX, lat * KY)
dist_km = lambda a, b: math.hypot((a[0] - b[0]) * KX, (a[1] - b[1]) * KY)
walk_min = lambda d: max(1, round(d * 1.3 / 4.8 * 60))
fmt_km = lambda d: f'{d * 1000:.0f} m' if d < 1 else f'{d:.1f} km'

stations = [(f['geometry']['coordinates'], f['properties']) for f in gj('subway_stations')]
subway_lines = gj('subway_lines')
streetcars = gj('streetcars')
go_lines = gj('go_lines')
go_stations = [(f['geometry']['coordinates'], f['properties']) for f in gj('go_stations')]
streets = gj('streets')
greenp = [(f['geometry']['coordinates'], f['properties']) for f in gj('parking') if f['properties'].get('c') == 'gp']
permit = [(shape(f['geometry']), f['properties']) for f in gj('permit_areas')]
bikeshare = [(f['geometry']['coordinates'], f['properties']) for f in gj('bikeshare')]
hood_shapes = [(make_valid(shape(f['geometry'])), f['properties']) for f in hoods]
transit = opt_json(os.path.join(D, 'transit.json'), {'routes': [], 'stops': []})
ROUTES, STOPS = transit['routes'], transit['stops']
LINE_COLOR = {f['properties'].get('line'): f['properties'].get('color') for f in subway_lines}
GO_BY_NAME = {p['name']: c for c, p in go_stations}


def slugify(s):
    s = re.sub(r"['’]", '', s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def walk_at(lon, lat):
    """{layer: (minutes, name)} from the fact sheets' walk grid, or None off the grid."""
    if not WG:
        return None
    c = int((lon - WG['lon0']) / WG['dlon']); r = int((lat - WG['lat0']) / WG['dlat'])
    if not (0 <= c < WG['cols'] and 0 <= r < WG['rows']):
        return None
    k = r * WG['cols'] + c
    out = {}
    for key, L in WG['layers'].items():
        m = L['min'][k]
        out[key] = None if m is None else (m, L['names'][L['src'][k]] if L.get('names') else None)
    return out


def hood_of(pt):
    p = Point(*pt)
    return next((props for g, props in hood_shapes if g.contains(p)), None)


def route_badges(rs):
    """Route chips in the fact sheets' TTC styles: streetcars red, buses outlined, express green, GO green."""
    out = []
    for r in rs:
        cls = 'tram' if r.get('m') == 'tram' else 'go' if r.get('m') == 'go' else 'exp' if 'exp' in r.get('f', []) else 'night' if 'night' in r.get('f', []) else ''
        out.append(f'<span class="rb {cls}" title="{esc(r["n"])}">{esc(r["r"])}</span>')
    return ''.join(out)


def near_routes(pt, limit_km=0.4):
    """Daytime routes with a stop within limit_km: streetcars, then frequent buses, then the rest."""
    idx = set()
    for s in STOPS:
        if dist_km((s[0], s[1]), pt) <= limit_km:
            idx.update(s[3] if len(s) > 3 else [])
    rs = [ROUTES[i] for i in sorted(idx) if 'night' not in ROUTES[i].get('f', [])]
    key = lambda r: (0 if r.get('m') == 'tram' else 1 if 'freq' in r.get('f', []) else 2 if r.get('m') != 'go' else 3, int(re.match(r'\d*', r['r']).group() or 0))
    return sorted(rs, key=key)


LINES_HTML = lambda lines: ''.join(f'<span class="ln l{esc(l)}">{esc(l)}</span>' for l in lines)


# ---- facts per venue ---------------------------------------------------------------------------------------------
def facts(v):
    pt = v['at']
    w = walk_at(*pt) or {}
    f = {}
    # subway stations within a long walk, nearest first (the grid gives a street-walk time for the nearest)
    near = sorted(((dist_km(c, pt), p) for c, p in stations), key=lambda t: t[0])
    subs = []
    for d, p in near[:3]:
        if d > 1.6:
            break
        mins = w['subway'][0] if w.get('subway') and w['subway'][1] == p['name'] else walk_min(d)
        subs.append((p['name'], p.get('lines', []), mins))
    f['subway'] = subs
    g = sorted(((dist_km(c, pt), p) for c, p in go_stations), key=lambda t: t[0])[0] if go_stations else None
    if g and g[0] <= 2.5:
        mins = w['go'][0] if w.get('go') and w['go'][1] == g[1]['name'] else walk_min(g[0])
        f['go'] = (g[1]['name'], g[1].get('lines', []), mins)
    f['routes'] = near_routes(pt)
    f['stop'] = w['stop'][0] if w.get('stop') else None
    f['bikeshare'] = w['bikeshare'][0] if w.get('bikeshare') else (walk_min(min(dist_km(c, pt) for c, _ in bikeshare)) if bikeshare else None)
    union = GO_BY_NAME.get('Union Station') or [-79.3806, 43.6453]
    f['union_km'] = dist_km(union, pt)
    f['union_walk'] = walk_min(f['union_km'])
    lots = sorted(((dist_km(c, pt), p) for c, p in greenp if dist_km(c, pt) <= NEAR_GP_KM), key=lambda t: t[0])
    f['greenp'] = [(p['n'], p.get('cap'), p.get('t'), d) for d, p in lots]
    pp = Point(*pt)
    f['permit'] = next((p.get('name') for g_, p in permit if g_.contains(pp)), None)
    f['hood'] = hood_of(pt)
    return f


# ---- events: this week and next, from the feed ----------------------------------------------------------------
TODAY = date.today()
WEEK0 = TODAY - timedelta(days=TODAY.weekday())            # Monday of the current week (the build runs nightly)
WEEK1 = WEEK0 + timedelta(days=7)
KIND_LABEL = {'sports': 'Sports', 'concerts': 'Concert', 'comedy': 'Comedy', 'theatre': 'Theatre', 'film': 'Film', 'other': 'Event'}
ASOF = EV.get('asof')
asof_text = None
if ASOF:
    dt = datetime.strptime(ASOF, '%Y-%m-%dT%H:%M:%SZ')
    asof_text = dt.strftime('%b %-d, %Y') + ' (UTC)'


def events_for(slug):
    rows = EV.get('venues', {}).get(slug, [])
    out = []
    for r in rows:
        try:
            d = date.fromisoformat(r['date'])
        except (TypeError, ValueError):
            continue
        if d < TODAY:
            continue
        out.append(dict(r, d=d))
    return out


def fmt_time(t):
    if not t:
        return 'Time TBA'
    h, m = map(int, t.split(':'))
    return f"{(h % 12) or 12}{':%02d' % m if m else ''} {'am' if h < 12 else 'pm'}"


def day_label(d):
    return d.strftime('%a %b %-d')


def event_li(e, show_venue=None):
    chip = f'<span class="tag {esc(e["kind"])}">{esc(KIND_LABEL.get(e["kind"], "Event"))}</span>'
    st = f' <span class="status">{esc(e["status"])}</span>' if e.get('status') else ''
    link = f' <a class="src" href="{esc(e["url"])}" rel="noopener">Ticketmaster ↗</a>' if e.get('url') else ''
    where = f' <span class="where">{esc(show_venue)}</span>' if show_venue else ''
    return (f'<li data-date="{e["d"].isoformat()}"><time datetime="{e["d"].isoformat()}{"T" + e["time"] if e.get("time") else ""}">'
            f'<b>{esc(day_label(e["d"]))}</b> {esc(fmt_time(e.get("time")))}</time> <span class="ev">{esc(e["name"])}</span>{where} {chip}{st}{link}</li>')


# ---- the small map on a venue page --------------------------------------------------------------------------------
MAP_W, MAP_H, HALF_KM = 600, 400, 1.15


def venue_map(v, others):
    cx, cy = km(*v['at'])
    half_y = HALF_KM * MAP_H / MAP_W
    x0, x1, y0, y1 = cx - HALF_KM, cx + HALF_KM, cy - half_y, cy + half_y
    s = MAP_W / (x1 - x0)
    xy = lambda lon, lat: (round((lon * KX - x0) * s, 1), round((y1 - lat * KY) * s, 1))

    def paths(geom, tol=0.004):
        g = clip_by_rect(make_valid(shape(geom)), x0 / KX, y0 / KY, x1 / KX, y1 / KY)
        out = []
        for part in getattr(g, 'geoms', [g]):
            if part.is_empty or part.geom_type != 'LineString':
                continue
            cs = part.simplify(tol / 100).coords
            out.append('M' + 'L'.join(f'{x} {y}' for x, y in (xy(*c) for c in cs)))
        return out

    inside = lambda lon, lat: x0 <= lon * KX <= x1 and y0 <= lat * KY <= y1
    p = [f'<svg class="vmap" viewBox="0 0 {MAP_W} {MAP_H}" role="img" aria-label="Map of the streets, transit and Green P parking around {esc(v["name"])}">',
         f'<rect width="{MAP_W}" height="{MAP_H}" fill="var(--land)"/>']
    for f in streets:
        w = 4.2 if f['properties'].get('cls') == 'major' else 2.6
        for d in paths(f['geometry']):
            p.append(f'<path d="{d}" fill="none" stroke="var(--street)" stroke-width="{w}" stroke-linecap="round"/>')
    for f in go_lines:
        for d in paths(f['geometry']):
            p.append(f'<path d="{d}" fill="none" stroke="var(--go)" stroke-width="2.4" stroke-dasharray="7 4"/>')
    for f in streetcars:
        for d in paths(f['geometry']):
            p.append(f'<path d="{d}" fill="none" stroke="#D7261E" stroke-width="2.2" stroke-opacity=".75"/>')
    for f in subway_lines:
        for d in paths(f['geometry']):
            p.append(f'<path d="{d}" fill="none" stroke="{esc(f["properties"].get("color") or "#333")}" stroke-width="5" stroke-linecap="round"/>')
    for c, pr in greenp:
        if inside(*c):
            x, y = xy(*c)
            p.append(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" rx="2" fill="#0B8A44"/><text x="{x}" y="{y + 3.4}" text-anchor="middle" font-size="8" font-weight="800" fill="#fff" font-family="var(--display)">P</text>')
    labels = []
    for c, pr in go_stations:
        if inside(*c) and pr['name'] != 'Union Station':
            x, y = xy(*c); p.append(f'<rect x="{x - 4}" y="{y - 4}" width="8" height="8" fill="#fff" stroke="var(--go)" stroke-width="2"/>'); labels.append((x, y, pr['name']))
    for c, pr in stations:
        if inside(*c):
            x, y = xy(*c); p.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="#fff" stroke="#1A1414" stroke-width="2"/>'); labels.append((x, y, pr['name']))
    for o in others:
        if o['slug'] != v['slug'] and inside(*o['at']):
            x, y = xy(*o['at']); p.append(f'<circle cx="{x}" cy="{y}" r="5" fill="var(--muted)"/>'); labels.append((x, y, o['name']))
    for x, y, name in labels:
        p.append(f'<text x="{x + 7}" y="{y + 4}" font-size="11" font-family="var(--body)" fill="var(--ink)" stroke="var(--land)" stroke-width="3" paint-order="stroke">{esc(name)}</text>')
    x, y = xy(*v['at'])
    p.append(f'<path transform="translate({x - 11},{y - 30}) scale(.26)" d="M42 94 C42 94 4 56 4 30 A38 38 0 0 1 80 30 C80 56 42 94 42 94 Z" fill="var(--accent)" stroke="#fff" stroke-width="6"/>')
    p.append(f'<circle cx="{x}" cy="{y - 22}" r="4" fill="#fff"/>')
    p.append(f'<text x="{x}" y="{y + 16}" text-anchor="middle" font-size="13" font-weight="700" font-family="var(--display)" fill="var(--ink)" stroke="var(--land)" stroke-width="4" paint-order="stroke">{esc(v["name"])}</text>')
    p.append('</svg>')
    return ''.join(p)


# ---- the social preview image -----------------------------------------------------------------------------------
def font(weight, size, fam='archivo'):
    f = TTFont(os.path.join(DOCS, 'fonts', f'{fam}-latin-{weight}-normal.woff2')); f.flavor = None
    b = io.BytesIO(); f.save(b); b.seek(0)
    return ImageFont.truetype(b, size)


F_BIG = {s: font(800, s) for s in (84, 72, 62, 54, 46)}
F_SUB, F_BRAND, F_BRAND2 = font(700, 34), font(800, 34), font(700, 34)
RED, INK, INK2, PAPER, LAND, EDGE = '#C8102E', '#1A1414', '#5C5251', '#FBF6F5', '#EDE4E2', '#D6C9C6'
CITY_SHAPE = unary_union([g for g, _ in hood_shapes])
minx, miny, maxx, maxy = CITY_SHAPE.bounds
kx = math.cos(math.radians((miny + maxy) / 2))
BOX = (660, 40, 1160, 590)
sc = min((BOX[2] - BOX[0]) / ((maxx - minx) * kx), (BOX[3] - BOX[1]) / (maxy - miny))
ox = BOX[0] + ((BOX[2] - BOX[0]) - (maxx - minx) * kx * sc) / 2
oy = BOX[1] + ((BOX[3] - BOX[1]) - (maxy - miny) * sc) / 2
proj = lambda x, y: (ox + (x - minx) * kx * sc, oy + (maxy - y) * sc)


def wrap(d, text, f, width):
    words, lines = text.split(), ['']
    for w in words:
        t = (lines[-1] + ' ' + w).strip()
        if d.textlength(t, font=f) <= width or not lines[-1]: lines[-1] = t
        else: lines.append(w)
    return lines


def og_image(name, pins, path, sub):
    S = 2
    im = Image.new('RGB', (1200 * S, 630 * S), PAPER); d = ImageDraw.Draw(im)
    P = lambda x, y: tuple(v * S for v in proj(x, y))
    for g in getattr(CITY_SHAPE, 'geoms', [CITY_SHAPE]):
        d.polygon([P(*c) for c in g.exterior.coords], fill=LAND, outline=EDGE, width=S)
    for lon, lat in pins:
        x, y = P(lon, lat); r = (16 if len(pins) == 1 else 9) * S
        d.ellipse([x - r, y - r, x + r, y + r], fill=RED, outline=PAPER, width=2 * S)
    im = im.resize((1200, 630), Image.LANCZOS); d = ImageDraw.Draw(im)
    d.text((72, 64), 'Layers', font=F_BRAND, fill=INK)
    d.text((72 + d.textlength('Layers', font=F_BRAND), 64), '.City', font=F_BRAND2, fill=RED)
    for s, f in F_BIG.items():
        lines = wrap(d, name, f, 540)
        if len(lines) <= 3 and max(d.textlength(ln, font=f) for ln in lines) <= 560: break
    y = 315 - len(lines) * s * 1.08 / 2
    for ln in lines:
        d.text((72, y), ln, font=f, fill=INK); y += s * 1.08
    d.text((72, y + 18), sub, font=F_SUB, fill=INK2)
    im.convert('P', palette=Image.ADAPTIVE, colors=48).save(path, optimize=True)


# ---- page chrome, in the place pages' style (engine/places.py) ------------------------------------------------
CSS = """@font-face{font-family:'Archivo';font-weight:800;font-display:swap;src:url(/fonts/archivo-latin-800-normal.woff2) format('woff2')}
@font-face{font-family:'Archivo';font-weight:700;font-display:swap;src:url(/fonts/archivo-latin-700-normal.woff2) format('woff2')}
@font-face{font-family:'IBM Plex Sans';font-weight:400;font-display:swap;src:url(/fonts/ibm-plex-sans-latin-400-normal.woff2) format('woff2')}
@font-face{font-family:'IBM Plex Sans';font-weight:500;font-display:swap;src:url(/fonts/ibm-plex-sans-latin-500-normal.woff2) format('woff2')}
:root{--bg:#F7F4F3;--card:#FFFFFF;--ink:#1A1414;--ink-2:#463D3C;--ink-3:#5C5251;--muted:#7A6E6C;--rule:#D8CFCD;--accent:#C8102E;--soft:rgba(200,16,46,.08);
--land:#F2EEEC;--street:#FFFFFF;--go:#1E6B47;--display:'Archivo',system-ui,sans-serif;--body:'IBM Plex Sans',system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#161212;--card:#201A1A;--ink:#F3ECEB;--ink-2:#CFC4C2;--ink-3:#A89D9B;--muted:#9A8E8C;--rule:#3A3130;--accent:#E5364F;--soft:rgba(229,54,79,.14);--land:#2A2222;--street:#3E3534;--go:#4FB37F}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);font-size:17px;line-height:1.55}
a{color:var(--accent)}
.wrap{max-width:860px;margin:0 auto;padding:0 20px}
header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:22px 0}
.brand{display:flex;align-items:center;gap:10px;color:var(--ink);text-decoration:none;font-family:var(--display);font-weight:800;font-size:20px}
.brand b{color:var(--accent);font-weight:700}.brand svg{width:26px;height:auto}
.crumbs{font-size:14px;color:var(--ink-3)}.crumbs a{color:var(--ink-2)}
h1{font-family:var(--display);font-weight:800;font-size:clamp(34px,6.5vw,56px);line-height:1.02;letter-spacing:-.02em;margin:22px 0 10px}
.kind{margin:0;color:var(--ink-2);font-size:18px}.in{margin:6px 0 0;color:var(--ink-2)}
.go{display:inline-flex;align-items:center;gap:8px;margin:22px 0 8px;min-height:48px;padding:0 22px;border-radius:999px;background:var(--accent);color:#fff;text-decoration:none;font-weight:500;font-size:17px}
.go:focus-visible,.brand:focus-visible,button:focus-visible,select:focus-visible{outline:3px solid var(--ink);outline-offset:3px}
section{background:var(--card);border:1.5px solid var(--rule);border-radius:14px;padding:22px 24px;margin:20px 0}
h2{font-family:var(--display);font-weight:700;font-size:22px;margin:0 0 12px}
h3{font-family:var(--display);font-weight:700;font-size:18px;margin:16px 0 6px}
dl{margin:0}dt{font-weight:500;margin-top:14px}dt:first-child{margin-top:0}dd{margin:2px 0 0;color:var(--ink-2)}
.note{font-size:14px;color:var(--ink-3)}
.stamp{font-size:14px;color:var(--ink-3);margin:8px 0 0}
ul.events{list-style:none;margin:0;padding:0}
ul.events li{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;padding:9px 0;border-top:1px solid var(--rule)}
ul.events li:first-child{border-top:0}
ul.events time{flex:0 0 150px;color:var(--ink-2);font-size:15px}ul.events time b{color:var(--ink);font-weight:500}
ul.events .ev{flex:1 1 220px;font-weight:500}
ul.events .where{color:var(--ink-3);font-size:15px}
.tag{display:inline-block;padding:1px 9px;border-radius:999px;font-size:13px;background:var(--soft);color:var(--ink)}
.status{font-size:13px;color:var(--accent);text-transform:capitalize}
.src{font-size:14px;white-space:nowrap}
.empty{color:var(--ink-3);margin:0}
.ln{display:inline-grid;place-items:center;width:18px;height:18px;border-radius:50%;font:800 11px/1 var(--display);color:#fff;vertical-align:-3px;margin-right:2px}
.ln.l1{background:#FFC425;color:#1A1414}.ln.l2{background:#00A64F}.ln.l4{background:#A8518A}.ln.l5{background:#F58426}.ln.l6{background:#959595}
.rbs{display:inline-flex;flex-wrap:wrap;gap:4px;vertical-align:middle}
.rb{display:inline-grid;place-items:center;box-sizing:border-box;height:19px;min-width:27px;padding:0 4px;border-radius:4px;font:700 11.5px/1 var(--body);background:#fff;color:#D7261E;box-shadow:inset 0 0 0 1.5px #D7261E}
.rb.tram{background:#D7261E;color:#fff;box-shadow:none}.rb.exp{background:#15924A;color:#fff;box-shadow:none}.rb.go{background:#1E6B47;color:#fff;box-shadow:none}.rb.night{background:#fff;color:#1F4FA3;box-shadow:inset 0 0 0 1.5px #1F4FA3}
.vmap{display:block;width:100%;height:auto;border-radius:10px;border:1px solid var(--rule)}
.legend{font-size:13px;color:var(--ink-3);margin:8px 0 0}
.card{background:var(--card);border:1.5px solid var(--rule);border-radius:14px;padding:20px 22px;margin:14px 0}
.card h2{margin:0}.card h2 a{color:var(--ink);text-decoration:none}.card h2 a:hover{color:var(--accent)}
.meta{color:var(--ink-3);font-size:15px;margin:4px 0 10px}
.card .from{margin:10px 0 0;padding-top:10px;border-top:1px dashed var(--rule);font-size:15px;color:var(--ink-2)}
.controls{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;margin:18px 0 6px;font-size:15px}
.controls label{display:inline-flex;align-items:center;gap:8px;color:var(--ink-2)}
.controls select{font:inherit;min-height:40px;padding:6px 10px;border:1.5px solid var(--rule);border-radius:8px;background:var(--card);color:var(--ink)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0;list-style:none}
.chips button{font:inherit;font-size:15px;min-height:36px;padding:0 14px;border-radius:999px;border:1.5px solid var(--rule);background:var(--card);color:var(--ink);cursor:pointer}
.chips button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.busy{border-color:var(--accent)}.busy ul{margin:0;padding-left:20px}.busy li{margin:4px 0}
table{width:100%;border-collapse:collapse;font-size:15px}th,td{text-align:left;padding:8px 10px 8px 0;border-top:1px solid var(--rule);vertical-align:top}th{font-weight:500;color:var(--ink-2)}tr:first-child th,tr:first-child td{border-top:0}
td.n{white-space:nowrap}
footer{padding:28px 0 40px;font-size:14px;color:var(--ink-3)}footer a{color:var(--ink-2)}
[hidden]{display:none!important}
@media (max-width:560px){section,.card{padding:16px}ul.events time{flex-basis:100%}h1{margin-top:12px}.in-card dt{margin-top:10px}}"""
PIN = ('<svg viewBox="18 6 84 108" aria-hidden="true"><path d="M60 112 C60 112 22 74 22 48 A38 38 0 0 1 98 48 C98 74 60 112 60 112 Z" fill="#C8102E"/>'
       '<polygon points="60,52 84,63 60,74 36,63" fill="#fff" fill-opacity=".42"/><polygon points="60,39 84,50 60,61 36,50" fill="#fff" fill-opacity=".72"/>'
       '<polygon points="60,20 90,34 60,48 30,34" fill="#fff"/>%s</svg>')
PIN %= ('<path transform="translate(51,24.5) scale(0.9)" d="M10 0 L11.6 3.2 L13.2 2.4 L12.6 6.6 L15.2 4.2 L15.8 5.8 '
        'L18.4 5.2 L17.4 8.2 L19.2 9.2 L14.6 12.8 L15.2 14.6 L10.6 14 L10.8 18.6 L9.2 18.6 L9.4 14 L4.8 14.6 L5.4 12.8 '
        'L0.8 9.2 L2.6 8.2 L1.6 5.2 L4.2 5.8 L4.8 4.2 L7.4 6.6 L6.8 2.4 L8.4 3.2 Z" fill="#C8102E"/>' if CA else '')
BRAND = '-ca' if CA else ''
SOURCE_NOTE = ('Event listings: Ticketmaster Discovery API, refreshed nightly; each event links to its own Ticketmaster page. '
               'Layers.City sells nothing and carries no paid or affiliate links. Transit: TTC and Metrolinx. Parking: Toronto Parking Authority. '
               'Walk and drive times: OpenStreetMap data, OSRM for driving (best case, empty roads).')


def page(title, desc, canonical, og, body, crumbs):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Layers.City">
<meta property="og:url" content="{canonical}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{og}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="/apple-touch-icon{BRAND}.png">
<style>{CSS}</style>
<script src="/stats.js" defer></script>
</head>
<body>
<div class="wrap">
<header><a class="brand" href="/">{PIN}<span>Layers<b>.City</b></span></a>
<nav class="crumbs">{crumbs}</nav></header>
<main>
{body}
</main>
<footer>{esc(SOURCE_NOTE)}<br><a href="/attributions/">Attributions</a> · <a href="/privacy/">Privacy</a> · <a href="/terms/">Terms</a> · <a href="/">All maps</a></footer>
</div>
<script>
(()=>{{const t=new Date(),today=t.getFullYear()+'-'+String(t.getMonth()+1).padStart(2,'0')+'-'+String(t.getDate()).padStart(2,'0');
document.querySelectorAll('li[data-date]').forEach(li=>{{if(li.dataset.date<today)li.hidden=true}});
document.querySelectorAll('ul.events').forEach(ul=>{{if(![...ul.children].some(li=>!li.hidden)){{const p=ul.nextElementSibling;if(p&&p.classList.contains('empty'))p.hidden=false;ul.hidden=true}}}});}})();
</script>
</body>
</html>
"""


# ---- origins: transit route in words, drive and taxi figures -----------------------------------------------------
FARES = V.get('fares', {})
ORIGINS = V.get('origins', [])
DR_MIN = {}
if DR:
    for i, o in enumerate(DR['origins']):
        for j, s in enumerate(DR['venues']):
            DR_MIN[(o, s)] = (DR['min'][i][j], DR['km'][i][j])


def taxi(km_):
    return FARES.get('taxiDrop', 0) + km_ * FARES.get('taxiPerKm', 0)


GO_LINES_AT = {p['name']: set(p.get('lines', [])) for _, p in go_stations}


def from_union_words(f):
    """How to finish the trip from Union Station, from the venue's own facts."""
    if f['union_walk'] <= 15:
        return f"then about {f['union_walk']} min on foot"
    if f['subway']:
        n, lines, mins = f['subway'][0]
        return f"then the subway to {n} and about {mins} min on foot"
    if f.get('go'):
        return f"then GO to {f['go'][0]} and about {f['go'][2]} min on foot"
    return 'then a TTC connection'


def site_name(u):
    return re.sub(r'^https?://(www\.)?', '', u).rstrip('/')


def origin_rows(v, f):
    rows = []
    for o in ORIGINS:
        dm = DR_MIN.get((o['name'], v['slug']))
        if o['mode'] == 'ttc':
            if o['via'] == 'Union Station':
                transit = f"From Union, {from_union_words(f)[5:]}"
            elif f['subway'] and f['subway'][0][2] <= 25:
                n, _, mins = f['subway'][0]
                transit = f"TTC from {o['via']} to {n}, then about {mins} min on foot"
            else:
                transit = f"TTC from {o['via']} to Union, {from_union_words(f)}"
            fare = f"TTC adult fare ${FARES['ttc']:.2f}" if FARES.get('ttc') else None
        else:
            # A GO train that stops at the venue's own station (Exhibition on Lakeshore West, Downsview Park on Barrie)
            direct = f.get('go') and f['go'][2] <= 25 and GO_LINES_AT.get(o['via'], set()) & set(f['go'][1]) and f['go'][0] != 'Union Station'
            if direct:
                transit = f"GO from {o['via']} to {f['go'][0]}, then about {f['go'][2]} min on foot"
            else:
                transit = f"GO from {o['via']} to Union, {from_union_words(f)}"
            fare = 'GO fare; the TTC leg is free (One Fare)'
        rows.append({'name': o['name'], 'transit': transit, 'fare': fare,
                     'drive': None if not dm or dm[0] is None else dm[0], 'km': None if not dm or dm[1] is None else dm[1],
                     'taxi': None if not dm or dm[1] is None or not FARES.get('taxiPerKm') else round(taxi(dm[1]))})
    return rows


# ---- build ------------------------------------------------------------------------------------------------------
venues = sorted(V['venues'], key=lambda v: -v['capacity'])
os.makedirs(OUT, exist_ok=True)
INDEX = f'{SITE}/{city}/venues/'
crumbs_idx = f'<a href="/{city}/">{esc(CITY)} map</a> · <a href="/{city}/venues/">Venues</a>'
cards, all_events = [], []
for v in venues:
    f = facts(v)
    evs = events_for(v['slug'])
    for e in evs:
        all_events.append(dict(e, venue=v))
    this_week = [e for e in evs if e['d'] < WEEK1]
    next_week = [e for e in evs if WEEK1 <= e['d'] < WEEK1 + timedelta(days=7)]
    kinds = ', '.join({'sports': 'sports', 'concerts': 'concerts', 'comedy': 'comedy', 'theatre': 'theatre'}[k] for k in v['kinds'])
    home = f" · Home of {' and '.join(v['homeOf'])}" if v.get('homeOf') else ''
    arrive = (f"{f['subway'][0][0]} station, about {f['subway'][0][2]} min on foot" if f['subway'] and f['subway'][0][2] <= 25
              else f"{f['go'][0]}, about {f['go'][2]} min on foot" if f.get('go') and f['go'][2] <= 25
              else 'Bus or streetcar at the door' if f['routes'] else 'Best reached by car')
    map_link = f"/{city}/#map=16/{v['at'][1]}/{v['at'][0]}&pin={v['at'][1]},{v['at'][0]}&name={quote(v['name'])}"

    # ---- the venue's own page
    parts = [f'<h1>{esc(v["name"])}</h1>',
             f'<p class="kind">{esc(v["address"])} · about {v["capacity"]:,} seats · {esc(kinds)}{esc(home)}</p>']
    if f['hood']:
        hs = slugify(f['hood']['name'])
        parts.append(f'<p class="in">In <a href="/{city}/{hs}/">{esc(f["hood"]["name"])}</a>' +
                     (f' · <a href="/{city}/profiles/?n={hs}&amp;at={v["at"][1]:.3f},{v["at"][0]:.3f}">Fact sheet from this spot</a>' if os.path.exists(os.path.join(DOCS, city, 'profiles', 'data', hs + '.json')) else '') + '</p>')
    parts.append(f'<a class="go" href="{esc(map_link)}">Open {esc(v["name"])} on the map <span aria-hidden="true">→</span></a>')
    parts.append(venue_map(v, venues))
    parts.append('<p class="legend">Subway lines in their colours, streetcars red, GO lines dashed green, Green P in green squares, other venues in grey.</p>')
    # events
    sec = '<section><h2>This week</h2>'
    if not EV:
        sec += '<p class="empty">No listing yet: the events feed hasn’t run. Getting-there facts below don’t depend on it.</p>'
    else:
        sec += (f'<ul class="events">{"".join(event_li(e) for e in this_week)}</ul>' if this_week else '') + \
               f'<p class="empty"{"" if not this_week else " hidden"}>Nothing listed here this week.</p>'
        if next_week:
            sec += f'<h3>Next week</h3><ul class="events">{"".join(event_li(e) for e in next_week)}</ul><p class="empty" hidden>Nothing listed for next week.</p>'
        sec += f'<p class="stamp">Listing from Ticketmaster, as of {esc(asof_text)}. Week runs {esc(V.get("week", "Monday to Sunday"))}.</p>'
    parts.append(sec + '</section>')
    # getting there
    dl = []
    if f['subway']:
        dl.append(('Subway', '<br>'.join(f'{LINES_HTML(l)} {esc(n)} · about {m} min on foot' for n, l, m in f['subway'])))
    if f.get('go'):
        dl.append(('GO Transit', f'{esc(f["go"][0])} · about {f["go"][2]} min on foot · {esc(", ".join(f["go"][1]))}'))
    if f['routes']:
        dl.append(('Streetcars and buses within a 5-minute walk', f'<span class="rbs">{route_badges(f["routes"][:14])}</span>' + (f' <span class="note">+{len(f["routes"]) - 14} more</span>' if len(f['routes']) > 14 else '')))
    dl.append(('From Union Station', f'about {f["union_walk"]} min on foot ({fmt_km(f["union_km"])} as the crow flies)' if f['union_walk'] <= 40 else f'{fmt_km(f["union_km"])} as the crow flies; see the origins table below'))
    if f['bikeshare'] is not None:
        dl.append(('Nearest Bike Share dock', f'about {f["bikeshare"]} min on foot'))
    parts.append('<section><h2>Getting there</h2><dl>' + ''.join(f'<dt>{esc(a)}</dt><dd>{b}</dd>' for a, b in dl) + '</dl></section>')
    # parking
    pk = []
    if f['greenp']:
        pk.append(('Green P within a 10-minute walk', '<br>'.join(f'{esc(n)} · {"garage" if t == "g" else "lot"}' + (f' · {c:,} spaces' if c else '') + f' · {fmt_km(d)}' for n, c, t, d in f['greenp'][:8]) +
                   (f'<br><span class="note">+{len(f["greenp"]) - 8} more</span>' if len(f['greenp']) > 8 else '')))
        pk.append(('Green P spaces within that walk', f'{sum(c or 0 for _, c, _, _ in f["greenp"]):,} in {len(f["greenp"])} locations'))
    else:
        pk.append(('Green P within a 10-minute walk', 'None'))
    pk.append(('Street parking', f'Permit area {esc(f["permit"])}: residents’ permits apply on side streets' if f['permit'] else 'Not in a permit-parking area'))
    parts.append('<section><h2>Parking</h2><dl>' + ''.join(f'<dt>{esc(a)}</dt><dd>{b}</dd>' for a, b in pk) + '</dl>'
                 '<p class="note" style="margin:12px 0 0">Green P figures are capacities, not live availability. Venues’ own lots are described in the notes.</p></section>')
    if v.get('notes'):
        parts.append('<section><h2>Arriving</h2>' + ''.join(f'<p style="margin:0 0 10px">{esc(n)}</p>' for n in v['notes']) +
                     f'<p class="note">Written from the venue’s own visitor pages; gates and policies change, so check <a href="{esc(v["site"])}" rel="noopener">{esc(site_name(v["site"]))}</a> before you go.</p></section>')
    # origins
    rows = origin_rows(v, f)
    have_drive = any(r['drive'] is not None for r in rows)
    tbl = '<table><tr><th>From</th>' + ('<th>Drive, best case</th><th>Taxi meter, about</th>' if have_drive else '') + '<th>Transit</th></tr>'
    for r in rows:
        tbl += f'<tr><td class="n">{esc(r["name"])}</td>'
        if have_drive:
            tbl += (f'<td class="n">{r["drive"]} min · {r["km"]} km</td><td class="n">${r["taxi"]}</td>' if r['drive'] is not None else '<td>–</td><td>–</td>')
        tbl += f'<td>{esc(r["transit"])}' + (f'<br><span class="note">{esc(r["fare"])}</span>' if r['fare'] else '') + '</td></tr>'
    tbl += '</table>'
    parts.append('<section><h2>From across the GTA</h2>' + tbl +
                 f'<p class="note" style="margin:12px 0 0">Drive times are OSRM’s on empty roads, the same best-case figure as the map’s suburban lens; game nights run far slower. '
                 f'The taxi figure is the City of Toronto meter rate (${FARES.get("taxiDrop", 0):.2f} plus ${FARES.get("taxiPerKm", 0):.2f}/km, as of {esc(FARES.get("asof", ""))}) on that distance, the only published benchmark; rideshare prices aren’t published and surge after events. '
                 f'{esc(FARES.get("oneFare", ""))}</p></section>')
    parts.append(f'<p class="note"><a href="/{city}/venues/">All {esc(CITY)} venues</a></p>')
    desc = f"{v['name']}, {v['address']}: what's on this week, nearest subway and GO, streetcars and buses, Green P parking within a ten-minute walk, and drive and transit from across the GTA."
    vdir = os.path.join(OUT, v['slug']); os.makedirs(vdir, exist_ok=True)
    og_image(v['name'], [v['at']], os.path.join(vdir, 'og.png'), f'Venue · {CITY}')
    open(os.path.join(vdir, 'index.html'), 'w').write(page(f"{v['name']} · {CITY} venues · Layers.City", desc, f'{INDEX}{v["slug"]}/', f'{INDEX}{v["slug"]}/og.png', '\n'.join(parts), crumbs_idx))

    # ---- its card on the list
    soon7 = [e for e in evs if e['d'] < TODAY + timedelta(days=7)]
    soonest = evs[0]['d'].isoformat() if evs else '9999-12-31'
    from_json = {r['name']: [r['drive'], r['km'], r['taxi'], r['transit'], r['fare']] for r in rows}
    ev_html = (f'<ul class="events">{"".join(event_li(e) for e in soon7)}</ul>' if soon7 else '') + \
              (f'<p class="empty"{"" if not soon7 else " hidden"}>Nothing listed here in the next seven days.</p>' if EV else '')
    cards.append(f'<article class="card" data-cap="{v["capacity"]}" data-kinds="{esc(" ".join(v["kinds"]))}" data-soon="{soonest}" data-from="{esc(json.dumps(from_json, separators=(",", ":")))}">'
                 f'<h2><a href="/{city}/venues/{v["slug"]}/">{esc(v["name"])}</a></h2>'
                 f'<p class="meta">about {v["capacity"]:,} seats · {esc(v["address"])}{esc(home)}<br>{esc(arrive)}</p>'
                 f'{ev_html}<p class="from" hidden></p></article>')

# ---- the list page: busy nights, controls, cards -----------------------------------------------------------------
busy = {}
for e in all_events:
    if e['venue']['capacity'] >= BIG and e['d'] < WEEK1 + timedelta(days=7) and not e.get('status'):
        busy.setdefault(e['d'], {}).setdefault(e['venue']['name'], []).append(e['name'])
busy_days = [(d, vs) for d, vs in sorted(busy.items()) if len(vs) >= 2]
strip = ''
if busy_days:
    strip = '<section class="busy"><h2>Busy nights downtown</h2><p class="note" style="margin:0 0 8px">Two or more of the big venues on the same day: expect full garages, slow approaches and crowded trains after.</p><ul>' + \
            ''.join(f'<li data-date="{d.isoformat()}"><b>{esc(day_label(d))}</b>: ' + ' · '.join(f'{esc(vn)} ({esc(evn[0])}{" +" + str(len(evn) - 1) if len(evn) > 1 else ""})' for vn, evn in vs.items()) + '</li>' for d, vs in busy_days) + '</ul></section>'
elif EV:
    strip = '<section class="busy"><h2>Busy nights downtown</h2><p class="note" style="margin:0">No day this week or next has two of the big venues busy at once, by the listing.</p></section>'

origin_opts = ''.join(f'<option value="{esc(o["name"])}">{esc(o["name"])}</option>' for o in ORIGINS)
controls = f"""<div class="controls">
<label>Sort <select id="sort"><option value="cap">Largest first</option><option value="soon">Soonest event</option><option value="near">Closest to where I’m coming from</option></select></label>
<label>From <select id="from"><option value="">—</option>{origin_opts}</select></label>
</div>
<ul class="chips" id="kinds" role="group" aria-label="Kind of event">
<li><button type="button" data-kind="" aria-pressed="true">All</button></li><li><button type="button" data-kind="sports" aria-pressed="false">Sports</button></li><li><button type="button" data-kind="concerts" aria-pressed="false">Concerts</button></li><li><button type="button" data-kind="comedy" aria-pressed="false">Comedy</button></li><li><button type="button" data-kind="theatre" aria-pressed="false">Theatre</button></li>
</ul>"""
script = """<script>
(()=>{const cards=[...document.querySelectorAll('article.card')],list=document.getElementById('list'),sortEl=document.getElementById('sort'),fromEl=document.getElementById('from');
let kind='';try{fromEl.value=localStorage.getItem('venues.from')||'';}catch(e){}
const fromOf=c=>{try{return JSON.parse(c.dataset.from)[fromEl.value]}catch(e){return null}};
function apply(){const f=fromEl.value;cards.forEach(c=>{const r=f?fromOf(c):null,p=c.querySelector('.from');c.hidden=!!kind&&!c.dataset.kinds.split(' ').includes(kind);
if(r){p.hidden=false;p.innerHTML='From <b>'+f.replace(/</g,'&lt;')+'</b>: '+(r[0]!=null?'drive about '+r[0]+' min ('+r[1]+' km), taxi meter about $'+r[2]+' · ':'')+r[3].replace(/</g,'&lt;')+(r[4]?' · '+r[4].replace(/</g,'&lt;'):'');}else p.hidden=true;});
const key=sortEl.value;const val=c=>key==='cap'?-(+c.dataset.cap):key==='soon'?c.dataset.soon:(f&&fromOf(c)&&fromOf(c)[0]!=null?fromOf(c)[0]:1e9);
[...cards].sort((a,b)=>val(a)<val(b)?-1:val(a)>val(b)?1:0).forEach(c=>list.appendChild(c));
try{localStorage.setItem('venues.from',f)}catch(e){}}
sortEl.addEventListener('change',apply);fromEl.addEventListener('change',()=>{if(fromEl.value&&sortEl.value==='cap')sortEl.value='near';apply()});
document.querySelectorAll('#kinds button').forEach(b=>b.addEventListener('click',()=>{kind=b.dataset.kind;document.querySelectorAll('#kinds button').forEach(x=>x.setAttribute('aria-pressed',x===b));apply()}));
apply();})();
</script>"""
intro = (f'<h1>{esc(CITY)}’s big venues, this week</h1>'
         f'<p class="kind">What’s on at the {len(venues)} places most of the GTA travels to, and how to get to each: nearest station, streetcars and buses, Green P within a ten-minute walk, and drive and transit from across the region. '
         f'A listing, not a guide: the facts and a link to the source, nothing else.</p>'
         + (f'<p class="stamp">Listing from Ticketmaster as of {esc(asof_text)} · week runs {esc(V.get("week", "Monday to Sunday"))}. Cards show the next seven days; each venue’s page has this week and next. Pick where you’re coming from to see the trip.</p>' if asof_text else
            '<p class="stamp">The events feed hasn’t run yet, so there’s no listing; every venue’s getting-there facts are here already.</p>'))
body = intro + strip + controls + '<div id="list">' + ''.join(cards) + '</div>' + script
idx_desc = f"What's on this week at {CITY}'s big venues, from Rogers Centre and Scotiabank Arena to Massey Hall, and how to get to each: nearest subway and GO, streetcars, Green P within a ten-minute walk, drive and transit from across the GTA."
og_image(f'{CITY}’s big venues', [v['at'] for v in venues], os.path.join(OUT, 'card.png'), 'This week, and how to get there')
open(os.path.join(OUT, 'index.html'), 'w').write(page(f'{CITY} venues this week · Layers.City', idx_desc, INDEX, f'{INDEX}card.png', body, crumbs_idx))
print(f'{city}: {len(venues)} venue pages + /{city}/venues/ ({sum(len(events_for(v["slug"])) for v in venues)} events{"" if DR else ", no drive times yet"})')
