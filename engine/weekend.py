"""The weekend brief: what's closed and what's on this weekend, for the iOS app (DATA_CONTRACT.md section 14).

Usage:  python3 engine/weekend.py <city>
Reads (each optional; a city with none of them gets no file):
  cities/<city>/raw/closures/subway.json   planned rapid transit closures (Toronto: fetch_subway_alerts.py)
  docs/<city>/data/events.geojson          special-event road closures (engine/events.py)
  cities/<city>/raw/closures/major.json    full closures of expressways and major arterials (fetch_closures.py)
  cities/<city>/venues.json + raw/venue_events.json   big venues and what's on at them (Venues)
Writes: docs/<city>/data/weekend.json

The weekend is Friday 5 p.m. to Sunday midnight in the city's time zone: the coming one from Monday to
Thursday, the current one from Friday to Sunday. Rebuilt daily, so it is always the next weekend.

Fixed ranking, so the brief never needs editing by hand (APP_BRIEF.md: "trust over coverage"):
  Closed: rapid transit closures first, then special events by number of closures, then full closures
          of expressways before major arterials. At most 5.
  On:     events at the venues, biggest venue first (capacity in venues.json), one line per show even when
          it repeats (repeats become "Fri–Sun" or "3 shows"). Season passes, upsells and parking left out.
          At most 5. Facts only: names, venues, times and a link to the venue's page on layers.city.
"""
import json, math, os, re, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: weekend.py <city>')
CITY = os.path.join(ROOT, 'cities', city)
DATA = os.path.join(ROOT, 'docs', city, 'data')
MAX = 5
SKIP = re.compile(r'season pass|upsell|parking|does not include a ticket|gift card|voucher', re.I)
DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def load(*p):
    path = os.path.join(*p)
    return json.load(open(path, encoding='utf-8')) if os.path.isfile(path) else None


cfg = json.load(open(os.path.join(CITY, 'city.json'), encoding='utf-8'))
tz_name = next((l.get('tz') for _, ls in cfg.get('groups', []) for l in ls if l.get('tz')), None) \
    or (cfg.get('card', {}).get('pickup') or {}).get('tz')
if not tz_name:
    print('%s: no time zone in city.json; no weekend.json' % city)
    sys.exit(0)
TZ = ZoneInfo(tz_name)

now = datetime.now(TZ)
if len(sys.argv) > 2:                      # a date to build for, for testing: weekend.py toronto 2026-10-21
    now = datetime.fromisoformat(sys.argv[2]).replace(tzinfo=TZ)
fri = (now - timedelta(days=now.weekday() - 4)) if now.weekday() >= 4 else now + timedelta(days=4 - now.weekday())
start = fri.replace(hour=17, minute=0, second=0, microsecond=0)
end = (start + timedelta(days=2)).replace(hour=23, minute=59)
W0, W1 = start.strftime('%Y-%m-%dT%H:%M'), end.strftime('%Y-%m-%dT%H:%M')


def overlaps(a, b):
    return (a or '0000') <= W1 and (b or '9999') >= W0


def ampm(t):
    h, m = int(t[11:13]), int(t[14:16])
    s = '%d%s %s' % (h % 12 or 12, (':%02d' % m) if m else '', 'a.m.' if h < 12 else 'p.m.')
    return 'noon' if (h, m) == (12, 0) else 'midnight' if (h, m) == (0, 0) else s


def day(t):
    return DAYS[datetime.fromisoformat(t[:10]).weekday()]


def span(a, b):
    """'Sat–Sun', 'Sat 9 a.m.–5 p.m.', 'All weekend', clipped to the weekend."""
    a, b = max(a or W0, W0), min(b or W1, W1)
    if a <= W0 and b >= W1[:10] + 'T23:00':
        return 'All weekend'
    d0, d1 = day(a), day(b)
    if d0 == d1:
        return '%s %s–%s' % (d0, ampm(a), ampm(b))
    return '%s–%s' % (d0, d1)


def km(a, b):
    (x1, y1), (x2, y2) = a, b
    return math.hypot((x2 - x1) * 111.32 * math.cos(math.radians((y1 + y2) / 2)), (y2 - y1) * 110.57)


closed, on, sources = [], [], []

# 1. Rapid transit closures.
sub = load(CITY, 'raw', 'closures', 'subway.json')
if sub is not None:
    sources.append('subway')
    for c in sub.get('closures', []):
        if not overlaps(c['start'], c['end']):
            continue
        early = 'early' in c['effect'].lower()
        closed.append({'kind': 'transit', 'rank': 0,
                       'title': '%s · %s to %s' % (re.sub(r'^(Line \d+).*', r'\1', c['name']), c['from'], c['to']),
                       'line': ('Closes early at night' if early else 'No service') + (' · shuttle buses' if c['shuttle'] else ''),
                       'when': span(c['start'], c['end']), 'start': c['start'], 'end': c['end'], 'text': c['text']})

# 2. Special-event road closures.
ev = load(DATA, 'events.geojson')
if ev is not None:
    sources.append('events')
    for e in ev.get('events', []):
        if not overlaps(e['start'], e['end']):
            continue
        (s, w), (n, x) = e['bounds']
        closed.append({'kind': 'event', 'rank': 1, 'size': e.get('closures', 0),
                       'title': e.get('short') or e['name'],
                       'line': '%d road closure%s' % (e.get('closures', 0), '' if e.get('closures') == 1 else 's'),
                       'when': span(e['start'], e['end']), 'start': e['start'], 'end': e['end'],
                       'at': [round((w + x) / 2, 5), round((s + n) / 2, 5)], 'link': e.get('notice') or e.get('link')})

# 3. Full closures of expressways and major arterials, one item per street.
maj = load(CITY, 'raw', 'closures', 'major.json')
if maj is not None:
    sources.append('roads')
    by_street = {}
    for p in maj.get('permits', []):
        if p.get('kind') != 'closed' or not overlaps(p['start'], p['end']) or not p.get('street'):
            continue
        by_street.setdefault(p['street'], []).append(p)
    for street, ps in by_street.items():
        ps.sort(key=lambda p: p['start'] or '')
        expressway = any('express' in str(p.get('roadClass') or '').lower() for p in ps)
        p = ps[0]
        mid = p['coords'][len(p['coords']) // 2]
        closed.append({'kind': 'road', 'rank': 2 if expressway else 3, 'size': len(ps),
                       'title': street, 'line': p['extent'] if len(ps) == 1 else '%d stretches closed' % len(ps),
                       'when': span(min(x['start'] for x in ps), max(x['end'] or W1 for x in ps)),
                       'start': p['start'], 'end': max(x['end'] or W1 for x in ps), 'at': mid})

closed.sort(key=lambda c: (c['rank'], -c.get('size', 0), c['start'] or ''))
closed = closed[:MAX]

# 4. What's on at the big venues.
venues = load(CITY, 'venues.json')
listing = load(CITY, 'raw', 'venue_events.json')
if venues and listing:
    sources.append('venues')
    vmap = {v['slug']: v for v in venues.get('venues', [])}
    shows = {}
    for slug, evs in (listing.get('venues') or {}).items():
        v = vmap.get(slug)
        if not v:
            continue
        for e in evs:
            t = '%sT%s' % (e['date'], e.get('time') or '19:00')
            if not (W0[:10] <= e['date'] <= W1[:10]) or (e['date'] == W0[:10] and t < W0[:10] + 'T12:00'):
                continue
            if e.get('kind') == 'other' or SKIP.search(e['name']) or e.get('status') in ('cancelled', 'canceled'):
                continue
            name = e['name'].split(' | ')[-1].strip()      # "CHAMPIONSHIP CELEBRATION GAME | Marlies vs. …"
            shows.setdefault((slug, name), []).append(t)
    for (slug, name), ts in shows.items():
        v = vmap[slug]
        ts.sort()
        days = sorted({day(t) for t in ts}, key=DAYS.index)
        when = '%s %s' % (days[0], ampm(ts[0])) if len(ts) == 1 else \
            ('%s–%s' % (days[0], days[-1]) if len(days) > 1 else '%s · %d shows' % (days[0], len(ts)))
        on.append({'title': name, 'venue': v['name'], 'slug': slug, 'when': when, 'start': ts[0], 'shows': len(ts),
                   'capacity': v.get('capacity') or 0, 'at': v.get('at'),
                   'link': 'https://layers.city/%s/venues/%s/' % (city, slug)})
    on.sort(key=lambda o: (-o['capacity'], o['start']))
    # Keep the list varied: at most two shows from one venue.
    seen, kept = {}, []
    for o in on:
        if seen.get(o['slug'], 0) < 2:
            kept.append(o)
            seen[o['slug']] = seen.get(o['slug'], 0) + 1
    on = kept[:MAX]
    for o in on:
        o.pop('capacity')

if not sources:
    print('%s: no weekend sources; no weekend.json' % city)
    sys.exit(0)
for c in closed:
    c.pop('rank', None)
    c.pop('size', None)

label = '%s %d–%d' % (start.strftime('%b'), start.day, end.day) if start.month == end.month else \
    '%s %d – %s %d' % (start.strftime('%b'), start.day, end.strftime('%b'), end.day)
out = {'version': 1, 'city': city, 'tz': tz_name, 'asof': datetime.now(TZ).strftime('%Y-%m-%dT%H:%M'),
       'weekend': {'from': W0, 'to': W1, 'label': label}, 'sources': sources, 'closed': closed, 'on': on}
json.dump(out, open(os.path.join(DATA, 'weekend.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('%s weekend %s: %d closed, %d on (%s)' % (city, label, len(closed), len(on), ', '.join(sources)))
