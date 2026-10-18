"""Build the ferries layer (kind rail: ferry_lines, ferry_stations, ferry_lines_inner) from raw/ferries/ (fetch_ferries.py):
NYC Ferry's routes (not its Rockaway shuttle buses) and the Staten Island Ferry, each route one line in its own colour from the GTFS, drawn along
its longest shape; landings as stations, each with the routes that call there. The inner file is the same lines
(they're all in the city's waters)."""
import csv, io, json, os, zipfile
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'raw', 'ferries')
DATA = os.path.join(HERE, '..', '..', 'docs', 'nyc', 'data')
LABEL = {'SIF': 'Staten Island Ferry'}


def table(z, n):
    return list(csv.DictReader(io.TextIOWrapper(z.open(n), encoding='utf-8-sig'))) if n in z.namelist() else []


lines, stations = [], {}
for name in ('nycferry', 'siferry'):
    with zipfile.ZipFile(os.path.join(SRC, name + '.zip')) as z:
        routes = {r['route_id'].strip(): r for r in table(z, 'routes.txt')}
        stops = {s['stop_id'].strip(): s for s in table(z, 'stops.txt')}
        trips = table(z, 'trips.txt')
        shapes = defaultdict(list)
        for p in table(z, 'shapes.txt'):
            shapes[p['shape_id'].strip()].append((int(p['shape_pt_sequence']), round(float(p['shape_pt_lon']), 5), round(float(p['shape_pt_lat']), 5)))
        stops_of = defaultdict(set)
        trip_route = {t['trip_id'].strip(): t['route_id'].strip() for t in trips}
        for st in table(z, 'stop_times.txt'):
            r = trip_route.get(st['trip_id'].strip())
            if r: stops_of[r].add(st['stop_id'].strip())
        for rid, r in routes.items():
            if (r.get('route_type') or '').strip() != '4': continue   # boats only: NYC Ferry's feed also has its free Rockaway shuttle buses
            shp = {t.get('shape_id', '').strip() for t in trips if t['route_id'].strip() == rid} - {''}
            pts = max((sorted(shapes[s]) for s in shp if s in shapes), key=len, default=None)
            if not pts: print('  no shape for', rid); continue
            long = (r.get('route_long_name') or '').strip()
            nm = LABEL.get(rid) or ('NYC Ferry ' + long + ' route' if name == 'nycferry' else long)
            color = '#' + (r.get('route_color') or 'FF8330').strip().lstrip('#')
            ends = [stops[s]['stop_name'].strip() for s in stops_of[rid] if s in stops]
            lines.append({'type': 'Feature', 'properties': {'line': 'ferry-' + rid.lower(), 'name': nm, 'color': color, 'offset': 0,
                                                            'to': '', 'agency': 'NYC Ferry' if name == 'nycferry' else 'NYC DOT'},
                          'geometry': {'type': 'LineString', 'coordinates': [[x, y] for _, x, y in pts]}})
            short = 'Staten Island Ferry' if rid == 'SIF' else long
            for s in stops_of[rid]:
                if s not in stops: continue
                k = stops[s]['stop_name'].strip()
                st = stations.setdefault(k, {'type': 'Feature', 'properties': {'name': k, 'lines': []},
                                             'geometry': {'type': 'Point', 'coordinates': [round(float(stops[s]['stop_lon']), 5), round(float(stops[s]['stop_lat']), 5)]}})
                if short not in st['properties']['lines']: st['properties']['lines'].append(short)

# A landing on four or more routes is drawn as a hub.
for s in stations.values():
    s['properties']['lines'].sort()
    if len(s['properties']['lines']) >= 4: s['properties']['hub'] = True
for n, fc in (('ferry_lines', lines), ('ferry_lines_inner', lines), ('ferry_stations', list(stations.values()))):
    json.dump({'type': 'FeatureCollection', 'features': fc}, open(os.path.join(DATA, n + '.geojson'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('ferries:', len(lines), 'routes', [f['properties']['name'] for f in lines], '·', len(stations), 'landings')
