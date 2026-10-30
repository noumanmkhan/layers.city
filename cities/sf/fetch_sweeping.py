"""Fetch San Francisco's street sweeping schedule into cities/sf/raw/sweeping.json, for the card's Street sweeping row
(sweeping.py builds the published tiles). Runs in GitHub Actions (fetch-sf.yml); monthly with the other refreshes.

DataSF yhqp-riqs, Public Works' Street Sweeping Schedule: one row per block side and sweeping day, with the street
(corridor), the block (limits), the side (blockside: North, South, East, West...), the weekday, the hours (fromhour,
tohour), which weeks of the month (week1 to week5), whether it's swept on holidays, and the block side's line.
Only those fields are kept, the lines rounded to about a metre."""
import json, os, sys, time, urllib.parse
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, RAW

KEEP = ('cnn', 'corridor', 'limits', 'cnnrightleft', 'blockside', 'fullname', 'weekday', 'fromhour', 'tohour',
        'week1', 'week2', 'week3', 'week4', 'week5', 'holidays', 'blocksweepid')
rows, off = [], 0
while True:
    q = urllib.parse.urlencode({'$limit': 20000, '$offset': off, '$order': ':id'})
    d = json.loads(get('https://data.sfgov.org/resource/yhqp-riqs.json?' + q, tries=3))
    if off == 0 and d: print('fields:', sorted(d[0]))
    for r in d:
        g = r.get('line') or r.get('the_geom') or r.get('geometry')
        if not g or not g.get('coordinates'): continue
        cs = g['coordinates']
        if g.get('type') == 'MultiLineString': cs = [c for part in cs for c in part]
        row = {k: r.get(k) for k in KEEP if r.get(k) is not None}
        row['xy'] = [[round(x, 5), round(y, 5)] for x, y in cs]
        rows.append(row)
    off += len(d)
    print('rows so far', len(rows), flush=True)
    if len(d) < 20000: break
if len(rows) < 10000: raise SystemExit(f'only {len(rows)} rows: not saved')
json.dump({'source': 'DataSF yhqp-riqs (Street Sweeping Schedule)', 'fetched': time.strftime('%Y-%m-%d'), 'rows': rows},
          open(os.path.join(RAW, 'sweeping.json'), 'w'), separators=(',', ':'))
print(len(rows), 'rows ·', Counter(r.get('weekday') for r in rows).most_common(8), '·', Counter(r.get('blockside') for r in rows).most_common(10))
print('sample', {k: v for k, v in rows[0].items() if k != 'xy'})
print('size', os.path.getsize(os.path.join(RAW, 'sweeping.json')))
