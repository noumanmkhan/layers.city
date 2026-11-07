"""Fetch the City of Vancouver's calendar of events and write docs/vancouver/data/happening.json (today through the next
14 days, placed events only), for "Happening nearby" on the card and in the iOS app (contract section 16). No Events
page: the calendar is small (a handful of events a month). Run daily from GitHub Actions (*Fetch events*); the sandbox
can't reach the feed.

Source: the City and Park Board's calendar of events (vancouver.ca, a Trumba calendar), its public JSON feed. The City's
terms allow feeds for personal, informational and non-commercial use only, and ask that links to its pages read
"City of Vancouver" or "vancouver.ca": the file's `linkText` says so, and the card links "vancouver.ca" rather than the
event's title. Used under the non-commercial rule (NONCOMMERCIAL.md).
- Category: the event's "Event type". Free: "Ticket price" is "Free" (else false when a price is given, else null).
  Link: the event's page on vancouver.ca. Cancelled and online events are dropped.
- Places: the feed's location is a name and an address with no coordinates. The name is matched to the map's own
  community centres, libraries, parks and landmarks; else the address goes to OpenStreetMap's Nominatim (one lookup per
  new place, cached in raw/events_places.json, a second apart, as its usage policy asks).
Never read: descriptions, images, organizer emails or websites, registration fields.

Usage: python3 cities/vancouver/fetch_happening.py [--today YYYY-MM-DD]
"""
import html, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, '..', '..', 'docs', 'vancouver')
TZ = ZoneInfo('America/Vancouver')
DAYS = 14
OUT = os.path.join(DOCS, 'data', 'happening.json')
CACHE = os.path.join(HERE, 'raw', 'events_places.json')
FEED = 'https://www.trumba.com/calendars/city-of-vancouver-events.json?events=200&months=2'
UA = {'User-Agent': 'layers.city events fetch (go@layers.city)'}

args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
now = datetime.now(TZ)
today = date.fromisoformat(args['--today']) if '--today' in args else now.date()
last14 = today + timedelta(days=DAYS)


def get(url, tries=3):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as ex:
            print(f'  try {attempt + 1} failed: {url[:90]} {ex!r}', flush=True)
            time.sleep(10)
    return None


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


norm = lambda s: re.sub(r'\b(the|park|community|centre|center|library|branch|vancouver)\b|[^a-z0-9]', '', (s or '').lower())
named = {}
nb = json.load(open(os.path.join(DOCS, 'data', 'nearby.json')))['groups']
for g in ('centre', 'library', 'park'):
    for p in nb.get(g, []):
        if len(p) > 2 and p[2]:
            named.setdefault(norm(p[2]), (round(p[1], 5), round(p[0], 5)))
for f in json.load(open(os.path.join(DOCS, 'data', 'landmarks.geojson')))['features']:
    n, g = f['properties'].get('name'), f['geometry']
    if n and g and g['type'] == 'Point':
        named.setdefault(norm(n), (round(g['coordinates'][1], 5), round(g['coordinates'][0], 5)))
named.pop('', None)
try:
    cache = json.load(open(CACHE))
except (OSError, ValueError):
    cache = {}


def nominatim(address):
    q = urllib.parse.urlencode({'q': address, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'ca',
                                'viewbox': '-123.27,49.33,-123.02,49.19', 'bounded': 1})
    t = get('https://nominatim.openstreetmap.org/search?' + q, tries=2)
    time.sleep(1.1)
    try:
        r = json.loads(t)
        return (round(float(r[0]['lat']), 5), round(float(r[0]['lon']), 5)) if r else None
    except (TypeError, ValueError, KeyError, IndexError):
        return None


def place(loc_html):
    """The feed's location (HTML: a name, an address, a maps link) -> (venue, address, lat, lng)."""
    link = re.search(r'href="([^"]+)"', loc_html or '')
    q = urllib.parse.parse_qs(urllib.parse.urlparse(html.unescape(link.group(1))).query).get('q', [''])[0] if link else ''
    text = clean(loc_html)
    parts = [p.strip() for p in re.split(r'\s*,\s*', text) if p.strip()]
    venue = parts[0] if parts and not re.match(r'^\d', parts[0]) else None
    address = q or ', '.join(p for p in parts if p != venue) or None
    hit = named.get(norm(venue)) if venue else None
    if not hit and venue and len(norm(venue)) >= 6:
        k = norm(venue)
        hit = next((v for n, v in sorted(named.items(), key=lambda kv: -len(kv[0])) if len(n) >= 6 and (n in k or k in n)), None)
    if hit:
        return venue, address, hit[0], hit[1]
    key = (address or text).lower()
    if key and key not in cache and address:
        cache[key] = nominatim(address if re.search(r'vancouver', address, re.I) else address + ', Vancouver, BC')
    at = cache.get(key)
    return venue, address, (at[0] if at else None), (at[1] if at else None)


def custom(ev, label):
    for c in ev.get('customFields') or []:
        if (c.get('label') or '').strip().lower() == label:
            return clean(c.get('value'))
    return None


text = get(FEED)
if not text:
    sys.exit('the calendar feed could not be read; the last file stays up')
feed = json.loads(text)
events, unplaced = {}, []
for ev in feed:
    title = clean(ev.get('title'))
    if not title or ev.get('canceled') or re.search(r'online|virtual', ev.get('locationType') or '', re.I):
        continue
    start = (ev.get('startDateTime') or '')[:16]
    end = (ev.get('endDateTime') or '')[:16]
    if ev.get('allDay'):
        start, end = start[:10], None
    if not start or start[:10] > last14.isoformat() or (end or start)[:10] < today.isoformat():
        continue
    if start[:10] < today.isoformat():
        start = today.isoformat()
    if re.search(r'citywide|city-wide|all of vancouver', clean(ev.get('location')), re.I):
        continue                                 # a citywide day has no place to be near
    venue, address, lat, lng = place(ev.get('location'))
    if lat is None:
        unplaced.append(clean(ev.get('location')))
        continue
    price = custom(ev, 'ticket price')
    item = {'id': 'cov-' + str(ev.get('eventID') or title), 'title': title, 'venue': venue, 'address': address,
            'lat': lat, 'lng': lng, 'free': True if price and price.lower() == 'free' else (False if price else None),
            'category': custom(ev, 'event type'), 'url': ev.get('permaLinkUrl') or 'https://vancouver.ca/news-calendar/calendar-of-events.aspx',
            'src': 'city'}
    e = events.setdefault((title, venue or address), dict(item, times=[]))
    t = [start, None] if len(start) == 10 else [start, end if len(end) == 16 and end > start else None]
    if t not in e['times']:
        e['times'].append(t)
print(f'{len(feed)} feed entries; {len(events)} events placed; not placed: {unplaced}')
os.makedirs(os.path.dirname(CACHE), exist_ok=True)
json.dump(cache, open(CACHE, 'w'), indent=0, sort_keys=True)

items = sorted(events.values(), key=lambda e: (min(t[0] for t in e['times']), e['title']))
for e in items:
    e['times'].sort()
doc = {'version': 1, 'city': 'vancouver', 'tz': 'America/Vancouver', 'asof': now.strftime('%Y-%m-%dT%H:%M'),
       'from': today.isoformat(), 'to': last14.isoformat(), 'source': 'City of Vancouver calendar of events (vancouver.ca)',
       'sources': ['city'], 'licence': 'City of Vancouver website terms: feeds for personal, informational and non-commercial use.',
       'linkText': 'vancouver.ca', 'events': items}
with open(OUT, 'w') as f:
    json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    f.write('\n')
print(f'{len(items)} events, {today} to {last14}')
