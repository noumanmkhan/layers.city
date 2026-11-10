"""Build a city's ride-hail explainer page, docs/<city>/<path>/index.html, from cities/<city>/rideshare.json.

Usage: python3 engine/rideshare/build.py <city>

Inputs are the small files a city's own script writes to cities/<city>/<dataDir>/ (Toronto: cities/toronto/rideshare.py,
from the City's ride-hail open data): pickups per hour by day type for the whole area and per ward, average waits,
drivers logged in by hour, top ward-to-ward flows and monthly totals, plus the ward boundaries. Everything is computed
and projected here, so the page needs no chart or map library. The engine names no city; the words are in the JSON."""
import json, math, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from theme import SCRIPT as THEME_SCRIPT, css as theme_css   # noqa: E402

city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: build.py <city>')
CITY = os.path.join(ROOT, 'cities', city)
cfg = json.load(open(os.path.join(CITY, 'rideshare.json'), encoding='utf-8'))
OUT = os.path.join(ROOT, 'docs', city, cfg['path'])
DD = os.path.join(CITY, cfg['dataDir'])
load = lambda n: json.load(open(os.path.join(DD, n + '.json'), encoding='utf-8'))
hourly, wards, flows, supply, years, meta = (load(n) for n in ('hourly', 'wards', 'flows', 'supply', 'years', 'meta'))
DT = [d['id'] for d in cfg['dayTypes']]
HOURS = hourly['hours']                     # clock order of a service day, 4 a.m. first


def clock(h, short=False):
    h %= 24
    n = 12 if h % 12 == 0 else h % 12
    return f'{n}{"a" if h < 12 else "p"}' if short else f'{n} {"a.m." if h < 12 else "p.m."}'


def rnd(n, to=1000):
    return f'{int(round(n / to) * to):,}'


def pct(x):
    return f'{x * 100:.0f}%'


def at(series, h):
    return series[HOURS.index(h)]


# ---- ward map -------------------------------------------------------------------------------------------------
gj = json.load(open(os.path.join(ROOT, cfg['wards']), encoding='utf-8'))
lat0 = 43.7
kx, ky = math.cos(math.radians(lat0)) * 111.32, 110.57


def rings(geom):
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    return [ring for poly in polys for ring in poly]


xs = [lon * kx for f in gj['features'] for r in rings(f['geometry']) for lon, lat in r]
ys = [-lat * ky for f in gj['features'] for r in rings(f['geometry']) for lon, lat in r]
x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
PAD = 12
S = (1000 - 2 * PAD) / (x1 - x0)
MAP_H = round((y1 - y0) * S + 2 * PAD)


def pt(lon, lat):
    return round((lon * kx - x0) * S + PAD, 1), round((-lat * ky - y0) * S + PAD, 1)


def path(f):
    out = []
    for ring in rings(f['geometry']):
        pts = [pt(lon, lat) for lon, lat in ring]
        keep = [pts[0]] + [q for a, q in zip(pts, pts[1:]) if abs(q[0] - a[0]) + abs(q[1] - a[1]) > 0.6]
        if len(keep) > 2:
            out.append('M' + 'L'.join(f'{x} {y}' for x, y in keep) + 'Z')
    return ''.join(out)


wmap = []
for f in gj['features']:
    p = f['properties']
    key = f'{p["num"]:02d}'
    if key not in wards:
        sys.exit(f'{cfg["dataDir"]}/wards.json has no ward {key}')
    wmap.append({'k': key, 'n': p['name'], 'd': path(f), 'l': pt(*p['lp'])})

# ---- numbers and words ----------------------------------------------------------------------------------------
per_day = {d: sum(hourly['all'][d]) for d in DT}
idle = supply['idle_share']['weekday']
night = [at(idle, h) for h in (1, 2, 3)]
yr = meta['annual_trips']
w10 = max(wards, key=lambda k: sum(wards[k]['pickups']['weekday']))
tot_t = hourly['toronto']
TOKENS = {
    'year2025': f'{yr["2025"] / 1e6:.1f} million', 'year2021': f'{yr["2021"] / 1e6:.1f} million',
    **{f'perDay_{d}': rnd(per_day[d]) for d in DT},
    'wk8': '8 a.m.', 'idle8': pct(at(idle, 8)), 'idleNight': pct(sum(night) / len(night)),
    'noWard': pct(meta['toronto_pickups_without_ward_share']), 'minTrips': str(meta['min_trips_for_wait_fare']),
    'trips': f'{meta["trips_in_window"] / 1e6:.1f} million',
    'days': ', '.join(f'{meta["days_by_type"][d["id"]]} {d["name"]}' for d in cfg['dayTypes']),
}


def words(s):
    return re.sub(r'\{(\w+)\}', lambda m: TOKENS[m.group(1)], s)


page = {k: (words(v) if isinstance(v, str) else [words(x) for x in v] if isinstance(v, list) else v) for k, v in cfg['page'].items()}

# Stat cards: each a fact that holds for the whole year's average.
late_wk, late_sat = at(hourly['all']['weekday'], 1), at(hourly['all']['sat'], 1)
peak_fri = max(range(24), key=lambda i: hourly['all']['fri'][i])
stats = [
    ('Busiest hour', f'{hourly["all"]["fri"][peak_fri]:,}', f'pickups at {clock(HOURS[peak_fri])} on a Friday'),
    ('1 a.m.', f'{late_sat / late_wk:.1f}'.rstrip('0').rstrip('.') + '×', 'as many pickups on a Saturday night as on a weeknight'),
    ('8 a.m. weekdays', TOKENS['idle8'], 'of drivers’ logged-in time spent waiting for a ride'),
    (wards[w10]['name'], pct(sum(wards[w10]['pickups']['weekday']) / sum(tot_t['weekday'])), 'of Toronto’s weekday pickups start in this one ward'),
]
stats_html = ''.join(f'<div class="stat"><span class="k">{a}</span><b>{b}</b><span>{c}</span></div>' for a, b, c in stats)
method_html = ''.join(f'<p>{p}</p>' for p in page['method'])

names = {k: v['name'] for k, v in wards.items()}


def place(x):
    return {'k': x, 'n': names[x]} if x in names else {'k': None, 'n': x.replace(' Airport', '')}


DATA = {
    'hours': HOURS,
    'days': [{'id': d['id'], 'n': d['name'], 'l': d['long'], 'c': d['colour']} for d in cfg['dayTypes']],
    'all': hourly['all'], 'pearson': hourly['pearson'],
    'wards': {k: {'n': v['name'], 'p': v['pickups'], 'w': v['wait']} for k, v in wards.items()},
    'map': {'h': MAP_H, 'w': wmap},
    'sup': {'d': supply['drivers'], 't': supply['trips'], 'i': supply['idle_share']},
    'flows': [{'l': m['label'], 'f': [{'a': place(x['from']), 'b': place(x['to']), 'n': x['per_hour']} for x in flows[m['id']][:8]]}
              for m in cfg['moments']],
    'years': [[y['month'], y['avg_daily_trips']] for y in years],
    'videos': cfg.get('videos', []),
}

tpl = open(os.path.join(ROOT, 'engine', 'rideshare', 'page.html'), encoding='utf-8').read()
rep = {
    **{k: v for k, v in page.items() if isinstance(v, str)},
    'method': method_html, 'stats': stats_html,
    **{k + 'JSON': json.dumps(page[k], ensure_ascii=False) for k in ('mapNote', 'waitNote', 'chartNote')},
    'robots': '<meta name="robots" content="noindex">' if cfg.get('unlisted') else '',
    'canonical': f'https://layers.city/{city}/{cfg["path"]}/',
    'DATA': json.dumps(DATA, separators=(',', ':'), ensure_ascii=False),
    'themeScript': THEME_SCRIPT, 'themeCss': theme_css(['{--water:#1B2A33;--land:#24272D;--edge:#4A4F57}']),
}
html = tpl
for k, v in rep.items():
    html = html.replace('{{' + k + '}}', v)
left = re.findall(r'\{\{\w+\}\}', html)
if left:
    sys.exit(f'page.html: unfilled {left}')
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)
print(f'{city}: {meta["trips_in_window"]:,} trips, {len(wmap)} wards -> docs/{city}/{cfg["path"]}/index.html '
      f'({os.path.getsize(os.path.join(OUT, "index.html")) // 1024} KB)')
