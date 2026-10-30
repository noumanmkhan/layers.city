"""Fetch Hyderabad's OpenStreetMap inputs into cities/hyderabad/raw/ (GitHub Actions: fetch-hyderabad.yml).
Reads Geofabrik's daily extract of southern India (the public Overpass servers time out on queries this size), cut to
the four districts with osmium, then walks it with pyosmium. Shapes are simplified (about 10 m) before saving.

Writes: admin.geojson (districts, mandals), lakes.geojson, roads.geojson, osm_rail.json (metro and MMTS routes and
their stops), osm_places.json, osm_landmarks.json."""
import json, os, re, subprocess, sys, tempfile, time, urllib.request
import osmium
from shapely import wkb
from shapely.geometry import LineString, Point, mapping, box
from shapely.ops import linemerge, unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from names import LANDMARKS

RAW = os.path.join(HERE, 'raw'); os.makedirs(RAW, exist_ok=True)
TMP = tempfile.mkdtemp()
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}
S, W, N, E = 16.6, 77.2, 18.45, 79.2          # the four districts with a margin
CORE = box(78.15, 17.15, 78.80, 17.70)          # around the Outer Ring Road
LAKE_BOX = box(77.75, 16.95, 78.95, 18.0)
SOURCES = ['https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf',
           'https://download.geofabrik.de/asia/india-latest.osm.pbf']
PLACE_KINDS = {'city', 'town', 'suburb', 'quarter', 'neighbourhood', 'locality', 'village', 'hamlet'}
LM_NAMES = {l['osm'] for l in LANDMARKS} | {l['name'] for l in LANDMARKS}
fab = osmium.geom.WKBFactory()


def download():
    for url in SOURCES:
        p = os.path.join(TMP, os.path.basename(url))
        for i in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=1800) as r, open(p, 'wb') as f:
                    while True:
                        b = r.read(1 << 22)
                        if not b: break
                        f.write(b)
                print('downloaded', url, os.path.getsize(p) // 1_000_000, 'MB', flush=True)
                return p
            except Exception as e:
                print('  retry', i + 1, url, e); time.sleep(30)
    raise RuntimeError('no extract')


def save(name, obj):
    with open(os.path.join(RAW, name), 'w') as f:
        json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
    print('wrote', name, os.path.getsize(os.path.join(RAW, name)) // 1000, 'KB', flush=True)


def r5(g):
    return json.loads(json.dumps(mapping(g)), parse_float=lambda v: round(float(v), 5))


tag = lambda t, k: t.get(k) if k in t else None
en = lambda t: tag(t, 'name:en') or tag(t, 'name')


class Pass1(osmium.SimpleHandler):
    """Areas (admin boundaries, lakes), roads, places, stations, landmark points, and the route relations."""
    def __init__(self):
        super().__init__()
        self.admin, self.lakes, self.roads, self.places, self.lm, self.routes, self.stations = [], [], [], [], [], [], []

    def node(self, n):
        t = n.tags
        if not n.location.valid(): return
        x, y = n.location.lon, n.location.lat
        if t.get('place') in PLACE_KINDS and 'name' in t:
            self.places.append({'id': n.id, 'lon': round(x, 5), 'lat': round(y, 5),
                                'tags': {k: t[k] for k in ('name', 'name:en', 'name:te', 'name:ur', 'alt_name', 'place', 'wikidata') if k in t}})
        if t.get('name') in LM_NAMES:
            self.lm.append({'type': 'node', 'id': n.id, 'lon': x, 'lat': y, 'tags': {'name': t['name']}})
        if t.get('railway') == 'station' and CORE.contains(Point(x, y)):
            self.stations.append({'id': n.id, 'lon': x, 'lat': y, 'tags': {k: v for k, v in [(k, t[k]) for k in ('name', 'name:en', 'station', 'subway', 'train', 'network', 'operator') if k in t]}})

    def way(self, w):
        t = w.tags
        hw = t.get('highway')
        if hw in ('motorway', 'trunk', 'primary', 'secondary'):
            try: g = wkb.loads(fab.create_linestring(w), hex=True)
            except Exception: return
            if hw in ('primary', 'secondary') and (not t.get('name') or not CORE.intersects(g)): return
            self.roads.append({'type': 'Feature', 'properties': {'hw': hw, 'name': en(t), 'ref': tag(t, 'ref'), 'nat': tag(t, 'nat_ref'), 'osm': w.id},
                               'geometry': r5(g.simplify(0.00004))})
        if t.get('name') in LM_NAMES:
            try:
                c = wkb.loads(fab.create_linestring(w), hex=True).centroid
                self.lm.append({'type': 'way', 'id': w.id, 'lon': c.x, 'lat': c.y, 'tags': {'name': t['name']}})
            except Exception: pass

    def area(self, a):
        t = a.tags
        if t.get('name') in LM_NAMES:
            try:
                c = wkb.loads(fab.create_multipolygon(a), hex=True).representative_point()
                self.lm.append({'type': 'area', 'id': a.orig_id(), 'lon': c.x, 'lat': c.y, 'tags': {'name': t['name']}})
            except Exception: pass
        lvl = t.get('admin_level') if t.get('boundary') == 'administrative' else None
        water = t.get('natural') == 'water' or t.get('landuse') == 'reservoir'
        if not (lvl in ('5', '6') and not a.from_way()) and not water: return
        if water and t.get('water') in ('river', 'canal', 'stream', 'wastewater', 'pond', 'swimming_pool'): return
        try: g = wkb.loads(fab.create_multipolygon(a), hex=True).buffer(0)
        except Exception: return
        if lvl in ('5', '6') and not a.from_way():
            self.admin.append({'type': 'Feature', 'properties': {'osm': a.orig_id(), 'level': int(lvl), 'name': en(t), 'name_te': tag(t, 'name:te'),
                               'official': tag(t, 'official_name'), 'wikidata': tag(t, 'wikidata'), 'source': tag(t, 'source')},
                               'geometry': r5(g.simplify(0.0001, preserve_topology=True))})
        elif water and g.area * 107 * 111 >= 0.15 and LAKE_BOX.intersects(g):
            self.lakes.append({'type': 'Feature', 'properties': {'name': en(t) or '', 'osm': ('w' if a.from_way() else 'r') + str(a.orig_id())},
                               'geometry': r5(g.simplify(0.0001, preserve_topology=True))})

    def relation(self, r):
        t = r.tags
        route = t.get('route')
        mmts = route == 'train' and re.search(r'(?i)mmts', ' '.join(t.get(k, '') for k in ('network', 'name', 'operator', 'ref')))
        if route in ('subway', 'light_rail') or mmts:
            self.routes.append({'id': r.id, 'route': route, 'name': en(t), 'ref': tag(t, 'ref'), 'colour': tag(t, 'colour'),
                                'network': tag(t, 'network'), 'from': tag(t, 'from'), 'to': tag(t, 'to'),
                                'ways': [m.ref for m in r.members if m.type == 'w' and m.role in ('', 'route', 'forward', 'backward')],
                                'stops': [m.ref for m in r.members if m.type == 'n' and m.role.startswith('stop')]})


class Pass2(osmium.SimpleHandler):
    """The route relations' ways and stop nodes."""
    def __init__(self, ways, nodes):
        super().__init__()
        self.want_w, self.want_n, self.ways, self.nodes = ways, nodes, {}, {}

    def node(self, n):
        if n.id in self.want_n and n.location.valid():
            self.nodes[n.id] = {'name': en(n.tags), 'lon': n.location.lon, 'lat': n.location.lat}

    def way(self, w):
        if w.id in self.want_w:
            try: self.ways[w.id] = wkb.loads(fab.create_linestring(w), hex=True)
            except Exception: pass


if __name__ == '__main__':
    src = download()
    cut = os.path.join(TMP, 'hyderabad.osm.pbf')
    subprocess.run(['osmium', 'extract', '-b', '%s,%s,%s,%s' % (W, S, E, N), '-s', 'smart', '-o', cut, '--overwrite', src], check=True)
    print('extract', os.path.getsize(cut) // 1_000_000, 'MB', flush=True)
    h = Pass1()
    h.apply_file(cut, locations=True)
    print('admin', len(h.admin), '· lakes', len(h.lakes), '· roads', len(h.roads), '· places', len(h.places), '· routes', len(h.routes), flush=True)
    h2 = Pass2({w for r in h.routes for w in r['ways']}, {n for r in h.routes for n in r['stops']})
    h2.apply_file(cut, locations=True)
    routes = []
    for r in h.routes:
        ls = [h2.ways[w] for w in r.pop('ways') if w in h2.ways]
        if not ls: continue
        r['geometry'] = r5(linemerge(unary_union(ls)).simplify(0.00003))
        routes.append(r)
    print('routes', sorted({(r['route'], r['name']) for r in routes}))
    save('admin.geojson', {'type': 'FeatureCollection', 'features': h.admin})
    save('lakes.geojson', {'type': 'FeatureCollection', 'features': h.lakes})
    save('roads.geojson', {'type': 'FeatureCollection', 'features': h.roads})
    save('osm_rail.json', {'routes': routes, 'stops': {str(k): v for k, v in h2.nodes.items()}, 'stations': h.stations})
    save('osm_places.json', {'elements': h.places})
    save('osm_landmarks.json', {'elements': h.lm})
    print('source', os.path.basename(src))
