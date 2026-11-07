"""Fetch San Francisco's public events and write docs/sf/data/happening.json (today through the next 14 days, placed
events only, for "Happening nearby" on the card and in the iOS app; contract section 16) and docs/sf/events/events.json
(30 days, online events included, for the Events page, engine/events_page.py). Same shape as Toronto's and Chicago's
fetch_happening.py. Run daily from GitHub Actions (*Fetch events*); the sandbox can't reach DataSF.

Source: Our415 Events and Activities (DataSF 8i3s-ih2a, published by DCYF, updated daily, Open Data Commons PDDL),
the San Francisco Public Library rows only: the library's programs for children, teens and families, about 30 days
ahead (its adult programs aren't in the feed, and the library publishes no other feed, so the page says so). One row
per occurrence; an event is one item per title and branch with each of its times. Free from `fee`. Category: the
title's prefix ("Storytime: For Toddlers" -> "Storytime"). Link: the event's sfpl.org page.
The feed's Rec and Park rows are left out: they're multi-week classes to register for, a timetable rather than events
(Chicago leaves out its Park District's "Program" rows for the same reason).
Never read: `event_description`, `event_photo`, contacts, and every `*_eligibility_tags` field (some are assigned by
software from race, ethnicity or gender; describe, don't target).

Usage: python3 cities/sf/fetch_happening.py [--library FILE] [--today YYYY-MM-DD]
"""
import html, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, '..', '..', 'docs', 'sf')
API = 'https://data.sf.gov/resource/'
TZ = ZoneInfo('America/Los_Angeles')
DAYS, PAGE_DAYS = 14, 30
OUT = os.path.join(DOCS, 'data', 'happening.json')
PAGE_OUT = os.path.join(DOCS, 'events', 'events.json')
HOODS = os.path.join(DOCS, 'data', 'neighbourhoods.geojson')
FIELDS = ('id,event_name,event_start_date,event_end_date,start_time,end_time,more_info,fee,'
          'site_location_name,site_address,latitude,longitude')

args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
now = datetime.now(TZ)
today = date.fromisoformat(args['--today']) if '--today' in args else now.date()
last, last14 = today + timedelta(days=PAGE_DAYS), today + timedelta(days=DAYS)


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


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(s or '')).strip()


def stamp(day, clock):
    day, clock = (day or '')[:10], (clock or '')[:5]
    return f'{day}T{clock}' if len(day) == 10 and re.fullmatch(r'\d\d:\d\d', clock) else day


def when(start, end):
    if len(start) < 16:
        return [start[:10], None]
    return [start, end if len(end) == 16 and end > start else None]


try:
    rows = json.load(open(args['--library'])) if '--library' in args else socrata('8i3s-ih2a', {
        '$select': FIELDS, '$order': 'event_start_date, start_time',
        '$where': f"org_name = 'SF Public Library' AND event_start_date between '{today}T00:00:00' AND '{last}T23:59:59'"})
except Exception as ex:
    sys.exit(f'library feed failed: {ex!r}; the last files stay up')

events, kept = {}, 0
for r in rows:
    title = clean(r.get('event_name'))
    start = stamp(r.get('event_start_date'), r.get('start_time'))
    if not title or not start or not (today.isoformat() <= start[:10] <= last.isoformat()):
        continue
    end = stamp(r.get('event_end_date') or r.get('event_start_date'), r.get('end_time'))
    try:
        lat, lng = round(float(r['latitude']), 5), round(float(r['longitude']), 5)
    except (KeyError, TypeError, ValueError):
        lat = lng = None
    site = clean(r.get('site_location_name')) or None
    venue = site if not site or lat is None or re.search(r'Library|Center|Centre', site) else site + ' branch'
    prefix = title.split(':', 1)[0].strip() if ':' in title else ''
    item = {'id': 'sfpl-' + str(r.get('id') or title), 'title': title, 'venue': venue,
            'address': clean(r.get('site_address')) or None, 'lat': lat, 'lng': lng,
            'free': (not r['fee']) if isinstance(r.get('fee'), bool) else None,
            'category': prefix if prefix and len(prefix.split()) <= 3 else None,
            'url': (r.get('more_info') or '').strip() or 'https://sfpl.org/events', 'src': 'library'}
    if lat is None:
        item['area'] = 'online'
    key = (title, site)
    e = events.get(key)
    if not e:
        e = events[key] = dict(item, times=[], _late=start[:10] > last14.isoformat())
    elif e['_late'] and start[:10] <= last14.isoformat():
        e.update(id=item['id'], url=item['url'], _late=False)
    t = when(start, end)
    if t not in e['times']:
        e['times'].append(t)
    kept += 1
print(f'library: {len(rows)} rows, {kept} times kept')
if not events:
    sys.exit('the library feed had nothing in the window; the last files stay up')

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


head = {'version': 1, 'city': 'sf', 'tz': 'America/Los_Angeles', 'asof': now.strftime('%Y-%m-%dT%H:%M'), 'from': today.isoformat()}
tail = {'source': 'San Francisco Public Library, via Our415 on DataSF', 'sources': ['library'],
        'licence': 'Open Data Commons Public Domain Dedication and License (PDDL).'}


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
print(f'Events page: {len(items)} events ({sum(e["lat"] is None for e in items)} online, '
      f'{sum(1 for e in items if e["lat"] is not None and not e["hood"])} outside the city), {today} to {last}')
