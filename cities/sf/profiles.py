"""Neighbourhood lenses from the American Community Survey (5-year estimates, San Francisco's tracts).
Inputs: raw/acs_tracts.json and raw/tracts.json (fetch_acs.py), tmp/neighbourhoods.geojson (build.py)
Output: docs/sf/data/nb_profiles.json  {code: {...figures and tiers...}}

The method is Chicago's (cities/chicago/profiles.py): each tract goes to the Analysis Neighborhood holding its
internal point (the 41 are 2020 tracts grouped by Planning, so they nest exactly), counts are summed, and the
medians of home value (B25075) and cash rent (B25063) are read from the summed brackets by linear interpolation.
The park units (Golden Gate Park, McLaren Park, Lincoln Park) get no figures.
Tiers:
Housing cost: median home value and rent ranked against the 38 residential neighbourhoods, weighted by owners and renters, thirds.
Getting to work: share of commuters who drive: mostly car 50%+, mixed 25-50%, mostly transit, walk or bike under 25%
  (New York's cuts: San Francisco also drives far less than its region).
Renters and owners: share of households that rent: mostly owners under 35%, a mix 35-60%, mostly renters over 60%.
Card-only rows (homes by building size, when built, language at home, ages, recent immigrants) as Chicago's.
"""
import json, os
from collections import Counter
from shapely.geometry import shape, Point

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
OUT = os.path.join(HERE, '..', '..', 'docs', 'sf', 'data', 'nb_profiles.json')

acs = json.load(open(os.path.join(RAW, 'acs_tracts.json')))
pts = json.load(open(os.path.join(RAW, 'tracts.json')))
cas = [(f['properties']['code'], f['properties']['name'], shape(f['geometry']).buffer(0))
       for f in json.load(open(os.path.join(HERE, 'tmp', 'neighbourhoods.geojson')))['features'] if 'park' not in f['properties']]

import acs_profile
from acs_profile import median, VALUE, RENT, v   # noqa: F401

sums = {}
placed = Counter()
for geoid, t in acs['tracts'].items():
    p = pts.get(geoid)
    if not p: continue
    pt = Point(p)
    ca = next((n for n, _, g in cas if g.contains(pt)), None)
    if ca is None: continue
    placed[ca] += 1
    s = sums.setdefault(ca, Counter())
    for k, v in t.items():
        if v: s[k] += v

# The extra tables: summed per community area the same way, then read by their Census labels.
MORE = acs   # one file for all nine tables
msums = {}
for geoid, t in MORE['tracts'].items():
    p = pts.get(geoid)
    if not p: continue
    ca = next((n for n, _, g in cas if g.contains(Point(p))), None)
    if ca is None: continue
    s = msums.setdefault(ca, Counter())
    for k, x in t.items():
        if x: s[k] += x
acs_profile.setup(MORE['labels'])

v = lambda s, tbl, n: s.get(f'{tbl}_E{n:03d}', 0)
data = {}
for n, name, _ in sorted(cas):
    data[str(n)] = acs_profile.figures(sums[n], msums.get(n, Counter()), name)
    d = data[str(n)]

def pct_rank(key):
    vals = sorted(d[key] for d in data.values() if d[key] is not None)
    return {k: (sum(x < d[key] for x in vals) + 0.5 * sum(x == d[key] for x in vals)) / len(vals)
            for k, d in data.items() if d[key] is not None}


rv, rr = pct_rank('value'), pct_rank('rent')
score = {k: (1 - d['renterPct'] / 100) * rv.get(k, rr.get(k, .5)) + (d['renterPct'] / 100) * rr.get(k, rv.get(k, .5)) for k, d in data.items()}
order = sorted(score, key=score.get)
# For region_profiles.py: the City's values, rents and the scores at its thirds, so a tract beyond the City is tiered
# against the same lines.
_sc = sorted(score.values())
json.dump({'values': sorted(d['value'] for d in data.values() if d['value']), 'rents': sorted(d['rent'] for d in data.values() if d['rent']),
           'cuts': [_sc[int(len(_sc) / 3)], _sc[int(2 * len(_sc) / 3)]]}, open(os.path.join(HERE, 'tmp', 'lens_cuts.json'), 'w'))
for i, k in enumerate(order):
    data[k]['cost'] = 'lower' if i < len(order) / 3 else 'middle' if i < 2 * len(order) / 3 else 'higher'
for d in data.values():
    d['commute'] = 'car' if d['carPct'] >= 50 else 'mixed' if d['carPct'] >= 25 else 'transit'
    d['tenure'] = 'owners' if d['renterPct'] < 35 else 'mix' if d['renterPct'] <= 60 else 'renters'

TL = os.path.join(RAW, 'transit_downtown.json')   # fetch_transit.py: minutes to each hub the viewer can pick
if os.path.exists(TL):
    tl = json.load(open(TL))['areas']
    for k, d in data.items():
        for hub in ('montgomery', 'missionbay'):
            m = (tl.get(k) or {}).get(hub)
            d[hub] = m
            d[hub + 'Band'] = None if m is None else 'under30' if m < 30 else '30to45' if m < 45 else '45to60' if m <= 60 else 'over60'

json.dump(data, open(OUT, 'w'), separators=(',', ':'))
for k in list(data)[:3]:
    print('example', k, data[k]['name'], data[k]['homes'], data[k]['built'], data[k]['lang'], data[k]['ages'], data[k]['recent'], data[k]['recentSince'])
print('languages ever in a top 3:', sorted({l[0] for d in data.values() for l in d.get('lang', [])[:3]}))
print('profiles:', len(data), 'neighbourhoods from', sum(placed.values()), 'tracts, ACS', acs['year'], ';',
      dict(Counter(d['cost'] for d in data.values())), dict(Counter(d['commute'] for d in data.values())),
      dict(Counter(d['tenure'] for d in data.values())), dict(Counter(d.get('montgomeryBand') for d in data.values())), dict(Counter(d.get('missionbayBand') for d in data.values())))
