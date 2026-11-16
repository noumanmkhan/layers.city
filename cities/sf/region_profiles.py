"""The neighborhood lens and the card's Living here beyond San Francisco, by census tract, for the other eight Bay
Area counties. Inputs: raw/region/acs_tracts.json and tracts.geojson (fetch_region.py), raw/acs_tracts.json (for the
labels, if the region file lacks them), docs/sf/data/base.geojson (each tract's city or town) and tmp/lens_cuts.json
(profiles.py). Outputs: docs/sf/data/bay_tracts.geojson ({code "tr<GEOID>", name}) and bay_tract_profiles.json, read
by the engine through city.json lens.region.

Each profile has the same ACS fields as a San Francisco neighborhood's (engine/acs_profile.py), plus region: 1 and muni. Tiers
use the City's own lines so a tract reads as a San Francisco neighborhood would:
- Housing cost: the tract's median home value and rent placed among San Francisco's neighborhoods (percentile),
  weighted by owners and renters as in profiles.py, then compared with the scores at the City's thirds.
- Getting to work and renters and owners: the same fixed lines.
Tracts with fewer than 200 people, or no households, get no profile (ACS margins are wide there)."""
import json, os, re
from collections import Counter
from shapely.geometry import shape, mapping
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, os.path.join(HERE, '..', '..', 'engine'))
import acs_profile   # engine/acs_profile.py
RG = os.path.join(HERE, 'raw', 'region')
DATA = os.path.join(HERE, '..', '..', 'docs', 'sf', 'data')
if not os.path.exists(os.path.join(RG, 'acs_tracts.json')):
    raise SystemExit('region_profiles: no raw/region/acs_tracts.json yet (fetch_region.py); skipped')
acs = json.load(open(os.path.join(RG, 'acs_tracts.json')))
acs_profile.setup(acs['labels'] or json.load(open(os.path.join(HERE, 'raw', 'acs_tracts.json')))['labels'])
CUTS = json.load(open(os.path.join(HERE, 'tmp', 'lens_cuts.json')))
munis = [(f['properties']['name'], prep(shape(f['geometry']).buffer(0))) for f in json.load(open(os.path.join(DATA, 'base.geojson')))['features']
         if f['properties']['kind'] == 'neighbour']
pct = lambda x, vals: (sum(y < x for y in vals) + 0.5 * sum(y == x for y in vals)) / len(vals)
r5 = lambda c: [r5(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 5), round(c[1], 5)]
units, data = [], {}
for f in json.load(open(os.path.join(RG, 'tracts.geojson')))['features']:
    gid = f['properties']['GEOID']
    g = shape(f['geometry']).buffer(0)
    if g.is_empty: continue
    pt = g.representative_point()
    muni = next((n for n, m in munis if m.contains(pt)), None)
    code = 'tr' + gid
    label = 'Census tract %d' % int(gid[5:9]) if gid[-2:] == '00' else 'Census tract %d.%s' % (int(gid[5:9]), gid[9:])
    name = label + (', ' + muni if muni else '')
    m = mapping(g.simplify(0.0001, preserve_topology=True))
    units.append({'type': 'Feature', 'properties': {'code': code, 'name': name}, 'geometry': {'type': m['type'], 'coordinates': r5(m['coordinates'])}})
    t = acs['tracts'].get(gid)
    if not t: continue
    s = Counter({k: x for k, x in t.items() if x})
    if s['B01001_E001'] < 200 or not s['B25003_E001']: continue
    d = acs_profile.figures(s, s, name)
    d.update(region=1, muni=muni)
    if d['value'] or d['rent']:
        rp = (d['renterPct'] or 0) / 100
        sc = (1 - rp) * (pct(d['value'], CUTS['values']) if d['value'] else pct(d['rent'], CUTS['rents'])) + \
             rp * (pct(d['rent'], CUTS['rents']) if d['rent'] else pct(d['value'], CUTS['values']))
        d['cost'] = 'lower' if sc < CUTS['cuts'][0] else 'middle' if sc < CUTS['cuts'][1] else 'higher'
    if d['carPct'] is not None:
        d['commute'] = 'car' if d['carPct'] >= 50 else 'mixed' if d['carPct'] >= 25 else 'transit'
    if d['renterPct'] is not None:
        d['tenure'] = 'owners' if d['renterPct'] < 35 else 'mix' if d['renterPct'] <= 60 else 'renters'
    data[code] = d
json.dump({'type': 'FeatureCollection', 'features': units}, open(os.path.join(DATA, 'bay_tracts.geojson'), 'w'), separators=(',', ':'))
json.dump(data, open(os.path.join(DATA, 'bay_tract_profiles.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('bay tracts', len(units), '· profiles', len(data), '· cost', Counter(d.get('cost') for d in data.values()),
      '· commute', Counter(d.get('commute') for d in data.values()), '· tenure', Counter(d.get('tenure') for d in data.values()))
