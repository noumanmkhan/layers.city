"""City vs city figures for the Compare page (docs/compare/, unlisted preview).

Usage: python3 engine/compare.py            writes docs/compare/data.json for every city with a profiles file

Reads only published files: each city's docs/<city>/data/<units>_profiles.json (the "Living here" figures the
card and the fact sheets use) and docs/<city>/data/city.json (labels, hub, source lines). Nothing else changes.

Every figure is an unweighted summary across the city's units (neighbourhoods, community areas, local areas,
ZIP codes, community districts): the median for money and minutes, the mean for shares. The units differ in
size from city to city, so these describe a typical neighbourhood, not the whole population; the page says so.
Population-weighted citywide totals are the first thing to add if this leaves the preview stage.
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

def median(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs)) if xs else None

def quartiles(xs):
    xs = sorted(x for x in xs if x is not None)
    if len(xs) < 4: return None
    q = statistics.quantiles(xs, n=4)
    return [round(q[0]), round(q[2])]

def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs)) if xs else None

def mean_bands(rows, key, n):
    cols = [[r[key][i] for r in rows if r.get(key) and len(r[key]) > i and r[key][i] is not None] for i in range(n)]
    return [mean(c) for c in cols]

def city(cid, pfile, hub, currency):
    D = os.path.join(DOCS, cid, 'data')
    cfg = json.load(open(os.path.join(D, 'city.json')))
    rows = list(json.load(open(os.path.join(D, pfile + '.json'))).values())
    living = cfg['card']['living']
    n = len(rows)

    # Language at home. Each unit lists only its leading languages (above the card's floor), so averaging
    # shares would undercount every language but English. Instead: the English share (listed everywhere),
    # and for the other languages, how many units each one leads in.
    english = [p for r in rows for name, p in (r.get('lang') or []) if name.startswith('English')]
    counts = {}
    for r in rows:
        for name, pct in r.get('lang') or []:
            if not name.startswith('English'): counts[name] = counts.get(name, 0) + 1
    lang = sorted(counts.items(), key=lambda kv: -kv[1])[:5]

    commute = {t: sum(1 for r in rows if r.get('commute') == t) for t in ('transit', 'mixed', 'car')}

    # The source line, from the card's footer ("2021 Census and TTC/GO schedules, {name}. Tiers ...").
    source = living.get('footer', '').replace(', {name}', '').replace(', ZIP {name}', '').split('. ')[0]
    recent_def = living.get('recent', {}).get('text', '').replace('{pct}% ', '')
    since = next((r.get('recentSince') for r in rows if r.get('recentSince')), None)
    if since: recent_def = recent_def.replace('{since}', since)

    return {
        'id': cid,
        'name': cfg['heading'],
        'title': cfg.get('title', ''),
        'unlisted': bool(cfg.get('unlisted')),
        'units': {'n': n, 'singular': cfg['units']['singular'], 'plural': cfg['units']['plural']},
        'currency': currency,
        'source': source,
        'value': {'median': median([r.get('value') for r in rows]), 'range': quartiles([r.get('value') for r in rows])},
        'rent': {'median': median([r.get('rent') for r in rows]), 'range': quartiles([r.get('rent') for r in rows])},
        'renterPct': mean([r.get('renterPct') for r in rows]),
        'modes': {'car': mean([r.get('carPct') for r in rows]),
                  'transit': mean([r.get('transitPct') for r in rows]),
                  'walkBike': mean([r.get('walkBikePct') for r in rows])},
        'commute': commute,
        'hub': {'label': living.get('hub', ''), 'median': median([r.get(hub) for r in rows]),
                'range': quartiles([r.get(hub) for r in rows]),
                'n': sum(1 for r in rows if r.get(hub) is not None)},
        'homes': {'labels': [t[1] for t in living['homes']['types']], 'shares': mean_bands(rows, 'homes', 4)},
        'built': {'labels': living['built']['bands'], 'shares': mean_bands(rows, 'built', 4)},
        'ages': {'labels': living['ages']['bands'], 'shares': mean_bands(rows, 'ages', 5)},
        'lang': {'english': mean(english), 'leading': lang},
        'recent': {'mean': mean([r.get('recent') for r in rows]), 'definition': recent_def},
        'canopy': median([r.get('canopy') for r in rows]),
    }

cities = []
for cid, pfile, hub, currency in CITIES:
    if os.path.exists(os.path.join(DOCS, cid, 'data', pfile + '.json')):
        cities.append(city(cid, pfile, hub, currency))
        print(cid, cities[-1]['units']['n'], cities[-1]['units']['plural'])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({'cities': cities}, open(OUT, 'w'), separators=(',', ':'))
print('wrote', os.path.relpath(OUT, ROOT))
