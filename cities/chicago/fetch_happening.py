"""Fetch Chicago's public events from the City of Chicago Data Portal and write docs/chicago/data/happening.json
(today through the next 14 days, placed events only, for "Happening nearby" on the card and in the iOS app;
contract section 16) and docs/chicago/events/events.json (30 days, online events included, for the Events page,
engine/events_page.py). Same shape as Toronto's fetch_happening.py. Run daily from GitHub Actions (*Fetch events*);
the sandbox can't reach the portal.

Sources (both updated daily; Data Portal terms of use):
- Chicago Public Library Events (vsdy-d8k7): every branch program. One item per program and place (a weekly club is
  one item with each of its times). Free: true (the library's programs are free; some need registration).
  Category: the first of `event_types`. Link: the program's page on the library's events site. Cancelled ones are
  dropped; events with no place (online) are kept for the Events page only, with `area` "online".
- Chicago Park District Activities (tn7v-6rnw), type "Event" only: the Park District's public events (festivals,
  holiday events, Night Out in the Parks). Its "Program" rows (classes and open skate or gym sessions, most with a
  fee, many an hour long) are left out: they're a timetable, not events. Free: `fee` "0" (else false). Category: the
  first of `category`. Link: the activity's page.
No descriptions, images, prices or contacts. Each placed item carries `hood`, its community area.

Usage: python3 cities/chicago/fetch_happening.py [--library FILE] [--parks FILE] [--today YYYY-MM-DD]
"""
import html, json, os, re, sys, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, '..', '..', 'docs', 'chicago')
API = 'https://data.cityofchicago.org/resource/'
TZ = ZoneInfo('America/Chicago')
DAYS, PAGE_DAYS = 14, 30
OUT = os.path.join(DOCS, 'data', 'happening.json')
PAGE_OUT = os.path.join(DOCS, 'events', 'events.json')
HOODS = os.path.join(DOCS, 'data', 'community_areas.geojson')

args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
now = datetime.now(TZ)
today = date.fromisoformat(args['--today']) if '--today' in args else now.date()
last, last14 = today + timedelta(days=PAGE_DAYS), today + timedelta(days=DAYS)


def socrata(rid, where, order):
    import time
    rows, off = [], 0
    while True:
        q = urllib.parse.urlencode({'$where': where, '$order': order, '$limit': 5000, '$offset': off})
        req = urllib.request.Request(API + rid + '.json?' + q, headers={'User-Agent': 'layers.city data fetch'})
        for attempt in range(3):            # the portal times out now and then
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


span = f"'{today}T00:00:00' AND '{last}T23:59:59'"
sources, events = [], {}


def point(r):
    try:
        lng, lat = r['location']['coordinates']
        return round(float(lat), 5), round(float(lng), 5)
    except (KeyError, TypeError, ValueError):
        try:
            return round(float(r['latitude']), 5), round(float(r['longitude']), 5)
        except (KeyError, TypeError, ValueError):
            return None, None


def first(s, sep):
    s = html.unescape((s or '').strip())
    return s.split(sep)[0].strip() or None if s else None


def when(start, end):
    start, end = (start or '')[:16], (end or '')[:16]
    if start[11:16] == '00:00' and (not end or end[:10] > start[:10] or end[11:16] in ('00:00', '23:59')):
        return [start[:10], None]
    return [start, end if len(end) == 16 and end > start else None]


def add(key, item, start, end):
    e = events.get(key)
    if not e:
        e = events[key] = dict(item, times=[], _late=start[:10] > last14.isoformat())
    elif e['_late'] and start[:10] <= last14.isoformat():
        e.update(id=item['id'], url=item['url'], _late=False)
    t = when(start, end)
    if t not in e['times']:
        e['times'].append(t)


# ---- Chicago Public Library ----
try:
    lib = json.load(open(args['--library'])) if '--library' in args else socrata('vsdy-d8k7', f'start between {span}', 'start')
    kept = 0
    for r in lib:
        title = re.sub(r'\s+', ' ', r.get('title') or '').strip()
        if not title or str(r.get('cancelled')).lower() in ('true', '1', 'yes'):
            continue
        lat, lng = point(r)
        venue = (r.get('location_name') or '').strip() or None
        url = (r.get('event_page') or {}).get('url') if isinstance(r.get('event_page'), dict) else None
        item = {'id': 'cpl-' + str(r.get('event_id') or title), 'title': title,
                'venue': (venue + ('' if venue.endswith(('Center', 'Library')) else ' Library' if venue.endswith('Regional') else ' branch')) if venue and lat is not None else venue,
                'address': (r.get('location_address') or '').strip() or None, 'lat': lat, 'lng': lng, 'free': True,
                'category': first(r.get('event_types'), ' | '), 'url': url or 'https://chipublib.bibliocommons.com/events', 'src': 'library'}
        if lat is None:
            item['area'] = 'online'
        add(('cpl', title, venue), item, r.get('start') or '', r.get('end') or '')
        kept += 1
    sources.append('library')
    print(f'library: {len(lib)} rows, {kept} times kept')
except Exception as ex:
    print(f'library feed failed: {ex!r}')

# ---- Chicago Park District: public events only ----
try:
    parks = json.load(open(args['--parks'])) if '--parks' in args else socrata('tn7v-6rnw', f"type = 'Event' AND start_date between {span}", 'start_date')
    kept = 0
    for r in parks:
        title = re.sub(r'\s+', ' ', html.unescape(r.get('title') or '')).strip()
        if r.get('type') != 'Event' or not title or str(r.get('event_cancelled')).lower() in ('true', '1', 'yes'):
            continue
        lat, lng = point(r)
        venue = (r.get('location_facility') or '').strip() or None
        link = r.get('information_link') or {}
        fee = (r.get('fee') or '').strip()
        item = {'id': 'cpd-' + str(r.get('activity_id')), 'title': title, 'venue': venue,
                'address': (r.get('address') or '').strip() or None, 'lat': lat, 'lng': lng,
                'free': True if fee in ('0', '0.0', '0.00') else (False if fee else None),
                'category': (first(r.get('category'), ',') or '').split(' - ')[0] or None,
                'url': (link.get('url') if isinstance(link, dict) else None) or 'https://www.chicagoparkdistrict.com/events', 'src': 'parks'}
        if lat is None:
            item['area'] = 'citywide'
        add(('cpd', title, venue), item, r.get('start_date') or '', r.get('end_date') or '')
        kept += 1
    sources.append('parks')
    print(f'parks: {len(parks)} event rows, {kept} times kept')
except Exception as ex:
    print(f'park district feed failed: {ex!r}')

if not sources:
    sys.exit('no source could be read; the last files stay up')

# A source that couldn't be read today keeps yesterday's items (still in the window), so one bad fetch doesn't empty
# half the page; `sources` lists only what was read today.
try:
    prev = json.load(open(PAGE_OUT))['events']
except (OSError, ValueError, KeyError):
    prev = []
for src in ('library', 'parks'):
    if src in sources:
        continue
    kept = 0
    for e in prev:
        if e.get('src') == src:
            times = [t for t in e['times'] if t[0][:10] >= today.isoformat()]
            if times:
                e = dict(e, times=times, _late=min(t[0] for t in times)[:10] > last14.isoformat()); e.pop('hood', None)
                events[(src, e['id'])] = e; kept += 1
    print(f'{src}: kept {kept} items from the last listing')

items = sorted(events.values(), key=lambda e: (min(t[0] for t in e['times']), e['title']))
for e in items:
    e['times'].sort()
    e.pop('_late', None)


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


names = {'library': 'Chicago Public Library', 'parks': 'Chicago Park District'}
head = {'version': 1, 'city': 'chicago', 'tz': 'America/Chicago', 'asof': now.strftime('%Y-%m-%dT%H:%M'), 'from': today.isoformat()}
tail = {'source': ' and '.join(names[s] for s in sources) + ', via the City of Chicago Data Portal', 'sources': sources,
        'licence': 'City of Chicago Data Portal terms of use.'}


def write(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')


near = []
for e in items:
    times = [t for t in e['times'] if t[0][:10] <= last14.isoformat()]
    if e['lat'] is not None and times:
        near.append({**e, 'times': times})
write(OUT, {**head, 'to': last14.isoformat(), **tail, 'events': near})
print(f'{len(near)} events at {len({(e["lat"], e["lng"]) for e in near})} places, {today} to {last14}')

for e in items:
    e['hood'] = hood_of(e['lng'], e['lat']) if e['lat'] is not None else None
write(PAGE_OUT, {**head, 'to': last.isoformat(), **tail, 'events': items})
print(f'Events page: {len(items)} events ({sum(e["lat"] is None for e in items)} online or citywide, '
      f'{sum(1 for e in items if e["lat"] is not None and not e["hood"])} outside the city), {today} to {last}')
