"""Build docs/dallas/data/collection.geojson (the card's Collection day row) from raw/city/ (fetch_more.py).

Dallas Sanitation collects garbage and recycling once a week, on the same day, from houses on City routes
(days_of_service.geojson: one area per weekday and sanitation district), and brush and bulky trash once a month,
in the week of the month each brush route is assigned (crm_brush_routes.geojson, WEEK 1-4).
Output, the engine's "pickup" file (app contract section 3): one feature per piece of a day-of-service area and a
brush route, with `k` (the weekday) and `bw` (the brush week, when the route has one); top-level `sched`
{k: [[date, ["garbage", "recycling"]], ...]} with every weekly date to the end of next year, `year`, `asof`.
The weekly dates are worked out from the day; the City's holiday changes aren't in its data, so the card says so.
"""
import json, os
from shapely.ops import unary_union
from datetime import date, timedelta
from shapely.geometry import shape, mapping

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'city')
OUT = os.path.join(HERE, '..', '..', 'docs', 'dallas', 'data', 'collection.geojson')
DAYS = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY']
load = lambda n: json.load(open(os.path.join(RAW, n)))['features']


def rnd(o):
    return [rnd(x) for x in o] if isinstance(o, (list, tuple)) and o and isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]


today = date.today()
start, end = date(today.year, 1, 1), date(today.year + 1, 12, 31)
sched = {}
for i, d in enumerate(DAYS):
    first = start + timedelta(days=(i - start.weekday()) % 7)
    sched[d.lower()] = [[(first + timedelta(weeks=w)).isoformat(), ['garbage', 'recycling']]
                        for w in range(0, 60 * 2) if first + timedelta(weeks=w) <= end]

brush = [(shape(f['geometry']).buffer(0), int(f['properties']['WEEK'])) for f in load('crm_brush_routes.geojson')
         if f.get('geometry') and int(f['properties'].get('WEEK') or 0) in (1, 2, 3, 4)]
feats = []
for f in load('days_of_service.geojson'):
    day = (f['properties'].get('DOS') or '').strip().upper()
    if day not in DAYS or not f.get('geometry'): continue
    g = shape(f['geometry']).buffer(0)
    pieces = [(g.intersection(b), w) for b, w in brush if g.intersects(b)]
    covered = None
    for pg, w in pieces:
        pg = pg.buffer(0)
        if pg.is_empty or pg.area < 1e-7: continue
        covered = pg if covered is None else covered.union(pg)
        feats.append((pg, {'k': day.lower(), 'bw': w}))
    left = g if covered is None else g.difference(covered)
    if not left.is_empty and left.area > 1e-6:
        feats.append((left, {'k': day.lower()}))
out = []
for g, p in feats:
    g = g.simplify(0.00003, preserve_topology=True)
    if g.is_empty or g.geom_type not in ('Polygon', 'MultiPolygon'):
        g = g.buffer(0)
        if g.is_empty: continue
    m = mapping(g)
    if m['type'] == 'GeometryCollection':
        polys = [x for x in g.geoms if x.geom_type in ('Polygon', 'MultiPolygon')]
        if not polys: continue
        m = mapping(unary_union(polys))
    out.append({'type': 'Feature', 'properties': p, 'geometry': {'type': m['type'], 'coordinates': rnd(m['coordinates'])}})
json.dump({'type': 'FeatureCollection', 'kind': 'pickup', 'year': today.year, 'asof': today.isoformat(),
           'sched': sched, 'features': out}, open(OUT, 'w'), separators=(',', ':'))
print('collection:', len(out), 'areas,', sum(1 for f in out if 'bw' in f['properties']), 'with a brush week,',
      round(os.path.getsize(OUT) / 1024), 'KB')
