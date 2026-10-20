"""Fetch road restrictions caused by transit construction from the City of Toronto's live Road
Restrictions feed (v3 JSON, refreshed in real time) into raw/closures/permits.json, in the common
shape engine/closures.py reads. Run daily from GitHub Actions (*Fetch transit closures*); the
sandbox can't reach secure.toronto.ca.

Kept: every permit whose source / work event type / permit type is "Metrolinx", plus permits from
the transit consortiums in construction.json "closures.contractors" (a few Ontario Line permits
are filed as "Other"). Which project a permit belongs to is decided later, by where it is.

Also kept, separately: full closures of expressways and major arterials starting within 10 days, from
any permit holder, written to raw/closures/major.json for the weekend brief (engine/weekend.py).

Also kept, separately: every record flagged specialEvent = "Yes" (races, parades, festivals, block
parties), written to raw/closures/events.json for engine/events.py and the Special events layer.
Event closures are filed with the event's organizer as contractor (the Waterfront Marathon's are all
"Canada Running Series Inc."), which is how events.py tells one event from another.

The feed isn't strict JSON (stray backslashes in free text), so lone backslashes are escaped first.

Usage: python3 cities/toronto/fetch_closures.py
       python3 cities/toronto/fetch_closures.py --records FILE   (rebuild events.json only, from a saved
       list of feed records, e.g. raw/scouting/events.json; for testing where the feed can't be reached)
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'https://secure.toronto.ca/opendata/cart/road_restrictions/v3?format=json'
TZ = ZoneInfo('America/Toronto')
cfg = json.load(open(os.path.join(HERE, 'construction.json')))
CONTRACTORS = [c.lower() for c in cfg['closures'].get('contractors', [])]
OUT = os.path.join(HERE, 'raw', 'closures')
os.makedirs(OUT, exist_ok=True)

LOCAL = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == '--records' else None
if LOCAL:
    data = json.load(open(LOCAL))
    recs = data['records'] if isinstance(data, dict) else data
else:
    req = urllib.request.Request(URL, headers={'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)'})
    raw = urllib.request.urlopen(req, timeout=180).read().decode('utf-8', 'replace')
    raw = re.sub(r'\\(["\\/bfnrtu]?)', lambda m: m.group(0) if m.group(1) else '\\\\', raw)
    data = json.loads(raw, strict=False)
    recs = [r for v in data.values() if isinstance(v, list) for r in v]


def is_transit(r):
    if any('metrolinx' in str(r.get(k) or '').lower() for k in ('source', 'workEventType', 'permitType')):
        return True
    c = (r.get('contractor') or '').lower()
    return any(k in c for k in CONTRACTORS)


def local(ms):
    return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).astimezone(TZ).strftime('%Y-%m-%dT%H:%M') if ms else None


def hours(r):
    """'24h', '21:00–05:00', or per-day text; days: daily / weekdays / weekends / custom."""
    ev = r.get('scheduleEveryday')
    days = [r.get('schedule' + d) for d in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')]
    if ev:
        h, d = ev, 'daily'
    elif any(days):
        wk, we = days[:5], days[5:]
        vals = {x for x in days if x}
        h = vals.pop() if len(vals) == 1 else None
        d = 'weekdays' if all(wk) and not any(we) else 'weekends' if all(we) and not any(wk) else 'daily' if all(days) else 'some days'
    else:
        return None, None
    if h in ('00:00-23:59', '00:00-24:00'):
        h = '24h'
    elif h:
        h = h.replace('-', '–')
    return h, d


def permit(r, kind):
    try:
        pts = json.loads('[' + r['geoPolyline'] + ']') if r.get('geoPolyline') else [[float(r['longitude']), float(r['latitude'])]]
    except Exception:
        return None
    h, d = hours(r)
    return {
        'id': r['id'],
        'street': r.get('road'),
        'extent': (r.get('name') or '').strip(),
        'kind': kind,
        'both': r.get('directionsAffected') == 'BOTH_DIRECTIONS',
        'start': local(r.get('startTime')), 'end': local(r.get('endTime')),
        'hours': h, 'days': d,
        'who': (r.get('contractor') or '').strip(),
        'desc': re.sub(r'\s+', ' ', (r.get('description') or '').replace('Toronto-TMC:', '')).strip(),
        'roadClass': r.get('roadClass'),
        'coords': [[round(x, 6), round(y, 6)] for x, y in pts],
    }


def event_kind(r):
    """Event closures are mostly filed as CONSTRUCTION with "All lanes are blocked" boilerplate in the
    description, even when the record's own name says only the curb lane is taken. The name is the more
    specific of the two: "curb lane" there means one lane; anything else is the road closed."""
    return 'narrowed' if 'curb lane' in (r.get('name') or '').lower() else 'closed'


now = datetime.now(TZ).strftime('%Y-%m-%dT%H:%M')
events = [p for p in (permit(r, event_kind(r)) for r in recs if str(r.get('specialEvent')).strip().lower() == 'yes') if p]
json.dump({'fetched': now, 'source': URL, 'permits': events}, open(os.path.join(OUT, 'events.json'), 'w'), indent=0)
print('Toronto:', len(events), 'special-event closures')
if LOCAL:
    sys.exit(0)

# Full closures of expressways and major arterials from any permit holder (Gardiner and DVP weekend
# work, bridge repairs, filming), starting within 10 days and not already ended: the weekend brief's road
# items (engine/weekend.py). Not drawn on the map. The road class counts go to the log for checking.
from collections import Counter
from datetime import timedelta
soon = (datetime.now(TZ) + timedelta(days=10)).strftime('%Y-%m-%dT%H:%M')
print('Toronto road classes of full closures:', dict(Counter(r.get('roadClass') for r in recs if r.get('type') == 'ROAD_CLOSED')))
major = [p for p in (permit(r, 'closed') for r in recs
                     if r.get('type') == 'ROAD_CLOSED' and not is_transit(r)
                     and str(r.get('specialEvent')).strip().lower() != 'yes'
                     and re.search(r'expressway|major', str(r.get('roadClass') or ''), re.I)) if p
         and (p['end'] or '9999') >= now and (p['start'] or '') <= soon]
json.dump({'fetched': now, 'source': URL, 'permits': major}, open(os.path.join(OUT, 'major.json'), 'w'), indent=0)
print('Toronto:', len(major), 'full closures of expressways and major arterials in the next 10 days')

out = [p for p in (permit(r, 'closed' if r.get('type') == 'ROAD_CLOSED' else 'narrowed') for r in recs if is_transit(r)) if p]
json.dump({'fetched': now, 'source': URL, 'permits': out},
          open(os.path.join(OUT, 'permits.json'), 'w'), indent=0)
print('Toronto:', len(recs), 'restrictions in feed;', len(out), 'from transit construction')
