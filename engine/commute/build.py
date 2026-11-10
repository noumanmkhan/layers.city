"""Build a city's commute explainer page, docs/<city>/<path>/index.html, from cities/<city>/commute.json.

Usage: python3 engine/commute/build.py <city>

Inputs are travel-survey cross-tabulations exported as text (commute.json "files"): trips into and out of one district
by start hour and mode, and the people who work there by home district, plus the districts' boundaries. The page has
three parts: people present hour by hour (residents + trips in - trips out), how they arrived, and a map of where the
district's workers live. Everything is computed and projected here, so the page needs no chart or map library.
The engine names no city; the district, the words and the files are in commute.json."""
import csv, json, math, os, re, sys
from datetime import date

from shapely.geometry import shape, Point, LineString, MultiLineString
from shapely.ops import linemerge, substring, unary_union

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from theme import SCRIPT as THEME_SCRIPT, css as theme_css   # noqa: E402

city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: build.py <city>')
CITY = os.path.join(ROOT, 'cities', city)
cfg = json.load(open(os.path.join(CITY, 'commute.json'), encoding='utf-8'))
OUT = os.path.join(ROOT, 'docs', city, cfg['path'])
HOURS = list(range(4, 28))          # the survey's day: 0400 to 2759


def crosstab(path):
    """An iDRS cross-tabulation export: the header row starts with a comma, then one row per row value."""
    lines = open(os.path.join(CITY, path), encoding='utf-8').read().splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith(','))
    head = next(csv.reader([lines[i]]))[1:]
    rows = []
    for l in lines[i + 1:]:
        if not l.strip():
            continue
        r = next(csv.reader([l]))
        rows.append((r[0], [float(x or 0) for x in r[1:]]))
    return head, rows


# ---- hour by hour --------------------------------------------------------------------------------------------
MODES = cfg['modes']
mode_of = {src: m['id'] for m in MODES for src in m['from']}


def by_hour(path):
    head, rows = crosstab(path)
    miss = [h for h in head if h not in mode_of]
    if miss:
        sys.exit(f'commute.json modes: no group for {miss}')
    out = {h: {m['id']: 0.0 for m in MODES} for h in HOURS}
    for t, vals in rows:
        h = int(t) // 100
        for col, v in zip(head, vals):
            out[h][mode_of[col]] += v
    return out


IN, OUTB = by_hour(cfg['files']['in']), by_hour(cfg['files']['out'])
RES = cfg['residents']
cum = {m['id']: 0.0 for m in MODES}
series = [{'t': 4, 'total': RES, 'm': {m['id']: 0 for m in MODES}, 'in': 0, 'out': 0}]
for h in HOURS:
    for m in MODES:
        cum[m['id']] += IN[h][m['id']] - OUTB[h][m['id']]
    series.append({'t': h + 1, 'total': RES + sum(cum.values()), 'm': {k: max(0, v) for k, v in cum.items()},
                   'in': sum(IN[h].values()), 'out': sum(OUTB[h].values())})
peak = max(series, key=lambda s: s['total'])
tot_in = {m['id']: sum(IN[h][m['id']] for h in HOURS) for m in MODES}
evening = next(s for s in series if s['t'] == 22)


def clock(t, short=False):
    t %= 24
    h = 12 if t % 12 == 0 else t % 12
    return f'{h}{"" if short else " "}{"a.m." if t < 12 else "p.m."}' if not short else f'{h}{"a" if t < 12 else "p"}'


def rnd(n, to=1000):
    return f'{int(round(n / to) * to):,}'


# ---- where the workers live -----------------------------------------------------------------------------------
gj = json.load(open(os.path.join(CITY, cfg['files']['districts']), encoding='utf-8'))
feats = gj['features']
by_name = {}
for f in feats:
    by_name.setdefault(f['properties']['PD_name'], []).append(f)
by_no = {f['properties']['PD_no']: f for f in feats}
_, rows = crosstab(cfg['files']['homes'])
workers = {}
unplaced = 0
for name, (v, *_) in rows:
    a = cfg.get('aliases', {}).get(name, {})
    cands = [by_no[a['no']]] if 'no' in a else by_name.get(a.get('name', name), [])
    if len(cands) != 1:
        unplaced += v
        print(f'  {len(cands)} boundaries for {name!r} ({v:.0f} workers): left off the map, kept in the totals')
        continue
    f = cands[0]
    workers[f['properties']['PD_no']] = workers.get(f['properties']['PD_no'], 0) + v
W_TOT = sum(workers.values()) + unplaced
dist_no = next(f['properties']['PD_no'] for f in feats if f['properties']['PD_name'] == cfg['district'])
dist_reg = by_no[dist_no]['properties']['Reg_no']
regions = []
used = set()
for r in cfg['regions']:
    if r.get('match') == 'district':
        ids = {dist_no}
    elif r.get('rest'):
        ids = set(workers) - used
    else:
        ids = {n for n in workers if by_no[n]['properties']['Reg_no'] in r['reg']} - used
    used |= ids
    v = sum(workers.get(n, 0) for n in ids) + (unplaced if r.get('rest') else 0)
    regions.append({'name': r['name'], 'n': round(v), 'p': round(v / W_TOT * 100, 1)})
city_share = sum(workers.get(n, 0) for n in workers if by_no[n]['properties']['Reg_no'] == dist_reg) / W_TOT


top = sorted(((v, n) for n, v in workers.items() if n != dist_no), reverse=True)[:12]

# Projection: local metres around the region's centre, then to a 1000-wide SVG per view.
lat0 = 43.7
kx = math.cos(math.radians(lat0)) * 111.32
ky = 110.57


def rings(geom):
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    return [ring for poly in polys for ring in poly]


def bbox(fs):
    xs, ys = [], []
    for f in fs:
        for ring in rings(f['geometry']):
            for lon, lat in ring:
                xs.append(lon * kx); ys.append(-lat * ky)
    return min(xs), min(ys), max(xs), max(ys)


def view(fs, width=1000, pad=12):
    x0, y0, x1, y1 = bbox(fs)
    s = (width - 2 * pad) / (x1 - x0)
    h = (y1 - y0) * s + 2 * pad

    def pt(lon, lat):
        return round((lon * kx - x0) * s + pad, 1), round((-lat * ky - y0) * s + pad, 1)

    def path(f):
        out = []
        for ring in rings(f['geometry']):
            pts = [((lon * kx - x0) * s + pad, (-lat * ky - y0) * s + pad) for lon, lat in ring]
            keep = [pts[0]]
            for p in pts[1:]:
                if abs(p[0] - keep[-1][0]) + abs(p[1] - keep[-1][1]) > 0.6:
                    keep.append(p)
            if len(keep) > 2:
                out.append('M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in keep) + 'Z')
        return ''.join(out)
    return round(h), path, pt


views = {}
for vid, fs in (('city', [f for f in feats if f['properties']['Reg_no'] == dist_reg]), ('region', feats)):
    h, path, pt = view(fs)
    views[vid] = {'h': h, 'd': [{'no': f['properties']['PD_no'], 'd': path(f)} for f in fs]}
    if vid == 'city':   # number the city's districts, which have no names of their own
        views[vid]['lab'] = []
        for f in fs:
            rp = shape(f['geometry']).representative_point()
            m = re.match(r'PD (\d+) ', f['properties']['PD_name'])
            if m:
                views[vid]['lab'].append([f['properties']['PD_no'], *pt(rp.x, rp.y), m.group(1)])
names = {}
for f in feats:
    p = f['properties']
    names[p['PD_no']] = {'n': p['PD_name'], 'r': p['Reg_name'], 'w': round(workers.get(p['PD_no'], 0))}


# ---- the moving-dots map --------------------------------------------------------------------------------------
def build_flow(fc):
    """Corridors projected to the frame, each running inward to the hub, plus the land, near land, streets and district."""
    DATA = os.path.join(ROOT, 'docs', city, 'data')
    layer = lambda n: json.load(open(os.path.join(DATA, n), encoding='utf-8'))['features']
    lkx, lky = math.cos(math.radians(fc['hub'][1])) * 111.32, 110.57          # km per degree at the hub
    hub = Point(fc['hub'][0] * lkx, fc['hub'][1] * lky)

    def km(g):                                # lon/lat geometry -> local km
        import shapely
        return shapely.transform(g, lambda a: a * [lkx, lky])
    fr = fc['frame']
    frame = unary_union([shape(f['geometry']) for f in layer(fr['layer']) if f['properties'].get('kind') == fr['kind']])
    if fr.get('clip'):
        from shapely.geometry import box as _box
        frame = frame.intersection(_box(*fr['clip']))
    x0, y0, x1, y1 = km(frame).bounds
    pad = fr.get('padKm', 1)
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    S = 1000 / (x1 - x0)
    H = round((y1 - y0) * S)

    def xy(x, y):
        return round((x - x0) * S, 1), round((y1 - y) * S, 1)

    def lines_of(g):
        return list(g.geoms) if hasattr(g, 'geoms') else [g]

    def poly_d(geoms):
        out = []
        for g in geoms:
            for p in lines_of(km(g)):
                for ring in [p.exterior, *p.interiors]:
                    pts = [xy(*c[:2]) for c in ring.coords]
                    keep = [pts[0]] + [q for a, q in zip(pts, pts[1:]) if abs(q[0] - a[0]) + abs(q[1] - a[1]) > 0.8]
                    if len(keep) > 2:
                        out.append('M' + 'L'.join(f'{a} {b}' for a, b in keep) + 'Z')
        return ''.join(out)
    land = poly_d([shape(f['geometry']) for f in layer(fc['land']['layer']) if f['properties'].get('kind') in fc['land']['kinds']])
    near = poly_d([shape(f['geometry']) for f in layer(fc['near']['layer']) if f['properties'].get('kind') in fc['near']['kinds']])
    dist = poly_d([shape(f['geometry']) for f in feats if f['properties']['PD_no'] == dist_no])
    box_km = LineString([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]).convex_hull
    st = []
    for f in layer(fc['streets']['layer']):
        if f['properties'].get('cls') != fc['streets']['cls']:
            continue
        for l in lines_of(km(shape(f['geometry'])).intersection(box_km)):
            if l.length > .2:
                st.append('M' + 'L'.join('%s %s' % xy(*c[:2]) for c in l.simplify(.05).coords))

    lines = []                                    # the roads and rail the dots run on, drawn under them
    for ln in fc.get('lines', []):
        for f in layer(ln['layer']):
            if not all(str(f['properties'].get(k)) in v for k, v in ln['match'].items()):
                continue
            ds = []
            for l in lines_of(km(shape(f['geometry'])).intersection(box_km)):
                if l.length > .2:
                    ds.append('M' + 'L'.join('%s %s' % xy(*c_[:2]) for c_ in l.simplify(.03).coords))
            if ds:
                lines.append({'k': ln['kind'], 'c': f['properties'].get(ln.get('colour', ''), None), 'd': ''.join(ds)})

    paths = []
    for c in fc['corridors']:
        fs = [f for f in layer(c['layer']) if all(str(f['properties'].get(k)) in v for k, v in c['match'].items())]
        if not fs:
            sys.exit(f'commute.json flow: nothing in {c["layer"]} matches {c["match"]}')
        u = unary_union([km(shape(f['geometry'])) for f in fs]).intersection(box_km)
        merged = linemerge(u) if u.geom_type == 'MultiLineString' else u
        pieces = []
        for l in lines_of(merged):
            if l.length < .5:
                continue
            at = l.project(hub)
            for a, b, inward in ((0, at, True), (at, l.length, False)):
                if b - a < .8:
                    continue
                seg = substring(l, a, b)
                cs = [c_[:2] for c_ in seg.coords]
                if not inward:
                    cs.reverse()
                seg = LineString(cs)
                if Point(seg.coords[-1]).distance(hub) > fc.get('endKm', 2.5):
                    continue                      # a stretch that never reaches downtown (a branch, a side piece)
                if c.get('maxKm') and seg.length > c['maxKm']:
                    seg = substring(seg, seg.length - c['maxKm'], seg.length)
                pieces.append(seg)
        tot = sum(p.length for p in pieces)
        for p_ in pieces:
            pts = [xy(*q) for q in p_.simplify(.04).coords]
            paths.append({'m': c['mode'], 'w': round(c['weight'] * p_.length / tot, 4), 'km': round(p_.length, 1),
                          'p': [v for q in pts for v in q]})
    return {'h': H, 'land': land, 'near': near, 'dist': dist, 'streets': ''.join(st), 'lines': lines, 'paths': paths, 'dots': fc['dots'],
            'hub': xy(hub.x, hub.y)}


FLOW = build_flow(cfg['flow']) if cfg.get('flow') else None

# ---- words ----------------------------------------------------------------------------------------------------
TOKENS = {
    'residents': rnd(RES), 'peak': rnd(peak['total']), 'peakTime': clock(peak['t']),
    'times': f'{peak["total"] / RES:.2f}'.rstrip('0').rstrip('.'), 'visitors': rnd(peak['total'] - RES),
    'evening': rnd(evening['total'] - RES), 'workers': rnd(cfg['workers']),
    'commuters': rnd(cfg['workers'] - workers.get(dist_no, 0)), 'cityShare': f'{city_share * 100:.0f}%',
    'dots': str(cfg['flow']['dots']) if cfg.get('flow') else '',
}


def words(s):
    return re.sub(r'\{(\w+)\}', lambda m: TOKENS[m.group(1)], s)


page = {k: (words(v) if isinstance(v, str) else [words(x) for x in v] if isinstance(v, list) else v) for k, v in cfg['page'].items()}

DATA = {
    'modes': [{'id': m['id'], 'n': m['name'], 'l': m['long'], 'c': m['colour']} for m in MODES],
    'res': RES,
    'series': [{'t': s['t'], 'tot': round(s['total']), 'm': {k: round(v) for k, v in s['m'].items()},
                'in': round(s['in']), 'out': round(s['out'])} for s in series],
    'peakT': peak['t'],
    'atPeak': {k: round(v) for k, v in peak['m'].items()},
    'allDay': {k: round(v) for k, v in tot_in.items()},
    'views': views, 'names': names, 'district': dist_no, 'wtot': round(W_TOT),
    'regions': regions, 'top': [[n, round(v)] for v, n in top],
    'videos': cfg.get('videos', []),
    'flow': FLOW,
    'byHour': {str(h + 1): {'in': {k: round(v) for k, v in IN[h].items()}, 'out': {k: round(v) for k, v in OUTB[h].items()}} for h in HOURS},
}

busy = max(series, key=lambda s: s['out'])
stats = [
    ('4 a.m.', rnd(RES), 'residents, nearly all asleep'),
    (clock(peak['t']), rnd(peak['total']), f'the day\'s peak, {TOKENS["times"]}× the residents'),
    (f'{clock(busy["t"] - 1).split()[0]} to {clock(busy["t"])}', rnd(busy['out']), 'trips out of downtown in its busiest hour'),
    ('10 p.m.', rnd(evening['total']), f'still {TOKENS["evening"]} more than live here'),
]
stats_html = ''.join(f'<div class="stat"><span class="k">{a}</span><b>{b}</b><span>{c}</span></div>' for a, b, c in stats)
method_html = ''.join(f'<p>{p}</p>' for p in page['method'])

tpl = open(os.path.join(ROOT, 'engine', 'commute', 'page.html'), encoding='utf-8').read()
DARK = ['{--water:#1B2A33;--land:#24272D;--edge:#4A4F57;--near-land:#1E2126}', '.flowbox .ln-hwy{stroke:#4D4A45}']
rep = {
    'title': page['title'], 'city': page['city'], 'short': page['short'], 'description': page['description'],
    'lede': page['lede'], 'chartNoteJSON': json.dumps(page['chartNote'], ensure_ascii=False), 'flowNote': page.get('flowNote', ''), 'howTitle': page['howTitle'], 'howLede': page['howLede'],
    'howA': page['howA'], 'howB': page['howB'], 'whereTitle': page['whereTitle'], 'whereLede': page['whereLede'],
    'whereNote': page['whereNote'], 'hybridTitle': page['hybridTitle'], 'hybridText': page['hybridText'],
    'hybridSmall': page['hybridSmall'], 'videosTitle': page['videosTitle'], 'methodTitle': page['methodTitle'],
    'method': method_html, 'credits': page['credits'], 'stats': stats_html,
    'robots': '<meta name="robots" content="noindex">' if cfg.get('unlisted') else '',
    'canonical': f'https://layers.city/{city}/{cfg["path"]}/',
    'DATA': json.dumps(DATA, separators=(',', ':'), ensure_ascii=False),
    'themeScript': THEME_SCRIPT, 'themeCss': theme_css(DARK),
}
html = tpl
for k, v in rep.items():
    html = html.replace('{{' + k + '}}', v)
left = re.findall(r'\{\{\w+\}\}', html)
if left:
    sys.exit(f'page.html: unfilled {left}')
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)
print(f'{city}: peak {peak["total"]:,.0f} at {clock(peak["t"])}, {W_TOT:,.0f} workers ({unplaced:,.0f} unplaced) '
      f'-> docs/{city}/{cfg["path"]}/index.html ({os.path.getsize(os.path.join(OUT, "index.html")) // 1024} KB)')
