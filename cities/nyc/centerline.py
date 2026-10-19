"""Placing street text on NYC DOT's street centerline (NYC Open Data inkn-q76z): "<street> between <street> and
<street>" becomes the stretch of the first street between where it meets the other two. Shared by fetch_closures.py
(permitted events) and fetch_marathon.py (the marathon's closure notice).

Use: lines = fetch_lines(names) with the bare names core(norm(s)) of every street a run needs, then
stretch(lines, borough, on, a, z) -> (coords, None) or (None, why)."""
import json, re, urllib.parse, urllib.request
from shapely.geometry import LineString, MultiLineString

CL_API = 'https://data.cityofnewyork.us/resource/inkn-q76z.json'
UA = {'User-Agent': 'city-layers-pipeline (layers.city)'}
BORO = {'Manhattan': '1', 'Bronx': '2', 'Brooklyn': '3', 'Queens': '4', 'Staten Island': '5'}
DIRS = {'EAST': 'E', 'WEST': 'W', 'NORTH': 'N', 'SOUTH': 'S'}
TYPES = {'STREET': 'ST', 'STREETS': 'ST', 'AVENUE': 'AVE', 'AV': 'AVE', 'ROAD': 'RD', 'BOULEVARD': 'BLVD', 'PLACE': 'PL', 'DRIVE': 'DR',
         'PARKWAY': 'PKWY', 'TERRACE': 'TER', 'LANE': 'LN', 'COURT': 'CT', 'HIGHWAY': 'HWY', 'EXPRESSWAY': 'EXPWY', 'SQUARE': 'SQ', 'PLAZA': 'PLZ'}
ORDS = {'FIRST': '1', 'SECOND': '2', 'THIRD': '3', 'FOURTH': '4', 'FIFTH': '5', 'SIXTH': '6', 'SEVENTH': '7', 'EIGHTH': '8', 'NINTH': '9',
        'TENTH': '10', 'ELEVENTH': '11', 'TWELFTH': '12'}
ALIAS = {'CPW': 'CENTRAL PARK W', 'CPS': 'CENTRAL PARK S', 'FDR': 'FDR DR', 'CROSSBAY BLVD': 'CROSS BAY BLVD', 'AVE OF THE AMERICAS': '6 AVE',
         'W SIDE HWY': 'JOE DIMAGGIO HWY'}


def norm(s):
    """A street as the centerline's full_street_name spells it: "WEST   51 STREET" -> "W 51 ST", "AVENUE R" -> "AVE R",
    "SOUTH STREET" stays "SOUTH ST", "COURT STREET" stays "COURT ST"."""
    s = re.sub(r'[^A-Z0-9 &\-]', ' ', (s or '').upper())
    s = re.sub(r'\b(\d+)(ST|AVE|PL|RD|DR)\s*$', r'\1 \2', s.strip())      # "139ST" at the end -> 139 ST
    s = re.sub(r'\b(\d+)(ST|ND|RD|TH)\b', r'\1', s)                      # 88TH AVENUE -> 88 AVENUE
    w = s.split()
    if not w: return ''
    if len(w) > 2 and w[0] in DIRS: w[0] = DIRS[w[0]]                   # a direction before the name
    if len(w) > 2 and w[-1] in DIRS: w[-1] = DIRS[w[-1]]                # ... or after it (CENTRAL PARK WEST)
    if len(w) > 2 and w[-1] in DIRS.values() and w[-2] in TYPES: w[-2] = TYPES[w[-2]]
    if len(w) > 1 and w[-1] in TYPES: w[-1] = TYPES[w[-1]]              # the street type at the end
    if len(w) > 1 and w[0] in ('AVENUE', 'AV') : w[0] = 'AVE'           # AVENUE R
    if w[0] == 'SAINT' and len(w) > 1: w[0] = 'ST'
    w = [ORDS.get(x, x) if i + 1 < len(w) and w[i + 1] in TYPES.values() else x for i, x in enumerate(w)]
    s = ' '.join(w)
    return ALIAS.get(s, s)


def core(n):
    """The bare name the centerline keeps in street_name: no direction or type ("W 51 ST" -> "51", "AVE N" -> "N")."""
    w = n.split()
    if len(w) > 1 and w[0] in DIRS.values(): w = w[1:]
    if len(w) > 1 and w[-1] in DIRS.values(): w = w[:-1]
    if len(w) > 1 and w[-1] in TYPES.values(): w = w[:-1]
    if len(w) > 1 and w[0] == 'AVE': w = w[1:]
    return ' '.join(w)



def fetch_lines(names):
    """Centerline segments for these bare street names, in every borough: (boroughcode, normalised full name) -> [LineString]."""
    lines = {}
    names = sorted(n for n in names if n)
    for i in range(0, len(names), 50):
        q = "street_name in(%s)" % ','.join("'" + n.replace("'", "''") + "'" for n in names[i:i + 50])
        got = json.load(urllib.request.urlopen(urllib.request.Request(CL_API + '?' + urllib.parse.urlencode({'$select': 'full_street_name,boroughcode,the_geom', '$where': q, '$limit': 50000}),
                                                                      headers=UA), timeout=300))
        for r in got:
            g = r.get('the_geom') or {}
            for part in (g.get('coordinates') or []) if g.get('type') == 'MultiLineString' else [g.get('coordinates')] if g.get('type') == 'LineString' else []:
                if part and len(part) > 1: lines.setdefault((r.get('boroughcode'), norm(r.get('full_street_name'))), []).append(LineString(part))
    return lines


def meet(lines, b, s1, s2):
    """Where street s1 meets s2: the nearest pair of points between them, if within 25 m."""
    L1, L2 = lines.get((b, s1)), lines.get((b, s2))
    if not L1 or not L2: return None
    m1, m2 = MultiLineString(L1), MultiLineString(L2)
    from shapely.ops import nearest_points
    p, q = nearest_points(m1, m2)
    return p if p.distance(q) * 111000 < 25 else None


def path(segs, pa, pz):
    """The stretch along a street's segments from near pa to near pz: the shortest route over the segments, joined
    where their ends meet (within about 1 m), so a divided avenue or a street in many short pieces still works."""
    import heapq
    key = lambda c: (round(c[0], 5), round(c[1], 5))
    adj = {}
    for L in segs:
        c = list(L.coords)
        a, z = key(c[0]), key(c[-1])
        adj.setdefault(a, []).append((z, L.length, c)); adj.setdefault(z, []).append((a, L.length, c[::-1]))
    nodes = list(adj)
    near = lambda p: min(nodes, key=lambda n: (n[0] - p.x) ** 2 + (n[1] - p.y) ** 2)
    s0, s1 = near(pa), near(pz)
    if s0 == s1: return None
    dist, prev, q = {s0: 0}, {}, [(0, s0)]
    while q:
        d, n = heapq.heappop(q)
        if n == s1: break
        if d > dist.get(n, 1e9): continue
        for m, w, c in adj[n]:
            if d + w < dist.get(m, 1e9): dist[m] = d + w; prev[m] = (n, c); heapq.heappush(q, (d + w, m))
    if s1 not in prev: return None
    edges, n = [], s1
    while n != s0:
        p, c = prev[n]; edges.append(c); n = p
    edges.reverse()
    return edges[0] + [pt for e in edges[1:] for pt in e[1:]]


def stretch(lines, b, on, a, z):
    on_n, a_n, z_n = norm(on), norm(a), norm(z)
    for bb in [b] + [x for x in BORO.values() if x != b]:     # the permit's borough first, then the rest
        if not lines.get((bb, on_n)): continue
        pa, pz = meet(lines, bb, on_n, a_n), meet(lines, bb, on_n, z_n)
        if pa is None or pz is None: continue
        c = path(lines[(bb, on_n)], pa, pz)
        if not c: continue
        L = LineString(c)
        if L.length * 111000 < 10 or L.length * 111000 > 8000: continue
        return [[round(x, 6), round(y, 6)] for x, y in c], None
    if not any(lines.get((bb, on_n)) for bb in BORO.values()): return None, 'no centerline for ' + on_n
    return None, 'no stretch between %s and %s' % (a_n, z_n)

