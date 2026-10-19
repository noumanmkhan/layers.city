"""What's on at a city's big venues, from Ticketmaster's Discovery API, for the Venues pages.

Usage:  TICKETMASTER_KEY=... python3 engine/fetch_venue_events.py <city>
Reads:  cities/<city>/venues.json             the curated venues (name, `tm` aliases), `exclude` ids, and "feed":
                                              {centre [lat, lon], radiusKm, country, drop (words left out when
                                              matching names), mode}
        cities/<city>/raw/venue_tm_ids.json   Ticketmaster venue ids learned on earlier runs (written here)
Writes: cities/<city>/raw/venue_events.json   the next two weeks of events per venue slug, plus (in a sweep)
                                              the venues the feed had events at that aren't in venues.json
                                              (so the list can grow by hand, not by itself)

Two ways to read the feed, by "mode":
  sweep   every event within radiusKm of the centre over the next 14 days (a few pages of 200; the API stops at
          1,000), grouped by the feed's venue and matched to ours by id, then by name. Fine where the area has
          fewer than 1,000 events a fortnight.
  venues  one query per venue: its Ticketmaster venue id (learned, or found once by searching the API's venues
          by name near our point), then its events. For a city with far more than 1,000 events a fortnight.
Either is well inside the API's default quota (5,000 calls a day, 5 a second). Nothing but the
listing facts is kept: name, date, time, kind, status and the event's own page on Ticketmaster, which is the
link the pages show. No images, prices or descriptions. Content is cached for a day at a time, which is the
"reasonable period" the API terms allow; an organiser's removal request is honoured by adding the event id
to `exclude` in venues.json, and the next nightly run drops it.

Without a key the script exits 0 without touching the file, so a build still has the last good listing;
the pages say when it is from. A run that gets no events at all also keeps the last file (a feed outage
should not blank the pages); an empty window for one venue is written as empty, which is real.

Terms (developer.ticketmaster.com): the API may not be used to derive revenue, so these pages carry no
affiliate or paid links; see claude/venues.md in the project notes.
"""
import json, os, re, sys, time, urllib.parse, urllib.request, unicodedata
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: fetch_venue_events.py <city>')
HERE = os.path.join(ROOT, 'cities', city)
RAW = os.path.join(HERE, 'raw')
OUT = os.path.join(RAW, 'venue_events.json')
IDS = os.path.join(RAW, 'venue_tm_ids.json')
API = 'https://app.ticketmaster.com/discovery/v2/events.json'
VAPI = 'https://app.ticketmaster.com/discovery/v2/venues.json'
DAYS = 14
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city; go@layers.city)'}

key = os.environ.get('TICKETMASTER_KEY', '').strip()
if not key:
    print('::notice::TICKETMASTER_KEY not set: leaving raw/venue_events.json as it is')
    sys.exit(0)

cfg = json.load(open(os.path.join(HERE, 'venues.json')))
FEED = cfg['feed']
CENTRE, RADIUS_KM = tuple(FEED['centre']), FEED.get('radiusKm', 30)
DROP = r'\b(the|at|' + '|'.join(map(re.escape, FEED.get('drop', []))) + r')\b'
venues = cfg['venues']
exclude = set(cfg.get('exclude', []))
known = json.load(open(IDS)) if os.path.exists(IDS) else {}       # tm venue id -> our slug


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    s = re.sub(DROP, ' ', s)
    return re.sub(r'[^a-z0-9]+', '', s)


by_name = {}
for v in venues:
    for n in [v['name']] + v.get('tm', []):
        by_name[norm(n)] = v['slug']


def get(params):
    url = API + '?' + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(2 + 2 * attempt); continue
            raise
    return None


now = datetime.now(timezone.utc)
start = now.replace(minute=0, second=0, microsecond=0)
end = start + timedelta(days=DAYS)
fmt = lambda d: d.strftime('%Y-%m-%dT%H:%M:%SZ')
base = {'apikey': key, 'latlong': f'{CENTRE[0]},{CENTRE[1]}', 'radius': RADIUS_KM, 'unit': 'km',
        'countryCode': FEED.get('country', 'US'), 'locale': '*', 'sort': 'date,asc', 'size': 200,
        'startDateTime': fmt(start), 'endDateTime': fmt(end)}

events = []
if FEED.get('mode', 'sweep') == 'sweep':
    page, pages = 0, 1
    while page < pages and page < 5:                 # the API caps page*size at 1,000: five pages at most
        data = get(dict(base, page=page))
        pages = data.get('page', {}).get('totalPages', 1)
        events += data.get('_embedded', {}).get('events', [])
        page += 1
        time.sleep(0.3)
    print(f'{len(events)} events in {page} page(s), {fmt(start)} to {fmt(end)}')
else:
    def ids_for(v):
        """The venue's Ticketmaster ids: learned ones, else the API's venues named like ours within 1.5 km of our point."""
        got = [i for i, s in known.items() if s == v['slug']]
        if got:
            return got
        for n in [v['name']] + v.get('tm', []):
            data = get({'apikey': key, 'keyword': n, 'countryCode': FEED.get('country', 'US'), 'size': 20, 'locale': '*'})
            time.sleep(0.25)
            for tv in (data or {}).get('_embedded', {}).get('venues', []):
                loc = tv.get('location') or {}
                try:
                    lat, lon = float(loc['latitude']), float(loc['longitude'])
                except (KeyError, TypeError, ValueError):
                    continue
                d = ((lat - v['at'][1]) * 111) ** 2 + ((lon - v['at'][0]) * 85) ** 2
                if d <= 1.5 ** 2 and norm(tv.get('name')) in {norm(x) for x in [v['name']] + v.get('tm', [])}:
                    known[tv['id']] = v['slug']; got.append(tv['id'])
            if got:
                break
        if not got:
            print(f"  no Ticketmaster venue found for {v['name']}")
        return got
    q = dict(base); [q.pop(k) for k in ('latlong', 'radius', 'unit')]
    for v in venues:
        try:
            vids = ids_for(v)
        except Exception as e:                       # one venue's lookup failing shouldn't lose the rest
            print(f"  {v['name']}: venue lookup failed ({e})"); continue
        print(f"  {v['name']}: Ticketmaster venue ids {vids}")
        for vid in vids:
            page, pages = 0, 1
            while page < pages and page < 5:
                data = get(dict(q, venueId=vid, page=page)) or {}
                pages = data.get('page', {}).get('totalPages', 1)
                events += data.get('_embedded', {}).get('events', [])
                page += 1
                time.sleep(0.25)
    print(f'{len(events)} events at {len(venues)} venues, {fmt(start)} to {fmt(end)}')
if not events:
    print('::warning::the feed returned no events: keeping the last venue_events.json')
    sys.exit(0)

KIND = {'Sports': 'sports', 'Music': 'concerts', 'Arts & Theatre': 'theatre', 'Film': 'film'}


def kind(ev):
    cl = (ev.get('classifications') or [{}])[0]
    seg = (cl.get('segment') or {}).get('name', '')
    gen = (cl.get('genre') or {}).get('name', '')
    if 'comedy' in gen.lower():
        return 'comedy'
    return KIND.get(seg, 'other')


def status(ev):
    s = (ev.get('dates') or {}).get('status', {}).get('code', '')
    return {'cancelled': 'cancelled', 'postponed': 'postponed', 'rescheduled': 'rescheduled'}.get(s)


# Not events: the feed also sells add-ons to a game (Fan Access "Plus Ups", warm-up access), building tours and
# parking as if they were shows. They arrive without a Sports/Music/Arts classification, so an unclassified entry
# whose name reads like one of those is dropped. A real show with no classification still goes through.
ADDON = re.compile(r'\b(fan access|plus ups?|add[- ]?ons?|upgrade|parking|guided tours?|tour of|courtside access|'
                   r'warm-?ups?|experience package|vip package|meet (and|&) greet|early entry|general admission|admission ticket)\b', re.I)

out, unmatched, seen = {v['slug']: [] for v in venues}, {}, set()
for ev in events:
    vs = (ev.get('_embedded') or {}).get('venues') or []
    if not vs or ev.get('id') in exclude:
        continue
    if kind(ev) == 'other' and ADDON.search(ev.get('name', '')):
        continue
    tv = vs[0]
    slug = known.get(tv.get('id')) or by_name.get(norm(tv.get('name', '')))
    if not slug:
        u = unmatched.setdefault(tv.get('id') or tv.get('name'), {'id': tv.get('id'), 'name': tv.get('name'), 'events': 0})
        u['events'] += 1
        continue
    if tv.get('id') and known.get(tv['id']) != slug:
        known[tv['id']] = slug
    d = ev.get('dates', {}).get('start', {})
    row = {
        'id': ev.get('id'),
        'name': ev.get('name', '').strip(),
        'date': d.get('localDate'),
        'time': None if d.get('timeTBA') or d.get('noSpecificTime') else d.get('localTime', '')[:5] or None,
        'kind': kind(ev),
        'url': ev.get('url'),
    }
    st = status(ev)
    if st:
        row['status'] = st
    k = (slug, row['name'], row['date'], row['time'])      # the feed lists some shows twice (a resale copy)
    if row['date'] and k not in seen:
        seen.add(k); out[slug].append(row)

for slug in out:
    out[slug].sort(key=lambda r: (r['date'], r['time'] or '99:99'))
os.makedirs(RAW, exist_ok=True)
json.dump(known, open(IDS, 'w'), indent=1, sort_keys=True)
json.dump({'asof': fmt(now), 'window': [start.date().isoformat(), end.date().isoformat()], 'source': 'Ticketmaster Discovery API',
           'venues': out, 'unmatched': sorted(unmatched.values(), key=lambda u: -u['events'])},
          open(OUT, 'w'), ensure_ascii=False, indent=1)
print({s: len(r) for s, r in out.items()})
if unmatched:
    print('venues in the feed that are not in venues.json (most events first):')
    for u in sorted(unmatched.values(), key=lambda u: -u['events'])[:25]:
        print(f"  {u['events']:3}  {u['name']}  ({u['id']})")
