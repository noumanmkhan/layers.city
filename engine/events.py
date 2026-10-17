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


def trace(street, a_re, b_re):
    """Coordinates along `street` (a centreline name) between where it meets a street matching a_re and
    one matching b_re, the shortest way along the street. None if either corner can't be found."""
    import heapq
    if not cfg.get('streets'):
        return None
    if not hasattr(trace, 'segs'):
        sj = json.load(open(os.path.join(CDIR, cfg['streets'])))
        trace.segs = [f for fc in (sj.values() if 'features' not in sj else [sj]) for f in fc['features']
                      if f['geometry']['type'] == 'LineString']
    key = lambda c: (round(c[0], 5), round(c[1], 5))
    own, graph = set(), {}
    for f in trace.segs:
        if f['properties'].get('LINEAR_NAME_FULL') != street:
            continue
        cs = [key(c) for c in f['geometry']['coordinates']]
        own.update(cs)
        for u, v in zip(cs, cs[1:]):
            d = ((u[0] - v[0]) * 0.72) ** 2 + (u[1] - v[1]) ** 2   # 0.72: cos(latitude) near 43.7
            graph.setdefault(u, []).append((v, d ** .5)); graph.setdefault(v, []).append((u, d ** .5))

    def corners(rx):
        r = re.compile(rx)
        pts = {key(c) for f in trace.segs if r.search(f['properties'].get('LINEAR_NAME_FULL') or '')
               for c in f['geometry']['coordinates']}
        hit = own & pts
        if hit or not pts:
            return hit
        # No shared node: the street's nearest node to the cross street, if within about 40 m.
        best = min(((((n[0] - q[0]) * 0.72) ** 2 + (n[1] - q[1]) ** 2, n) for n in own for q in pts), default=None)
        return {best[1]} if best and best[0] ** .5 < 0.00036 else set()

    A, B = corners(a_re), corners(b_re)
    if not A or not B:
        return None
    best = None
    for s in A:
        dist, prev, pq = {s: 0}, {}, [(0, s)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, 9e9):
                continue
            if u in B:
                if best is None or d < best[0]:
                    path = [u]
                    while path[-1] in prev:
                        path.append(prev[path[-1]])
                    best = (d, path[::-1])
                break
            for v, w in graph.get(u, []):
                if d + w < dist.get(v, 9e9):
                    dist[v], prev[v] = d + w, u
                    heapq.heappush(pq, (d + w, v))
    return [list(c) for c in best[1]] if best and len(best[1]) > 1 else None


def corrected(permits):
    """Apply events.json "corrections": per organizer, rules that retime or drop the feed's closures
    (matched by the closure's start, optionally its street and how far north it lies; first match wins),
    then stretches the feed leaves out, traced along the street centrelines. Each changed or added
    closure says so in its text. A correction stops applying at its "until" time."""
    out = list(permits)
    for fx in cfg.get('corrections', []):
        if fx.get('until') and fx['until'] <= NOW:
            continue
        res, changed, dropped = [], 0, 0
        for p in out:
            if p.get('who') != fx['who']:
                res.append(p); continue
            rule = next((r for r in fx.get('rules', [])
                         if (not r.get('start') or r['start'] == p.get('start'))
                         and (not r.get('street') or re.search(r['street'], p.get('street') or ''))
                         and (r.get('minLat') is None or min(c[1] for c in p['coords']) >= r['minLat'])), None)
            if not rule:
                res.append(p); continue
            if rule.get('drop'):
                dropped += 1; continue
            q = dict(p, **rule.get('set', {}))
            if fx.get('note'):
                q['desc'] = ((p.get('desc') or '').rstrip() + ' ' + fx['note']).strip()
            res.append(q); changed += 1
        added, missed = 0, []
        for a in fx.get('add', []):
            cs = trace(a['street'], a['from'], a['to'])
            if not cs:
                missed.append(a['extent']); continue
            res.append({'who': fx['who'], 'street': a['street'], 'extent': a['extent'], 'kind': a.get('kind', 'closed'),
                        'both': a.get('both', True), 'start': a['start'], 'end': a['end'], 'coords': cs,
                        'desc': fx.get('addedNote', '')})
            added += 1
        print(city + ': corrections for %s: %d retimed, %d dropped, %d added%s' % (
            fx['who'], changed, dropped, added, ('; not found: ' + '; '.join(missed)) if missed else ''))
        out = res
    return out


keep, dup = [], set()
for p in corrected(src['permits']):
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
