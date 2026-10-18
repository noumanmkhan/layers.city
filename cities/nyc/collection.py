"""Build docs/nyc/data/collection.geojson (the card's Collection day row) from raw/places/dsny_frequencies.geojson
(fetch_places.py): DSNY Frequencies, one area per sanitation section and schedule, with the weekdays for trash
(freq_refuse), recycling (freq_recycling), compost (freq_organics) and bulk items (freq_bulk), as "Mon, Wed, Fri".

Output, the engine's "pickup" file (app contract section 3): one feature per area with `k` (its schedule code) and
the day lists as text (`r` trash, `y` recycling, `o` compost); top-level `sched` {k: [[date, [items]], ...]} with every
date to the end of next year, worked out from the weekdays. DSNY's holiday changes aren't in its data, so the card
says so. Curbside collection covers homes and most buildings; some large complexes have private carting."""
import json, os, re
from datetime import date, timedelta
from shapely.geometry import shape, mapping

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'raw', 'places', 'dsny_frequencies.geojson')
OUT = os.path.join(HERE, '..', '..', 'docs', 'nyc', 'data', 'collection.geojson')
WD = {'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 'FRI': 4, 'SAT': 5, 'SUN': 6}
NAME = {'MON': 'Mon', 'TUE': 'Tue', 'WED': 'Wed', 'THU': 'Thu', 'FRI': 'Fri', 'SAT': 'Sat', 'SUN': 'Sun'}


def days(s):
    return sorted({WD[d[:3].upper()] for d in re.split(r'[,\s/&]+', s or '') if d[:3].upper() in WD})


def text(ds):
    inv = {v: k for k, v in WD.items()}
    return ', '.join(NAME[inv[d]] for d in ds)


def rnd(o):
    return [rnd(x) for x in o] if isinstance(o, (list, tuple)) and o and isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]


today = date.today()
start, end = date(today.year, 1, 1), date(today.year + 1, 12, 31)
sched, out = {}, []
for f in json.load(open(SRC))['features']:
    p = f['properties']
    if not f.get('geometry'): continue
    r, y, o = days(p.get('freq_refuse')), days(p.get('freq_recycling')), days(p.get('freq_organics'))
    if not (r or y): continue
    k = '%s|%s|%s' % (text(r), text(y), text(o))
    if k not in sched:
        dates, d = [], start
        while d <= end:
            items = [n for n, ds in (('trash', r), ('recycling', y), ('compost', o)) if d.weekday() in ds]
            if items: dates.append([d.isoformat(), items])
            d += timedelta(days=1)
        sched[k] = dates
    g = shape(f['geometry']).buffer(0).simplify(0.00003, preserve_topology=True)
    if g.is_empty: continue
    pr = {'k': k, 'r': text(r), 'y': text(y)}
    if o: pr['o'] = text(o)
    out.append({'type': 'Feature', 'properties': pr, 'geometry': {'type': g.geom_type, 'coordinates': rnd(mapping(g)['coordinates'])}})
json.dump({'type': 'FeatureCollection', 'kind': 'pickup', 'year': today.year, 'asof': today.isoformat(), 'sched': sched, 'features': out},
          open(OUT, 'w'), separators=(',', ':'))
print('collection:', len(out), 'areas,', len(sched), 'schedules,', sum(1 for f in out if 'o' in f['properties']), 'with compost ·',
      round(os.path.getsize(OUT) / 1024), 'KB')
