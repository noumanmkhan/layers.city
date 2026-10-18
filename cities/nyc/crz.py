"""Build docs/nyc/data/crz.geojson: the Congestion Relief Zone, Manhattan from 60th Street south, where drivers pay
the MTA's daily toll (since January 5, 2025). Drawn from the map's own Manhattan outline (raw/boroughs.geojson) cut
along 60th Street (the East and West 60th Street lines in docs/nyc/data/streets_ew.geojson, from build.py), the line
carried straight on to both rivers. The FDR Drive, the West Side Highway and the Battery Park Underpass are outside
the zone; they're too narrow to draw at this scale, so the card row mentions them."""
import json, os
from shapely.geometry import shape, mapping, Polygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'docs', 'nyc', 'data')
man = next(shape(f['geometry']) for f in json.load(open(os.path.join(HERE, 'raw', 'boroughs.geojson')))['features']
           if 'Manhattan' in json.dumps(f['properties']))
ew = {f['properties']['name']: f['geometry']['coordinates'] for f in json.load(open(os.path.join(DATA, 'streets_ew.geojson')))['features']}
w, e = min(ew['W 60th St']), max(ew['E 60th St'])     # the west end of W 60th, the east end of E 60th
dx, dy = e[0] - w[0], e[1] - w[1]
a, b = [w[0] - dx, w[1] - dy], [e[0] + dx, e[1] + dy]   # carried on past both rivers
south = Polygon([a, b, [b[0] + 0.3, b[1] - 0.6], [a[0] - 0.3, a[1] - 0.6]])   # everything south of the line
# Liberty, Ellis and Governors Islands are in Manhattan but not reached by car: left out.
zone = man.buffer(0).intersection(south).difference(Polygon([[-74.06, 40.66], [-74.02, 40.66], [-74.02, 40.705], [-74.06, 40.705]]))
zone = zone.difference(Polygon([[-74.03, 40.68], [-74.012, 40.68], [-74.012, 40.697], [-74.03, 40.697]]))
# Only Manhattan island itself: Roosevelt Island (reached from Queens) and the scraps of piers the borough line takes in are not in the zone.
zone = max(getattr(zone, 'geoms', [zone]), key=lambda p: p.area)
lp = zone.representative_point()
rnd = lambda o: [rnd(x) for x in o] if isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]
m = mapping(zone.simplify(0.00005, preserve_topology=True))
json.dump({'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'name': 'Congestion Relief Zone', 'lp': [round(lp.x, 5), round(lp.y, 5)]},
           'geometry': {'type': m['type'], 'coordinates': rnd(m['coordinates'])}}]}, open(os.path.join(DATA, 'crz.geojson'), 'w'), separators=(',', ':'))
print('crz:', round(zone.area * 84.4 * 111.2, 1), 'km²', os.path.getsize(os.path.join(DATA, 'crz.geojson')) // 1024, 'KB')
