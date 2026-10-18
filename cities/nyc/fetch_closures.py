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
