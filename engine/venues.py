"""Venues pages: a city's big live venues, what's on at each this week, and how to get there.

Usage:  python3 engine/venues.py <city>            (refresh-venues.yml runs it nightly after the events fetch)
Reads:  cities/<city>/venues.json                  the curated venues, regional origins and fare figures, and
                                                   "page": which of the map's files are the subway, regional
                                                   rail, streetcars, parking and boundaries, and the city's
                                                   own words for them (the engine names no city)
        cities/<city>/factsheet.css                line bullets and route badges in the city's colours
        cities/<city>/raw/venue_events.json        this fortnight's events (fetch_venue_events.py; optional)
        cities/<city>/raw/venue_drives.json        best-case drive minutes and km from each origin (optional)
        docs/<city>/data/*                         the map's published files: stations, lines, stops, streets,
                                                   parking, permit areas, bike share, boundaries
        docs/<city>/profiles/data/walk_grid.json   walk minutes to the nearest station, stop and dock
Writes: docs/<city>/venues/index.html, og.png      the list: every venue, this week's events, a "busy nights"
                                                   strip, sort and filter controls, a "From …" picker
        docs/<city>/venues/<slug>/index.html, og.png   one page per venue: map, events, getting there, parking,
                                                   arrival notes, every regional origin

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
PG = V.get('page', {})
W = PG.get('words', {})
word = lambda k, d='': W.get(k, d)
RAIL = PG.get('rail') or {}
HUBS = PG.get('hubs') or []
PARK = PG.get('parking') or {}
MI = PG.get('distance') == 'mi'
UNIT = 'mi' if MI else 'km'
dist_u = lambda d: round(d / 1.609344, 1) if (MI and d is not None) else d      # road km from OSRM, in the page's unit
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
hoods = gj(PG.get('units', 'neighbourhoods'))
LAT0 = sum(shape(f['geometry']).centroid.y for f in hoods) / len(hoods)
KX, KY = 111.32 * math.cos(math.radians(LAT0)), 110.574
km = lambda lon, lat: (lon * KX, lat * KY)
dist_km = lambda a, b: math.hypot((a[0] - b[0]) * KX, (a[1] - b[1]) * KY)
walk_min = lambda d: max(1, round(d * 1.3 / 4.8 * 60))
fmt_km = ((lambda d: f'{d / 1.609344 * 5280:,.0f} ft' if d < 0.4 else f'{d / 1.609344:.1f} mi') if MI else
          (lambda d: f'{d * 1000:.0f} m' if d < 1 else f'{d:.1f} km'))

stations = [(f['geometry']['coordinates'], f['properties']) for f in gj('subway_stations')]
subway_lines = gj('subway_lines')
streetcars = gj(PG['trams']) if PG.get('trams') else []
go_lines = gj(RAIL['lines']) if RAIL.get('lines') else []
go_stations = [(f['geometry']['coordinates'], f['properties']) for f in gj(RAIL['stations'])] if RAIL.get('stations') else []
streets = gj('streets')
greenp = [(f['geometry']['coordinates'], f['properties']) for f in gj('parking') if f['properties'].get('c') == PARK.get('cat', 'gp')] if PARK else []
permit = [(shape(f['geometry']), f['properties']) for f in gj(PG['permit'])] if PG.get('permit') else []
bikeshare = [(f['geometry']['coordinates'], f['properties']) for f in gj('bikeshare')]
hood_shapes = [(make_valid(shape(f['geometry'])), f['properties']) for f in hoods]
# For the What's here preview: the same boundaries the map's card reads, by point-in-polygon at build time.
def shapes(name):
    return [(make_valid(shape(f['geometry'])), f['properties']) for f in gj(name)]
HERE_SHAPES = {r['file']: None for r in PG.get('here', [])}
for r_ in PG.get('here', []):
    if r_.get('within'): HERE_SHAPES[r_['within']['file']] = None
for k in HERE_SHAPES: HERE_SHAPES[k] = shapes(k)
REPS = opt_json(os.path.join(D, 'representatives.json'), {})
transit = opt_json(os.path.join(D, 'transit.json'), {'routes': [], 'stops': []})
ROUTES, STOPS = transit['routes'], transit['stops']
LINE_COLOR = {f['properties'].get('line'): f['properties'].get('color') for f in subway_lines}


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


def first_in(items, pt):
    p = Point(*pt)
    return next((props for g, props in items if g.contains(p)), None)


def whats_here(pt):
    """[(label, text, url or None)]: what the map's card would say at this spot, by the rows in "page.here":
    {label, file, text ("{field}" placeholders), empty (shown when the spot is in none; else the row is left
    out), page (link the unit's place page), rep: [representatives.json key, field] (adds the member and links
    their page), within: {file, name} (only when the spot is inside that one)}."""
    rows = []
    for r in PG.get('here', []):
        if r.get('within'):
            w = first_in(HERE_SHAPES[r['within']['file']], pt)
            if not w or w.get('name') != r['within']['name']:
                continue
        props = first_in(HERE_SHAPES[r['file']], pt)
        if not props:
            if 'empty' in r: rows.append((r['label'], r['empty'], None))
            continue
        text = re.sub(r'\{(\w+)\}', lambda m: str(props.get(m.group(1), '')), r['text'])
        url = f"/{city}/{slugify(props['name'])}/" if r.get('page') else None
        if r.get('rep'):
            m = (REPS.get(r['rep'][0]) or {}).get(str(props.get(r['rep'][1])), {})
            text += f" · {m['name']}" if m.get('name') else ''
            url = m.get('url')
        rows.append((r['label'], text, url))
    return rows


def route_badges(rs):
    """Route chips in the fact sheets' styles (cities/<city>/factsheet.css): streetcar, express, night, regional."""
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
    f['subway'] = sorted(subs, key=lambda t: (t[2], -len(t[1])))       # by the walk, the busiest station first on a tie
    g = sorted(((dist_km(c, pt), p) for c, p in go_stations), key=lambda t: t[0])[0] if go_stations else None
    gk = RAIL.get('walk', 'go')
    if g and g[0] <= RAIL.get('within', 2.5):
        mins = w[gk][0] if w.get(gk) and w[gk][1] == g[1]['name'] else walk_min(g[0])
        f['go'] = (g[1]['name'], g[1].get('lines', []), mins)
    f['routes'] = near_routes(pt)
    f['stop'] = w['stop'][0] if w.get('stop') else None
    f['bikeshare'] = w['bikeshare'][0] if w.get('bikeshare') else (walk_min(min(dist_km(c, pt) for c, _ in bikeshare)) if bikeshare else None)
    f['hubs'] = [(h, dist_km(h['at'], pt), walk_min(dist_km(h['at'], pt))) for h in HUBS]
    # the main hub (the first), as the origins table finishes trips from it
    f['union_km'], f['union_walk'] = (f['hubs'][0][1], f['hubs'][0][2]) if f['hubs'] else (99, 999)
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
    """This venue's upcoming events, with timed-entry slots (the same show sold at several times on one day,
    as a haunted house or an exhibition is) folded into one row that gives the first and last entry."""
    rows = EV.get('venues', {}).get(slug, [])
    out, by_day = [], {}
    for r in rows:
        try:
            d = date.fromisoformat(r['date'])
        except (TypeError, ValueError):
            continue
        if d < TODAY:
            continue
        k = (r['name'], d)
        if k in by_day:
            prev = by_day[k]
            prev.setdefault('times', [prev['time']]).append(r['time'])
        else:
            by_day[k] = dict(r, d=d); out.append(by_day[k])
    for e in out:
        ts = sorted(t for t in e.get('times', []) if t)
        if len(ts) > 1:
            e['time'], e['until'], e['slots'] = ts[0], ts[-1], len(ts)
    return out


def empty_html(v, plain):
    """What an empty listing says: a box-office note with a link to the hall's own calendar, a seasonal note, or plain."""
    if v.get('tickets'):
        return esc(v['tickets']) + (f' <a href="{esc(v["calendar"])}" rel="noopener">See what’s on at {esc(v["name"])} ↗</a>' if v.get('calendar') else '')
    return esc(v.get('season') or plain)


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
    when = f'<b>{esc(day_label(e["d"]))}</b> {esc(fmt_time(e.get("time")))}' + (f' to {esc(fmt_time(e["until"]))}, {e["slots"]} entry times' if e.get('until') else '')
    return (f'<li data-date="{e["d"].isoformat()}"><time datetime="{e["d"].isoformat()}{"T" + e["time"] if e.get("time") else ""}">{when}</time>'
            f' <span class="ev">{esc(e["name"])}</span>{where} {chip}{st}{link}</li>')


HUB_NAMES = {h.get('station', h['name']) for h in HUBS}


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
    p = [f'<svg class="vmap" viewBox="0 0 {MAP_W} {MAP_H}" role="img" aria-label="Map of the streets, transit{esc(" and " + PARK["label"] + " parking" if PARK else "")} around {esc(v["name"])}">',
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
        if inside(*c) and pr['name'] not in HUB_NAMES:
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
.rbs{display:flex;flex-wrap:wrap;align-items:center;gap:4px;margin-top:2px}.rbs .rb{flex:none}.rb.go{min-height:0;margin:0;padding:0 4px;text-decoration:none}
.rb{display:inline-grid;place-items:center;box-sizing:border-box;height:19px;min-width:27px;padding:0 4px;border-radius:4px;font:700 11.5px/1 var(--body)}
.vmap{display:block;width:100%;height:auto;border-radius:10px;border:1px solid var(--rule)}
.legend{font-size:13px;color:var(--ink-3);margin:8px 0 0}
.card{background:var(--card);border:1.5px solid var(--rule);border-radius:14px;padding:20px 22px;margin:14px 0}
.card h2{margin:0;display:flex;align-items:center;gap:10px;flex-wrap:wrap}.card h2 a{color:var(--ink);text-decoration:none}.card h2 a:hover{color:var(--accent)}
.pinbtn{display:inline-flex;align-items:center;gap:6px;font:500 14px/1 var(--body);color:var(--accent);background:var(--soft);border:0;border-radius:999px;padding:7px 12px 7px 9px;cursor:pointer}
.pinbtn svg{width:14px;height:17px}.pinbtn[aria-expanded="true"]{background:var(--accent);color:#fff}
.here{position:relative}
.pop{margin:12px 0 4px;padding:14px 16px 12px;border:1.5px solid var(--accent);border-radius:12px;background:var(--card);box-shadow:0 10px 30px rgba(26,20,20,.10)}
.pop .k{font-size:11px;font-weight:500;letter-spacing:.1em;color:var(--accent);text-transform:uppercase;margin:0 0 6px}
.pop dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:0;font-size:15px}.pop dt{font-weight:500;margin:0;color:var(--ink-2)}.pop dd{margin:0}
.pop .acts{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.pop .go{margin:0;min-height:40px;padding:0 16px;font-size:15px}.pop .alt{display:inline-flex;align-items:center;min-height:40px;padding:0 14px;border-radius:999px;border:1.5px solid var(--rule);color:var(--ink);text-decoration:none;font-size:15px}
@media (max-width:560px){.pop dl{grid-template-columns:1fr;gap:2px 0}.pop dt{margin-top:6px}}
.meta{color:var(--ink-3);font-size:15px;margin:4px 0 10px}
.card .from{margin:10px 0 0;padding-top:10px;border-top:1px dashed var(--rule);font-size:15px;color:var(--ink-2)}
.controls{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;margin:18px 0 6px;font-size:15px}
.controls label{display:inline-flex;align-items:center;gap:8px;color:var(--ink-2)}
.controls select{font:inherit;min-height:40px;padding:6px 10px;border:1.5px solid var(--rule);border-radius:8px;background:var(--card);color:var(--ink)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0;list-style:none}
.chips button{font:inherit;font-size:15px;min-height:36px;padding:0 14px;border-radius:999px;border:1.5px solid var(--rule);background:var(--card);color:var(--ink);cursor:pointer}
.chips button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.hide{display:flex;align-items:center;gap:8px;margin:12px 0 0;font-size:15px;color:var(--ink-2)}.hide input{width:18px;height:18px;margin:0;accent-color:var(--accent)}
.tier{margin-top:32px;padding:0;border:0;background:none}.tier h2{font-size:24px}
.busy{border-color:var(--accent)}.busy ul{margin:0;padding-left:20px}.busy li{margin:4px 0}
table{width:100%;border-collapse:collapse;font-size:15px}th,td{text-align:left;padding:8px 10px 8px 0;border-top:1px solid var(--rule);vertical-align:top}th{font-weight:500;color:var(--ink-2)}tr:first-child th,tr:first-child td{border-top:0}
td.n{white-space:nowrap}
footer{padding:28px 0 40px;font-size:14px;color:var(--ink-3)}footer a{color:var(--ink-2)}
[hidden]{display:none!important}
@media (max-width:560px){section,.card{padding:16px}ul.events time{flex-basis:100%}h1{margin-top:12px}.in-card dt{margin-top:10px}}"""
_fc = os.path.join(CITY_DIR, 'factsheet.css')       # the city's line bullets and route badges, shared with the fact sheets
CSS += '\n' + open(_fc).read() if os.path.exists(_fc) else ''
PIN = ('<svg viewBox="18 6 84 108" aria-hidden="true"><path d="M60 112 C60 112 22 74 22 48 A38 38 0 0 1 98 48 C98 74 60 112 60 112 Z" fill="#C8102E"/>'
       '<polygon points="60,52 84,63 60,74 36,63" fill="#fff" fill-opacity=".42"/><polygon points="60,39 84,50 60,61 36,50" fill="#fff" fill-opacity=".72"/>'
       '<polygon points="60,20 90,34 60,48 30,34" fill="#fff"/>%s</svg>')
PIN %= ('<path transform="translate(51,24.5) scale(0.9)" d="M10 0 L11.6 3.2 L13.2 2.4 L12.6 6.6 L15.2 4.2 L15.8 5.8 '
        'L18.4 5.2 L17.4 8.2 L19.2 9.2 L14.6 12.8 L15.2 14.6 L10.6 14 L10.8 18.6 L9.2 18.6 L9.4 14 L4.8 14.6 L5.4 12.8 '
        'L0.8 9.2 L2.6 8.2 L1.6 5.2 L4.2 5.8 L4.8 4.2 L7.4 6.6 L6.8 2.4 L8.4 3.2 Z" fill="#C8102E"/>' if CA else '')
BRAND = '-ca' if CA else ''
SOURCE_NOTE = ('Event listings: Ticketmaster Discovery API, refreshed nightly; each event links to its own Ticketmaster page. '
               'Layers.City sells nothing and carries no paid or affiliate links. ' + word('sources') +
               ' Walk and drive times: OpenStreetMap data, OSRM for driving (best case, empty roads).')


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
    """The meter on that road distance: drop, plus the rate per km or per mile, plus any flat surcharges."""
    per = FARES.get('taxiPerMi', 0) / 1.609344 if FARES.get('taxiPerMi') else FARES.get('taxiPerKm', 0)
    return FARES.get('taxiDrop', 0) + FARES.get('taxiExtra', 0) + km_ * per


GO_LINES_AT = {p['name']: set(p.get('lines', [])) for _, p in go_stations}
LINES_AT = {}
for c_, p_ in stations:
    LINES_AT.setdefault(p_['name'], set()).update(p_.get('lines', []))
HUB_LINES = {h['name']: set().union(*[set(p.get('lines', [])) for c, p in stations if dist_km(c, h['at']) <= h.get('lineRadius', 0.35)])
             for h in HUBS}
LOCAL = word('local', 'Transit')
order_lines = lambda ls: sorted(ls, key=lambda l: (not l.isdigit(), len(l), l))


def ride(frm_lines, n, lines):
    """The subway from somewhere to station n: "the 4/5/6 to n" when lines run straight there (and the city asks
    for line hints), else "the subway to n"."""
    common = order_lines(set(frm_lines) & set(lines)) if PG.get('lineHints') else []
    return f"the {'/'.join(common)} to {n}" if common else f"the subway to {n}"


def best_station(f, frm_lines):
    """The venue's station to ride to: with line hints, the nearest (within 15 min on foot) that a line from the
    starting point runs straight to; else the nearest."""
    if PG.get('lineHints'):
        for t in f['subway']:
            if t[2] <= 15 and set(frm_lines) & set(t[1]):
                return t
    return f['subway'][0]


def from_hub_words(f, hub=None):
    """How to finish the trip from a hub station, from the venue's own facts."""
    hub = hub or (HUBS[0] if HUBS else {'name': ''})
    hw = next((w for h, d, w in f['hubs'] if h is hub), f['union_walk'])
    if hw <= 15:
        return f"then about {hw} min on foot"
    if f['subway']:
        n, lines, mins = best_station(f, HUB_LINES.get(hub['name'], ()))
        return f"then {ride(HUB_LINES.get(hub['name'], ()), n, lines)} and about {mins} min on foot"
    if f.get('go'):
        return f"then {word('railShort', 'the train')} to {f['go'][0]} and about {f['go'][2]} min on foot"
    return f"then a {LOCAL} connection"


def site_name(u):
    return re.sub(r'^https?://(www\.)?', '', u).rstrip('/')


def origin_rows(v, f):
    rows = []
    for o in ORIGINS:
        dm = DR_MIN.get((o['name'], v['slug']))
        hub = next((h for h in HUBS if h['name'] == o.get('hub')), HUBS[0] if HUBS else None)
        hshort = (hub or {}).get('short', (hub or {}).get('name', ''))
        if o['mode'] in ('ttc', 'local'):
            if hub and o['via'] == hub.get('station', hub['name']):
                transit = f"From {hshort}, {from_hub_words(f, hub)[5:]}"
            elif f['subway'] and f['subway'][0][2] <= 25:
                n, lines, mins = best_station(f, LINES_AT.get(o['via'], ()))
                transit = (f"{LOCAL} from {o['via']} to {n}" if not PG.get('lineHints') else
                           f"From {o['via']}, {ride(LINES_AT.get(o['via'], ()), n, lines)}") + f", then about {mins} min on foot"
            else:
                transit = f"{LOCAL} from {o['via']} to {hshort}, {from_hub_words(f, hub)}"
            fare = word('localFare').format(fare=FARES.get('local', 0)) if word('localFare') and FARES.get('local') else None
        else:
            rail = o.get('rail') or word('railShort', 'Train')
            # A train that stops at the venue's own station (Exhibition on Lakeshore West; Mets-Willets Point on the Port Washington Branch)
            # (only where the rail file's lines are real branches: "direct": false turns it off)
            direct = RAIL.get('direct', True) and f.get('go') and f['go'][2] <= 25 and GO_LINES_AT.get(o['via'], set()) & set(f['go'][1]) and f['go'][0] not in HUB_NAMES
            if f.get('go') and f['go'][0] == o['via'] and f['go'][2] <= 25:
                transit = f"From {o['via']}, about {f['go'][2]} min on foot"
            elif direct:
                transit = f"{rail} from {o['via']} to {f['go'][0]}, then about {f['go'][2]} min on foot"
            else:
                transit = f"{rail} from {o['via']} to {hshort}, {from_hub_words(f, hub)}"
            fare = o.get('fare') or word('railFare') or None
        # A venue can say it in its own words: outside the city, where the trip doesn't run through a hub
        # (UBS Arena by LIRR, MetLife by the event train from Secaucus), keyed by origin name or "*".
        own = (v.get('transit') or {})
        mine = own.get(o['name']) if o['name'] in own else own.get('*')       # null: the worked-out route
        if mine:
            transit, fare = mine, v.get('transitFare')
        if fare and o['mode'] not in ('ttc', 'local') and ';' in fare and re.search(r'(then|From [^,]+,) about \d+ min on foot$', transit) and ' the ' not in transit.split(',', 1)[-1]:
            fare = fare.split(';')[0]          # no subway leg: the rail fare alone
        rows.append({'name': o['name'], 'transit': transit, 'fare': fare,
                     'drive': None if not dm or dm[0] is None else dm[0], 'km': None if not dm or dm[1] is None else dist_u(dm[1]),
                     'taxi': None if not dm or dm[1] is None or not (FARES.get('taxiPerKm') or FARES.get('taxiPerMi')) else round(taxi(dm[1]))})
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
    arrive = v.get('arrive') or (f"{f['subway'][0][0]} station, about {f['subway'][0][2]} min on foot" if f['subway'] and f['subway'][0][2] <= 25
              else f"{f['go'][0]}, about {f['go'][2]} min on foot" if f.get('go') and f['go'][2] <= 25
              else word('atDoor', 'Bus at the door') if f['routes'] else 'Best reached by car')
    map_link = f"/{city}/#map=16/{v['at'][1]}/{v['at'][0]}&pin={v['at'][1]},{v['at'][0]}&name={quote(v['name'])}"

    # ---- the venue's own page
    parts = [f'<h1>{esc(v["name"])}</h1>',
             f'<p class="kind">{esc(v["address"])} · about {v["capacity"]:,} seats · {esc(kinds)}{esc(home)}</p>']
    if f['hood']:
        hs = slugify(f['hood']['name'])
        parts.append(f'<p class="in">In <a href="/{city}/{hs}/">{esc(f["hood"]["name"])}</a>' +
                     (f' · <a href="/{city}/profiles/?n={hs}&amp;at={v["at"][1]:.3f},{v["at"][0]:.3f}">Fact sheet from this spot</a>' if os.path.exists(os.path.join(DOCS, city, 'profiles', 'data', hs + '.json')) else '') + '</p>')
    parts.append(f'<a class="go" href="{esc(map_link)}">Open {esc(v["name"])} on the map <span aria-hidden="true">→</span></a>')
    if not v.get('outside'):        # the map's streets stop at the city line
        parts.append(venue_map(v, venues))
    here = [] if v.get('outside') else whats_here(v['at'])
    if here:
        parts.append('<section><h2>What’s here</h2><dl>' + ''.join(f'<dt>{esc(l)}</dt><dd>' + (f'<a href="{esc(u)}">{esc(t)}</a>' if u else esc(t)) + '</dd>' for l, t, u in here) +
                     '</dl><p class="note" style="margin:12px 0 0">The same rows the map’s What’s here card gives for this address; the map adds collection day, heritage and school wards.</p></section>')
    if not v.get('outside'):
        parts.append(f'<p class="legend">{esc(word("legend"))}</p>')
    # events
    sec = '<section><h2>This week</h2>'
    if not EV:
        sec += '<p class="empty">No listing yet: the events feed hasn’t run. Getting-there facts below don’t depend on it.</p>'
    else:
        empty = empty_html(v, 'Nothing listed here this week.')
        sec += (f'<ul class="events">{"".join(event_li(e) for e in this_week)}</ul>' if this_week else '') + \
               f'<p class="empty"{"" if not this_week else " hidden"}>{empty}</p>'
        if next_week:
            sec += f'<h3>Next week</h3><ul class="events">{"".join(event_li(e) for e in next_week)}</ul><p class="empty" hidden>Nothing listed for next week.</p>'
        sec += f'<p class="stamp">Listing from Ticketmaster, as of {esc(asof_text)}. Week runs {esc(V.get("week", "Monday to Sunday"))}.</p>'
    parts.append(sec + '</section>')
    # getting there
    dl = []
    if f['subway']:
        dl.append((word('subway', 'Subway'), '<br>'.join(f'{LINES_HTML(l)} {esc(n)} · about {m} min on foot' for n, l, m in f['subway'])))
    if f.get('go'):
        dl.append((word('rail', 'Regional rail'), f'{esc(f["go"][0])} · about {f["go"][2]} min on foot · {esc(", ".join(f["go"][1]))}'))
    if f['routes']:
        dl.append((word('routes', 'Buses within a 5-minute walk'), f'<span class="rbs">{route_badges(f["routes"][:14])}</span>' + (f' <span class="note">+{len(f["routes"]) - 14} more</span>' if len(f['routes']) > 14 else '')))
    for h, hk, hw in f['hubs']:
        if h.get('row') is False or v.get('outside'): continue
        dl.append((f'From {h["name"]}', f'about {hw} min on foot ({fmt_km(hk)} as the crow flies)' if hw <= 40 else f'{fmt_km(hk)} as the crow flies; see the origins table below'))
    if f['bikeshare'] is not None and not v.get('outside'):
        dl.append((f'Nearest {word("bikeshare", "bike-share")} dock', f'about {f["bikeshare"]} min on foot'))
    parts.append('<section><h2>Getting there</h2><dl>' + ''.join(f'<dt>{esc(a)}</dt><dd>{b}</dd>' for a, b in dl) + '</dl></section>')
    # parking (the city's own lots and garages; a venue outside the city has only its notes)
    pk = []
    PL = PARK.get('label', 'Public parking')
    if PARK and not v.get('outside'):
        if f['greenp']:
            pk.append((f'{PL} within a 10-minute walk', '<br>'.join(f'{esc(n)} · {"garage" if t == "g" else "lot"}' + (f' · {c:,} spaces' if c else '') + f' · {fmt_km(d)}' for n, c, t, d in f['greenp'][:8]) +
                       (f'<br><span class="note">+{len(f["greenp"]) - 8} more</span>' if len(f['greenp']) > 8 else '')))
            pk.append((f'{PL} spaces within that walk', f'{sum(c or 0 for _, c, _, _ in f["greenp"]):,} in {len(f["greenp"])} locations'))
        else:
            pk.append((f'{PL} within a 10-minute walk', 'None'))
        if permit:
            pk.append(('Street parking', f'Permit area {esc(f["permit"])}: residents’ permits apply on side streets' if f['permit'] else 'Not in a permit-parking area'))
        parts.append('<section><h2>Parking</h2><dl>' + ''.join(f'<dt>{esc(a)}</dt><dd>{b}</dd>' for a, b in pk) + '</dl>'
                     f'<p class="note" style="margin:12px 0 0">{esc(PARK.get("note", ""))}</p></section>')
    if v.get('notes'):
        parts.append('<section><h2>Arriving</h2>' + ''.join(f'<p style="margin:0 0 10px">{esc(n)}</p>' for n in v['notes']) +
                     f'<p class="note">Written from the venue’s own visitor pages; gates and policies change, so check <a href="{esc(v["site"])}" rel="noopener">{esc(site_name(v["site"]))}</a> before you go.</p></section>')
    # origins
    rows = origin_rows(v, f)
    star = (v.get('transit') or {}).get('*')          # one way in from everywhere: said once, above the table
    have_drive = any(r['drive'] is not None for r in rows)
    have_transit = any(r['transit'] != star for r in rows) or not star
    tbl = ''
    if have_drive or have_transit:
        tbl = '<table><tr><th>From</th>' + ('<th>Drive, best case</th><th>Taxi meter, about</th>' if have_drive else '') + ('<th>Transit</th>' if have_transit else '') + '</tr>'
        for r in rows:
            tbl += f'<tr><td class="n">{esc(r["name"])}</td>'
            if have_drive:
                tbl += (f'<td class="n">{r["drive"]} min · {r["km"]} {UNIT}</td><td class="n">${r["taxi"]}</td>' if r['drive'] is not None else '<td>–</td><td>–</td>')
            if have_transit:
                tbl += ('<td><span class="note">As above</span></td>' if star and r['transit'] == star else
                        f'<td>{esc(r["transit"])}' + (f'<br><span class="note">{esc(r["fare"])}</span>' if r['fare'] else '') + '</td>')
            tbl += '</tr>'
        tbl += '</table>'
    if star:
        tbl = f'<p style="margin:0 0 14px"><b>By transit, from anywhere in {esc(word("region", "the region"))}:</b> {esc(star)}.</p>' + tbl
    rate = (f'${FARES.get("taxiDrop", 0):.2f} plus ${FARES["taxiPerMi"]:.2f}/mi' if FARES.get('taxiPerMi') else f'${FARES.get("taxiDrop", 0):.2f} plus ${FARES.get("taxiPerKm", 0):.2f}/km') + \
           (f' plus ${FARES["taxiExtra"]:.2f} in surcharges' if FARES.get('taxiExtra') else '')
    parts.append(f'<section><h2>From across {esc(word("region", "the region"))}</h2>' + tbl +
                 f'<p class="note" style="margin:12px 0 0">Drive times are OSRM’s on empty roads, the same best-case figure as the map’s suburban lens; game nights run far slower. '
                 f'The taxi figure is {esc(word("taxi", "the local meter rate"))} ({rate}, as of {esc(FARES.get("asof", ""))}) on that distance, the only published benchmark; rideshare prices aren’t published and surge after events. '
                 f'{esc(FARES.get("oneFare", ""))}</p></section>')
    parts.append(f'<p class="note"><a href="/{city}/venues/">All {esc(CITY)} venues</a></p>')
    desc = f"{v['name']}, {v['address']}: " + word('venueDesc', "what's on this week, nearest stations, parking and how to get there from across the region.")
    vdir = os.path.join(OUT, v['slug']); os.makedirs(vdir, exist_ok=True)
    og_image(v['name'], [v['at']], os.path.join(vdir, 'og.png'), f'Venue · {CITY}')
    open(os.path.join(vdir, 'index.html'), 'w').write(page(f"{v['name']} · {CITY} venues · Layers.City", desc, f'{INDEX}{v["slug"]}/', f'{INDEX}{v["slug"]}/og.png', '\n'.join(parts), crumbs_idx))

    # ---- its card on the list
    soon7 = [e for e in evs if e['d'] < TODAY + timedelta(days=7)]
    soonest = evs[0]['d'].isoformat() if evs else '9999-12-31'
    from_json = {r['name']: [r['drive'], r['km'], r['taxi'], r['transit'], r['fare']] for r in rows}
    ev_html = (f'<ul class="events">{"".join(event_li(e) for e in soon7)}</ul>' if soon7 else '') + \
              (f'<p class="empty"{"" if not soon7 else " hidden"}>{empty_html(v, "Nothing listed here in the next seven days.")}</p>' if EV else '')
    here = [] if v.get('outside') else whats_here(v['at'])
    here_rows = ''.join(f'<dt>{esc(l)}</dt><dd>' + (f'<a href="{esc(u)}">{esc(t)}</a>' if u else esc(t)) + '</dd>' for l, t, u in here)
    pop = (f'<div class="pop" id="pop-{v["slug"]}" hidden><p class="k">What’s here</p><dl>{here_rows}'
           + (f'<dt>Nearest {word("subway", "Subway").lower()}</dt><dd>{esc(f["subway"][0][0])} · about {f["subway"][0][2]} min on foot</dd>' if f['subway'] else '')
           + (f'<dt>{esc(PARK.get("label", ""))} nearby</dt><dd>{len(f["greenp"])} within a 10-min walk · {sum(c or 0 for _, c, _, _ in f["greenp"]):,} spaces</dd>' if f['greenp'] else '')
           + f'</dl><div class="acts"><a class="go" href="{esc(map_link)}">Open on the map <span aria-hidden="true">→</span></a>'
             f'<a class="alt" href="/{city}/venues/{v["slug"]}/">Venue page</a></div></div>')
    pin_svg = '<svg viewBox="18 6 84 108" aria-hidden="true"><path d="M60 112 C60 112 22 74 22 48 A38 38 0 0 1 98 48 C98 74 60 112 60 112 Z" fill="currentColor"/><circle cx="60" cy="48" r="14" fill="var(--card)"/></svg>'
    cards.append((v.get('tier', 'main'), f'<article class="card here" data-cap="{v["capacity"]}" data-kinds="{esc(" ".join(v["kinds"]))}" data-soon="{soonest}" data-has="{1 if soon7 else 0}" data-from="{esc(json.dumps(from_json, separators=(",", ":")))}">'
                 f'<h2><a href="/{city}/venues/{v["slug"]}/">{esc(v["name"])}</a> <button type="button" class="pinbtn" aria-expanded="false" aria-controls="pop-{v["slug"]}">{pin_svg}Where is it?</button></h2>{pop}'
                 f'<p class="meta">about {v["capacity"]:,} seats · {esc(v["address"])}{esc(home)}<br>{esc(arrive)}</p>'
                 f'{ev_html}<p class="from" hidden></p></article>'))

# ---- the list page: busy nights, controls, cards -----------------------------------------------------------------
busy = {}
for e in all_events:
    if e['venue']['capacity'] >= BIG and e['d'] < WEEK1 + timedelta(days=7) and not e.get('status'):
        busy.setdefault(e['d'], {}).setdefault(e['venue']['name'], []).append(e['name'])
busy_days = [(d, vs) for d, vs in sorted(busy.items()) if len(vs) >= 2]
strip = ''
if busy_days:
    strip = f'<section class="busy"><h2>{esc(word("busy", "Busy nights"))}</h2><p class="note" style="margin:0 0 8px">Two or more of the big venues on the same day: expect full garages, slow approaches and crowded trains after.</p><ul>' + \
            ''.join(f'<li data-date="{d.isoformat()}"><b>{esc(day_label(d))}</b>: ' + ' · '.join(f'{esc(vn)} ({esc(evn[0])}{" +" + str(len(evn) - 1) if len(evn) > 1 else ""})' for vn, evn in vs.items()) + '</li>' for d, vs in busy_days) + '</ul></section>'
elif EV:
    strip = f'<section class="busy"><h2>{esc(word("busy", "Busy nights"))}</h2><p class="note" style="margin:0">No day this week or next has two of the big venues busy at once, by the listing.</p></section>'

origin_opts = ''.join(f'<option value="{esc(o["name"])}">{esc(o["name"])}</option>' for o in ORIGINS)
controls = f"""<div class="controls">
<label>Sort <select id="sort"><option value="cap">Largest first</option><option value="soon">Soonest event</option><option value="near">Closest to where I’m coming from</option></select></label>
<label>From <select id="from"><option value="">—</option>{origin_opts}</select></label>
</div>
<ul class="chips" id="kinds" role="group" aria-label="Kind of event">
<li><button type="button" data-kind="" aria-pressed="true">All</button></li><li><button type="button" data-kind="sports" aria-pressed="false">Sports</button></li><li><button type="button" data-kind="concerts" aria-pressed="false">Concerts</button></li><li><button type="button" data-kind="comedy" aria-pressed="false">Comedy</button></li><li><button type="button" data-kind="theatre" aria-pressed="false">Theatre</button></li>
</ul>
<label class="hide"><input type="checkbox" id="hideEmpty"> Hide venues with nothing on in the next seven days</label>"""
script = """<script>
(()=>{const cards=[...document.querySelectorAll('article.card')],lists={main:document.getElementById('list'),other:document.getElementById('list2')},sortEl=document.getElementById('sort'),fromEl=document.getElementById('from'),hideEl=document.getElementById('hideEmpty');
const tierOf=c=>c.closest('#list2')?'other':'main';cards.forEach(c=>c.dataset.tier=tierOf(c));
let kind='';try{fromEl.value=localStorage.getItem('venues.from')||'';}catch(e){}
const fromOf=c=>{try{return JSON.parse(c.dataset.from)[fromEl.value]}catch(e){return null}};
function apply(){const f=fromEl.value;cards.forEach(c=>{const r=f?fromOf(c):null,p=c.querySelector('.from');c.hidden=(!!kind&&!c.dataset.kinds.split(' ').includes(kind))||(hideEl.checked&&c.dataset.has==='0');
if(r){p.hidden=false;p.innerHTML='From <b>'+f.replace(/</g,'&lt;')+'</b>: '+(r[0]!=null?'drive about '+r[0]+' min ('+r[1]+' UNIT), taxi meter about $'+r[2]+' · ':'')+r[3].replace(/</g,'&lt;')+(r[4]?' · '+r[4].replace(/</g,'&lt;'):'');}else p.hidden=true;});
const key=sortEl.value;const val=c=>key==='cap'?-(+c.dataset.cap):key==='soon'?c.dataset.soon:(f&&fromOf(c)&&fromOf(c)[0]!=null?fromOf(c)[0]:1e9);
[...cards].sort((a,b)=>val(a)<val(b)?-1:val(a)>val(b)?1:0).forEach(c=>lists[c.dataset.tier].appendChild(c));
const sec=document.getElementById('other');if(sec)sec.hidden=!cards.some(c=>c.dataset.tier==='other'&&!c.hidden);
try{localStorage.setItem('venues.from',f)}catch(e){}}
sortEl.addEventListener('change',apply);hideEl.addEventListener('change',apply);
document.querySelectorAll('.pinbtn').forEach(b=>b.addEventListener('click',()=>{const pop=document.getElementById(b.getAttribute('aria-controls')),open=pop.hidden;
document.querySelectorAll('.pop').forEach(p=>p.hidden=true);document.querySelectorAll('.pinbtn').forEach(x=>x.setAttribute('aria-expanded','false'));
if(open){pop.hidden=false;b.setAttribute('aria-expanded','true');}}));
document.addEventListener('keydown',e=>{if(e.key==='Escape'){document.querySelectorAll('.pop').forEach(p=>p.hidden=true);document.querySelectorAll('.pinbtn').forEach(x=>x.setAttribute('aria-expanded','false'));}});fromEl.addEventListener('change',()=>{if(fromEl.value&&sortEl.value==='cap')sortEl.value='near';apply()});
document.querySelectorAll('#kinds button').forEach(b=>b.addEventListener('click',()=>{kind=b.dataset.kind;document.querySelectorAll('#kinds button').forEach(x=>x.setAttribute('aria-pressed',x===b));apply()}));
apply();})();
</script>""".replace('UNIT', UNIT)
intro = (f'<h1>{esc(CITY)}’s big venues, this week</h1>'
         f'<p class="kind">What’s on at the {len(main_cards_count := [v for v in venues if v.get('tier', 'main') == 'main'])} {esc(word("intro", "places most of the region travels to, and how to get to each."))} '
         f'A listing, not a guide: the facts and a link to the source, nothing else.</p>'
         + (f'<p class="stamp">Listing from Ticketmaster as of {esc(asof_text)} · week runs {esc(V.get("week", "Monday to Sunday"))}. Cards show the next seven days; each venue’s page has this week and next. Pick where you’re coming from to see the trip.</p>' if asof_text else
            '<p class="stamp">The events feed hasn’t run yet, so there’s no listing; every venue’s getting-there facts are here already.</p>'))
main_cards = [h for t, h in cards if t == 'main']; other_cards = [h for t, h in cards if t == 'other']
other_sec = (f'<section class="tier" id="other"><h2>Other venues</h2><p class="note" style="margin:0 0 4px">{esc(word("other", "Smaller rooms, same facts, same listing."))}</p></section>'
             '<div id="list2">' + ''.join(other_cards) + '</div>') if other_cards else '<div id="list2"></div>'
body = intro + strip + controls + '<div id="list">' + ''.join(main_cards) + '</div>' + other_sec + script
idx_desc = f"What's on this week at {CITY}'s big venues, " + word('listDesc', 'and how to get to each.')
og_image(f'{CITY}’s big venues', [v['at'] for v in venues], os.path.join(OUT, 'card.png'), 'This week, and how to get there')
open(os.path.join(OUT, 'index.html'), 'w').write(page(f'{CITY} venues this week · Layers.City', idx_desc, INDEX, f'{INDEX}card.png', body, crumbs_idx))
print(f'{city}: {len(venues)} venue pages + /{city}/venues/ ({sum(len(events_for(v["slug"])) for v in venues)} events{"" if DR else ", no drive times yet"})')
