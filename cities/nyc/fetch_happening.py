"""Fetch New York City's public events and write docs/nyc/data/happening.json (today through the next 14 days, placed
events only, for "Happening nearby" on the card and in the iOS app; contract section 16) and docs/nyc/events/events.json
(the same 14 days, online events included, for the Events page, engine/events_page.py). Same shape as Toronto's and
Chicago's fetch_happening.py. Run daily from GitHub Actions (*Fetch events*); the sandbox can't reach the portal.

Source: NYC Parks Public Events - Upcoming 14 Days (NYC Open Data w3wp-dpdi, updated daily; NYC's Open Data Law puts no
restrictions on use). Every public event on NYC Parks property for the next two weeks: one row per occurrence, so an
event is one item per title and park with each of its times. The feed looks two weeks ahead, so the page covers 14 days,
not 30. Category: the first of `categories`. Link: the event's page on nycgovparks.org. Free: null (the feed has no
cost field). Rows tagged "Virtual/Online Events" are kept for the page only, with `area` "online".
Never read: `instructor` (people's names), `contact_phone`, `description`, `image`, registration fields.
The city's libraries publish no open events feed (see the project's scouting notes), so they aren't here.

Usage: python3 cities/nyc/fetch_happening.py [--parks FILE] [--today YYYY-MM-DD]
"""
import html, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, '..', '..', 'docs', 'nyc')
API = 'https://data.cityofnewyork.us/resource/'
TZ = ZoneInfo('America/New_York')
DAYS = PAGE_DAYS = 14
OUT = os.path.join(DOCS, 'data', 'happening.json')
PAGE_OUT = os.path.join(DOCS, 'events', 'events.json')
HOODS = os.path.join(DOCS, 'data', 'ntas.geojson')
ONLINE = 'Virtual/Online Events'

args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
now = datetime.now(TZ)
today = date.fromisoformat(args['--today']) if '--today' in args else now.date()
last = today + timedelta(days=PAGE_DAYS)


def socrata(rid, params):
    rows, off = [], 0
    while True:
        q = urllib.parse.urlencode({**params, '$limit': 5000, '$offset': off})
        req = urllib.request.Request(API + rid + '.json?' + q, headers={'User-Agent': 'layers.city data fetch'})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    page = json.load(r)
                break
            except Exception as ex:
                print(f'{rid}: try {attempt + 1} failed: {ex!r}')
                if attempt == 2:
                    raise
                time.sleep(20)
        rows += page
        if len(page) < 5000:
            return rows
        off += 5000


def when(start, end):
    start, end = (start or '')[:16], (end or '')[:16]
    if len(start) < 16 or (start[11:16] == '00:00' and (not end or end[:10] > start[:10] or end[11:16] in ('00:00', '23:59'))):
        return [start[:10], None]
    return [start, end if len(end) == 16 and end > start else None]


def point(s):
    try:
        lat, lng = (float(v) for v in (s or '').split(',')[:2])
        return (round(lat, 5), round(lng, 5)) if 40.4 < lat < 41.0 and -74.3 < lng < -73.6 else (None, None)
    except ValueError:
        return None, None


events = {}
try:
    rows = json.load(open(args['--parks'])) if '--parks' in args else socrata('w3wp-dpdi', {'$order': 'starttime'})
except Exception as ex:
    sys.exit(f'parks feed failed: {ex!r}; the last files stay up')

kept = 0
for r in rows:
    title = re.sub(r'\s+', ' ', html.unescape(r.get('title') or '')).strip()
    start = r.get('starttime') or ''          # 17 or so exhibitions have none; skipped
    if not title or not start or start[:10] > last.isoformat():
        continue
    end = r.get('endtime') or ''
    if (end or start)[:10] < today.isoformat():
        continue
    cats = [c.strip() for c in html.unescape(r.get('categories') or '').split('|') if c.strip()]
    online = ONLINE in cats
    lat, lng = (None, None) if online else point(r.get('coordinates'))
    park = re.sub(r'\s+', ' ', html.unescape(r.get('parknames') or '')).strip() or None
    spot = re.sub(r'\s+', ' ', html.unescape(r.get('location') or '')).strip() or None
    venue = spot if spot and (not park or park in spot) else (f'{spot}, {park}' if spot and park else park or spot)
    link = r.get('link') if isinstance(r.get('link'), dict) else {}
    link = (link.get('url') or '').strip().replace('http://', 'https://', 1) or 'https://www.nycgovparks.org/events'
    cat = next((c for c in cats if c != ONLINE), None)
    item = {'id': 'nycp-' + str(r.get('guid') or title), 'title': title, 'venue': venue, 'address': None,
            'lat': lat, 'lng': lng, 'free': None, 'category': cat, 'url': link, 'src': 'parks'}
    if lat is None:
        item['area'] = 'online' if online else 'citywide'
    key = (title, venue)
    e = events.setdefault(key, dict(item, times=[]))
    if start[:10] < today.isoformat():          # a multi-day run (an exhibition) that began before today
        start = today.isoformat()
    t = when(start, end)
    if t not in e['times']:
        e['times'].append(t)
    kept += 1
print(f'parks: {len(rows)} rows, {kept} times kept')
if not events:
    sys.exit('the parks feed had nothing in the window; the last files stay up')

items = sorted(events.values(), key=lambda e: (min(t[0] for t in e['times']), e['title']))
for e in items:
    e['times'].sort()


def ring_has(ring, x, y):
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


HOOD_LIST = []
for f in json.load(open(HOODS))['features']:
    g = f['geometry']
    polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
    xs = [c[0] for p in polys for c in p[0]]; ys = [c[1] for p in polys for c in p[0]]
    HOOD_LIST.append((f['properties']['name'], (min(xs), min(ys), max(xs), max(ys)), polys))


def hood_of(lng, lat):
    for name, (x0, y0, x1, y1), polys in HOOD_LIST:
        if x0 <= lng <= x1 and y0 <= lat <= y1:
            for p in polys:
                if ring_has(p[0], lng, lat) and not any(ring_has(h, lng, lat) for h in p[1:]):
                    return name
    return None


head = {'version': 1, 'city': 'nyc', 'tz': 'America/New_York', 'asof': now.strftime('%Y-%m-%dT%H:%M'), 'from': today.isoformat(),
        'to': last.isoformat(), 'source': 'NYC Parks, via NYC Open Data', 'sources': ['parks'],
        'licence': 'NYC Open Data (NYC Open Data Law: no restrictions on use).'}


def write(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')


near = [e for e in items if e['lat'] is not None]
write(OUT, {**head, 'events': near})
print(f'{len(near)} events at {len({(e["lat"], e["lng"]) for e in near})} places, {today} to {last}')
for e in items:
    e['hood'] = hood_of(e['lng'], e['lat']) if e['lat'] is not None else None
write(PAGE_OUT, {**head, 'events': items})
print(f'Events page: {len(items)} events ({sum(e["lat"] is None for e in items)} online or unplaced, '
      f'{sum(1 for e in items if e["lat"] is not None and not e["hood"])} outside the city), {today} to {last}')
