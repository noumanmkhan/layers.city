"""Build docs/toronto/data/collection.geojson (the card's Collection day row) from
raw/collection/ (fetch_collection.py).

Output, the engine's "pickup" file (app contract section 3): one feature per collection area with
`k` (the calendar, e.g. "Wednesday1"); top-level `sched` {k: [[date, [item, ...]], ...]} with every
pickup date of the year and what goes out that day (`green`, `garbage`, `recycling`, `yard`,
`tree`), `year`, `asof` (the fetch). Geometry simplified to about 3 m.
"""
import csv, json, os
from datetime import datetime
from shapely.geometry import shape, mapping

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'collection')
OUT = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'collection.geojson')
if not os.path.exists(os.path.join(RAW, 'areas.geojson')):
    raise SystemExit('no raw/collection yet: run fetch_collection.py in Actions')

meta = json.load(open(os.path.join(RAW, 'meta.json')))
FLAGS = [('GreenBin', 'green'), ('Garbage', 'garbage'), ('Recycling', 'recycling'), ('YardWaste', 'yard'), ('ChristmasTree', 'tree')]
sched = {}
for r in csv.DictReader(open(os.path.join(RAW, 'schedule.csv'))):
    d = datetime.strptime(r['WeekStarting'].strip(), '%m/%d/%y').date().isoformat()
    items = [k for col, k in FLAGS if (r.get(col) or '').strip().upper() not in ('', '0', 'F')]
    if items: sched.setdefault(r['Calendar'].strip(), []).append([d, items])
for v in sched.values(): v.sort()

def rnd(o):
    return [rnd(x) for x in o] if isinstance(o, (list, tuple)) and o and isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]

feats, missing = [], set()
for f in json.load(open(os.path.join(RAW, 'areas.geojson')))['features']:
    k = f['properties']['AREA_NAME'].replace(' ', '')
    if k not in sched: missing.add(k); continue
    g = shape(f['geometry']).buffer(0).simplify(0.00003, preserve_topology=True)
    if g.is_empty: continue
    m = mapping(g)
    feats.append({'type': 'Feature', 'properties': {'k': k}, 'geometry': {'type': m['type'], 'coordinates': rnd(m['coordinates'])}})
if missing: print('areas with no calendar (left out):', sorted(missing))
json.dump({'type': 'FeatureCollection', 'kind': 'pickup', 'year': meta['year'], 'asof': meta['fetched'][:10],
           'sched': sched, 'features': feats}, open(OUT, 'w'), separators=(',', ':'))
print('collection:', len(feats), 'areas,', len(sched), 'calendars,', sum(len(v) for v in sched.values()), 'pickup days,',
      round(os.path.getsize(OUT) / 1024), 'KB')
