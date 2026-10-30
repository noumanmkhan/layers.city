"""Build the card's Address row data from raw/addresses.json (fetch_addresses.py): docs/sf/data/addresses/<i>_<j>.json,
one file per square of about 450 m (card.address.cell degrees), like the street sweeping squares.

San Francisco has no citywide address grid: every street counts up from its own start, about 100 a block. So for
each street this works out, from the City's own address points, where its numbers start (the cross street nearest
its lowest numbers) and which way they rise (the compass direction from its lowest numbers to its highest), and
keeps its address points thinned to about one per 30 m. Each square:
  {"s": [[street, starts at, rises toward, lowest hundred], ...], "p": [[street index, lon, lat, number], ...]}"""
import json, math, os, re
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'docs', 'sf', 'data', 'addresses')
CELL = json.load(open(os.path.join(HERE, 'city.json')))['card']['address']['cell']
rows = json.load(open(os.path.join(HERE, 'raw', 'addresses.json')))['rows']
KEEP = {'SF', 'UN', 'US', 'II', 'III', 'IV'}
def tidy(s):
    s = re.sub(r'\b0(\d)(ST|ND|RD|TH)\b', r'\1\2', s)   # the City writes 3rd St as "03RD ST"
    s = ' '.join(w if w in KEEP else (w[:1] + w[1:].lower()) for w in s.split())
    s = re.sub(r'\b(\d+)(St|Nd|Rd|Th)\b', lambda m: m.group(1) + m.group(2).lower(), s)
    s = re.sub(r'\bMc(\w)', lambda m: 'Mc' + m.group(1).upper(), s)
    return re.sub(r"\bO'(\w)", lambda m: "O'" + m.group(1).upper(), s)
KX, KY = 111320 * math.cos(math.radians(37.76)), 110574
by = defaultdict(list)
for st, n, x, y in rows:
    if n > 0: by[st].append((n, x, y))
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
for name in ('Castro St', 'Mission St', 'Valencia St', 'Geary Blvd', '21st Ave', 'Lombard St', 'Market St', '24th St', 'Irving St', 'Divisadero St', 'Folsom St', '3rd St', 'Van Ness Ave', 'Columbus Ave', 'Taraval St'):
    print('  ', next((s for s in streets if s[0] == name), name))
