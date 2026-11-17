"""Dubai's rail and water transit layers (run after build.py and fetch_surface.py):
  - metro_lines / metro_stations: the Red and Green lines, from RTA's GTFS (raw/surface/rapid_*.json);
  - tram_lines / tram_stops: Dubai Tram (T1), from the same feed (raw/surface/routes.json, stops.json);
  - ferry_lines / ferry_stations / ferry_lines_inner: RTA's marine routes (abras, water buses, Dubai Ferry, the
    water taxi), straight from the GTFS zip (route type 4; engine/fetch_surface.py keeps trams and buses only);
  - rail_lines / rail_stations / rail_lines_inner: Etihad Rail's passenger line, from OpenStreetMap (raw/rail.geojson),
    and its one station in the city so far;
  - monorail_lines / monorail_stations: the Palm Jumeirah Monorail (private; not in RTA's feed), from OpenStreetMap;
  - raw/construction/osm.json: the Blue Line's ways under construction, for engine/construction.py.
Polylines go to tmp/ (simplified in run.sh); points to docs/dubai/data/."""
import csv, io, json, os, re, sys, zipfile
from collections import defaultdict
from shapely.geometry import shape, mapping, LineString, MultiLineString, Point
from shapely.ops import unary_union, linemerge

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, 'raw') + '/'
OUT = os.path.join(HERE, '..', '..', 'docs', 'dubai', 'data') + '/'
TMP = os.path.join(HERE, 'tmp') + '/'
KM = 101.0
fc = lambda feats: {'type': 'FeatureCollection', 'features': feats}
feat = lambda g, p: {'type': 'Feature', 'properties': p, 'geometry': mapping(g)}
pt = lambda c, p: {'type': 'Feature', 'properties': p, 'geometry': {'type': 'Point', 'coordinates': [round(c[0], 5), round(c[1], 5)]}}
dump = lambda n, f: json.dump(fc(f), open(TMP + n + '.geojson', 'w'), separators=(',', ':'), ensure_ascii=False)
write = lambda n, f: json.dump(fc(f), open(OUT + n + '.geojson', 'w'), separators=(',', ':'), ensure_ascii=False)
CITY = shape(next(f for f in json.load(open(TMP + 'base.geojson'))['features'] if f['properties']['kind'] == 'city')['geometry'])


def merged(gs, min_km=0.05):
    u = unary_union(gs)
    ls = [u] if u.geom_type == 'LineString' else [g for g in getattr(u, 'geoms', []) if g.geom_type == 'LineString']
    m = linemerge(ls) if len(ls) > 1 else ls[0]
    parts = [p for p in getattr(m, 'geoms', [m]) if p.length * KM > min_km]
    return MultiLineString(parts) if len(parts) > 1 else parts[0]


def ends_of(g):
    return [c for p in getattr(g, 'geoms', [g]) for c in (p.coords[0], p.coords[-1])]


near = lambda a, b, km: ((a[0] - b[0]) * KM) ** 2 + ((a[1] - b[1]) * 111.2) ** 2 < km * km

# ---------- Metro ----------
rr = json.load(open(R + 'surface/rapid_routes.json'))['routes']
rs = json.load(open(R + 'surface/rapid_stops.json'))['stops']
LINE = {'MRed1': 'red', 'MRed2': 'red', 'MGrn': 'green'}
NAME = {'red': 'Red Line', 'green': 'Green Line'}
FIX = {'centrepoint': 'Centrepoint', 'EXPO': 'Expo 2020', 'Burj Khalifa/ Dubai Mall': 'Burj Khalifa/Dubai Mall', 'Al Jadaf': 'Al Jaddaf'}
def stn(n):
    n = re.sub(r'(?i)\s+metro\s+station.*$', '', n).strip()
    n = re.sub(r'\s*\(.*$', '', n).strip()
    return FIX.get(n, n)
lines = defaultdict(list)
term = set()   # the first and last platforms of each line's busiest patterns: the end stations
for r in rr:
    for sh in r['shapes']:
        if sh['dir'] == '0': lines[LINE[r['short']]].append(LineString(sh['coords']))
        if sh['share'] > 0.5 and sh.get('stops'): term.update((sh['stops'][0], sh['stops'][-1]))
ml = {l: merged(gs) for l, gs in lines.items()}
dump('metro_lines', [feat(g, {'line': l, 'name': NAME[l]}) for l, g in ml.items()])
st = {}
for sid, n, x, y, routes, code in rs:
    v = st.setdefault(stn(n), {'pts': [], 'lines': set(), 'end': False})
    v['end'] |= sid in term
    v['pts'].append((x, y)); v['lines'].update(NAME[LINE[r]].replace(' Line', '') for r in routes if r in LINE)
ends = {l: ends_of(g) for l, g in ml.items()}
mf = []
for n, v in st.items():
    c = (sum(p[0] for p in v['pts']) / len(v['pts']), sum(p[1] for p in v['pts']) / len(v['pts']))
    p = {'name': n, 'lines': sorted(v['lines'], key=['Red', 'Green'].index)}
    if v['end']: p['terminus'] = True
    mf.append(pt(c, p))
write('metro_stations', mf)
print('metro', {l: round(g.length * KM, 1) for l, g in ml.items()}, 'km ·', len(mf), 'stations', sum('terminus' in f['properties'] for f in mf), 'ends')

# ---------- Tram ----------
sr = json.load(open(R + 'surface/routes.json'))['routes']
ss = json.load(open(R + 'surface/stops.json'))['stops']
t1 = next(r for r in sr if r['short'] == 'T1')
tl = merged([LineString(sh['coords']) for sh in t1['shapes']])
dump('tram_lines', [feat(tl, {'line': 't1', 'name': 'Dubai Tram'})])
ts = defaultdict(list)
for sid, n, x, y, routes, code in ss:
    if 'T1' in routes: ts[re.sub(r'\s*\d$', '', n).strip()].append((x, y))
tend = ends_of(tl)
write('tram_stops', [pt((sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)),
                        dict({'name': n, 'lines': ['T1']}, **({'terminus': True} if any(near(v[0], e, 0.4) for e in tend) else {})))
                     for n, v in ts.items()])
print('tram', round(tl.length * KM, 1), 'km ·', len(ts), 'stops')

# ---------- Marine (GTFS route type 4) ----------
z = zipfile.ZipFile(R + 'gtfs2026/Ops_GTFS_11-Sep-2026.zip')
def rows(n):
    with z.open(n) as f: yield from csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))
FAM = [('BM', 'abra', 'Abras', '#2C8C7E'), ('CR', 'abra', 'Abras', '#2C8C7E'), ('FR', 'ferry', 'Dubai Ferry', '#1F6FB2'),
       ('DC', 'taxi', 'Water taxi', '#7A4E9E')]
marine = {r['route_id']: r for r in rows('routes.txt') if r['route_type'] == '4'}
shape_of, trip_route = {}, {}
for t in rows('trips.txt'):
    if t['route_id'] in marine:
        shape_of.setdefault(t['route_id'], set()).add(t['shape_id']); trip_route[t['trip_id']] = t['route_id']
need = {s for v in shape_of.values() for s in v}
pts = defaultdict(list)
for r in rows('shapes.txt'):
    if r['shape_id'] in need: pts[r['shape_id']].append((int(r['shape_pt_sequence']), float(r['shape_pt_lon']), float(r['shape_pt_lat'])))
stops_of = defaultdict(set)
for r in rows('stop_times.txt'):
    rt = trip_route.get(r['trip_id'])
    if rt: stops_of[rt].add(r['stop_id'])
stop = {s['stop_id']: s for s in rows('stops.txt')}
fam_geo, fam_routes, fstn = defaultdict(list), defaultdict(list), {}
mclean = lambda n: re.sub(r'(?i)\s+(MTS|Marine (Transport )?(Stn|Station))\s*\d*$', '', n).strip()
for rid, r in marine.items():
    code = re.match(r'[A-Z]+', r['route_short_name']).group(0)
    fam = next(f for f in FAM if f[0] == code)
    for s in shape_of.get(rid, ()):
        c = [(x, y) for _, x, y in sorted(pts[s])]
        if len(c) > 1: fam_geo[fam[1:]].append(LineString(c))
    fam_routes[fam[1:]].append(r['route_short_name'])
    for sid in stops_of[rid]:
        s = stop[sid]; n = mclean(s['stop_name'])
        v = fstn.setdefault(n, {'pts': [], 'lines': set()})
        v['pts'].append((float(s['stop_lon']), float(s['stop_lat']))); v['lines'].add(fam[2])
TO = {'abra': 'Across and along the Creek, and in Dubai Marina', 'ferry': 'Al Ghubaiba, Dubai Canal, Dubai Marina and Sharjah',
      'taxi': 'On call along the coast and the canal'}
fl = []
for (key, name, color), gs in fam_geo.items():
    fl.append(feat(merged(gs, 0.02), {'line': 'ferry-' + key, 'name': name, 'color': color, 'offset': 0, 'to': TO[key],
                                       'agency': 'RTA', 'routes': sorted(set(fam_routes[(key, name, color)]))}))
dump('ferry_lines', fl)
dump('ferry_lines_inner', [f for f in fl])
write('ferry_stations', [pt((sum(p[0] for p in v['pts']) / len(v['pts']), sum(p[1] for p in v['pts']) / len(v['pts'])),
                            {'name': n, 'lines': sorted(v['lines'])}) for n, v in fstn.items()])
print('marine', {k[1]: sorted(set(v)) for k, v in fam_routes.items()}, '·', len(fstn), 'stations')

# ---------- Etihad Rail, the Palm Monorail, the Blue Line (OpenStreetMap) ----------
rail = json.load(open(R + 'rail.geojson'))['features']
nm = lambda p: p.get('name:en') or p.get('name') or ''
er = [shape(f['geometry']) for f in rail if f['properties'].get('railway') == 'rail' and nm(f['properties']) in ('Etihad Rail', 'Etihad Rail Sharjah Branch')]
eg = merged(er, 0.5)
ep = {'line': 'etihad', 'name': 'Etihad Rail', 'color': '#5B6770', 'offset': 0, 'agency': 'Etihad Rail',
      'to': 'Abu Dhabi, Al Dhaid and Fujairah; Sharjah from 2027'}
inner = eg.intersection(CITY.buffer(0.002))
dump('rail_lines', [feat(eg, ep)])
dump('rail_lines_inner', [feat(inner, ep)] if not inner.is_empty else [])
yal = next(f for f in rail if f['geometry']['type'] == 'Point' and nm(f['properties']) == 'Dubai Al Yalayis Station')
write('rail_stations', [pt(yal['geometry']['coordinates'], {'name': 'Dubai (Al Yalayis)', 'lines': ['Etihad Rail'], 'hub': True})])
print('Etihad Rail', round(eg.length * KM), 'km in the frame,', round(inner.length * KM, 1), 'in the city')

mono = [shape(f['geometry']) for f in rail if f['properties'].get('railway') == 'monorail' and nm(f['properties']) == 'Palm Jumeirah Monorail']
mg = merged(mono, 0.05)
dump('monorail_lines', [feat(mg, {'line': 'palm', 'name': 'Palm Monorail', 'color': '#B08A3E', 'offset': 0, 'agency': 'Palm Monorail',
                                  'to': 'Palm Gateway to Atlantis Aquaventure'})])
ms = [f for f in rail if f['geometry']['type'] == 'Point' and f['properties'].get('railway') in ('station', 'stop', 'halt')
      and Point(f['geometry']['coordinates']).distance(mg) < 0.0015 and nm(f['properties'])]
seen = {}
for f in ms: seen.setdefault(re.sub(r'(?i)\s+(monorail\s+)?station$', '', nm(f['properties'])), f['geometry']['coordinates'])
write('monorail_stations', [pt(c, {'name': n, 'lines': ['Palm Monorail']}) for n, c in seen.items()])
print('Palm Monorail', round(mg.length * KM, 1), 'km,', sorted(seen))

os.makedirs(R + 'construction', exist_ok=True)
els = []
for f in rail:
    p = f['properties']
    if p.get('railway') != 'construction' and not (p.get('railway') in ('station', 'stop') and 'construction' in json.dumps(p)): continue
    g = f['geometry']
    tags = {k: v for k, v in p.items() if not k.startswith('@') and not k.startswith('_')}
    if 'name:en' in tags: tags['name'] = tags['name:en']
    if g['type'] == 'LineString': els.append({'type': 'way', 'tags': tags, 'geom': g['coordinates']})
    elif g['type'] == 'Point': els.append({'type': 'node', 'tags': tags, 'lon': g['coordinates'][0], 'lat': g['coordinates'][1]})
json.dump({'source': 'OpenStreetMap via raw/rail.geojson (extract_osm.py)', 'elements': els}, open(R + 'construction/osm.json', 'w'), ensure_ascii=False)
print('construction ways and stations for engine/construction.py:', len(els))
