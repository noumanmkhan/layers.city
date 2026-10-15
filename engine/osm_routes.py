"""Bus routes from OpenStreetMap, for an agency whose own GTFS can't be used (Chicago's Pace offers its
GTFS "for non commercial use"; OSM is ODbL). Called by engine/fetch_surface.py for a feed whose
surface.json entry has "osm" instead of "gtfs", and writes the same routes.json and stops.json, so
engine/surface.py builds them like any other feed.

surface.json feed options:
  "osm": {"box": [south, west, north, east], "network": a regex matched against the route's network or
          operator tag, "ref": optional regex for route numbers to keep}
  "mode", "prefix", "simplify": as for a GTFS feed. "names": {"ref": "number to show"} renames a route
          number (e.g. "Pulse Dempster Line" -> "Pulse Dempster", shown without the prefix).

What OSM can't say: how often a route runs. Routes carry "day": true (shown with daytime routes) and no
trip counts, so the map gives no "every N min" and no families. School-trip and other part-time variants
are folded into their route's number. The sha is of the written output, so a week where nobody edited
the routes in OSM commits nothing."""
import datetime as dt, hashlib, json, os, re, time, urllib.parse, urllib.request
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge, unary_union

UA = {'User-Agent': 'city-layers-pipeline (layers.city; go@layers.city)'}
ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
STOP_ROLES = ('stop', 'platform')


def overpass(q):
    data = urllib.parse.urlencode({'data': q}).encode()
    for attempt in range(6):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=400) as r:
                return json.load(r)
        except Exception as e:
            print('  retry', attempt + 1, url, e); time.sleep(20 * (attempt + 1))
    raise SystemExit('Overpass request failed')


def metres(a, b):
    import math
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * 111320 * k, (a[1] - b[1]) * 110540)


def tidy_name(name, ref):
    # Route names as mappers write them: "Bus 208: Davis CTA Station => …", "Pace Bus Route 385: 87th-111th-127th
    # Streets", "Pace Bus: 250 Dempster Street". Keep what follows the number; drop school-trip and B-trip notes.
    n = re.sub(r'^(Pace\s+)?(Bus\s*)?(Route\s*)?:?\s*', '', (name or '').strip(), flags=re.I)
    n = re.sub(r'^(' + re.escape(ref) + r'|\d+[A-Z]?(-[A-Z])?)(\s*[:\-–]\s*|\s+(?=[A-Za-z]))', '', n)
    n = re.sub(r'\s*\((AM|PM)?[^)]*(school|trips?)[^)]*\)\s*$', '', n, flags=re.I)
    n = re.sub(r'\s+[AB] Trips$', '', n)
    return '' if re.fullmatch(r'(Bus\s*)?\d*', n, flags=re.I) else n


def run(cfg, out, city):
    o = cfg['osm']
    box = ','.join(map(str, o['box']))
    net = re.compile(o['network'], re.I)
    keep_ref = re.compile(o['ref']) if o.get('ref') else None
    q = f"""[out:json][timeout:360];
(relation["type"="route"]["route"="bus"]["network"~"{o['network']}",i]({box});
 relation["type"="route"]["route"="bus"]["operator"~"{o['network']}",i]({box}););
out geom;"""
    rels = [r for r in overpass(q).get('elements', [])
            if r['type'] == 'relation' and (net.search(r.get('tags', {}).get('network', '')) or net.search(r.get('tags', {}).get('operator', '')))]
    ids = ','.join(str(r['id']) for r in rels)
    extra = overpass(f"""[out:json][timeout:240];
relation(id:{ids})->.r;
node(r.r);
out;
rel(br.r)["type"="route_master"];
out tags;""").get('elements', []) if rels else []
    nodes = {e['id']: e for e in extra if e['type'] == 'node'}
    masters = [e for e in extra if e['type'] == 'relation']

    by_ref = {}
    for r in rels:
        ref = (r.get('tags', {}).get('ref') or '').strip()
        if not ref or (keep_ref and not keep_ref.fullmatch(ref)): continue
        by_ref.setdefault(ref, []).append(r)
    master_name = {}
    for m in masters:
        t = m.get('tags', {})
        if t.get('ref'): master_name[t['ref'].strip()] = t.get('name', '')

    names, prefix, tol = cfg.get('names', {}), cfg.get('prefix', ''), cfg.get('simplify', 0.0001)
    show = lambda ref: names.get(ref, prefix + ref)
    routes, stops, by_name = [], {}, {}
    for ref, rs in sorted(by_ref.items(), key=lambda kv: (len(kv[0]), kv[0])):
        # Each relation's ways merged into lines, longest relation first; surface.py keeps the first whole
        # and only the stretches of the others that run somewhere new.
        pieces = []
        for r in sorted(rs, key=lambda r: -sum(len(m.get('geometry', [])) for m in r.get('members', []))):
            ways = [LineString([(p['lon'], p['lat']) for p in m['geometry']]) for m in r.get('members', [])
                    if m['type'] == 'way' and m.get('role', '') in ('', 'forward', 'backward') and len(m.get('geometry', [])) > 1]
            if not ways: continue
            u = unary_union(ways)
            g = linemerge(u) if u.geom_type == 'MultiLineString' else u
            for l in sorted(getattr(g, 'geoms', [g]), key=lambda l: -l.length):
                s = l.simplify(tol)
                pieces.append({'dir': '0', 'share': 1.0, 'trips': 0, 'coords': [[round(x, 5), round(y, 5)] for x, y in s.coords]})
        if not pieces:
            print('  no ways in OSM, left out:', ref); continue
        # The name: the route master's, else the commonest pair of ends among its relations.
        nm = tidy_name(master_name.get(ref, ''), ref)
        if not nm or nm == ref:
            ends = [tidy_name(r['tags'].get('name', ''), ref) for r in rs]
            ends = [e for e in ends if e]
            nm = max(set(ends), key=ends.count) if ends else ''
            ends = re.split(r'\s*(?:=>|->|→|>)\s*', nm)
            nm = ends[0] + ' – ' + ends[-1] if len(ends) > 1 else nm   # first and last stop of a via-list
        routes.append({'id': ref, 'short': show(ref), 'long': nm, 'mode': cfg.get('mode', 'bus'), 'color': '', 'text': '',
                       'shapes': pieces, 'day': True, 'src': 'osm'})
        # Stops: member stop positions and platforms with a position; one per name within 60 m.
        for r in rs:
            for m in r.get('members', []):
                if m['type'] != 'node' or not m.get('role', '').startswith(STOP_ROLES): continue
                n = nodes.get(m['ref'])
                if not n or 'lon' not in n: continue
                name = n.get('tags', {}).get('name', '').strip()
                at = [round(n['lon'], 5), round(n['lat'], 5)]
                key = next((k for k in by_name.get(name, []) if name and metres(stops[k][2:4], at) < 60), None)
                if not key:
                    key = 'n' + str(n['id']); stops[key] = [key, name, at[0], at[1], []]; by_name.setdefault(name, []).append(key)
                s = stops[key]
                if show(ref) not in s[4]: s[4].append(show(ref))
    stop_list = [s for s in stops.values() if s[1]]   # an unnamed stop can't be named on the card
    for s in stop_list: s[4].sort(key=lambda x: (len(x), x))

    body = json.dumps([routes, stop_list], separators=(',', ':'), sort_keys=True)
    sha = hashlib.sha256(body.encode()).hexdigest()[:16]
    try:
        if json.load(open(os.path.join(out, 'routes.json'))).get('sha') == sha:
            print('routes unchanged in OSM (sha', sha + '); keeping the files from last time'); return
    except (OSError, ValueError):
        pass
    today = dt.date.today().isoformat()
    meta = {'source': 'OpenStreetMap contributors (ODbL) via Overpass API', 'sha': sha, 'fetched': today, 'week': today, 'days': {}}
    json.dump(dict(meta, routes=routes), open(os.path.join(out, 'routes.json'), 'w'), separators=(',', ':'))
    json.dump(dict(meta, stops=stop_list), open(os.path.join(out, 'stops.json'), 'w'), separators=(',', ':'))
    print(f'{city}: {len(routes)} routes from {len(rels)} OSM relations · {len(stop_list)} named stops '
          f'({len(stops) - len(stop_list)} unnamed left out)')
    for r in routes: print(f"  {r['short']:>16}  {r['long'][:60]:60}  pieces {len(r['shapes'])}")
