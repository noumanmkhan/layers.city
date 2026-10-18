"""Fetch street closures caused by transit construction from NYC DOT's Street Closures due to Construction
Activities by Block (NYC Open Data i6b5-j7bu, updated weekly) into raw/closures/permits.json, in the common shape
engine/closures.py reads. Run daily from GitHub Actions (*Fetch transit closures*); the sandbox can't reach the portal.

Kept: closures whose purpose is "RAPID TRANSIT CONSTRUCT/ ALTERATION" (the MTA's and its contractors' street work,
"-PROT" included), in force now or starting within the next week. Each is a closed block with its own line. The
dataset names no permit holder and no hours, so those rows stay empty. engine/closures.py then says which project
each belongs to (the Second Avenue Subway within closures.near metres, else "Other MTA work").
"""
import json, os, re, urllib.parse, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
API = 'https://data.cityofnewyork.us/resource/i6b5-j7bu.json'
TZ = ZoneInfo('America/New_York')
OUT = os.path.join(HERE, 'raw', 'closures'); os.makedirs(OUT, exist_ok=True)
now = datetime.now(TZ)
today, week = now.date(), (now + timedelta(days=8)).date()
where = (f"upper(purpose) like 'RAPID TRANSIT%' AND work_end_date >= '{today}T00:00:00' AND work_start_date <= '{week}T00:00:00'")
url = API + '?' + urllib.parse.urlencode({'$where': where, '$limit': 5000})
rows = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'city-layers-pipeline (layers.city)'}), timeout=180))

ABBR = {'STREET': 'St', 'AVENUE': 'Ave', 'ROAD': 'Rd', 'BOULEVARD': 'Blvd', 'PLACE': 'Pl', 'DRIVE': 'Dr', 'PARKWAY': 'Pkwy', 'EAST': 'E', 'WEST': 'W',
        'NORTH': 'N', 'SOUTH': 'S', 'LANE': 'Ln', 'TERRACE': 'Ter', 'EXPRESSWAY': 'Expy', 'HIGHWAY': 'Hwy'}


def street(s):
    w = re.sub(r'\s+', ' ', (s or '').strip()).split(' ')
    out = []
    for i, x in enumerate(w):
        if x in ABBR and not (i == 0 and x in ('EAST', 'WEST', 'NORTH', 'SOUTH') and len(w) == 1): out.append(ABBR[x])
        elif x.isdigit(): out.append(x + ('th' if 10 <= int(x) % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(int(x) % 10, 'th')))
        else: out.append(x.capitalize())
    return ' '.join(out)


permits = []
for r in rows:
    g = r.get('the_geom') or {}
    lines = g.get('coordinates') if g.get('type') == 'MultiLineString' else [g.get('coordinates')] if g.get('type') == 'LineString' else []
    for coords in lines:
        if not coords or len(coords) < 2: continue
        permits.append({'street': street(r.get('onstreetname')), 'extent': f"{street(r.get('fromstreetname'))} to {street(r.get('tostreetname'))}",
                        'kind': 'closed', 'start': (r.get('work_start_date') or '')[:10], 'end': (r.get('work_end_date') or '')[:10],
                        'coords': [[round(x, 6), round(y, 6)] for x, y in coords], 'both': True,
                        'desc': 'Street closed for rapid transit construction (NYC DOT permit).'})
json.dump({'fetched': str(today), 'source': API, 'permits': permits}, open(os.path.join(OUT, 'permits.json'), 'w'), indent=0)
print('nyc closures:', len(rows), 'rows ->', len(permits), 'segments;', sorted({p['street'] for p in permits})[:40])


# ---------- Special events: NYC Permitted Event Information (tvpp-9vvx) -> raw/closures/events.json ----------
# Kept: events whose permit closes the street (Full Street Closure, Sidewalk and Street Closure), not ended, starting
# within 15 days; park sports permits never close streets. The permits locate their closures only as text, chunks of
# "<STREET> between <STREET> and <STREET>" (or "<STREET> - <STREET> to <STREET>"), so each chunk is placed on NYC DOT's
# street centerline (inkn-q76z): the stretch of the first street between where it meets the other two. Only the
# streets the day's events name are fetched from the centerline. A chunk that can't be placed is left out and printed.
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import linemerge, substring

EV_API, CL_API = 'https://data.cityofnewyork.us/resource/tvpp-9vvx.json', 'https://data.cityofnewyork.us/resource/inkn-q76z.json'
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


def chunks(loc):
    out = []
    for c in re.split(r',\s+', loc or ''):
        c = c.strip()
        m = re.match(r'^(.+?) between (.+?) and (.+?)$', c) or re.match(r'^(.+?) - (.+?) to (.+?)(?::.*)?$', c)
        if m and not re.match(r'^\d+[- ]', m.group(1)): out.append(tuple(x.strip() for x in m.groups()))
    return out


now_l = datetime.now(TZ)
ev_where = ("street_closure_type in('Full Street Closure','Sidewalk and Street Closure') "
            f"AND end_date_time >= '{now_l:%Y-%m-%dT00:00:00}' AND start_date_time <= '{now_l + timedelta(days=15):%Y-%m-%dT23:59:59}'")
evs = json.load(urllib.request.urlopen(urllib.request.Request(EV_API + '?' + urllib.parse.urlencode({'$where': ev_where, '$limit': 5000}),
                                                             headers={'User-Agent': 'city-layers-pipeline (layers.city)'}), timeout=180))
def core(n):
    """The bare name the centerline keeps in street_name: no direction or type ("W 51 ST" -> "51", "AVE N" -> "N")."""
    w = n.split()
    if len(w) > 1 and w[0] in DIRS.values(): w = w[1:]
    if len(w) > 1 and w[-1] in DIRS.values(): w = w[:-1]
    if len(w) > 1 and w[-1] in TYPES.values(): w = w[:-1]
    if len(w) > 1 and w[0] == 'AVE': w = w[1:]
    return ' '.join(w)


want = {}
for e in evs:
    b = BORO.get(e.get('event_borough'))
    for on, a, z in chunks(e.get('event_location')):
        for n in (on, a, z): want.setdefault(b, set()).add(core(norm(n)))
lines = {}   # (boro, normalised full name) -> [LineString]
for names in [set().union(*want.values()) if want else set()]:
    names = sorted(n for n in names if n)
    for i in range(0, len(names), 50):
        q = "street_name in(%s)" % ','.join("'" + n.replace("'", "''") + "'" for n in names[i:i + 50])   # every borough: routes cross them
        got = json.load(urllib.request.urlopen(urllib.request.Request(CL_API + '?' + urllib.parse.urlencode({'$select': 'full_street_name,boroughcode,the_geom', '$where': q, '$limit': 50000}),
                                                                      headers={'User-Agent': 'city-layers-pipeline (layers.city)'}), timeout=300))
        for r in got:
            g = r.get('the_geom') or {}
            for part in (g.get('coordinates') or []) if g.get('type') == 'MultiLineString' else [g.get('coordinates')] if g.get('type') == 'LineString' else []:
                if part and len(part) > 1: lines.setdefault((r.get('boroughcode'), norm(r.get('full_street_name'))), []).append(LineString(part))
print('centerline:', sum(len(v) for v in lines.values()), 'segments on', len(lines), 'streets; sample names', sorted(k[1] for k in lines)[:12])


def meet(b, s1, s2):
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


def stretch(b, on, a, z):
    on_n, a_n, z_n = norm(on), norm(a), norm(z)
    for bb in [b] + [x for x in BORO.values() if x != b]:     # the permit's borough first, then the rest
        if not lines.get((bb, on_n)): continue
        pa, pz = meet(bb, on_n, a_n), meet(bb, on_n, z_n)
        if pa is None or pz is None: continue
        c = path(lines[(bb, on_n)], pa, pz)
        if not c: continue
        L = LineString(c)
        if L.length * 111000 < 10 or L.length * 111000 > 8000: continue
        return [[round(x, 6), round(y, 6)] for x, y in c], None
    if not any(lines.get((bb, on_n)) for bb in BORO.values()): return None, 'no centerline for ' + on_n
    return None, 'no stretch between %s and %s' % (a_n, z_n)


ev_permits, misses = [], []
for e in evs:
    b = BORO.get(e.get('event_borough'))
    name = re.sub(r'\s+', ' ', (e.get('event_name') or 'Street event')).strip()
    kind = 'closed'
    seen = set()
    for on, a, z in chunks(e.get('event_location')):
        key = (norm(on), frozenset((norm(a), norm(z))))
        if key in seen: continue
        seen.add(key)
        coords, why = stretch(b, on, a, z)
        if not coords: misses.append('%s | %s between %s and %s | %s' % (name, on, a, z, why)); continue
        ev_permits.append({'id': '%s-%d' % (e.get('event_id'), len(seen)), 'street': street(on),
                           'extent': '%s to %s' % (street(a), street(z)), 'kind': kind, 'both': True,
                           'start': (e.get('start_date_time') or '')[:16], 'end': (e.get('end_date_time') or '')[:16],
                           'who': name, 'desc': 'Street closed for the %s: %s.' % (name, (e.get('event_type') or 'street event').lower()), 'coords': coords})
json.dump({'fetched': str(today), 'source': EV_API, 'permits': ev_permits}, open(os.path.join(OUT, 'events.json'), 'w'), indent=0)
print('nyc events:', len(evs), 'permits ->', len(ev_permits), 'closures placed;', len(misses), 'chunks not placed')
for m in misses[:40]: print('   not placed:', m)
