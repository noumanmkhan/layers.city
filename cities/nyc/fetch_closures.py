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

EV_API = 'https://data.cityofnewyork.us/resource/tvpp-9vvx.json'
from centerline import BORO, norm, core, fetch_lines, stretch as _stretch


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


want = {}
for e in evs:
    b = BORO.get(e.get('event_borough'))
    for on, a, z in chunks(e.get('event_location')):
        for n in (on, a, z): want.setdefault(b, set()).add(core(norm(n)))
lines = fetch_lines(set().union(*want.values()) if want else set())   # (boro, normalised full name) -> [LineString]
print('centerline:', sum(len(v) for v in lines.values()), 'segments on', len(lines), 'streets; sample names', sorted(k[1] for k in lines)[:12])


def stretch(b, on, a, z): return _stretch(lines, b, on, a, z)

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
# The marathon's closures come from the City's own notice (fetch_marathon.py, run just before this), not the permit feed.
MC = json.load(open(os.path.join(HERE, 'marathon.json'))) if os.path.exists(os.path.join(HERE, 'marathon.json')) else None
MP = MC and os.path.join(OUT, 'marathon_%d.json' % MC['year'])
if MP and os.path.exists(MP):
    mar = [p for p in json.load(open(MP))['permits'] if p['end'] >= f'{now_l:%Y-%m-%dT%H:%M}']
    ev_permits += mar
    print('nyc marathon:', len(mar), 'closures from the City notice')
json.dump({'fetched': str(today), 'source': EV_API, 'permits': ev_permits}, open(os.path.join(OUT, 'events.json'), 'w'), indent=0)
print('nyc events:', len(evs), 'permits ->', len(ev_permits), 'closures placed;', len(misses), 'chunks not placed')
for m in misses[:40]: print('   not placed:', m)
