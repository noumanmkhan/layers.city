"""Fetch What's On Melbourne's events and write docs/melbourne/data/happening.json (today through the next 14 days,
placed events only, for "Happening nearby" on the card and in the iOS app; contract section 16) and
docs/melbourne/events/events.json (30 days, for the Events page, engine/events_page.py). Same shapes as the other
cities' fetch_happening.py. Run daily from GitHub Actions (*Fetch events*); the sandbox can't reach the site.

Source: What's On Melbourne (whatson.melbourne.vic.gov.au), the City of Melbourne's own listings of events in the
City. Its terms (/disclaimer): the content is the Council's, "no part may be reproduced or reused for any commercial
purposes"; nothing restricts automated access, and the site runs a public MCP server for agents. Non-commercial use,
so it's in NONCOMMERCIAL.md and marked on the Attributions page.
- The list: the MCP server's search_tool (https://whatson.melbourne.vic.gov.au/mcp, no key), category things_to_do,
  sub-category "events", the next 30 days. It gives each listing's title, address and first and last dates only.
- Each event's own page (/things-to-do/<slug>) gives its sessions (the "Dates and times" table: every day it's on,
  with its times or "All day"), its place (the page's schema.org Event: venue name and street address) and its
  tags (meta "tags": "Free", "Music", "Family and kids"...). Pages are kept in raw/whatson/items.json and fetched
  again only when the listing's dates change or the copy is three days old, one a second.
- Places: the venue's name matched to a place the map already has (landmarks, parks, libraries and community
  centres, the Venues list), else the street address placed with Vicmap Address (CC BY 4.0, as fetch_voting.py
  does: a number on a street, or the corner of two). Kept in raw/whatson/places.json. An event with no place
  (online, or "around the city") is kept for the Events page only.
No descriptions, images, prices or contacts: a title, its times, its place, Free when the page says so, one category
and the link.

Usage: python3 cities/melbourne/fetch_happening.py [--today YYYY-MM-DD]
"""
import html, json, os, re, sys, time, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DOCS = os.path.join(HERE, '..', '..', 'docs', 'melbourne')
RAW = os.path.join(HERE, 'raw', 'whatson'); os.makedirs(RAW, exist_ok=True)
SITE = 'https://whatson.melbourne.vic.gov.au'
UA = 'layers.city (non-commercial civic map; https://layers.city/)'
TZ = ZoneInfo('Australia/Melbourne')
DAYS, PAGE_DAYS = 14, 30
OUT = os.path.join(DOCS, 'data', 'happening.json')
PAGE_OUT = os.path.join(DOCS, 'events', 'events.json')
ITEMS = os.path.join(RAW, 'items.json')
PLACES = os.path.join(RAW, 'places.json')

args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
now = datetime.now(TZ)
today = date.fromisoformat(args['--today']) if '--today' in args else now.date()
last, last14 = today + timedelta(days=PAGE_DAYS), today + timedelta(days=DAYS)


def http(url, body=None, headers=None, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={'User-Agent': UA, **(headers or {})}, method='POST' if body else 'GET')
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode('utf-8', 'replace'), r.headers
        except Exception as ex:
            if i == tries - 1: raise
            print('  retry', url[:80], ex); time.sleep(5 * (i + 1))


# --- the list, from the MCP server ---
session, rid = None, 0


def rpc(method, params=None, note=False):
    global session, rid
    rid += 1
    body = {'jsonrpc': '2.0', 'method': method, **({} if note else {'id': rid}), **({'params': params} if params is not None else {})}
    h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    if session: h['Mcp-Session-Id'] = session
    raw, hd = http(SITE + '/mcp', json.dumps(body).encode(), h)
    session = hd.get('Mcp-Session-Id') or session
    if note: return None
    if 'event-stream' in hd.get('Content-Type', ''):
        datas = [l[5:].strip() for l in raw.splitlines() if l.startswith('data:')]
        raw = datas[-1] if datas else '{}'
    return json.loads(raw)


def listing():
    rpc('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {}, 'clientInfo': {'name': 'layers.city', 'version': '1.0'}})
    try: rpc('notifications/initialized', note=True)
    except Exception: pass
    out, page, pages = {}, 1, 1
    while page <= pages and page <= 80:
        res = rpc('tools/call', {'name': 'search_tool', 'arguments': {
            'query': '', 'category': 'things_to_do', 'sub_categories': ['events'], 'date_keyword': 'specific_dates',
            'date_range': f'{today} to {last}', 'page_number': page}})
        text = ''.join(c.get('text', '') for c in res['result']['content'])
        m = re.search(r'Page: \d+ of (\d+)', text)
        pages = int(m.group(1)) if m else pages
        for block in re.split(r'\n(?=\d+\. )', text):
            u = re.search(r'URL: (/things-to-do/[^\s]+)', block)
            if not u: continue
            title = re.match(r'\d+\. (.+)', block.strip()).group(1).strip()
            sd = re.search(r'Start Date: (\d{4}-\d\d-\d\d)', block); ed = re.search(r'End Date: (\d{4}-\d\d-\d\d)', block)
            out[u.group(1)] = {'title': title, 'start': sd and sd.group(1), 'end': ed and ed.group(1)}
        page += 1
        time.sleep(1)
    print(f'listing: {len(out)} events over {pages} pages')
    return out


# --- each event's own page ---
MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}


def clock(t):
    """'4.15pm' -> '16:15'."""
    m = re.match(r'(\d{1,2})(?:[.:](\d\d))?\s*(am|pm|noon)?', t.strip().lower())
    if not m: return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == 'pm' and h < 12: h += 12
    if ap == 'am' and h == 12: h = 0
    return f'{h:02d}:{mi:02d}' if h < 24 and mi < 60 else None


def day_of(text):
    """'Thu 10 Dec' -> the date in the year that puts it nearest today."""
    m = re.search(r'(\d{1,2})\s+([A-Za-z]{3})', text)
    if not m or m.group(2).lower() not in MONTHS: return None
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try: d = date(y, MONTHS[m.group(2).lower()], int(m.group(1)))
        except ValueError: continue
        if best is None or abs((d - today).days) < abs((best - today).days): best = d
    return best


def strip(s): return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).strip()


def parse(page):
    ld = {}
    for blk in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try: j = json.loads(blk, strict=False)
        except ValueError: continue
        if isinstance(j, dict) and j.get('@type') == 'Event': ld = j; break
    loc = ld.get('location') or {}
    if isinstance(loc, list): loc = loc[0] if loc else {}
    addr = loc.get('address') or {}
    if isinstance(addr, str): addr = {'streetAddress': addr}
    tags = re.search(r'<meta name="tags" content="([^"]*)"', page)
    tags = [html.unescape(t).strip() for t in tags.group(1).split(',')] if tags else []
    times = []
    tab = re.search(r'<table id="date-times-table".*?</table>', page, re.S)
    if tab:
        for row in re.findall(r'<tr[^>]*>(.*?)</tr>', tab.group(0), re.S):
            th = re.search(r'<th[^>]*>(.*?)</th>', row, re.S); td = re.search(r'<td[^>]*>(.*?)</td>', row, re.S)
            if not th or not td: continue
            d = day_of(strip(th.group(1)))
            if not d: continue
            lis = re.findall(r'<li[^>]*>(.*?)</li>', td.group(1), re.S) or [td.group(1)]
            for li in lis:
                shown = re.search(r'<span aria-hidden="true">(.*?)</span>', li, re.S)
                t = strip(shown.group(1) if shown else re.sub(r'<span class="sr-only">.*?</span>', '', li, flags=re.S))
                parts = [clock(x) for x in re.split(r'\s*[-–]\s*', t) if x.strip()]
                if not parts or parts[0] is None:
                    times.append([d.isoformat(), None])            # "All day", or a time we can't read
                else:
                    e = parts[1] if len(parts) > 1 and parts[1] else None
                    times.append([f'{d}T{parts[0]}', f'{d}T{e}' if e and e > parts[0] else None])
    return {'name': ld.get('name'), 'venue': (loc.get('name') or '').strip() or None,
            'online': loc.get('@type') == 'VirtualLocation',
            'street': addr.get('streetAddress'), 'locality': addr.get('addressLocality'), 'pc': addr.get('postalCode'),
            'start': (ld.get('startDate') or '')[:10] or None, 'end': (ld.get('endDate') or '')[:10] or None,
            'tags': tags, 'times': times, 'free': 'Free' in tags or 'This is a free event' in page}


# --- places ---
def centre(g):
    c = g['coordinates']
    if g['type'] == 'Point': return c[:2]
    pts = []
    def walk(x):
        if isinstance(x[0], (int, float)): pts.append(x)
        else:
            for y in x: walk(y)
    walk(c if g['type'] != 'MultiPolygon' else [p[0] for p in c])
    return [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]


def norm(s): return re.sub(r'[^a-z0-9]+', ' ', re.sub(r'^the ', '', (s or '').lower())).strip()


KNOWN = {}
for f, key in (('landmarks', 'name'), ('parks', 'n'), ('community', 'name'), ('institutions', 'name')):
    try:
        for ft in json.load(open(os.path.join(DOCS, 'data', f + '.geojson')))['features']:
            p = ft['properties']
            for n in [p.get(key)] + [a for a in (p.get('aliases') or []) if len(a) > 5]:
                if n: KNOWN.setdefault(norm(n), centre(ft['geometry']))
    except (OSError, KeyError, ValueError) as ex: print('  places from', f, ex)
try:
    for v in json.load(open(os.path.join(HERE, 'venues.json')))['venues']:
        if v.get('at'):
            for n in [v.get('name')] + (v.get('tm') or []):
                if n: KNOWN.setdefault(norm(n), v['at'][:2])
except (OSError, KeyError, ValueError) as ex: print('  places from venues.json', ex)

places = json.load(open(PLACES)) if os.path.exists(PLACES) else {}
vic = None


# Street words as Vicmap spells them, for the shortened ones What's On uses.
ROADS = {'st': 'Street', 'ln': 'Lane', 'rd': 'Road', 'ave': 'Avenue', 'av': 'Avenue', 'pl': 'Place', 'prom': 'Promenade',
         'dr': 'Drive', 'pde': 'Parade', 'tce': 'Terrace', 'cres': 'Crescent', 'blvd': 'Boulevard', 'esp': 'Esplanade',
         'hwy': 'Highway', 'sq': 'Square'}
ROAD_WORDS = r'(?:St|Street|Ln|Lane|Rd|Road|Ave|Av|Avenue|Pl|Place|Prom|Promenade|Dr|Drive|Pde|Parade|Tce|Terrace|Cres|Crescent|Blvd|Boulevard|Esp|Esplanade|Hwy|Highway|Alley|Arcade|Walk|Way|Square|Sq)'


def street_line(street):
    """'Rm 5 Level 8/37 Swanston St' -> '37 Swanston Street'; 'Swanston St & Flinders St' -> 'corner of ...'; a street
    with no number stays a street ('Flinders Ln' -> 'Flinders Lane'); None when no street is in it."""
    t = street.replace('&amp;', '&')
    if '&' in t or ' and ' in t:
        a, b = re.split(r'\s*(?:&|\band\b)\s*', t, 1)
        a, b = street_line(a), street_line(b)
        return f'corner of {a} and {b}' if a and b and not a.startswith('corner') else None
    t = re.sub(r'\bS(?= [A-Z][a-z])', 'South', re.sub(r'\bN(?= [A-Z][a-z])', 'North', t))
    name = r"((?:[A-Za-z'./]+\s+)*?[A-Za-z'./]+)\s+(" + ROAD_WORDS + r")\b"
    m = re.search(r"(?:^|[\s/,])(\d+[A-Za-z]?(?:-\d+[A-Za-z]?)?)\s+" + name, t)
    if m: return f"{m.group(1)} {m.group(2)} {ROADS.get(m.group(3).lower(), m.group(3))}"
    m = re.search(name, t.split(',')[-1].strip() or t.split(',')[0])
    return f"{m.group(1)} {ROADS.get(m.group(2).lower(), m.group(2))}" if m else None


# Places What's On names with no street (its address is just "Melbourne"), as a street line Vicmap can place.
NAMED = {'city square': 'corner of Swanston Street and Collins Street'}


def known(*names):
    for n in names:
        k = norm(n)
        if not k: continue
        if k in KNOWN: return KNOWN[k]
        hit = max((x for x in KNOWN if len(x) >= 8 and (k.startswith(x + ' ') or k == x)), key=len, default=None)
        if hit: return KNOWN[hit]
    return None


def place_of(it):
    if it['online']: return None
    k = '|'.join(str(it.get(x) or '') for x in ('venue', 'street', 'locality', 'pc'))
    if places.get(k): return places[k]
    v, st = it['venue'] or '', it['street'] or ''
    got = known(v, v.split(',')[0], v.split(' (')[0], re.split(r'\s+[-–]\s+', v)[0], st.split(',')[0])
    if got: got = [round(got[0], 6), round(got[1], 6), 'known']
    line = NAMED.get(norm(v)) or (street_line(st) if st else None)
    if not got and line:
        global vic
        try:
            from fetch_voting import address_layer, place
            if vic is None: vic = address_layer()[0]
            loc = it['locality'] if it['locality'] and it['locality'] != 'Victoria' else 'Melbourne'
            got = place(vic, line, loc, it['pc'] or '')
        except Exception as ex:
            print('  vicmap', k, ex)
            return None          # try again tomorrow
    places[k] = got
    return got


# --- run ---
try:
    lst = listing()
except Exception as ex:
    sys.exit(f'What\'s On listing failed: {ex!r}; the last files stay up')
if len(lst) < 20:
    sys.exit(f'only {len(lst)} events listed; the last files stay up')

items = json.load(open(ITEMS)) if os.path.exists(ITEMS) else {}
fetched = 0
for url, L in lst.items():
    old = items.get(url)
    stale = not old or old.get('list') != [L['start'], L['end']] or old.get('at', '') < (today - timedelta(days=3)).isoformat()
    if not stale: continue
    try:
        page, _ = http(SITE + url)
        items[url] = {**parse(page), 'list': [L['start'], L['end']], 'at': today.isoformat(), 'title': L['title']}
        fetched += 1
    except Exception as ex:
        print('  page', url, ex)
    time.sleep(1)
    if fetched % 50 == 0 and fetched:
        print(f'  {fetched} pages'); json.dump(items, open(ITEMS, 'w'), ensure_ascii=False, indent=0, sort_keys=True)
items = {u: v for u, v in items.items() if u in lst}           # keep only what's listed now
json.dump(items, open(ITEMS, 'w'), ensure_ascii=False, indent=0, sort_keys=True)
print(f'pages: {fetched} fetched, {len(items)} kept')

# One category per event: the first of these its tags carry (the site's own words, some shortened).
CATS = [('Festival', 'Festival'), ('Music', 'Music'), ('Theatre', 'Theatre'), ('Comedy', 'Comedy'), ('Dance', 'Dance'),
        ('Cabaret', 'Theatre'), ('Film', 'Film'), ('Exhibition', 'Exhibition'), ('Art', 'Art'), ('Design', 'Art'),
        ('Market', 'Market'), ('Talks and workshops', 'Talk or workshop'), ('Workshop', 'Talk or workshop'),
        ('Learning', 'Talk or workshop'), ('Talk', 'Talk or workshop'), ('Tour', 'Tour'), ('Tours and cruises', 'Tour'),
        ('Walking tour', 'Tour'), ('Cruise', 'Tour'), ('Sport', 'Sport'), ('Fitness', 'Sport'),
        ('Food and drink', 'Food and drink'), ('Family and kids', 'Family and kids'), ('Community', 'Community'),
        ('Wellbeing', 'Community'), ('Activity', 'Community'), ('Nightlife', 'Nightlife'), ('Entertainment', 'Entertainment')]

events = []
for url, it in items.items():
    times = it['times']
    if not times:     # no sessions table: a one-day listing is that day; a longer one is each day of its run
        s, e = it.get('start') or it['list'][0], it.get('end') or it['list'][1]
        if s:
            d0, d1 = date.fromisoformat(s), date.fromisoformat(e or s)
            times = [[(d0 + timedelta(days=i)).isoformat(), None] for i in range((d1 - d0).days + 1)]
    times = sorted({tuple(t) for t in times if today.isoformat() <= t[0][:10] <= last.isoformat()})
    if not times: continue
    p = place_of(it)
    cat = next((label for tag, label in CATS if tag in it['tags']), None)
    events.append({'id': 'wom-' + url.rsplit('/', 1)[-1], 'title': html.unescape(it.get('name') or it['title']).strip(),
                   'venue': it['venue'], 'address': it['street'], 'lat': p[1] if p else None, 'lng': p[0] if p else None,
                   'free': bool(it['free']), 'category': cat, 'url': SITE + url, 'src': 'whatson',
                   'times': [list(t) for t in times], **({'area': 'online'} if it['online'] else {})})
json.dump(places, open(PLACES, 'w'), ensure_ascii=False, indent=0, sort_keys=True)
events.sort(key=lambda e: (e['times'][0][0], e['title']))
from collections import Counter
print('placed:', Counter(v[2] if v else None for v in places.values()), '; unplaced venues:',
      sorted({e['venue'] or '-' for e in events if e['lat'] is None})[:40])


def ring_has(ring, x, y):
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


HOODS = []
for f in json.load(open(os.path.join(DOCS, 'data', 'suburbs.geojson')))['features']:
    g = f['geometry']; polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
    HOODS.append((f['properties']['name'], polys))


def hood_of(lng, lat):
    for name, polys in HOODS:
        for p in polys:
            if ring_has(p[0], lng, lat) and not any(ring_has(h, lng, lat) for h in p[1:]): return name
    return None


head = {'version': 1, 'city': 'melbourne', 'tz': 'Australia/Melbourne', 'asof': now.strftime('%Y-%m-%dT%H:%M'), 'from': today.isoformat()}
tail = {'source': "What's On Melbourne (City of Melbourne)", 'sources': ['whatson'],
        'licence': "© City of Melbourne; non-commercial use (whatson.melbourne.vic.gov.au/disclaimer)."}


def write(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':')); f.write('\n')


near = [{**e, 'times': [t for t in e['times'] if t[0][:10] <= last14.isoformat()]} for e in events if e['lat'] is not None]
near = [e for e in near if e['times']]
write(OUT, {**head, 'to': last14.isoformat(), **tail, 'events': near})
print(f'{len(near)} events at {len({(e["lat"], e["lng"]) for e in near})} places, {today} to {last14}')
for e in events:
    e['hood'] = hood_of(e['lng'], e['lat']) if e['lat'] is not None else None
write(PAGE_OUT, {**head, 'to': last.isoformat(), **tail, 'events': events})
print(f'Events page: {len(events)} events ({sum(e["lat"] is None for e in events)} with no place, '
      f'{sum(1 for e in events if e["lat"] is not None and not e["hood"])} outside the City), {today} to {last}')
