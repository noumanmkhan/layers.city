"""Fetch the City of Toronto Festivals & Events Calendar (Open Data "Festivals & Events", JSON feed,
Open Government Licence – Toronto) and write docs/toronto/data/happening.json: every event on the
calendar from today through the next 14 days, for "Happening nearby" on the card's Nearby section and
in the iOS app (contract, Happening nearby). Run daily from GitHub Actions (*Fetch events*).

Also docs/toronto/events/events.json, for the Events page (engine/events_page.py): the same items over 30 days,
plus the City's events with no address on the map (city-wide or virtual, a boundary, a route, an address
without GPS), which keep the organizer's place name, `lat`/`lng` null and `area` saying which. Each placed item
carries `hood`, the neighbourhood its GPS falls in (docs/toronto/data/neighbourhoods.geojson), or null.

The feed is one record per occurrence (`calendar_date`), with `submission_id` shared by an event's
occurrences; `event_dates` is capped at 20 entries, so it isn't used for the schedule. What's kept:
- Title (`event_name`), category (the first `event_category`), free (`free_event` "Yes"/"No", else null)
  and the City's own page for the event (the calendar's `?event_id=` detail link).
- Places: each `event_locations` entry of type "Address" with GPS. City-Wide/Virtual, Boundary and
  Route entries, and addresses without GPS, are never placed by guess; an event with none is left out
  of happening.json (the Events page keeps it, placeless). An event at several addresses gives one item
  per address.
- Times: each occurrence's local start, and its end that day from the location's schedule (the
  weekday's hours for weekly events, the dated entry for "Multiple"), else null. All-day occurrences
  are a bare date.
No descriptions, images, prices or contacts: organizer-submitted, and not needed for a glance.

Also Toronto Public Library's programs and events at its branches (Open Data "Library Branch Programs and
Events Feed", same licence): one record per occurrence, kept as one item per program and branch (a weekly
club is one item with each of its times). The feed names the branch only, so the place is the branch's
GPS from raw/nearby/tpl_branches.json (fetch_nearby.py), matched by name; closed branches ("… - Closed"),
"None" and names that don't match are dropped. Category: the first of `EventTypes`. Free: true (the feed
doesn't say, but the library's programs are free to attend; some need registration). Link: the program's page on the library's events site. Ended occurrences are left out. If the
library feed can't be read, the file is written with the City's events alone and `sources` says so.

Usage: python3 cities/toronto/fetch_happening.py [--feed FILE] [--library FILE] [--today YYYY-MM-DD]
"""
import json, os, sys, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
URL = ('https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/9201059e-43ed-4369-885e-0b867652feac/'
       'resource/8900fdb2-7f6c-4f50-8581-b463311ff05d/download/file.json')
PAGE = 'https://www.toronto.ca/explore-enjoy/festivals-events/festivals-events-calendar/'
TPL_URL = ('https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/fb343332-03cd-40b9-a1c8-c03a4a85ca1e/'
           'resource/aa5e1425-77f4-4cb4-a8ea-eb5ce7d4f34c/download/tpl-events-feed.json')
TPL_PAGE = 'https://tpl.bibliocommons.com/events/'
BRANCHES = os.path.join(HERE, 'raw', 'nearby', 'tpl_branches.json')
TZ = ZoneInfo('America/Toronto')
DAYS = 14          # happening.json (the card and the app)
PAGE_DAYS = 30     # the Events page
OUT = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'happening.json')
PAGE_OUT = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'events', 'events.json')
HOODS = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'neighbourhoods.geojson')
AREA = {'City-Wide/Virtual': 'citywide', 'Boundary': 'boundary', 'Route': 'route', 'Address': 'address'}

args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
now = datetime.now(TZ)
today = date.fromisoformat(args['--today']) if '--today' in args else now.date()
last = today + timedelta(days=PAGE_DAYS)
last14 = today + timedelta(days=DAYS)

if '--feed' in args:
    feed = json.load(open(args['--feed']))
else:
    req = urllib.request.Request(URL, headers={'User-Agent': 'layers.city data fetch'})
    with urllib.request.urlopen(req, timeout=300) as r:
        feed = json.load(r)
recs = feed['value'] if isinstance(feed, dict) else feed
print(f'{len(recs)} calendar records')


def clock(s):
    """"10:00 AM" -> (10, 0), or None."""
    try:
        t = datetime.strptime((s or '').strip().upper(), '%I:%M %p')
        return t.hour, t.minute
    except ValueError:
        return None


def end_of(start, schedules):
    """The occurrence's end that day from its location's schedule, as local time, or None."""
    day, hm = start.date().isoformat(), clock(start.strftime('%I:%M %p'))
    for s in schedules:
        etime = None
        if s.get('event_frequency') == 'Multiple':
            # The first date is the entry itself; the rest are in multiple_dates (`sdate`, `stime`,
            # `etime`), sometimes two on one day, told apart by start time.
            dates = [(s.get('startdate'), s.get('starttime'), s.get('endtime'))] + \
                    [(m.get('sdate'), m.get('stime'), m.get('etime')) for m in s.get('multiple_dates') or []]
            same = [d for d in dates if (d[0] or '')[:10] == day]
            hit = [d for d in same if clock(d[1]) == hm] or same
            if not hit:
                continue
            etime = hit[0][2]
        else:
            if not (s.get('startdate') or '') <= day <= (s.get('repeat_enddate') or s.get('enddate') or ''):
                continue
            etime = s.get('endtime')
            if s.get('event_frequency') == 'Weekly':
                wd = s.get('repeat_weekdays') or []
                i = (start.weekday() + 1) % 7     # the list starts on Sunday
                if i < len(wd) and wd[i].get('checked') and clock(wd[i].get('etime')):
                    etime = wd[i]['etime']
        c = clock(etime)
        if c:
            end = start.replace(hour=c[0], minute=c[1])
            if end <= start:
                end += timedelta(days=1)    # runs past midnight
            return end
    return None


def all_day(schedules):
    return any(s.get('allday_chk') for s in schedules)


events = {}
dropped_place = set()
for r in recs:
    if r.get('event_status') != 'Approved' or not r.get('calendar_date') or not r.get('event_name'):
        continue
    start = datetime.fromisoformat(r['calendar_date']).astimezone(TZ)
    if not today <= start.date() <= last:
        continue
    places = []
    for loc in r.get('event_locations') or []:
        if loc.get('location_type') != 'Address':
            continue
        try:
            gps = json.loads(loc.get('location_gps') or '[]')
            lat, lng = float(gps[0]['gps_lat']), float(gps[0]['gps_lng'])
        except (ValueError, KeyError, IndexError, TypeError):
            continue
        try:
            sched = json.loads(loc.get('location_dates') or '[]')
        except ValueError:
            sched = []
        places.append((loc, lat, lng, sched))
    if not places:
        # No place on the map: kept for the Events page only, under the first location's name.
        dropped_place.add(r['submission_id'])
        loc = (r.get('event_locations') or [{}])[0]
        try:
            sched = json.loads(loc.get('location_dates') or '[]')
        except ValueError:
            sched = []
        places = [(loc, None, None, sched)]
    for n, (loc, lat, lng, sched) in enumerate(places):
        key = (r['submission_id'], n)
        e = events.get(key)
        if not e:
            free = {'Yes': True, 'No': False}.get(r.get('free_event'))
            e = events[key] = {
                'id': r['submission_id'] + ('' if n == 0 else f'-{n}'),
                'title': r['event_name'].strip(),
                'venue': (loc.get('location_name') or '').strip() or None,
                'address': (loc.get('location_address') or '').strip() or None,
                'lat': None if lat is None else round(lat, 5), 'lng': None if lng is None else round(lng, 5),
                'free': free,
                'category': (r.get('event_category') or [None])[0],
                'url': PAGE + '?' + urllib.parse.urlencode({'event_id': r['id'], 'event_name': r['event_name'].strip()},
                                                          quote_via=urllib.parse.quote),
                'times': [],
            }
            if lat is None:
                e['area'] = AREA.get(loc.get('location_type'), 'citywide')
            e['_late'] = start.date() > last14
        if e['_late'] and start.date() <= last14:
            # The link is the first listed occurrence's; within 14 days if there is one, as happening.json had it.
            e['url'] = PAGE + '?' + urllib.parse.urlencode({'event_id': r['id'], 'event_name': r['event_name'].strip()},
                                                          quote_via=urllib.parse.quote)
            e['_late'] = False
        if all_day(sched):
            when = [start.date().isoformat(), None]
        else:
            end = end_of(start, sched)
            when = [start.strftime('%Y-%m-%dT%H:%M'), end.strftime('%Y-%m-%dT%H:%M') if end else None]
        if when not in e['times']:
            e['times'].append(when)

for e in events.values():
    e['src'] = 'city'
sources = ['city']


def branch_key(name):
    """"Daniel G. Hill (formely Jane/Dundas)" and "Dufferin/St.Clair" -> "danielghill", "dufferinstclair"."""
    return ''.join(c for c in name.split(' (')[0].lower() if c.isalnum())


try:
    if '--library' in args:
        lib = json.load(open(args['--library']))
    else:
        req = urllib.request.Request(TPL_URL, headers={'User-Agent': 'layers.city data fetch'})
        with urllib.request.urlopen(req, timeout=120) as r:
            lib = json.load(r)
    lib = lib if isinstance(lib, list) else next(iter(lib.values()))
    branches = {}
    for b in json.load(open(BRANCHES)):
        try:
            branches[branch_key(b['BranchName'])] = (float(b['Lat']), float(b['Long']), b['BranchName'].split(' (')[0].strip())
        except (TypeError, ValueError, KeyError):
            continue    # bookmobiles have no place
    kept, unplaced = 0, set()
    for r in lib:
        loc, title, start = (r.get('LocationName') or '').strip(), (r.get('Title') or '').strip(), r.get('StartTime') or ''
        if r.get('Status') == 'ENDED' or not title or not today.isoformat() <= start[:10] <= last.isoformat():
            continue
        b = None if loc.endswith('- Closed') else branches.get(branch_key(loc))
        if not b:
            unplaced.add(loc)
            continue
        key = ('tpl', title, b[2])
        e = events.get(key)
        if not e:
            e = events[key] = {
                'id': 'tpl-' + r['EventID'], 'title': title, 'venue': b[2] + ' branch', 'address': None,
                'lat': round(b[0], 5), 'lng': round(b[1], 5), 'free': True,
                'category': (r.get('EventTypes') or '').split(', ')[0] or None,
                'url': TPL_PAGE + urllib.parse.quote(r['EventID']), 'times': [], 'src': 'library',
                '_late': start[:10] > last14.isoformat(),
            }
        if e['_late'] and start[:10] <= last14.isoformat():
            e['id'], e['url'], e['_late'] = 'tpl-' + r['EventID'], TPL_PAGE + urllib.parse.quote(r['EventID']), False
        end = r.get('EndTime') or ''
        if start[11:16] == '00:00' and end[:16] <= start[:16]:
            when = [start[:10], None]    # midnight to midnight: all day
        else:
            when = [start[:16], end[:16] if len(end) >= 16 and end[:16] > start[:16] else None]
        if when not in e['times']:
            e['times'].append(when)
            kept += 1
    sources.append('library')
    print(f'library: {kept} times kept; not placed: {sorted(unplaced)}')
except Exception as ex:    # the City's events still go out
    print(f'library feed failed, City events only: {ex!r}')

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


def hoods():
    """[(name, bbox, polygons)] from the map's neighbourhoods, each polygon [outer, *holes]."""
    out = []
    try:
        feats = json.load(open(HOODS))['features']
    except (OSError, ValueError, KeyError):
        return out
    for f in feats:
        g = f['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        xs = [c[0] for p in polys for c in p[0]]; ys = [c[1] for p in polys for c in p[0]]
        out.append((f['properties']['name'], (min(xs), min(ys), max(xs), max(ys)), polys))
    return out


HOOD_LIST = hoods()


def hood_of(lng, lat):
    for name, (x0, y0, x1, y1), polys in HOOD_LIST:
        if x0 <= lng <= x1 and y0 <= lat <= y1:
            for p in polys:
                if ring_has(p[0], lng, lat) and not any(ring_has(h, lng, lat) for h in p[1:]):
                    return name
    return None


head = {
    'version': 1,
    'city': 'toronto',
    'tz': 'America/Toronto',
    'asof': now.strftime('%Y-%m-%dT%H:%M'),
    'from': today.isoformat(),
}
tail = {
    'source': 'City of Toronto Festivals & Events Calendar' + (' and Toronto Public Library' if 'library' in sources else ''),
    'sources': sources,
    'licence': 'Contains information licensed under the Open Government Licence – Toronto.',
}


def write(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')


# happening.json: placed events only, through 14 days (contract section 16).
near = []
for e in items:
    times = [t for t in e['times'] if t[0][:10] <= last14.isoformat()]
    if e['lat'] is not None and times:
        near.append({**e, 'times': times})
write(OUT, {**head, 'to': last14.isoformat(), **tail, 'events': near})
print(f'{len(near)} events at {len({(e["lat"], e["lng"]) for e in near})} places, {today} to {last14}; '
      f'{len(dropped_place)} with no address on the map')

# The Events page: everything through 30 days, with each placed item's neighbourhood.
for e in items:
    e['hood'] = hood_of(e['lng'], e['lat']) if e['lat'] is not None else None
write(PAGE_OUT, {**head, 'to': last.isoformat(), **tail, 'events': items})
print(f'Events page: {len(items)} events ({sum(e["lat"] is None for e in items)} placeless, '
      f'{sum(1 for e in items if e["lat"] is not None and not e["hood"])} outside every neighbourhood), {today} to {last}')
