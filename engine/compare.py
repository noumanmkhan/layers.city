"""City vs city figures for the Compare page (docs/compare/, unlisted preview).

Usage: python3 engine/compare.py            writes docs/compare/data.json for every city with a profiles file

The Neighbourhoods mode reads each city's profiles file directly in the browser; this script only tells it where.

Reads only published files: each city's docs/<city>/data/<units>_profiles.json (the "Living here" figures the
card and the fact sheets use, plus each unit's population `pop` and households `hh`) and
docs/<city>/data/city.json (labels, hub, source lines). Nothing else changes.

Two views of every figure, so the page can switch between them:
- "city": weighted by people (ages, languages, recent immigrants, commuting, hub minutes) or by households
  (home types, when built, renters, home value, rent). Weighting a unit's share by its people and summing gives
  the citywide share, as the census would report it. Money and minutes become weighted medians: the
  neighbourhood figure of the median household or resident.
- "typical": the unweighted summary across units (median for money and minutes, mean for shares): what the
  typical neighbourhood looks like, one unit one vote. The units differ in size from city to city, so this
  view flattens a city of big districts (New York's 59) more than one of small neighbourhoods (Toronto's 158).
"""
import json, os, statistics

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DOCS = os.path.join(ROOT, 'docs')
OUT = os.path.join(DOCS, 'compare', 'data.json')

# Which profiles file each city publishes, which field holds its transit minutes to the hub, and what its
# money is in. (The card's config names the hub; the field name is the hub's slug.)
CITIES = [
    ('toronto',   'nbhd_profiles', 'union',      'CAD'),
    ('vancouver', 'la_profiles',   'waterfront', 'CAD'),
    ('chicago',   'ca_profiles',   'loop',       'USD'),
    ('nyc',       'cd_profiles',   'penn',       'USD'),
    ('dallas',    'zip_profiles',  'downtown',   'USD'),
]

def pairs(rows, key, wkey):
    return [(r[key], r[wkey]) for r in rows if r.get(key) is not None and r.get(wkey)]

def wmean(rows, key, wkey):
    p = pairs(rows, key, wkey)
    return round(sum(v * w for v, w in p) / sum(w for _, w in p)) if p else None

def wquantile(rows, key, wkey, q):
    p = sorted(pairs(rows, key, wkey))
    if not p: return None
    total, run = sum(w for _, w in p), 0
    for v, w in p:
        run += w
        if run >= q * total: return round(v)
    return round(p[-1][0])

def wbands(rows, key, wkey, n):
    out = []
    for i in range(n):
        p = [(r[key][i], r[wkey]) for r in rows if r.get(key) and len(r[key]) > i and r[key][i] is not None and r.get(wkey)]
        out.append(round(sum(v * w for v, w in p) / sum(w for _, w in p)) if p else None)
    return out

def mean(rows, key):
    xs = [r[key] for r in rows if r.get(key) is not None]
    return round(statistics.mean(xs)) if xs else None

def median(rows, key):
    xs = [r[key] for r in rows if r.get(key) is not None]
    return round(statistics.median(xs)) if xs else None

def quartiles(rows, key):
    xs = sorted(r[key] for r in rows if r.get(key) is not None)
    if len(xs) < 4: return None
    q = statistics.quantiles(xs, n=4)
    return [round(q[0]), round(q[2])]

def bands(rows, key, n):
    return [mean([{'x': r[key][i]} for r in rows if r.get(key) and len(r[key]) > i], 'x') for i in range(n)]

def english(rows, weighted):
    xs = [(p, r['pop']) for r in rows for name, p in (r.get('lang') or []) if name.startswith('English') and r.get('pop')]
    if not xs: return None
    return round(sum(p * w for p, w in xs) / sum(w for _, w in xs)) if weighted else round(statistics.mean(p for p, _ in xs))

def city(cid, pfile, hub, currency):
    D = os.path.join(DOCS, cid, 'data')
    cfg = json.load(open(os.path.join(D, 'city.json')))
    rows = list(json.load(open(os.path.join(D, pfile + '.json'))).values())
    living = cfg['card']['living']
    n = len(rows)
    # Every unit lists only its leading languages, so for the other languages the honest figure is how many
    # units each one leads in, not a share.
    counts = {}
    for r in rows:
        for name, pct in r.get('lang') or []:
            if not name.startswith('English'): counts[name] = counts.get(name, 0) + 1
    leading = sorted(counts.items(), key=lambda kv: -kv[1])[:5]

    source = living.get('footer', '').replace(', {name}', '').replace(', ZIP {name}', '').split('. ')[0]
    recent_def = living.get('recent', {}).get('text', '').replace('{pct}% ', '')
    since = next((r.get('recentSince') for r in rows if r.get('recentSince')), None)
    if since: recent_def = recent_def.replace('{since}', since)

    views = {
        'city': {   # weighted: the city as its people and households experience it
            'value': {'median': wquantile(rows, 'value', 'hh', .5), 'range': [wquantile(rows, 'value', 'hh', .25), wquantile(rows, 'value', 'hh', .75)]},
            'rent': {'median': wquantile(rows, 'rent', 'hh', .5), 'range': [wquantile(rows, 'rent', 'hh', .25), wquantile(rows, 'rent', 'hh', .75)]},
            'renterPct': wmean(rows, 'renterPct', 'hh'),
            'modes': {'car': wmean(rows, 'carPct', 'pop'), 'transit': wmean(rows, 'transitPct', 'pop'), 'walkBike': wmean(rows, 'walkBikePct', 'pop')},
            'hub': {'median': wquantile(rows, hub, 'pop', .5), 'range': [wquantile(rows, hub, 'pop', .25), wquantile(rows, hub, 'pop', .75)]},
            'homes': wbands(rows, 'homes', 'hh', 4), 'built': wbands(rows, 'built', 'hh', 4), 'ages': wbands(rows, 'ages', 'pop', 5),
            'english': english(rows, True), 'recent': wmean(rows, 'recent', 'pop'), 'canopy': wquantile(rows, 'canopy', 'pop', .5),
        },
        'typical': {   # unweighted: one unit, one vote
            'value': {'median': median(rows, 'value'), 'range': quartiles(rows, 'value')},
            'rent': {'median': median(rows, 'rent'), 'range': quartiles(rows, 'rent')},
            'renterPct': mean(rows, 'renterPct'),
            'modes': {'car': mean(rows, 'carPct'), 'transit': mean(rows, 'transitPct'), 'walkBike': mean(rows, 'walkBikePct')},
            'hub': {'median': median(rows, hub), 'range': quartiles(rows, hub)},
            'homes': bands(rows, 'homes', 4), 'built': bands(rows, 'built', 4), 'ages': bands(rows, 'ages', 5),
            'english': english(rows, False), 'recent': mean(rows, 'recent'), 'canopy': median(rows, 'canopy'),
        },
    }
    if views['city']['hub']['median'] is None: views['city']['hub']['range'] = None
    return {
        'id': cid, 'name': cfg['heading'], 'unlisted': bool(cfg.get('unlisted')),
        'units': {'n': n, 'singular': cfg['units']['singular'], 'plural': cfg['units']['plural'],
                  'pop': sum(r.get('pop') or 0 for r in rows), 'hh': sum(r.get('hh') or 0 for r in rows),
                  'hubN': sum(1 for r in rows if r.get(hub) is not None)},
        'currency': currency, 'source': source,
        # For the Neighbourhoods mode: the page loads this file when a column picks the city, reads the hub's
        # minutes from `hubKey`, and links each unit to the map with #focus=<unitsLayer>:<name>.
        'profiles': f'/{cid}/data/{pfile}.json', 'hubKey': hub,
        'unitsLayer': next(it['id'] for _, items in cfg['groups'] for it in items if it['kind'] == 'units'),
        'hubLabel': living.get('hub', ''),
        'labels': {'homes': [t[1] for t in living['homes']['types']], 'built': living['built']['bands'], 'ages': living['ages']['bands']},
        'leading': leading, 'recentDefinition': recent_def,
        'views': views,
    }

cities = []
for cid, pfile, hub, currency in CITIES:
    if os.path.exists(os.path.join(DOCS, cid, 'data', pfile + '.json')):
        cities.append(city(cid, pfile, hub, currency))
        c = cities[-1]
        print(f"{cid}: {c['units']['n']} {c['units']['plural']}, {c['units']['pop']:,} people; drive {c['views']['typical']['modes']['car']}% typical → {c['views']['city']['modes']['car']}% city; towers/20+ {c['views']['typical']['homes'][3]}% → {c['views']['city']['homes'][3]}%")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({'cities': cities}, open(OUT, 'w'), separators=(',', ':'))
print('wrote', os.path.relpath(OUT, ROOT))
