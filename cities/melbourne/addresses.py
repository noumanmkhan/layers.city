"""Build the card's Address row data from raw/addresses.json (fetch_addresses.py, Vicmap Address):
docs/melbourne/data/addresses/<i>_<j>.json, one file per square of about 450 m (card.address.cell degrees).
San Francisco's method (cities/sf/addresses.py), with Victoria's street names.

Melbourne, like San Francisco, has no citywide address grid: every street counts up from its own start, about 100 a block. So for
each street this works out, from the City's own address points, where its numbers start (the cross street nearest
its lowest numbers) and which way they rise (the compass direction from its lowest numbers to its highest), and
keeps its address points thinned to about one per 30 m. Each square:
  {"s": [[street, starts at, rises toward, lowest hundred], ...], "p": [[street index, lon, lat, number], ...]}"""
import json, math, os, re
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'docs', 'melbourne', 'data', 'addresses')
CELL = json.load(open(os.path.join(HERE, 'city.json')))['card']['address']['cell']
rows = json.load(open(os.path.join(HERE, 'raw', 'addresses.json')))['rows']
SHORT = {'STREET': 'St', 'ROAD': 'Rd', 'AVENUE': 'Ave', 'PARADE': 'Pde', 'PLACE': 'Pl', 'LANE': 'La', 'DRIVE': 'Dr',
         'HIGHWAY': 'Hwy', 'BOULEVARD': 'Blvd', 'CRESCENT': 'Cres', 'TERRACE': 'Tce', 'SQUARE': 'Sq', 'ALLEY': 'Aly',
         'COURT': 'Ct', 'GROVE': 'Gr', 'CLOSE': 'Cl', 'WAY': 'Way', 'WALK': 'Walk', 'QUAY': 'Quay',
         'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W'}
def tidy(s):
    s = s.split('|')[0]
    """'COLLINS STREET' -> 'Collins St', 'ST KILDA ROAD' -> 'St Kilda Rd', the way the map's street names read."""
    w = s.split()
    out = [SHORT.get(x, x) if i > 0 and i >= len(w) - 2 else x for i, x in enumerate(w)]
    s = ' '.join(x if x in SHORT.values() else x[:1] + x[1:].lower() for x in out)
    s = re.sub(r'\bMc(\w)', lambda m: 'Mc' + m.group(1).upper(), s)
    return re.sub(r"\bO'(\w)", lambda m: "O'" + m.group(1).upper(), s)
KX, KY = 111320 * math.cos(math.radians(-37.81)), 110574
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep
CITYP = prep(unary_union([shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(OUT, '..', 'suburbs.geojson')))['features']]).buffer(0.002))
by0 = defaultdict(list)
for st, n, x, y in rows:   # the fetch's box reaches past the City (St Kilda, Fitzroy): only the City's own points
    if n > 0 and CITYP.contains(Point(x, y)): by0[st].append((n, x, y))
# Melbourne reuses street names across suburbs (an Elizabeth St in the CBD and another in Kensington): a name's points
# more than 250 m from the rest of its points are another street, numbered on its own. Keyed "name|k"; tidy() drops k.
by = {}
for st, pts in by0.items():
    cell = defaultdict(list)
    for i, (n, x, y) in enumerate(pts): cell[(int(x * 88000 // 250), int(y * 110574 // 250))].append(i)
    parent = list(range(len(pts)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for (cx, cy), ids in cell.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in cell.get((cx + dx, cy + dy), ()):
                    for i in ids:
                        if math.hypot((pts[i][1] - pts[j][1]) * 88000, (pts[i][2] - pts[j][2]) * 110574) < 250:
                            parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i, q in enumerate(pts): groups[find(i)].append(q)
    for k, g in enumerate(sorted(groups.values(), key=len, reverse=True)):
        by[f'{st}|{k}' if k else st] = g
grid = defaultdict(list)   # ~60 m cells -> [(street, x, y)], for finding cross streets
for st, pts in by.items():
    for n, x, y in pts: grid[(int(x * KX // 60), int(y * KY // 60))].append((st, x, y))
def near(x, y, r):
    gx, gy, k = int(x * KX // 60), int(y * KY // 60), int(r // 60) + 1
    for i in range(-k, k + 1):
        for j in range(-k, k + 1):
            for o, ox, oy in grid.get((gx + i, gy + j), ()):
                if math.hypot((ox - x) * KX, (oy - y) * KY) < r: yield o, ox, oy
def axis(pts):
    """A street's direction near a spot (degrees 0-180) from its address points there, by their principal axis."""
    if len(pts) < 3: return None
    mx, my = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    sxx = sum(((p[0] - mx) * KX) ** 2 for p in pts); syy = sum(((p[1] - my) * KY) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * KX * (p[1] - my) * KY for p in pts)
    return math.degrees(0.5 * math.atan2(2 * sxy, sxx - syy)) % 180
def cross_at(st, x, y):
    """The street crossing this one where its numbers start: of the other streets with address points within about
    70 m, the one with the most that runs across it (not alongside, like the next avenue over)."""
    here = [(ox, oy) for o, ox, oy in near(x, y, 160) if o == st]
    a = axis(here)
    c = Counter(o for o, _, _ in near(x, y, 70) if o != st)
    for o, _ in c.most_common():
        b = axis([(ox, oy) for oo, ox, oy in near(x, y, 160) if oo == o])
        if a is None or b is None or min(abs(a - b), 180 - abs(a - b)) > 40: return tidy(o)
    return ''
WORDS = ['north', 'northeast', 'east', 'southeast', 'south', 'southwest', 'west', 'northwest']
streets, tiles = [], defaultdict(list)
for st, pts in sorted(by.items()):
    if len(pts) < 4: continue
    pts.sort()
    k = max(1, len(pts) // 25)
    lo, hi = pts[:k], pts[-k:]
    lx, ly = sum(p[1] for p in lo) / k, sum(p[2] for p in lo) / k
    hx, hy = sum(p[1] for p in hi) / k, sum(p[2] for p in hi) / k
    dx, dy = (hx - lx) * KX, (hy - ly) * KY
    toward = WORDS[int(((math.degrees(math.atan2(dx, dy)) % 360) + 22.5) // 45) % 8] if math.hypot(dx, dy) > 150 else ''
    # [street, starts at, rises toward, its lowest hundred]: a street that carries on another's numbers (Geary Blvd
    # from Geary St at Van Ness) starts at its own lowest hundred, not at 1.
    si = len(streets); streets.append([tidy(st), cross_at(st, pts[0][1], pts[0][2]), toward, pts[0][0] // 100 * 100])
    thin = {}
    for n, x, y in pts:   # one point per ~30 m cell, the cell's middle number
        thin.setdefault((int(x * KX // 30), int(y * KY // 30)), []).append((n, x, y))
    for v in thin.values():
        v.sort(); n, x, y = v[len(v) // 2]
        tiles[(math.floor(x / CELL), math.floor(y / CELL))].append([si, round(x, 5), round(y, 5), n])
os.makedirs(OUT, exist_ok=True)
for fn in os.listdir(OUT): os.remove(os.path.join(OUT, fn))
sizes = []
for (i, j), ps in tiles.items():
    used = sorted({p[0] for p in ps}); m = {v: k for k, v in enumerate(used)}
    p = os.path.join(OUT, f'{i}_{j}.json')
    json.dump({'s': [streets[k] for k in used], 'p': [[m[q[0]]] + q[1:] for q in ps]}, open(p, 'w'), separators=(',', ':'), ensure_ascii=False)
    sizes.append(os.path.getsize(p))
sizes.sort()
print(f'addresses: {len(streets)} streets, {sum(len(v) for v in tiles.values())} points in {len(tiles)} squares, {sizes[0]}-{sizes[-1]} bytes, {sum(sizes) // 1024} KB')
for name in ('Collins St', 'Swanston St', 'Elizabeth St', 'Lygon St', 'St Kilda Rd', 'Flinders St', 'Queensberry St', 'Racecourse Rd'):
    print('  ', next((s for s in streets if s[0] == name), name))
