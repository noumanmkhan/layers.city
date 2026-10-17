"""Build docs/<city>/data/events.geojson: road closures for special events (races, parades, festivals,
block parties), from cities/<city>/raw/closures/events.json (written daily by the city's
fetch_closures.py) and the city's events.json.

What it does, in order:
  1. Keeps closures that haven't ended (the city's own time) and start within events.json "ahead" days.
  2. Groups them into events: by organizer (the permit's contractor), split where two days or more
     pass between one closure ending and the next starting, so an organizer's spring and fall races
     stay apart.
  3. Names each event from events.json "organizers", or else from its closure text ("closed for the
     Wyndham Street Block Party"), and works out its dates, the box that frames its closures, a link
     to the organizer's closure notice if the text has one, and whether it gets the map's banner.
  4. Drops duplicates (the same stretch, kind and times filed twice, once per direction).

Each closure keeps its own start and end time: race closures open and close in waves through the day.
Skips quietly (writes nothing) when the city has no events.json or no fetched events.

Usage: python3 engine/events.py <city>
"""
import json, os, re, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
city = sys.argv[1]
CDIR, DATA = os.path.join(ROOT, 'cities', city), os.path.join(ROOT, 'docs', city, 'data')
CFG_F, SRC_F = os.path.join(CDIR, 'events.json'), os.path.join(CDIR, 'raw', 'closures', 'events.json')
if not (os.path.isfile(CFG_F) and os.path.isfile(SRC_F)):
    print(city + ': no special events set up; skipped')
    sys.exit(0)
cfg, src = json.load(open(CFG_F)), json.load(open(SRC_F))
TZ = ZoneInfo(cfg['tz'])
now = datetime.now(TZ)
NOW, HORIZON = now.strftime('%Y-%m-%dT%H:%M'), (now + timedelta(days=cfg.get('ahead', 14))).strftime('%Y-%m-%dT%H:%M')
ORGS = cfg.get('organizers', {})
URL_RE = re.compile(r'https?://\S+')


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:40]


def name_from(descs):
    """'Road is temporarily closed for the Wyndham Street Halloween Eve Trick or Treat Block Party'
    -> 'Wyndham Street Halloween Eve Trick or Treat Block Party'. The commonest such phrase wins."""
    seen = {}
    for d in descs:
        m = re.search(r'(?:closed|blocked)\s+(?:due to|for)\s+(?:the\s+)?(.+?)(?:\s*[:.]?\s*https?://|[.:;]\s|[.:;]?$)', URL_RE.sub(' ', d).strip() + ' ')
        if m:
            n = m.group(1).strip(' .:;,')
            seen[n] = seen.get(n, 0) + 1
    return max(seen, key=seen.get) if seen else None


def clean(d):
    return re.sub(r'\s+', ' ', URL_RE.sub('', d)).strip(' :')


keep, dup = [], set()
for p in src['permits']:
    s, e = p.get('start') or '', p.get('end') or '9999'
    if e < NOW or s > HORIZON or not p.get('coords'):
        continue
    k = (json.dumps(p['coords']), p['kind'], s, e)
    if k in dup:
        continue
    dup.add(k)
    keep.append(p)

# Organizer, then runs of closures with less than two days between them.
by_org = {}
for p in keep:
    by_org.setdefault(p.get('who') or '', []).append(p)
groups = []
for org, ps in by_org.items():
    ps.sort(key=lambda p: p['start'] or '')
    run, last = [], None
    for p in ps:
        if run and last and (p['start'] or '') > (datetime.fromisoformat(last) + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'):
            groups.append((org, run)); run = []
        run.append(p)
        last = max(last or '', p['end'] or '')
    if run:
        groups.append((org, run))

events, feats = [], []
for org, ps in groups:
    o = ORGS.get(org, {})
    name = o.get('name') or name_from(p['desc'] for p in ps) or 'Special event'
    start, end = min(p['start'] for p in ps), max(p['end'] for p in ps)
    eid = slug(o.get('short') or name) + '-' + start[:10]
    xs = [c[0] for p in ps for c in p['coords']]
    ys = [c[1] for p in ps for c in p['coords']]
    notice = next((m.group(0).rstrip('.,)') for p in ps for m in [URL_RE.search(p['desc'] or '')] if m), None)
    ev = {'id': eid, 'name': name, 'short': o.get('short') or name, 'organizer': org or None,
          'start': start, 'end': end, 'closures': len(ps),
          'bounds': [[round(min(ys), 5), round(min(xs), 5)], [round(max(ys), 5), round(max(xs), 5)]],
          'banner': bool(o.get('banner', len(ps) >= cfg.get('bannerMin', 60))),
          'bannerFrom': (datetime.fromisoformat(start) - timedelta(days=cfg.get('lead', 3))).strftime('%Y-%m-%d')}
    if o.get('link'): ev['link'] = o['link']
    if notice: ev['notice'] = notice
    events.append(ev)
    for p in ps:
        c = p['coords']
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': c[0]} if len(c) == 1 else {'type': 'LineString', 'coordinates': c},
                      'properties': {'ev': eid, 'street': p['street'], 'extent': p['extent'], 'kind': p['kind'], 'both': p['both'],
                                     'start': p['start'], 'end': p['end'], 'desc': clean(p['desc'] or '')}})

events.sort(key=lambda e: (e['start'], -e['closures']))
out = {'type': 'FeatureCollection', 'asof': src['fetched'], 'today': now.strftime('%Y-%m-%d'), 'events': events, 'features': feats}
os.makedirs(DATA, exist_ok=True)
json.dump(out, open(os.path.join(DATA, 'events.geojson'), 'w'), separators=(',', ':'), ensure_ascii=False)
print(city + ':', len(feats), 'special-event closures in', len(events), 'events:',
      '; '.join('%s (%d, %s to %s%s)' % (e['name'], e['closures'], e['start'], e['end'], ', banner' if e['banner'] else '') for e in events))
