"""San Francisco's hazard zones and Bay ferries, from raw/extras/ (fetch_extras.py).
Writes into docs/sf/data/:
  tsunami.geojson        the State's tsunami hazard area for San Francisco, one shape (patches layer and card row)
  seismic.geojson        the State's seismic hazard zones (liquefaction and earthquake-induced landslide), joined
                         into one shape (patches layer and card row)
  ferry_lines.geojson, ferry_lines_inner.geojson, ferry_stations.geojson
                         the Bay's commuter ferries (San Francisco Bay Ferry, Golden Gate Ferry, the Treasure Island
                         Ferry), drawn from OpenStreetMap's ferry routes; seasonal ballpark and arena runs left out
Slow Streets go into the bike network (bikes.json "extra"), and soft-story buildings into the card's Nearby counts
(places.py), not here."""
import json, os, re
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping, LineString, MultiLineString, Point
from shapely.ops import unary_union, linemerge

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'extras')
DATA = os.path.join(HERE, '..', '..', 'docs', 'sf', 'data')
load = lambda n: json.load(open(os.path.join(RAW, n)))
rnd = lambda o: [rnd(x) for x in o] if isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]


def write(name, feats, **top):
    json.dump(dict({'type': 'FeatureCollection'}, **top, features=feats), open(os.path.join(DATA, name + '.geojson'), 'w'), separators=(',', ':'), ensure_ascii=False)


def poly_feat(g, props):
    g = g.simplify(0.00003, preserve_topology=True).buffer(0)
    m = mapping(g)
    lp = g.representative_point()
    return {'type': 'Feature', 'properties': dict(props, lp=[round(lp.x, 5), round(lp.y, 5)]), 'geometry': {'type': m['type'], 'coordinates': rnd(m['coordinates'])}}


city = next(shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(DATA, 'base.geojson')))['features'] if f['properties'].get('kind') == 'city')

# ---------- tsunami hazard area ----------
ts = unary_union([shape(f['geometry']).buffer(0) for f in load('tsunami.geojson')['features']]).intersection(city.buffer(0.002))
write('tsunami', [poly_feat(ts, {'name': 'Tsunami hazard area'})])
print('tsunami: %.1f km² of the city' % (ts.intersection(city).area * 111 * 88))

# ---------- seismic hazard zones ----------
se = unary_union([shape(f['geometry']).buffer(0) for f in load('seismic.geojson')['features'] if f.get('geometry')]).intersection(city.buffer(0.002))
write('seismic', [poly_feat(se, {'name': 'Seismic hazard zone'})])
print('seismic: %d shapes joined, %.1f km²' % (len(load('seismic.geojson')['features']), se.intersection(city).area * 111 * 88))

# ---------- Bay ferries ----------
KEEP = {'San Francisco Bay Ferry': ('ferry-sfbf', '#1F6FB2'), 'Golden Gate Ferry': ('ferry-ggf', '#B5382F'), 'Treasure Island Ferry': ('ferry-ti', '#2C8C7E')}
by = defaultdict(list)
for e in load('osm_ferries.json')['elements']:
    t = e.get('tags', {})
    if e['type'] != 'way' or 'geometry' not in e: continue
    net = t.get('network') or ''
    if net not in KEEP or re.search(r'(?i)seasonal|water shuttle', t.get('name', '')): continue
    by[net].append(LineString([(p['lon'], p['lat']) for p in e['geometry']]))
inner = city.buffer(0.01)
lines, lines_in = [], []
for net, gs in by.items():
    lid, col = KEEP[net]
    u = unary_union(gs)
    g = (linemerge(u) if u.geom_type == 'MultiLineString' else u).simplify(0.0002)
    p = {'line': lid, 'name': net, 'color': col, 'offset': 0, 'to': '', 'agency': net}
    lines.append({'type': 'Feature', 'properties': p, 'geometry': {'type': mapping(g)['type'], 'coordinates': rnd(mapping(g)['coordinates'])}})
    gi = g.intersection(inner)
    if not gi.is_empty: lines_in.append({'type': 'Feature', 'properties': p, 'geometry': {'type': mapping(gi)['type'], 'coordinates': rnd(mapping(gi)['coordinates'])}})
ends = {net: [Point(c) for g in gs for c in (g.coords[0], g.coords[-1])] for net, gs in by.items()}
st = {}
for e in load('osm_ferry_terminals.json')['elements']:
    n = (e.get('tags') or {}).get('name')
    c = e.get('center') or e
    if not n or c.get('lon') is None or re.search(r'(?i)alcatraz|red & white|gate \d|water shuttle', n): continue
    p = Point(c['lon'], c['lat'])
    nets = [net for net, pts in ends.items() if any(p.distance(q) * 100000 < 400 for q in pts)]
    if not nets: continue
    n = re.sub(r'\s+(Ferry\s+)?Terminal$', '', n)
    v = st.setdefault(n, {'pts': [], 'lines': set()})
    v['pts'].append((c['lon'], c['lat'])); v['lines'] |= set(nets)
stations = [{'type': 'Feature', 'properties': {'name': n, 'lines': sorted(v['lines'])},
             'geometry': {'type': 'Point', 'coordinates': [round(sum(x for x, _ in v['pts']) / len(v['pts']), 5), round(sum(y for _, y in v['pts']) / len(v['pts']), 5)]}} for n, v in st.items()]
write('ferry_lines', lines); write('ferry_lines_inner', lines_in); write('ferry_stations', stations)
print('ferries:', {f['properties']['name']: f['geometry']['type'] for f in lines}, '· terminals', sorted(st))
