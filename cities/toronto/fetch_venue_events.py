"""What's on at Toronto's big venues, from Ticketmaster's Discovery API, for the Venues pages.

Usage:  TICKETMASTER_KEY=... python3 cities/toronto/fetch_venue_events.py
Reads:  cities/toronto/venues.json             the curated venues (name, `tm` aliases) and `exclude` ids
        cities/toronto/raw/venue_tm_ids.json   Ticketmaster venue ids learned on earlier runs (written here)
Writes: cities/toronto/raw/venue_events.json   the next two weeks of events per venue slug, plus the venues
                                               the feed had events at that aren't in venues.json (so the
                                               list can grow by hand, not by itself)

One sweep of every event within RADIUS_KM of downtown over the next 14 days (a few pages of 200), grouped
by the feed's venue and matched to ours by id, then by name. That is well inside the API's default quota
(5,000 calls a day, 5 a second) and gives the "tonight downtown" strip every venue at once. Nothing but the
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

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
OUT = os.path.join(RAW, 'venue_events.json')
IDS = os.path.join(RAW, 'venue_tm_ids.json')
API = 'https://app.ticketmaster.com/discovery/v2/events.json'
CENTRE = (43.675, -79.45)     # between downtown and Downsview; Mississauga and Rexdale are inside the radius
RADIUS_KM = 30
DAYS = 14
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city; go@layers.city)'}

key = os.environ.get('TICKETMASTER_KEY', '').strip()
if not key:
    print('::notice::TICKETMASTER_KEY not set: leaving raw/venue_events.json as it is')
    sys.exit(0)

cfg = json.load(open(os.path.join(HERE, 'venues.json')))
venues = cfg['venues']
exclude = set(cfg.get('exclude', []))
known = json.load(open(IDS)) if os.path.exists(IDS) else {}       # tm venue id -> our slug


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(the|at|toronto|on|ontario|canada)\b', ' ', s)
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
        'countryCode': 'CA', 'locale': '*', 'sort': 'date,asc', 'size': 200,
        'startDateTime': fmt(start), 'endDateTime': fmt(end)}

events = []
page, pages = 0, 1
while page < pages and page < 5:                 # the API caps page*size at 1,000: five pages at most
    data = get(dict(base, page=page))
    pages = data.get('page', {}).get('totalPages', 1)
    events += data.get('_embedded', {}).get('events', [])
    page += 1
    time.sleep(0.3)
print(f'{len(events)} events in {page} page(s), {fmt(start)} to {fmt(end)}')
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


out, unmatched, seen = {v['slug']: [] for v in venues}, {}, set()
for ev in events:
    vs = (ev.get('_embedded') or {}).get('venues') or []
    if not vs or ev.get('id') in exclude:
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
