"""Fetch the City of Toronto Festivals & Events Calendar (Open Data "Festivals & Events", JSON feed,
Open Government Licence – Toronto) and write docs/toronto/data/happening.json: every event on the
calendar from today through the next 14 days, for "Happening nearby" on the card's Nearby section and
in the iOS app (contract, Happening nearby). Run daily from GitHub Actions (*Fetch Toronto events*).

The feed is one record per occurrence (`calendar_date`), with `submission_id` shared by an event's
occurrences; `event_dates` is capped at 20 entries, so it isn't used for the schedule. What's kept:
- Title (`event_name`), category (the first `event_category`), free (`free_event` "Yes"/"No", else null)
  and the City's own page for the event (the calendar's `?event_id=` detail link).
- Places: each `event_locations` entry of type "Address" with GPS. City-Wide/Virtual, Boundary and
  Route entries, and addresses without GPS, are dropped rather than guessed; an event with none is
  dropped. An event at several addresses gives one item per address.
- Times: each occurrence's local start, and its end that day from the location's schedule (the
  weekday's hours for weekly events, the dated entry for "Multiple"), else null. All-day occurrences
  are a bare date.
No descriptions, images, prices or contacts: organizer-submitted, and not needed for a glance.

Usage: python3 cities/toronto/fetch_happening.py [--feed FILE] [--today YYYY-MM-DD]
"""
import json, os, sys, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
URL = ('https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/9201059e-43ed-4369-885e-0b867652feac/'
       'resource/8900fdb2-7f6c-4f50-8581-b463311ff05d/download/file.json')
PAGE = 'https://www.toronto.ca/explore-enjoy/festivals-events/festivals-events-calendar/'
TZ = ZoneInfo('America/Toronto')
DAYS = 14
OUT = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'happening.json')

args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
now = datetime.now(TZ)
today = date.fromisoformat(args['--today']) if '--today' in args else now.date()
last = today + timedelta(days=DAYS)

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
        dropped_place.add(r['submission_id'])
        continue
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
                'lat': round(lat, 5), 'lng': round(lng, 5),
                'free': free,
                'category': (r.get('event_category') or [None])[0],
                'url': PAGE + '?' + urllib.parse.urlencode({'event_id': r['id'], 'event_name': r['event_name'].strip()},
                                                          quote_via=urllib.parse.quote),
                'times': [],
            }
        if all_day(sched):
            when = [start.date().isoformat(), None]
        else:
            end = end_of(start, sched)
            when = [start.strftime('%Y-%m-%dT%H:%M'), end.strftime('%Y-%m-%dT%H:%M') if end else None]
        if when not in e['times']:
            e['times'].append(when)

items = sorted(events.values(), key=lambda e: (min(t[0] for t in e['times']), e['title']))
for e in items:
    e['times'].sort()
out = {
    'version': 1,
    'city': 'toronto',
    'tz': 'America/Toronto',
    'asof': now.strftime('%Y-%m-%dT%H:%M'),
    'from': today.isoformat(),
    'to': last.isoformat(),
    'source': 'City of Toronto Festivals & Events Calendar',
    'licence': 'Contains information licensed under the Open Government Licence – Toronto.',
    'events': items,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    f.write('\n')
print(f'{len(items)} events at {len({(e["lat"], e["lng"]) for e in items})} places, {today} to {last}; '
      f'{len(dropped_place)} dropped with no address on the map')
