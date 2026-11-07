"""Fetch street closures caused by transit construction from CDOT's Transportation Department Permits
(Chicago Data Portal, Socrata pubx-yq2d, updated daily) into raw/closures/permits.json, in the common
shape engine/closures.py reads. Run daily from GitHub Actions (*Fetch transit closures*); the sandbox
can't reach the portal. Also writes raw/closures/events.json, the special-event closures for engine/events.py
and the Special events layer (see the section near the end).

Kept: open permits active now or within the next week whose application name, comments or detail name
a project in construction.json "closures.keywords" (Red Line Extension: "RLE"; Red and Purple
Modernization: "RPM"), matched as whole words, and whose street closure is Full, Partial or Curblane.
Sidewalk-only and unstated closures are left out (the map draws roads).

CDOT gives a point at the start of an address range plus the house numbers. Chicago's grid puts 800
numbers in a mile, counted from State St (east-west) and Madison St (north-south), so the far end of the
range is placed from the "to" number along the street's direction. A one-address range gets a short stub.
"""
import collections, json, math, os, re, urllib.parse, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
API = 'https://data.cityofchicago.org/resource/pubx-yq2d.json'
TZ = ZoneInfo('America/Chicago')
cfg = json.load(open(os.path.join(HERE, 'construction.json')))['closures']
WORDS = re.compile(r'\b(' + '|'.join(re.escape(k) for k in cfg['keywords']) + r')\b', re.I)
KIND = {'Full': 'closed', 'Partial': 'narrowed', 'Curblane': 'narrowed'}
OUT = os.path.join(HERE, 'raw', 'closures')
os.makedirs(OUT, exist_ok=True)

now = datetime.now(TZ)
today, week = now.date(), (now + timedelta(days=8)).date()
where = (f"applicationstatus = 'Open' AND applicationenddate >= '{today}T00:00:00' AND applicationstartdate <= '{week}T00:00:00' "
         "AND streetclosure in ('Full', 'Partial', 'Curblane') AND ("
         + ' OR '.join(f"upper({f}) like '%{k.upper()}%'" for f in ('applicationname', 'comments', 'detail') for k in cfg['keywords'])
         + ')')
url = API + '?' + urllib.parse.urlencode({'$where': where, '$limit': 5000})
req = urllib.request.Request(url, headers={'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)'})
rows = json.load(urllib.request.urlopen(req, timeout=180))

M_PER_NUM = 1609.344 / 800
KX = 111320 * math.cos(math.radians(41.85))


def far_end(lon, lat, direction, n_from, n_to):
    """Point n_to - n_from address numbers along the street, in its grid direction."""
    d = (n_to - n_from) * M_PER_NUM
    if not d:
        d = 30                                      # a single address: draw a short stub
    d = max(-2500, min(2500, d))
    dx, dy = {'N': (0, 1), 'S': (0, -1), 'E': (1, 0), 'W': (-1, 0)}.get(direction, (0, 0))
    if not (dx or dy):
        return None
    return [round(lon + dx * d / KX, 6), round(lat + dy * d / 110540, 6)]


def street_name(r):
    s = ' '.join(x for x in (r.get('direction'), (r.get('streetname') or '').title(), (r.get('suffix') or '').title()) if x)
    return re.sub(r'\b(\d+)(St|Nd|Rd|Th)\b', lambda m: m.group(1) + m.group(2).lower(), s)


out, skipped = [], 0
for r in rows:
    text = ' '.join(r.get(k) or '' for k in ('applicationname', 'comments', 'detail'))
    if not WORDS.search(text):
        continue                                    # "RLE" inside Harlem, Orleans, Charles...
    try:
        lon, lat = float(r['longitude']), float(r['latitude'])
        a, b = int(float(r.get('streetnumberfrom') or 0)), int(float(r.get('streetnumberto') or 0))
    except (KeyError, TypeError, ValueError):
        skipped += 1
        continue
    end = far_end(lon, lat, r.get('direction'), a, b or a)
    if not end:
        skipped += 1
        continue
    extent = f"{a}–{b} {street_name(r)}" if b and b != a else f"{a} {street_name(r)}"
    out.append({
        'id': f"{r.get('applicationnumber')}:{a}-{b}:{r.get('streetname')}",
        'street': street_name(r),
        'extent': extent,
        'kind': KIND[r['streetclosure']],
        'both': r['streetclosure'] == 'Full',
        'start': (r.get('applicationstartdate') or '')[:10], 'end': (r.get('applicationenddate') or '')[:10],
        'hours': None, 'days': None,
        'who': (r.get('primarycontactlast') or '').rstrip('*').strip(),
        'desc': re.sub(r'<[^>]+>|\s+', ' ', r.get('comments') or r.get('detail') or r.get('applicationname') or '').strip(),
        'project': r.get('applicationname'),
        'coords': [[round(lon, 6), round(lat, 6)], end],
    })

json.dump({'fetched': now.strftime('%Y-%m-%dT%H:%M'), 'source': API, 'permits': out},
          open(os.path.join(OUT, 'permits.json'), 'w'), indent=0)
print('Chicago:', len(rows), 'permits matched the query;', len(out), 'kept;', skipped, 'without a usable location')


# ---------- Special events -> raw/closures/events.json (engine/events.py, cities/chicago/events.json) ----------
# The same CDOT dataset: DOT Special Event permits (applicationtype DOT_SE) of work type Festival, Athletic, Parade or
# Block Party that close or narrow the street (Full -> closed; Curblane, Partial, Intermittent -> narrowed), not ended
# and starting within events.json "ahead" days. Cancelled and incomplete applications are dropped; applications still
# in review (the big annual events often are, until days before) are kept and say so. Permits run by the day, so
# every closure is a whole day: start T00:00, end T23:59, and `day: true`.
# Privacy: a block party's permit names the resident who applied, so block parties are always named by their street
# ("Block party on Kostner Ave"); for the others the application name is the event's name, and the applicant's own
# comments are never shown (they can be personal). events.json "hide" drops names by pattern; events longer than
# "maxDays" (weekly markets on season-long permits) are left out unless listed in "long".
EV = json.load(open(os.path.join(HERE, 'events.json')))
EV_KIND = {'Full': 'closed', 'Curblane': 'narrowed', 'Partial': 'narrowed', 'Intermitte': 'narrowed'}
EV_WORDS = {'Festival': 'Festival', 'Athletic': 'Race or athletic event', 'Parade': 'Parade', 'Block Party': 'Block party'}
ev_end = (now + timedelta(days=EV.get('ahead', 14) + 1)).date()
ev_where = (f"applicationtype = 'DOT_SE' AND worktypedescription in ('Festival', 'Athletic', 'Parade', 'Block Party') "
            f"AND applicationenddate >= '{today}T00:00:00' AND applicationstartdate <= '{ev_end}T00:00:00' "
            "AND streetclosure in ('Full', 'Curblane', 'Partial', 'Intermitte')")
req = urllib.request.Request(API + '?' + urllib.parse.urlencode({'$where': ev_where, '$limit': 5000}),
                             headers={'User-Agent': 'layers.city data fetch'})
ev_rows = json.load(urllib.request.urlopen(req, timeout=180))

# Main streets from the map, to draw a closure along its street rather than as a straight line (diagonals such as
# Clybourn, Milwaukee and Northwest Highway). Chicago's grid gives the far end's latitude (north-south streets) or
# longitude (east-west streets) from the house number, wherever the street runs.
STREETS = os.path.join(HERE, '..', '..', 'docs', 'chicago', 'data', 'streets.geojson')
skey = lambda n: re.sub(r'[^a-z0-9]', '', re.sub(r'^(N|S|E|W)\s+', '', n or '').lower())
by_street = {}
try:
    for f in json.load(open(STREETS))['features']:
        g = f['geometry']
        for line in (g['coordinates'] if g['type'] == 'MultiLineString' else [g['coordinates']]):
            by_street.setdefault(skey(f['properties'].get('name')), []).append(line)
except (OSError, ValueError, KeyError):
    pass


def along(street, lon, lat, direction, n_from, n_to):
    """The closure drawn along the street's own line, or None (then a straight grid line)."""
    import heapq
    lines = by_street.get(skey(street))
    if not lines or n_to == n_from or direction not in 'NSEW':
        return None
    ns = direction in 'NS'
    sign = 1 if direction in 'NE' else -1
    target = (lat + sign * (n_to - n_from) * M_PER_NUM / 110540) if ns else (lon + sign * (n_to - n_from) * M_PER_NUM / KX)
    k = lambda c: (round(c[0], 6), round(c[1], 6))
    dm = lambda a, b: math.hypot((a[0] - b[0]) * KX, (a[1] - b[1]) * 110540)
    graph = {}
    for line in lines:
        for u, v in zip(line, line[1:]):
            u, v = k(u), k(v)
            graph.setdefault(u, []).append((v, dm(u, v))); graph.setdefault(v, []).append((u, dm(u, v)))
    s = min(graph, key=lambda n: dm(n, (lon, lat)))
    if dm(s, (lon, lat)) > 120:
        return None
    dist, prev, pq = {s: 0}, {}, [(0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in graph[u]:
            if d + w < dist.get(v, 9e9):
                dist[v], prev[v] = d + w, u
                heapq.heappush(pq, (d + w, v))
    off = lambda n: abs((n[1] if ns else n[0]) - target) * (110540 if ns else KX)
    want = abs(n_to - n_from) * M_PER_NUM
    near = [n for n in dist if dist[n] <= 1.4 * want + 150]     # a diagonal runs a little longer than its grid span, not 4x
    if not near:
        return None
    e = min(near, key=lambda n: (off(n), dist[n]))
    if off(e) > 120 or e == s:
        return None
    path = [e]
    while path[-1] in prev:
        path.append(prev[path[-1]])
    return [[round(lon, 6), round(lat, 6)]] + [list(c) for c in path[::-1][1:]]


hide = [re.compile(h, re.I) for h in EV.get('hide', [])]
long_ok = [re.compile(h, re.I) for h in EV.get('long', [])]
ev_out, ev_skip = [], collections.Counter()
for r in ev_rows:
    wt, name = r.get('worktypedescription'), re.sub(r'\s+', ' ', r.get('applicationname') or '').strip()
    status = (r.get('applicationstatus') or '') + ' ' + (r.get('currentmilestone') or '')
    if 'Cancel' in status or 'Incomplete' in status or 'Withdrawn' in status or 'Denied' in status:
        ev_skip['cancelled or incomplete'] += 1; continue
    try:
        lon, lat = float(r['longitude']), float(r['latitude'])
        a, b = int(float(r.get('streetnumberfrom') or 0)), int(float(r.get('streetnumberto') or 0))
    except (KeyError, TypeError, ValueError):
        ev_skip['no location'] += 1; continue
    s, e = (r.get('applicationstartdate') or '')[:10], (r.get('applicationenddate') or '')[:10]
    st = street_name(r)
    if wt == 'Block Party':
        name = f"Block party on {re.sub(r'^(N|S|E|W) ', '', st)}"
    if len(name) < 4 or any(h.search(name) for h in hide):
        ev_skip['hidden name'] += 1; continue
    days = (datetime.fromisoformat(e) - datetime.fromisoformat(s)).days + 1 if s and e else 999
    if days > EV.get('maxDays', 21) and not any(h.search(name) for h in long_ok):
        ev_skip['season-long permit'] += 1; continue
    coords = along(st, lon, lat, r.get('direction'), a, b or a) or [[round(lon, 6), round(lat, 6)], far_end(lon, lat, r.get('direction'), a, b or a)]
    if not coords[-1]:
        ev_skip['no direction'] += 1; continue
    ev_out.append({
        'who': name, 'street': st,
        'extent': f"{a}–{b} {st}" if b and b != a else f"{a} {st}",
        'kind': EV_KIND[r['streetclosure']], 'both': r['streetclosure'] == 'Full',
        'start': s + 'T00:00', 'end': e + 'T23:59', 'day': True,
        'desc': EV_WORDS.get(wt, 'Special event') + ' permit' + (' (application still in review; closures may change)' if 'review' in status.lower() else '') + '.',
        'coords': coords,
    })
json.dump({'fetched': now.strftime('%Y-%m-%dT%H:%M'), 'source': API, 'permits': ev_out}, open(os.path.join(OUT, 'events.json'), 'w'), indent=0)
print('Chicago events:', len(ev_rows), 'special-event permit rows;', len(ev_out), 'closures kept from',
      len({p['who'] for p in ev_out}), 'events; left out:', dict(ev_skip), ';',
      sum(len(p['coords']) > 2 for p in ev_out), 'drawn along their street')
