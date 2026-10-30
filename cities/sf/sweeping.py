"""Build the card's Street sweeping row data from raw/sweeping.json (fetch_sweeping.py): docs/sf/data/sweeping/<i>_<j>.json,
one file per square of about 450 m (card.sweep.cell degrees), so the card fetches only the square around a spot.

Each file: {"s": [street names], "l": [block limits], "f": [[street, limits, side, [[weekday 0-6 (Monday 0), from
hour, to hour, weeks bitmask (1 = 1st week of the month ... 16 = 5th)], ...], [lon, lat, lon, lat, ...]], ...]}.
A block side is in every square its line comes within about 40 m of, so one square is enough for the card. The
schedule's "Holiday" rows (sweeping that runs on holidays) and rows with no side are left out."""
import json, math, os, re
from collections import defaultdict
from shapely.geometry import LineString

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'docs', 'sf', 'data', 'sweeping')
CFG = json.load(open(os.path.join(HERE, 'city.json')))['card']['sweep']
CELL = CFG['cell']
rows = json.load(open(os.path.join(HERE, 'raw', 'sweeping.json')))['rows']
DAY = {'Mon': 0, 'Tues': 1, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Thurs': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
SIDE = {'North': 'North side', 'South': 'South side', 'East': 'East side', 'West': 'West side', 'NorthEast': 'Northeast side',
        'NorthWest': 'Northwest side', 'SouthEast': 'Southeast side', 'SouthWest': 'Southwest side'}
tidy = lambda s: re.sub(r'\s+', ' ', re.sub(r'\b0(\d)(st|nd|rd|th)\b', r'\1\2', s or '')).strip()   # "03rd Ave" -> "3rd Ave"

sides = defaultdict(lambda: {'sch': set()})
for r in rows:
    if r.get('weekday') not in DAY or r.get('blockside') not in SIDE: continue
    k = (r.get('cnn'), r.get('cnnrightleft'), r['blockside'])
    v = sides[k]
    v.update(street=tidy(r.get('corridor')), limits=tidy((r.get('limits') or '').replace('  -  ', ' – ')), side=SIDE[r['blockside']], xy=r['xy'])
    w = sum(1 << i for i in range(5) if r.get(f'week{i + 1}') == '1')
    if w: v['sch'].add((DAY[r['weekday']], int(r.get('fromhour') or 0), int(r.get('tohour') or 0), w))

streets, limits, si, li = [], [], {}, {}
tiles = defaultdict(list)
pad = 40 / 111000   # about 40 m in degrees of latitude (and a bit less than that in longitude): plenty for the card's reach
for (cnn, lr, bs), v in sides.items():
    if not v['sch'] or len(v['xy']) < 2: continue
    g = LineString(v['xy']).simplify(0.000015)
    flat = [round(c, 5) for p in g.coords for c in p]
    if v['street'] not in si: si[v['street']] = len(streets); streets.append(v['street'])
    if v['limits'] not in li: li[v['limits']] = len(limits); limits.append(v['limits'])
    f = [si[v['street']], li[v['limits']], v['side'], sorted(v['sch']), flat]
    x0, y0, x1, y1 = g.bounds
    for i in range(math.floor((x0 - pad * 1.3) / CELL), math.floor((x1 + pad * 1.3) / CELL) + 1):
        for j in range(math.floor((y0 - pad) / CELL), math.floor((y1 + pad) / CELL) + 1):
            tiles[(i, j)].append(f)

os.makedirs(OUT, exist_ok=True)
for fn in os.listdir(OUT): os.remove(os.path.join(OUT, fn))
sizes = []
for (i, j), fs in tiles.items():
    used_s = sorted({f[0] for f in fs}); used_l = sorted({f[1] for f in fs})
    ms, ml = {v: n for n, v in enumerate(used_s)}, {v: n for n, v in enumerate(used_l)}
    doc = {'s': [streets[k] for k in used_s], 'l': [limits[k] for k in used_l], 'f': [[ms[f[0]], ml[f[1]], f[2], f[3], f[4]] for f in fs]}
    p = os.path.join(OUT, f'{i}_{j}.json')
    json.dump(doc, open(p, 'w'), separators=(',', ':'), ensure_ascii=False)
    sizes.append(os.path.getsize(p))
sizes.sort()
print(f'sweeping: {len(sides)} block sides, {len(tiles)} squares, {sizes[0]}-{sizes[-1]} bytes (median {sizes[len(sizes) // 2]}), {sum(sizes) // 1024} KB in all')
