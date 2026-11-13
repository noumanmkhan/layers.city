"""Melbourne's Transit under construction layer -> docs/melbourne/data/construction.geojson (the shape Toronto's,
New York's and Vancouver's use: one line per project, and its stations as points with part "station").
The Suburban Rail Loop East, Cheltenham to Box Hill: its route from OpenStreetMap (raw/more/osm_construction.json,
fetch_more.py; rail ways under construction whose name or operator is the Suburban Rail Loop), and the project's
facts in our own words from Victoria's Big Build pages (26 km of twin tunnels, six underground stations, trains
running by 2035). Stations are OSM's station nodes or station building sites; Box Hill, not yet mapped, is the line's northern end."""
import json, os, re
from shapely.geometry import LineString, Point, mapping
from shapely.ops import linemerge, unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'docs', 'melbourne', 'data')
els = json.load(open(os.path.join(HERE, 'raw', 'more', 'osm_construction.json')))['elements']
SRL = re.compile(r'Suburban Rail Loop|^SRL', re.I)
STATIONS = ['Cheltenham', 'Clayton', 'Monash', 'Glen Waverley', 'Burwood', 'Box Hill']


def srl(t): return SRL.search(t.get('name', '') + ' ' + t.get('operator', '') + ' ' + t.get('construction:name', ''))


lines, stations = [], {}
for e in els:
    t = e.get('tags', {})
    if not srl(t): continue
    if e['type'] == 'way' and (t.get('railway') == 'construction' or t.get('construction') in ('subway', 'rail', 'light_rail')) and e.get('geometry'):
        lines.append(LineString([(p['lon'], p['lat']) for p in e['geometry']]))
    # stations: nodes named "Cheltenham (Suburban Rail Loop)", else the station's building site ("... Clayton Station Site")
    txt = (t.get('name', '') + ' ' + t.get('note', '') + ' ' + t.get('description', '')).lower()
    st = (e['type'] == 'node' and '(suburban rail loop)' in txt) or 'station site' in txt
    if st:
        n = next((s for s in STATIONS if (s.lower() + ' (suburban rail loop)') in txt or (s.lower() + ' station site') in txt), None)
        if n and n not in stations:
            if e['type'] == 'node': stations[n] = (e['lon'], e['lat'])
            elif e.get('geometry'):
                g = e['geometry']; stations[n] = (sum(p['lon'] for p in g) / len(g), sum(p['lat'] for p in g) / len(g))
feats = []
if lines:
    # OSM maps both tunnels and the crossovers at each station box: draw one line, the shortest way along the mapped
    # track from the southern end (Cheltenham) to the northern end (Box Hill)
    import heapq
    segs = [s for s in getattr(unary_union(lines), 'geoms', [unary_union(lines)])]
    key = lambda c: (round(c[0], 6), round(c[1], 6))
    adj = {}
    for sg in segs:
        a, b = key(sg.coords[0]), key(sg.coords[-1])
        adj.setdefault(a, []).append((b, sg.length, list(sg.coords)))
        adj.setdefault(b, []).append((a, sg.length, list(sg.coords)[::-1]))
    deg1 = [n for n in adj if len(adj[n]) == 1] or list(adj)
    start = min(deg1, key=lambda c: c[1]); goal = max(deg1, key=lambda c: c[1])
    dist, prev, q = {start: 0}, {}, [(0, start)]
    while q:
        d, n = heapq.heappop(q)
        if n == goal: break
        if d > dist[n]: continue
        for m, w, cs in adj[n]:
            if d + w < dist.get(m, 1e9): dist[m] = d + w; prev[m] = (n, cs); heapq.heappush(q, (d + w, m))
    path, n = [], goal
    while n != start:
        n, cs = prev[n]; path = cs[:-1] + path if path else cs
    g = LineString(path).simplify(0.00005)
    if 'Box Hill' not in stations:   # no station mapped yet: the line's northern end is the Box Hill station box
        ends = [c for part in (getattr(g, 'geoms', None) or [g]) for c in (part.coords[0], part.coords[-1])]
        stations['Box Hill'] = max(ends, key=lambda c: c[1])
    rnd = lambda o: [rnd(v) for v in o] if isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]
    gm = mapping(g)
    feats.append({'type': 'Feature', 'properties': {'id': 'srl-east', 'name': 'Suburban Rail Loop East', 'short': 'SRL East', 'mode': 'subway',
        'color': '#00A6A6', 'owner': 'Suburban Rail Loop Authority (Victorian Government)', 'opens': 'Trains running by 2035 (Victoria’s Big Build)',
        'length': '26 km of twin tunnels, 6 stations',
        'about': 'An underground line from Cheltenham to Box Hill through Clayton, Monash University, Glen Waverley and Burwood, crossing the Frankston, Pakenham and Cranbourne, Glen Waverley and Belgrave and Lilydale lines without passing through the city.',
        'link': 'https://bigbuild.vic.gov.au/projects/suburban-rail-loop/srl-east'},
        'geometry': {'type': gm['type'], 'coordinates': rnd(gm['coordinates'])}})
for n in STATIONS:
    if n in stations:
        feats.append({'type': 'Feature', 'properties': {'part': 'station', 'id': 'srl-east', 'name': n},
                      'geometry': {'type': 'Point', 'coordinates': [round(stations[n][0], 5), round(stations[n][1], 5)]}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(DATA, 'construction.geojson'), 'w'), separators=(',', ':'))
print('construction:', len(lines), 'ways;', 'stations', sorted(stations), '; missing', [s for s in STATIONS if s not in stations])
