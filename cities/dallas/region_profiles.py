"""The ZIP lens and the card's Living here beyond the City of Dallas, for the rest of the nine counties.
Inputs: raw/region/zctas.geojson and acs_zcta.json (fetch_region.py), docs/dallas/data/base.geojson (each ZIP's town)
and zip_profiles.json (the City's ZIPs). Outputs: docs/dallas/data/region_zips.geojson ({code "z<ZIP>", name}) and
region_zip_profiles.json, read by the engine through city.json lens.region.

A ZIP is kept when its inside point is in one of the counties' towns or unincorporated areas beyond the City; its
outline is cut where it reaches into Dallas (inside the City the card uses the City's own ZIP units), but its figures
describe the whole ZIP, as Dallas's own do. Each profile has the same ACS fields as a Dallas ZIP's
(engine/acs_profile.py), plus region: 1 and muni. Tiers use the City's own lines, so a ZIP in Plano reads as a Dallas
ZIP would:
- Housing cost: the ZIP's median home value and rent placed among Dallas's ZIPs (percentile), weighted by owners and
  renters as in profiles.py, then compared with the scores at the City's thirds.
- Getting to work (Dallas's cuts: over 80% / 65-80% / under 65% drive) and renters and owners: the same fixed lines.
ZIPs with fewer than 200 people, or no households, get no profile."""
import json, os, sys
from collections import Counter
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'engine'))
import acs_profile   # engine/acs_profile.py

RG = os.path.join(HERE, 'raw', 'region')
DATA = os.path.join(HERE, '..', '..', 'docs', 'dallas', 'data')
if not os.path.exists(os.path.join(RG, 'acs_zcta.json')):
    raise SystemExit('region_profiles: no raw/region/acs_zcta.json yet (fetch_region.py); skipped')
acs = json.load(open(os.path.join(RG, 'acs_zcta.json')))
acs_profile.setup(acs['labels'] or json.load(open(os.path.join(HERE, 'raw', 'acs_zcta.json')))['labels'])

city = json.load(open(os.path.join(DATA, 'zip_profiles.json')))
tv = sorted(d['value'] for d in city.values() if d.get('value'))
trn = sorted(d['rent'] for d in city.values() if d.get('rent'))
pct = lambda vals, x: (sum(v < x for v in vals) + 0.5 * sum(v == x for v in vals)) / len(vals)
score = lambda d: (1 - d['renterPct'] / 100) * (pct(tv, d['value']) if d.get('value') else pct(trn, d['rent'])) + \
                  (d['renterPct'] / 100) * (pct(trn, d['rent']) if d.get('rent') else pct(tv, d['value']))
tscore = sorted(score(d) for d in city.values() if (d.get('value') or d.get('rent')) and d.get('renterPct') is not None)
cut1, cut2 = tscore[len(tscore) // 3], tscore[2 * len(tscore) // 3]

base = [f for f in json.load(open(os.path.join(DATA, 'base.geojson')))['features'] if f['geometry']]
CITY = unary_union([shape(f['geometry']).buffer(0) for f in base if f['properties']['kind'] == 'city']).buffer(0)
CITYP = prep(CITY)
munis = [(f['properties']['name'], prep(shape(f['geometry']).buffer(0))) for f in base if f['properties']['kind'] == 'neighbour']
r5 = lambda c: [r5(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 5), round(c[1], 5)]
units, data = [], {}
for f in json.load(open(os.path.join(RG, 'zctas.geojson')))['features']:
    z = f['properties']['ZCTA5CE20']
    g = shape(f['geometry']).buffer(0)
    pt = g.representative_point()
    if CITYP.contains(pt): continue
    muni = next((n for n, m in munis if m.contains(pt)), None)
    if not muni: continue
    g = g.difference(CITY).buffer(0)
    if g.is_empty: continue
    code = 'z' + z
    name = 'ZIP %s, %s' % (z, muni)
    m = mapping(g.simplify(0.0002, preserve_topology=True))
    units.append({'type': 'Feature', 'properties': {'code': code, 'name': 'ZIP ' + z}, 'geometry': {'type': m['type'], 'coordinates': r5(m['coordinates'])}})
    t = acs['zctas'].get(z)
    if not t: continue
    s = Counter({k: x for k, x in t.items() if x})
    if s['B01001_E001'] < 200 or not s['B25003_E001']: continue
    d = acs_profile.figures(s, s, name)
    d.update(region=1, muni=muni)
    if (d['value'] or d['rent']) and d['renterPct'] is not None:
        sc = score(d)
        d['cost'] = 'lower' if sc < cut1 else 'middle' if sc < cut2 else 'higher'
    if d['carPct'] is not None:
        d['commute'] = 'car' if d['carPct'] >= 80 else 'mixed' if d['carPct'] >= 65 else 'transit'
    if d['renterPct'] is not None:
        d['tenure'] = 'owners' if d['renterPct'] < 35 else 'mix' if d['renterPct'] <= 60 else 'renters'
    data[code] = {k: x for k, x in d.items() if x is not None}
json.dump({'type': 'FeatureCollection', 'features': units}, open(os.path.join(DATA, 'region_zips.geojson'), 'w'), separators=(',', ':'))
json.dump(data, open(os.path.join(DATA, 'region_zip_profiles.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('region ZIPs', len(units), '· profiles', len(data), '· cost', Counter(d.get('cost') for d in data.values()),
      '· commute', Counter(d.get('commute') for d in data.values()), '· tenure', Counter(d.get('tenure') for d in data.values()))
