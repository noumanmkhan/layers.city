"""Build a city's Fun maps page, docs/<city>/fun/index.html, from cities/<city>/fun.json.

Usage: python3 engine/fun/build.py <city>

Each map in fun.json is one of:
  pair          two kinds of place counted per neighbourhood: which one has more. A side is OpenStreetMap places
                (raw/fun/osm_places.json, matched by tag regexes) or a published layer (docs/<city>/data/<file>,
                filtered by "where" properties or a "has" sport).
  signature311  each ward's most over-represented 311 request type (raw/fun/sr311.json).
  tickets       parking tickets and fines per neighbourhood (raw/fun/tickets.json).
  suffix        each neighbourhood's most over-represented street ending (raw/fun/suffixes.json).
A map whose input file is missing is left out, so the page builds with whatever has been fetched.

The page draws every map from one shared set of outlines (projected here, simplified) and a short list of
class indexes per map, so adding a map costs a few hundred bytes. The engine names no city."""
import json, math, os, re, sys
from collections import Counter

from shapely.geometry import shape, Point
from shapely.strtree import STRtree

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from theme import SCRIPT as THEME_SCRIPT, css as theme_css   # noqa: E402

city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: build.py <city>')
CITY = os.path.join(ROOT, 'cities', city)
DATA = os.path.join(ROOT, 'docs', city, 'data')
OUT = os.path.join(ROOT, 'docs', city, 'fun')
cfg = json.load(open(os.path.join(CITY, 'fun.json')))
page = cfg['page']
W = 1000          # SVG width; the height follows the city's shape
NONE = '#E4DCDA'  # "neither": overridden in dark mode by the page's CSS (class n)


def load(p):
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


# ---- outlines -------------------------------------------------------------------------------------------------
def outlines(fname, key):
    feats = load(os.path.join(DATA, fname))['features']
    shp = [shape(f['geometry']) for f in feats]
    return [f['properties'][key] for f in feats], shp


nb_names, nb_shapes = outlines('neighbourhoods.geojson', 'name')
wd_names, wd_shapes = outlines('wards.geojson', 'num')
wd_label = {f['properties']['num']: f['properties']['name'] for f in load(os.path.join(DATA, 'wards.geojson'))['features']}
minx, miny, maxx, maxy = (min(s.bounds[i] for s in nb_shapes) if i < 2 else max(s.bounds[i] for s in nb_shapes) for i in range(4))
KX = math.cos(math.radians((miny + maxy) / 2))
SCALE = W / ((maxx - minx) * KX)
H = round((maxy - miny) * SCALE)


def project_path(geom):
    geom = geom.simplify(0.00025, preserve_topology=True)
    polys = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
    out = []
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            pts = [(round((x - minx) * KX * SCALE, 1), round((maxy - y) * SCALE, 1)) for x, y in ring.coords]
            d = 'M' + 'L'.join(f'{x:g} {y:g}' for x, y in pts[:-1]) + 'Z'
            out.append(d)
    return ''.join(out)


def label_point(geom):
    p = geom.representative_point()
    return [round((p.x - minx) * KX * SCALE), round((maxy - p.y) * SCALE)]


tree = STRtree(nb_shapes)


def nbhd_index(lon, lat):
    pt = Point(lon, lat)
    for i in tree.query(pt):
        if nb_shapes[i].covers(pt):
            return int(i)
    return None


# ---- colours ---------------------------------------------------------------------------------------------------
def mix(hex_, t):
    """Blend a colour toward white by t (0 = the colour, 1 = white)."""
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return '#%02X%02X%02X' % tuple(round(c + (255 - c) * t) for c in (r, g, b))


CATS = ['#C8102E', '#1F6FB5', '#D9822B', '#2E7D32', '#8E5BB5', '#00838F', '#B5651D', '#5C5C8A', '#C2185B', '#7FA51F',
        '#455A64', '#A1683B']


def plural(n, one, many=None):
    return f'{n:,} {one if n == 1 else (many or one + "s")}'


# ---- pair maps -------------------------------------------------------------------------------------------------
osm = load(os.path.join(CITY, cfg.get('osm', 'raw/fun/osm_places.json')))
osm_rows = None
if osm:
    cols = osm['cols']
    osm_rows = [dict(zip(cols, r)) for r in osm['rows']]
    for r in osm_rows:
        r['_nb'] = nbhd_index(r['lon'], r['lat'])


def matches(row, filt):
    return all(re.search(rx, str(row.get(k) or ''), re.I) for k, rx in filt.items())


def side_counts(side):
    """Per-neighbourhood counts for one side of a pair, or None if its source isn't there yet."""
    c = Counter()
    if 'osm' in side:
        if osm_rows is None:
            return None
        for r in osm_rows:
            if r['_nb'] is None:
                continue
            if any(matches(r, f) for f in side['osm']) and not any(matches(r, f) for f in side.get('except', [])):
                c[r['_nb']] += 1
    else:
        d = load(os.path.join(DATA, side['layer']))
        if not d:
            return None
        for f in d['features']:
            p = f['properties']
            if any(str(p.get(k)) != str(v) for k, v in side.get('where', {}).items()):
                continue
            if 'has' in side and side['has'] not in (p.get('cats') or [p.get('cat')]):
                continue
            g = f['geometry']
            lon, lat = (g['coordinates'] if g['type'] == 'Point' else shape(g).representative_point().coords[0])
            i = nbhd_index(lon, lat)
            if i is not None:
                c[i] += 1
    return c


def noun(side):
    l = side['label']
    return side.get('noun') or (l if side.get('brand') or l[:2].isupper() else l[0].lower() + l[1:])


def sent(side):
    """A side's short name for use mid-sentence: brands keep their capitals."""
    w = side.get('short', side['label'])
    return w if side.get('brand') or w[:2].isupper() else w[0].lower() + w[1:]


def pair_map(m):
    a, b = m['a'], m['b']
    a_, b_ = a, b
    ca, cb = side_counts(a), side_counts(b)
    if ca is None or cb is None:
        return None
    A, B = a.get('short', a['label']), b.get('short', b['label'])
    ta, tb = sum(ca.values()), sum(cb.values())
    relative = m.get('mode') == 'relative'
    if relative:
        # Lopsided pairs (pizza outnumbers shawarma almost everywhere): compare each neighbourhood's mix with
        # the city's, so the map shows where each one is over-represented rather than one colour everywhere.
        legend = [{'c': a['colour'], 'l': f'Far more {A} than usual'}, {'c': mix(a['colour'], .55), 'l': f'More {A} than usual'},
                  {'c': '#C9B98F', 'l': 'About the city mix'},
                  {'c': mix(b['colour'], .55), 'l': f'More {B} than usual'}, {'c': b['colour'], 'l': f'Far more {B} than usual'},
                  {'c': NONE, 'l': f'Fewer than {m.get("minPlaces", 3)} of either', 'n': 1}]
    else:
        legend = [{'c': a['colour'], 'l': f'Mostly {A}'}, {'c': mix(a['colour'], .55), 'l': f'More {A}'},
                  {'c': '#C9B98F', 'l': 'Tie'},
                  {'c': mix(b['colour'], .55), 'l': f'More {B}'}, {'c': b['colour'], 'l': f'Mostly {B}'},
                  {'c': NONE, 'l': 'Neither', 'n': 1}]
    v, tips, wins = [], [], Counter()
    for i in range(len(nb_names)):
        x, y = ca[i], cb[i]
        if relative:
            if x + y < m.get('minPlaces', 3):
                k = 5
            else:
                r = ((x + .5) / (y + .5)) / (ta / tb)   # odds against the city's, half-count smoothed
                k = 0 if r >= 2.5 else 1 if r >= 1.4 else 2 if r > 1 / 1.4 else 3 if r > 1 / 2.5 else 4
        elif x + y == 0:
            k = 5
        else:
            sh = x / (x + y)
            k = 0 if sh >= .75 else 1 if sh > .5 else 2 if sh == .5 else 3 if sh > .25 else 4
        wins['none' if k == 5 else 'a' if k < 2 else 'tie' if k == 2 else 'b'] += 1
        v.append(k)
        tips.append(f'{x} {A} · {y} {B}')
    units = page['unitPlural']
    if relative:
        big, small, bn, sn = (b_, a_, tb, ta) if tb >= ta else (a_, b_, ta, tb)
        line = (f'City-wide there are about {round(bn / max(sn, 1))} {big.get("many", noun(big))} for every {small.get("one", noun(small))}, '
                f'so {sent(big)} wins nearly everywhere. '
                f'Against that mix, {wins["a"]} {units} lean {sent(a)} and {wins["b"]} lean {sent(b)}.')
    else:
        sa, sb = sent(a), sent(b)
        line = (f'More {sa} than {sb} in {plural(wins["a"], page["unitName"], units)}, and more {sb} in {wins["b"]}.'
                + (f' Tied: {wins["tie"]}.' if wins['tie'] else '') + (f' Neither: {wins["none"]}.' if wins['none'] else ''))
    def top(side_c, other_c, n=3):
        if relative:
            ok = [i for i in range(len(nb_names)) if side_c[i] + other_c[i] >= m.get('minPlaces', 3) and side_c[i] > 0]
            ok.sort(key=lambda i: (-(side_c[i] + .5) / (other_c[i] + .5), -side_c[i], nb_names[i]))
            return [f'{nb_names[i]} ({side_c[i]}–{other_c[i]})' for i in ok[:n]]
        diff = sorted(range(len(nb_names)), key=lambda i: (-(side_c[i] - other_c[i]), nb_names[i]))
        return [f'{nb_names[i]} ({side_c[i]}–{other_c[i]})' for i in diff[:n] if side_c[i] > other_c[i]]
    stand = []
    ta_top, tb_top = top(ca, cb), top(cb, ca)
    if ta_top:
        stand.append({'k': f'Most {A}', 'v': ', '.join(ta_top)})
    if tb_top:
        stand.append({'k': f'Most {B}', 'v': ', '.join(tb_top)})
    return {'unit': 'nb', 'legend': legend, 'v': v, 'tips': tips, 'line': line,
            'total': f'City-wide: {ta:,} {noun(a)} and {tb:,} {noun(b)}.',
            'stand': stand}


# ---- signature maps (311 by ward, street suffixes by neighbourhood) --------------------------------------------
def signature(counts_by_area, n_areas, min_total, min_area, ignore=()):
    """For each area, the category with the highest location quotient (its share here / its share city-wide)."""
    city_tot = Counter()
    for c in counts_by_area.values():
        city_tot.update(c)
    grand = sum(city_tot.values())
    picks = {}
    for area, c in counts_by_area.items():
        tot = sum(c.values())
        best = None
        for cat, n in c.items():
            if cat in ignore or city_tot[cat] < min_total or n < min_area:
                continue
            lq = (n / tot) / (city_tot[cat] / grand)
            if not best or lq > best[1]:
                best = (cat, lq, n)
        if best:
            picks[area] = best
    return picks, city_tot


def cat_legend(picks, label=lambda s: s, max_cats=None):
    """Colours for the categories that won somewhere, most wins first; past max_cats they share one grey."""
    order = [c for c, _ in Counter(p[0] for p in picks.values()).most_common()]
    rest = []
    if max_cats and len(order) > max_cats:
        order, rest = order[:max_cats - 1], order[max_cats - 1:]
    cols = {c: CATS[i % len(CATS)] for i, c in enumerate(order)}
    legend = [{'c': cols[c], 'l': label(c)} for c in order]
    if rest:
        legend.append({'c': '#9E9592', 'l': 'Something else'})
    index = {c: i for i, c in enumerate(order)}
    index.update({c: len(order) for c in rest})
    return index, legend


def clean_311(t):
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'^(Residential|Road|Sidewalk|Graffiti|Bylaw|Property|Water|Sewer|General Pruning|Tree)\s*[-:]\s*', r'\1: ', t)
    return t


def sig311_map(m):
    d = load(os.path.join(CITY, 'raw', 'fun', 'sr311.json'))
    if not d:
        return None
    themes = [(name, re.compile(rx, re.I)) for name, rx in m['themes']]
    def theme(t):
        return next((name for name, rx in themes if rx.search(t)), 'Other')
    by = {int(k): Counter(v) for k, v in d['by_ward'].items()}
    by_theme = {}
    for k, c in by.items():
        tc = Counter()
        for t, n in c.items():
            tc[theme(t)] += n
        by_theme[k] = tc
    picks, _ = signature(by_theme, len(wd_names), m.get('minTypeTotal', 1000) * 3, m.get('minAreaCount', 50) * 3, {'Other'})
    types, city_tot = signature(by, len(wd_names), m.get('minTypeTotal', 1000), m.get('minAreaCount', 50))
    # The ward's most over-represented single request inside its winning theme, for the tooltip.
    grand = sum(city_tot.values())
    def best_type(num, th):
        c, tot = by[num], sum(by[num].values())
        cands = [(t, (n / tot) / (city_tot[t] / grand), n) for t, n in c.items()
                 if theme(t) == th and city_tot[t] >= m.get('minTypeTotal', 1000) and n >= m.get('minAreaCount', 50)]
        return max(cands, key=lambda x: x[1]) if cands else None
    index, legend = cat_legend(picks)
    v, tips = [], []
    for num in wd_names:
        p = picks.get(num)
        v.append(index[p[0]] if p else len(legend))
        bt = best_type(num, p[0]) if p else None
        tips.append((f'{p[0]}, {p[1]:.1f}× the city rate' + (f'. Top: {clean_311(bt[0])} ({bt[2]:,}, {bt[1]:.1f}×)' if bt else '')) if p else 'No standout')
    legend.append({'c': NONE, 'l': 'No standout', 'n': 1})
    top = city_tot.most_common(1)[0]
    strongest = sorted(types.items(), key=lambda kv: -kv[1][1])[:3]
    stand = [{'k': wd_label[num], 'v': f'{clean_311(p[0])}: {p[1]:.1f}× the city rate'} for num, p in strongest]
    wins = Counter(p[0] for p in picks.values()).most_common()
    return {'unit': 'wd', 'legend': legend, 'v': v, 'tips': tips,
            'line': f'{d["total"]:,} requests in {d["year"]}. The most common was {clean_311(top[0]).lower()}, '
                    f'but each ward has its own pet issue: {wins[0][0].lower()} leads in {wins[0][1]} wards.',
            'total': '', 'stand': stand, 'standTitle': 'Biggest outliers', 'asof': str(d['year'])}


def splural(w, n=2):
    return w if n == 1 or w.endswith('s') else w + 's'


def suffix_map(m):
    d = load(os.path.join(CITY, 'raw', 'fun', 'suffixes.json'))
    if not d:
        return None
    ignore = set(m.get('ignore', []))
    by = {name: Counter(v) for name, v in d['by_nbhd'].items()}
    picks, _ = signature(by, len(nb_names), 20, m.get('minNames', 3), ignore)
    index, legend = cat_legend(picks, splural, m.get('maxCats'))
    v, tips = [], []
    for name in nb_names:
        p = picks.get(name)
        v.append(index[p[0]] if p else len(legend))
        ex = ', '.join(x.title() for x in d.get('examples', {}).get(name, {}).get(p[0], [])[:2]) if p else ''
        tips.append(f'{p[2]} {splural(p[0], p[2])}, {p[1]:.1f}× the city share' + (f' (like {ex})' if ex else '') if p else 'No standout')
    legend.append({'c': NONE, 'l': 'No standout', 'n': 1})
    city = Counter({k: n for k, n in d['city'].items() if k not in ignore})
    common = [k for k, _ in city.most_common(3)]
    rare = [k for k, n in sorted(city.items(), key=lambda kv: (kv[1], kv[0])) if n == 1]
    stand = []
    for suf in m.get('standouts', []):
        best = max(by.items(), key=lambda kv: kv[1].get(suf, 0))
        if best[1].get(suf):
            stand.append({'k': 'Most ' + splural(suf), 'v': f'{best[0]} ({best[1][suf]})'})
    return {'unit': 'nb', 'legend': legend, 'v': v, 'tips': tips,
            'line': f'{page["city"]} has {city[common[0]]:,} {splural(common[0])}, {city[common[1]]:,} {splural(common[1])} and {city[common[2]]:,} {splural(common[2])}. '
                    f'Here is the ending each neighbourhood has far more of than the city.',
            'total': ('One of a kind: ' + ', '.join(f'the only {r}' for r in rare[:4]) + '.') if rare else '',
            'stand': stand}


def tickets_map(m):
    d = load(os.path.join(CITY, 'raw', 'fun', 'tickets.json'))
    if not d:
        return None
    by = d['by_nbhd']
    if not by:
        return None
    fines = sorted(v['fines'] for v in by.values())
    # Quintile breaks, so each colour holds about a fifth of the neighbourhoods.
    br = [fines[int(len(fines) * q)] for q in (.2, .4, .6, .8)]
    ramp = [mix('#C8102E', t) for t in (.82, .62, .42, .2, 0)]
    def money(x):
        return f'${x / 1e6:.1f}M' if x >= 1e6 else f'${round(x / 1e3):,}K' if x >= 1e4 else f'${x:,.0f}'
    legend = [{'c': ramp[0], 'l': f'Under {money(br[0])}'}] + \
             [{'c': ramp[i + 1], 'l': f'{money(br[i])}–{money(br[i + 1])}'} for i in range(3)] + \
             [{'c': ramp[4], 'l': f'Over {money(br[3])}'}, {'c': NONE, 'l': 'No data', 'n': 1}]
    v, tips = [], []
    for name in nb_names:
        x = by.get(name)
        if not x:
            v.append(5)
            tips.append('No tickets placed here')
            continue
        v.append(sum(x['fines'] >= b for b in br))
        top = x.get('top')
        tips.append(f'{x["tickets"]:,} tickets, {money(x["fines"])} in fines' + (f'. Busiest: {top[0]} ({top[1]:,})' if top else ''))
    ranked = sorted(by.items(), key=lambda kv: -kv[1]['fines'])
    busiest = max((x['top'] for x in by.values() if x.get('top')), key=lambda t: t[1])
    inf = Counter()
    for x in by.values():
        for k, n in x['inf']:
            inf[k] += n
    total_f = sum(x['fines'] for x in by.values())
    return {'unit': 'nb', 'legend': legend, 'v': v, 'tips': tips,
            'line': f'{d["tickets"]:,} tickets in {d["year"]}. The single busiest address was {busiest[0]}, with {busiest[1]:,} tickets.',
            'total': f'The {plural(len(by), page["unitName"], page["unitPlural"])} we could place them in collected {money(total_f)}. '
                     f'Most common reason: {inf.most_common(1)[0][0].capitalize()}.',
            'stand': [{'k': 'Most in fines', 'v': ', '.join(f'{n} ({money(x["fines"])})' for n, x in ranked[:3])}],
            'asof': str(d['year'])}


BUILD = {'pair': pair_map, 'signature311': sig311_map, 'tickets': tickets_map, 'suffix': suffix_map}
maps = []
for m in cfg['maps']:
    out = BUILD[m['type']](m)
    if out is None:
        print('  skipped (input not fetched yet):', m['id'])
        continue
    out.update({'id': m['id'], 'title': m['title'], 'note': m.get('note', '')})
    maps.append(out)
    print('  map:', m['id'], '-', out['line'])

shapes = {'nb': {'d': [project_path(s) for s in nb_shapes], 'names': nb_names},
          'wd': {'d': [project_path(s) for s in wd_shapes], 'names': [wd_label[n] for n in wd_names]}}
asof = (osm or {}).get('asof', '')
payload = {'w': W, 'h': H, 'shapes': shapes, 'maps': maps, 'asof': asof}

tpl = open(os.path.join(ROOT, 'engine', 'fun', 'page.html'), encoding='utf-8').read()
DARK = ['.fm .n{fill:#2E3238}', '.fm path{stroke:#15171B}']
html = (tpl.replace('{{FUN}}', json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
        .replace('{{title}}', page['title']).replace('{{city}}', page['city'])
        .replace('{{description}}', page['description']).replace('{{lede}}', page['lede'])
        .replace('{{credits}}', page['credits']).replace('{{refresh}}', page.get('refresh', ''))
        .replace('{{themeScript}}', THEME_SCRIPT).replace('{{themeCss}}', theme_css(DARK)))
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)
print(f'wrote docs/{city}/fun/index.html: {len(maps)} maps, {len(html) // 1024} KB')
