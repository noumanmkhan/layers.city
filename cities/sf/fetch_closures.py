"""Special-event street closures for San Francisco -> cities/sf/raw/closures/events.json, for engine/events.py.
Runs daily in GitHub Actions (fetch-closures.yml); the sandbox can't reach DataSF.

Source: SFMTA's Temporary Street Closures (DataSF 8x25-yybr, public domain), one row per closed block with its line.
Kept: type "Special Event" (races, parades, festivals, block parties) with a "Permitted" status, not ended and
starting within 15 days. "Roadway Shared Spaces" (long-running parklet and shared-street permits) and "Special
Traffic Permit" (work zones) are left out. Each permit's event name (case_name) is its organizer, so an event's
blocks group together in events.py; vehicle impact "all-lanes-closed" is a closure, anything else a narrowing.
"""
import json, os, re, sys, urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, RAW

API = 'https://data.sfgov.org/resource/8x25-yybr.json'
TZ = ZoneInfo('America/Los_Angeles')
OUT = os.path.join(RAW, 'closures'); os.makedirs(OUT, exist_ok=True)
now = datetime.now(TZ)

where = (f"type = 'Special Event' AND status = 'Permitted' AND end_dt >= '{now:%Y-%m-%dT00:00:00}' "
         f"AND start_dt <= '{now + timedelta(days=15):%Y-%m-%dT23:59:59}'")
rows = json.loads(get(API + '?' + urllib.parse.urlencode({'$where': where, '$limit': 50000, '$order': 'start_dt'})))
print('rows:', len(rows))

ABBR = {'ST': 'St', 'AVE': 'Ave', 'AV': 'Ave', 'BLVD': 'Blvd', 'DR': 'Dr', 'WAY': 'Way', 'PL': 'Pl', 'TER': 'Ter', 'CT': 'Ct',
        'LN': 'Ln', 'RD': 'Rd', 'HWY': 'Hwy', 'ALY': 'Alley', 'CIR': 'Cir', 'PLZ': 'Plaza', 'EXPY': 'Expy', 'BL': 'Blvd'}


def street(s):
    s = re.sub(r'\\.*$', '', (s or '').strip())          # "MISSION ST\\ BART" style suffixes
    out = []
    for w in s.split():
        u = w.upper()
        m = re.match(r'^0*(\d+)(ST|ND|RD|TH)$', u)
        out.append(ABBR.get(u) or (m.group(1) + m.group(2).lower() if m else u if u in ('JFK', 'MLK') else w.capitalize()))
    return ' '.join(out)


def name(s):
    s = re.sub(r'\s+', ' ', s or 'Street event').strip()
    return s.title() if s.isupper() else s


permits, kinds, skipped = [], {}, 0
for r in rows:
    g = r.get('shape') or {}
    cs = g.get('coordinates')
    if not cs: skipped += 1; continue
    lines = [cs] if g.get('type') == 'LineString' else cs if g.get('type') == 'MultiLineString' else []
    vi = r.get('veh_imp') or ''
    kinds[vi] = kinds.get(vi, 0) + 1
    who = name(r.get('case_name'))
    for i, line in enumerate(lines):
        if len(line) < 2: continue
        permits.append({'id': '%s-%s-%d' % (r.get('case_num'), r.get('objectid'), i), 'street': street(r.get('street')),
                        'extent': '%s to %s' % (street(r.get('from_st')), street(r.get('to_st'))),
                        'kind': 'closed' if vi == 'all-lanes-closed' else 'narrowed', 'both': True,
                        'start': (r.get('start_dt') or '')[:16], 'end': (r.get('end_dt') or '')[:16], 'who': who,
                        'desc': 'Street closed for the %s.' % who, 'coords': [[round(x, 6), round(y, 6)] for x, y in line[:400]]})
json.dump({'fetched': now.date().isoformat(), 'source': API, 'permits': permits}, open(os.path.join(OUT, 'events.json'), 'w'), indent=0)
print('sf events:', len(permits), 'closures from', len({p['who'] for p in permits}), 'permits · vehicle impact', kinds, '· no line', skipped)
