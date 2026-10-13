"""Build docs/chicago/data/sweeping.geojson (the card's Street sweeping row) from raw/sweeping/
(fetch_sweeping.py).

Output, the engine's "pickup" file (app contract section 3): one feature per ward section with `k`
("0101"), `w` (ward) and `s` (section); top-level `sched` {k: [[date, ["sweep"]], ...]} with every
sweeping date of the year, `year`, `asof` (the fetch). Geometry simplified to about 3 m.
"""
import json, os
from datetime import date
from shapely.geometry import shape, mapping

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'sweeping')
OUT = os.path.join(HERE, '..', '..', 'docs', 'chicago', 'data', 'sweeping.geojson')
if not os.path.exists(os.path.join(RAW, 'zones.geojson')):
    raise SystemExit('no raw/sweeping yet: run fetch_sweeping.py in Actions')

meta = json.load(open(os.path.join(RAW, 'meta.json')))
year = int(meta['year'])
sched = {}
for r in json.load(open(os.path.join(RAW, 'schedule.json'))):
    k, m = r['ward_section_concatenated'].strip(), int(r['month_number'])
    for d in (r.get('dates') or '').split(','):
        d = d.strip()
        if d.isdigit(): sched.setdefault(k, set()).add(date(year, m, int(d)).isoformat())
sched = {k: [[d, ['sweep']] for d in sorted(v)] for k, v in sched.items()}

def rnd(o):
    return [rnd(x) for x in o] if isinstance(o, (list, tuple)) and o and isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]

feats, missing = [], []
for f in json.load(open(os.path.join(RAW, 'zones.geojson')))['features']:
    p = f['properties']; k = (p.get('ward_section') or '').strip()
    if k not in sched: missing.append(k); continue
    g = shape(f['geometry']).buffer(0).simplify(0.00003, preserve_topology=True)
    if g.is_empty: continue
    m = mapping(g)
    feats.append({'type': 'Feature', 'properties': {'k': k, 'w': str(int(p['ward'])), 's': str(int(p['section']))},
                  'geometry': {'type': m['type'], 'coordinates': rnd(m['coordinates'])}})
if missing: print('zones with no schedule (left out):', missing)
json.dump({'type': 'FeatureCollection', 'kind': 'pickup', 'year': year, 'asof': meta['fetched'][:10],
           'sched': sched, 'features': feats}, open(OUT, 'w'), separators=(',', ':'))
print('sweeping:', len(feats), 'zones,', sum(len(v) for v in sched.values()), 'dates,', round(os.path.getsize(OUT) / 1024), 'KB')
