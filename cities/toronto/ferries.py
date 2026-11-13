"""Build the Ferries layer (kind rail: ferry_lines, ferry_stations, ferry_lines_inner) from raw/ferries/tcl_ferry_routes.json
(fetch_ferries.py, the City's Toronto Centreline).

Four routes, each one line in its own colour, drawn from the mainland out to the island so the island docks are the
line ends: the City's three Toronto Island ferries from Jack Layton Ferry Terminal (Ward's Island, Centre Island,
Hanlan's Point) and PortsToronto's Billy Bishop Airport ferry across the Western Gap. The TCL splits each route into
segments joined at intersection ids; they're chained here from the terminal. Docks are the route ends; Jack Layton is
drawn as a hub. Seasons and timetables aren't in any open feed: city.json's layer note and the card text carry them,
and link to the City's schedule page. The inner file is the same lines (all in the city's waters)."""
import json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'ferries', 'tcl_ferry_routes.json')
DATA = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data')

# TCL name -> (line id, name shown, colour, operator, mainland dock, island dock).
ROUTES = {
    "Toronto-Ward's Island Ferry Route":   ('wards',   "Ward's Island ferry",  '#1B7F79', 'City of Toronto', 'Jack Layton Ferry Terminal', "Ward's Island"),
    'Toronto-Centre Island Ferry Route':   ('centre',  'Centre Island ferry',  '#1F6FB2', 'City of Toronto', 'Jack Layton Ferry Terminal', 'Centre Island'),
    "Toronto-Hanlan's Point Ferry Route":  ('hanlans', "Hanlan's Point ferry", '#4E5FB0', 'City of Toronto', 'Jack Layton Ferry Terminal', "Hanlan's Point"),
    'Island Airport Ferry Route':           ('airport', 'Billy Bishop Airport ferry', '#5D6B78', 'PortsToronto', 'Eireann Quay (airport ferry)', 'Billy Bishop Airport'),
}
TERMINAL = 'Jack Layton Ferry Terminal'

rows = json.load(open(RAW))['rows']
segs = defaultdict(list)
for r in rows:
    if r['LINEAR_NAME_FULL'] in ROUTES: segs[r['LINEAR_NAME_FULL']].append(r)
missing = set(ROUTES) - set(segs)
if missing: raise SystemExit('ferries: no TCL rows for ' + ', '.join(sorted(missing)))


def chain(parts):
    """Join a route's segments end to end into one line. Starts at the node only one segment touches whose position
    is furthest north (the mainland), so every route runs mainland -> island."""
    ends = defaultdict(list)
    for p in parts:
        ends[p['FROM_INTERSECTION_ID']].append(p); ends[p['TO_INTERSECTION_ID']].append(p)
    pos = {}
    for p in parts:
        c = p['geometry']['coordinates']
        pos[p['FROM_INTERSECTION_ID']] = c[0]; pos[p['TO_INTERSECTION_ID']] = c[-1]
    tips = [n for n, ps in ends.items() if len(ps) == 1]
    if len(tips) != 2: raise SystemExit('ferries: route is not one chain: %d ends' % len(tips))
    node = max(tips, key=lambda n: pos[n][1])
    line, used = [], set()
    while True:
        nxt = [p for p in ends[node] if p['CENTRELINE_ID'] not in used]
        if not nxt: break
        p = nxt[0]; used.add(p['CENTRELINE_ID'])
        c = p['geometry']['coordinates']
        if p['TO_INTERSECTION_ID'] == node: c = c[::-1]
        line += c if not line else c[1:]
        node = p['TO_INTERSECTION_ID'] if p['FROM_INTERSECTION_ID'] == node else p['FROM_INTERSECTION_ID']
    if len(used) != len(parts): raise SystemExit('ferries: %d of %d segments chained' % (len(used), len(parts)))
    out = [[round(x, 5), round(y, 5)] for x, y in line]
    return [c for i, c in enumerate(out) if i == 0 or c != out[i - 1]]


lines, docks = [], {}
for tcl, (lid, name, color, op, main, island) in ROUTES.items():
    coords = chain(segs[tcl])
    lines.append({'type': 'Feature', 'properties': {'line': 'ferry-' + lid, 'name': name, 'color': color, 'offset': 0, 'to': island, 'agency': op},
                  'geometry': {'type': 'LineString', 'coordinates': coords}})
    for dock, c in ((main, coords[0]), (island, coords[-1])):
        d = docks.setdefault(dock, {'type': 'Feature', 'properties': {'name': dock, 'lines': []}, 'geometry': {'type': 'Point', 'coordinates': c}})
        d['properties']['lines'].append(name if dock == island else island)   # island docks name their ferry; the mainland lists where it goes

# Every City route leaves from the same slip: one dock, drawn as the hub, listing where it goes.
docks[TERMINAL]['properties']['hub'] = True
docks[TERMINAL]['properties']['lines'] = ["Ward's Island", 'Centre Island', "Hanlan's Point"]
docks['Eireann Quay (airport ferry)']['properties']['lines'] = ['Billy Bishop Airport']
order = [TERMINAL, "Ward's Island", 'Centre Island', "Hanlan's Point", 'Eireann Quay (airport ferry)', 'Billy Bishop Airport']
stations = [docks[n] for n in order]
for n, fc in (('ferry_lines', lines), ('ferry_lines_inner', lines), ('ferry_stations', stations)):
    json.dump({'type': 'FeatureCollection', 'features': fc}, open(os.path.join(DATA, n + '.geojson'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('ferries:', len(lines), 'routes', [(f['properties']['name'], len(f['geometry']['coordinates'])) for f in lines], '·', len(stations), 'docks')
for s in stations: print('  ', s['properties']['name'], s['geometry']['coordinates'], s['properties']['lines'])
