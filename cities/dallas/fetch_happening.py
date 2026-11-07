"""Fetch Dallas's public events and write docs/dallas/data/happening.json (today through the next 14 days, placed events
only, for "Happening nearby" on the card and in the iOS app; contract section 16) and docs/dallas/events/events.json
(30 days, for the Events page, engine/events_page.py). Same shape as the other cities' fetch_happening.py. Run daily
from GitHub Actions (*Fetch events*); the sandbox can't reach the feeds.

Source: Dallas Park and Recreation's calendars (dallasparks.org, CivicPlus iCal feeds), one feed per calendar. The City
of Dallas's terms bar commercial use without written permission, so this is used under the site's non-commercial rule
(NONCOMMERCIAL.md): take it out, or get the City's permission, before the site earns money.
- One item per title and place, with each of its times. Category: the calendar's name. Free: null (the feeds carry no
  cost). Link: the event's page on dallasparks.org.
- Places: the feed has free text only ("Janie C. Turner Recreation Center, 6424 Elam Rd"). The name is matched to the
  map's own parks, recreation centers, libraries and landmarks (nearby.json, landmarks.geojson), else the street address
  goes to the U.S. Census Bureau geocoder; answers are kept in raw/events_places.json, so each place is looked up once.
  Unplaced events stay on the page under "Place to be confirmed"; events outside the city stay with no ZIP.
- Dropped: board, commission and public-input meetings (government business, not outings), and cancelled ones.
No descriptions, images, prices or contacts.

Usage: python3 cities/dallas/fetch_happening.py [--today YYYY-MM-DD]
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, '..', '..', 'docs', 'dallas')
TZ = ZoneInfo('America/Chicago')
DAYS, PAGE_DAYS = 14, 30
OUT = os.path.join(DOCS, 'data', 'happening.json')
PAGE_OUT = os.path.join(DOCS, 'events', 'events.json')
HOODS = os.path.join(DOCS, 'data', 'zips.geojson')
CACHE = os.path.join(HERE, 'raw', 'events_places.json')
FEED = 'https://www.dallasparks.org/common/modules/iCalendar/iCalendar.aspx?catID={}&feed=calendar'
PAGE = 'https://www.dallasparks.org/Calendar.aspx?EID={}'
CALENDARS = {14: 'Parks and recreation', 39: 'City Park', 40: 'Fair Park', 31: 'Outdoor adventures', 25: 'Volunteer',
             29: 'Nature', 33: 'Teens', 32: 'Older adults', 38: 'Golf'}
DROP = re.compile(r'\b(board|commission|committee|public (input|meeting|hearing)|town hall meeting|council)\b', re.I)
UA = {'User-Agent': 'layers.city events fetch (go@layers.city)'}

args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
now = datetime.now(TZ)
today = date.fromisoformat(args['--today']) if '--today' in args else now.date()
last, last14 = today + timedelta(days=PAGE_DAYS), today + timedelta(days=DAYS)


def get(url, tries=3):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as ex:
            print(f'  try {attempt + 1} failed: {url[:90]} {ex!r}', flush=True)
            time.sleep(10)
    return None


def unfold(text):
    return re.sub(r'\r?\n[ \t]', '', text)


def unescape(v):
    return v.replace('\\n', ' ').replace('\\,', ',').replace('\\;', ';').replace('\\\\', '\\').strip()


def stamp(v, params):
    """iCal date or date-time -> local 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM'."""
    v = v.strip()
    if 'VALUE=DATE' in params or re.fullmatch(r'\d{8}', v):
        return f'{v[:4]}-{v[4:6]}-{v[6:8]}'
    m = re.fullmatch(r'(\d{8})T(\d{4})\d{0,2}(Z?)', v)
    if not m:
        return None
    dt = datetime.strptime(m.group(1) + m.group(2), '%Y%m%d%H%M')
    if m.group(3):
        dt = dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(TZ)
    return dt.strftime('%Y-%m-%dT%H:%M')


def vevents(text):
    for block in re.findall(r'BEGIN:VEVENT(.*?)END:VEVENT', unfold(text), re.S):
        ev = {}
        for line in block.strip().splitlines():
            if ':' not in line:
                continue
            key, val = line.split(':', 1)
            name, *params = key.split(';')
            ev[name.upper()] = (val, ';'.join(params))
        yield ev


# ---- places: the map's own named points, then the Census geocoder (cached) ----
norm = lambda s: re.sub(r'\b(the|park|recreation|rec|center|centre|library|branch|dallas)\b|[^a-z0-9]', '', (s or '').lower())
named = {}
nb = json.load(open(os.path.join(DOCS, 'data', 'nearby.json')))['groups']
for g in ('centre', 'library', 'park', 'pool', 'dogpark', 'spray'):
    for p in nb.get(g, []):
        if len(p) > 2 and p[2]:
            named.setdefault(norm(p[2]), (round(p[1], 5), round(p[0], 5), p[2]))
for f in json.load(open(os.path.join(DOCS, 'data', 'landmarks.geojson')))['features']:
    n = f['properties'].get('name'); g = f['geometry']
    if n and g and g['type'] == 'Point':
        named.setdefault(norm(n), (round(g['coordinates'][1], 5), round(g['coordinates'][0], 5), n))
named.pop('', None)
try:
    cache = json.load(open(CACHE))
except (OSError, ValueError):
    cache = {}


def census(address):
    q = urllib.parse.urlencode({'address': address, 'benchmark': 'Public_AR_Current', 'format': 'json'})
    t = get('https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?' + q, tries=2)
    try:
        m = json.loads(t)['result']['addressMatches']
        return (round(m[0]['coordinates']['y'], 5), round(m[0]['coordinates']['x'], 5)) if m else None
    except (TypeError, ValueError, KeyError):
        return None


def place(loc):
    """Free-text LOCATION -> (venue, address, lat, lng)."""
    loc = re.sub(r'\s+', ' ', loc).strip(' ,')
    parts = [p.strip() for p in loc.split(',') if p.strip()]
    venue = parts[0] if parts else None
    if venue and re.match(r'^\d+\s', venue):     # the address came first: no place name
        venue = None
    address = ', '.join(parts[1:] if venue else parts) or None
    if address and not re.search(r'\d', address):   # a second name, not an address
        address = None
    hit = named.get(norm(venue)) if venue else None
    if not hit and venue and len(norm(venue)) >= 6:   # "Cotton Bowl Stadium" is the landmark "Cotton Bowl"
        k = norm(venue)
        hit = next((v for n, v in sorted(named.items(), key=lambda kv: -len(kv[0])) if len(n) >= 6 and (n in k or k in n)), None)
    if hit:
        return venue, address, hit[0], hit[1]
    key = (address or loc).lower()
    if key not in cache and address:
        a = address if re.search(r'\bTX\b', address) else address + ', Dallas, TX'
        cache[key] = census(a)
        time.sleep(1)
    at = cache.get(key)
    return venue, address, (at[0] if at else None), (at[1] if at else None)


events, seen_cals = {}, []
for cat, label in CALENDARS.items():
    text = get(FEED.format(cat))
    if not text or 'BEGIN:VCALENDAR' not in text:
        print(f'calendar {cat} ({label}): no feed')
        continue
    seen_cals.append(cat)
    kept = 0
    for ev in vevents(text):
        title = unescape(ev.get('SUMMARY', ('', ''))[0])
        if not title or DROP.search(title) or 'CANCEL' in ev.get('STATUS', ('', ''))[0].upper() or re.search(r'\bcancel', title, re.I):
            continue
        start = stamp(*ev['DTSTART']) if 'DTSTART' in ev else None
        end = stamp(*ev['DTEND']) if 'DTEND' in ev else None
        if not start or start[:10] > last.isoformat() or (end or start)[:10] < today.isoformat():
            continue
        if start[:10] < today.isoformat():
            start = today.isoformat()
        venue, address, lat, lng = place(unescape(ev.get('LOCATION', ('', ''))[0]))
        uid = re.sub(r'\D', '', ev.get('UID', ('', ''))[0]) or None
        item = {'id': 'dpr-' + (uid or title), 'title': title, 'venue': venue, 'address': address, 'lat': lat, 'lng': lng,
                'free': None, 'category': label, 'url': PAGE.format(uid) if uid else 'https://www.dallasparks.org/Calendar.aspx', 'src': 'parks'}
        if lat is None:
            item['area'] = 'unplaced'
        e = events.setdefault((title, venue or address), dict(item, times=[]))
        t = [start[:10], None] if len(start) == 10 else [start, end if end and len(end) == 16 and end > start else None]
        if t not in e['times']:
            e['times'].append(t)
        kept += 1
    print(f'calendar {cat} ({label}): {kept} times kept')
if not seen_cals:
    sys.exit('no calendar could be read; the last files stay up')
os.makedirs(os.path.dirname(CACHE), exist_ok=True)
json.dump(cache, open(CACHE, 'w'), indent=0, sort_keys=True)

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


head = {'version': 1, 'city': 'dallas', 'tz': 'America/Chicago', 'asof': now.strftime('%Y-%m-%dT%H:%M'), 'from': today.isoformat()}
tail = {'source': 'Dallas Park and Recreation', 'sources': ['parks'],
        'licence': 'City of Dallas content, used for non-commercial purposes (the City bars commercial use without permission).'}


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
print(f'Events page: {len(items)} events ({sum(e["lat"] is None for e in items)} unplaced, '
      f'{sum(1 for e in items if e["lat"] is not None and not e["hood"])} outside the city), {today} to {last}')
