"""Build a city's cycling explainer page, docs/<city>/<path>/index.html, from cities/<city>/cycling.json.

Usage: python3 engine/cycling/build.py <city>

Inputs are the small files a city's own script writes to cities/<city>/<dataDir>/ (Toronto: cities/toronto/cycling.py):
bike-share trips per month, the bike network's km by install year and dated snapshots, travel-survey shares and
counts, and counter averages; plus the city's bike network file (drawn as the map) and a boundary file for the land.
Everything is computed and projected here, so the page needs no chart or map library. The engine names no city;
the words are in the JSON."""
import json, math, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from theme import SCRIPT as THEME_SCRIPT, css as theme_css   # noqa: E402

city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: build.py <city>')
CITY = os.path.join(ROOT, 'cities', city)
cfg = json.load(open(os.path.join(CITY, 'cycling.json'), encoding='utf-8'))
OUT = os.path.join(ROOT, 'docs', city, cfg['path'])
DD = os.path.join(CITY, cfg['dataDir'])
load = lambda n: json.load(open(os.path.join(DD, n + '.json'), encoding='utf-8'))
bs, net, tts, counts = (load(n) for n in ('bikeshare', 'network', 'tts', 'counts'))
pub = cfg['published']

CLASS = {'Cycle Track': 'prot', 'Bi-Directional Cycle Track': 'prot', 'Cycle Track - Contraflow': 'prot',
         'Bike Lane': 'paint', 'Bike Lane - Buffered': 'paint', 'Bike Lane - Contraflow': 'paint'}


def klass(h):
    h = h or ''
    return CLASS.get(h) or ('trail' if 'Trail' in h or h == 'Park Road' else 'shared')


# ---- map: land from the boundary file, bikeways from the network file ------------------------------------------
lat0 = 43.7
kx, ky = math.cos(math.radians(lat0)) * 111.32, 110.57


def rings(geom):
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    return [ring for poly in polys for ring in poly]


def lines(geom):
    return [geom['coordinates']] if geom['type'] == 'LineString' else geom['coordinates']


base = json.load(open(os.path.join(ROOT, cfg['base']), encoding='utf-8'))
xs = [lon * kx for f in base['features'] for r in rings(f['geometry']) for lon, lat in r]
ys = [-lat * ky for f in base['features'] for r in rings(f['geometry']) for lon, lat in r]
x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
PAD = 10
S = (1000 - 2 * PAD) / (x1 - x0)
MAP_H = round((y1 - y0) * S + 2 * PAD)


def pt(lon, lat):
    return round((lon * kx - x0) * S + PAD, 1), round((-lat * ky - y0) * S + PAD, 1)


def d_of(seq, close=False, tol=0.6):
    pts = [pt(lon, lat) for lon, lat in (p[:2] for p in seq)]
    keep = [pts[0]] + [q for a, q in zip(pts, pts[1:]) if abs(q[0] - a[0]) + abs(q[1] - a[1]) > tol]
    if not close and keep[-1] != pts[-1]:
        keep.append(pts[-1])
    return 'M' + 'L'.join(f'{x:g} {y:g}' for x, y in keep) + ('Z' if close else '')


land = ''.join(d_of(r, close=True) for f in base['features'] for r in rings(f['geometry']) if len(r) > 3)
segs = []
for f in json.load(open(os.path.join(ROOT, cfg['network']), encoding='utf-8'))['features']:
    p = f['properties']
    segs.append({'y': int(p['INSTALLED'] or 2001) if (p['INSTALLED'] or 0) >= 2001 else 2001,
                 'c': klass(p['INFRA_HIGHORDER']), 'd': ''.join(d_of(l, tol=0.4) for l in lines(f['geometry']) if len(l) > 1)})
removed = [{'label': r['label'], 'km': r['km'], 'd': d_of(r['line'], tol=0.3)} for r in net['removed']]

# ---- numbers and words ------------------------------------------------------------------------------------------
months = bs['months']
year_tot = {}
for m, n in months:
    year_tot[m[:4]] = year_tot.get(m[:4], 0) + (n or 0)
through = bs['through']
ty, tm = through[:4], int(through[5:])
prev = str(int(ty) - 1)
ytd = sum(n or 0 for m, n in months if m[:4] == ty and int(m[5:]) <= tm)
ytd_prev = sum(n or 0 for m, n in months if m[:4] == prev and int(m[5:]) <= tm)
ebike_prev = sum(v for m, v in bs['ebike'].items() if m[:4] == prev)
snaps = net['snapshots']
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


def mil(n, d=1):
    return f'{n / 1e6:.{d}f} million'


def share(d, bike_only=False):
    t = sum(d.values())
    return (d.get('Cycle', 0) + (0 if bike_only else d.get('E-scooter', 0))) / t


def pct(x, d=1):
    return f'{x * 100:.{d}f}%'


def one_in(x):
    return f'1 in {round(1 / x)}'


T = {y: tts[y] for y in ('2011', '2016', '2022')}
into16, into22 = T['2016']['intoPd1'], T['2022']['intoPd1']
cnt = {c['name']: c['aprSep'] for c in counts['counters']}
palm = cnt[cfg['reduce']['counters'][0]]
cord = counts['cordon']
TOKENS = {
    'rides2025': mil(year_tot[prev]), 'ytd': mil(ytd, 2), 'ytdPct': f'{(ytd / ytd_prev - 1) * 100:.0f}%',
    'ebike2025': mil(ebike_prev), 'bsTotal': f'{sum(year_tot.values()):,}',
    'prot2019': f'{snaps[0]["km"]["prot"]:.0f}', 'prot2023': f'{snaps[1]["km"]["prot"]:.0f}', 'protNow': f'{snaps[-1]["km"]["prot"]:.0f}',
    'networkKm': f'{pub["networkKm"]:g}', 'removedKm': f'{sum(r["km"] for r in net["removed"]):g}',
    'cityShare': pct(share(T['2022']['withinToronto'])), 'cityShare2016': pct(share(T['2016']['withinToronto'])),
    'cityShare2011': pct(share(T['2011']['withinToronto'])), 'cityShareBike': pct(share(T['2022']['withinToronto'], True)),
    'dtShare': pct(share(T['2022']['torontoToPd1'])),
    'allIntoDrop': f'{(1 - sum(into22.values()) / sum(into16.values())) * 100:.0f}%',
    'bikeInto2016': f'{into16["Cycle"]:,}', 'bikeInto2022': f'{into22["Cycle"]:,}',
    'withinGrowth': f'{(T["2022"]["withinPd1"]["Cycle"] / T["2016"]["withinPd1"]["Cycle"] - 1) * 100:.0f}%',
    'palmerston2025': f'{palm["2025"]["avg"]:,}', 'palmerston2023': f'{palm["2023"]["avg"]:,}',
    'cordonSites': str(counts['cordonSites']), 'cordon2010': f'{cord["2010"]:,}', 'cordon2014': f'{cord["2014"]:,}',
    'cordon2022': f'{cord["2022"]:,}', 'cordon2022all': f'{cord["2022all"]:,}',
}


def words(s):
    return re.sub(r'\{(\w+)\}', lambda m: TOKENS[m.group(1)], s)


page = {k: (words(v) if isinstance(v, str) else [words(x) for x in v] if isinstance(v, list) else v) for k, v in cfg['page'].items()}

first_full = min(y for y in year_tot if y >= '2018')
stats = [
    (f'Bike Share, {prev}', mil(year_tot[prev]), f'trips, {year_tot[prev] / year_tot[first_full]:.0f} times as many as in {first_full}'),
    (f'Bike Share, Jan–{MONTHS[tm - 1][:3]} {ty}', f'+{TOKENS["ytdPct"]}', f'{mil(ytd, 2)} trips, against {mil(ytd_prev, 2)} in the same months of {prev}'),
    ('Protected bike lanes', f'{snaps[-1]["km"]["prot"]:.0f} km', f'on the City’s map in {MONTHS[int(snaps[-1]["date"][5:7]) - 1]} {snaps[-1]["date"][:4]}, from about {TOKENS["prot2019"]} km in {snaps[0]["date"][:4]}'),
    ('Into downtown, 2022', one_in(share(T['2022']['torontoToPd1'])), f'trips from across the city made by bike or e-scooter, from {one_in(share(T["2016"]["torontoToPd1"]))} in 2016'),
]
stats_html = ''.join(f'<div class="stat"><span class="k">{a}</span><b>{b}</b><span>{c}</span></div>' for a, b, c in stats)
method_html = ''.join(f'<p>{p}</p>' for p in page['method'])

years_net = sorted(int(y) for y in net['byYear'] if int(y) >= 2001)
by_year = {}
for y, v in net['byYear'].items():
    k = max(2001, int(y))
    for c, km_ in v.items():
        by_year.setdefault(k, {}).setdefault(c, 0)
        by_year[k][c] += km_

def survey(t):
    """One survey year for the page: shares as [bikes, bikes + e-scooters], and the downtown counts."""
    w, into = t['withinPd1'], t['intoPd1']
    return {'city': [share(t['withinToronto'], True), share(t['withinToronto'])],
            'toDt': [share(t['torontoToPd1'], True), share(t['torontoToPd1'])],
            'inDt': [share(w, True), share(w)],
            'bikeInto': into['Cycle'], 'eInto': into.get('E-scooter', 0), 'allInto': sum(into.values()),
            'bikeWithin': w['Cycle'], 'eWithin': w.get('E-scooter', 0), 'allWithin': sum(w.values()),
            'hour': t['bikeIntoPd1ByHour']}


DATA = {
    'months': months, 'ebike': bs['ebike'], 'missing': bs['missing'],
    'map': {'h': MAP_H, 'land': land, 'segs': segs, 'removed': removed},
    'net': {'years': years_net, 'byYear': {str(y): {c: round(v, 2) for c, v in by_year[y].items()} for y in years_net},
            'asof': net['asof'], 'snaps': snaps},
    'tts': {y: survey(T[y]) for y in T},
    'counters': counts['counters'], 'videos': cfg.get('videos', []),
}

tpl = open(os.path.join(ROOT, 'engine', 'cycling', 'page.html'), encoding='utf-8').read()
rep = {
    **{k: v for k, v in page.items() if isinstance(v, str)},
    'method': method_html, 'stats': stats_html,
    'robots': '<meta name="robots" content="noindex">' if cfg.get('unlisted') else '',
    'canonical': f'https://layers.city/{city}/{cfg["path"]}/',
    'DATA': json.dumps(DATA, separators=(',', ':'), ensure_ascii=False),
    'themeScript': THEME_SCRIPT,
    'themeCss': theme_css(['{--water:#1B2A33;--land:#24272D;--edge:#3A3F47;--bike:#B4F03A;--bike-2:#6E9E2A;--bike-trail:#D9A35E;--ebike:#5FB98A}']),
}
html = tpl
for k, v in rep.items():
    html = html.replace('{{' + k + '}}', v)
left = re.findall(r'\{\{\w+\}\}', html)
if left:
    sys.exit(f'page.html: unfilled {left}')
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)
print(f'{city}: {sum(year_tot.values()):,} bike-share trips, {len(segs)} bikeway segments -> docs/{city}/{cfg["path"]}/index.html '
      f'({os.path.getsize(os.path.join(OUT, "index.html")) // 1024} KB)')
