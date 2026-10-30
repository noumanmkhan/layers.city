"""Fetch Hyderabad's map inputs into cities/hyderabad/raw/ (run in GitHub Actions: fetch-hyderabad.yml).
The sandbox can't reach these hosts. Every step is logged on its own, so one failure doesn't lose the rest.
Shapes are simplified (about 10 m) before saving, so the raw files stay small enough to commit.

- OpenStreetMap (Overpass): districts and mandals (admin levels 5 and 6, from the Telangana government's shapefiles),
  big lakes and reservoirs, motorways and trunk roads, main streets inside the ring road, the metro and MMTS, place
  names, landmark positions.
- OpenCity: the Department of Posts' 2025 PIN code boundaries (Hyderabad and Secunderabad, and all of India).
- DataMeet: assembly and Lok Sabha constituencies (2008 delimitation, still in force).
"""
import json, os, re, subprocess, sys, tempfile, time, traceback, urllib.parse, urllib.request, zipfile
from shapely.geometry import LineString, MultiLineString, Polygon, shape, mapping, box
from shapely.ops import polygonize, unary_union, linemerge

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from names import LANDMARKS, KNOWN_AS

RAW = os.path.join(HERE, 'raw'); os.makedirs(RAW, exist_ok=True)
TMP = tempfile.mkdtemp()
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}
S, W, N, E = 16.6, 77.2, 18.45, 79.2          # the four districts with a margin
BOX = '%s,%s,%s,%s' % (S, W, N, E)
CORE = '17.15,78.15,17.70,78.80'               # around the Outer Ring Road
FAILED = []


def step(label, fn):
    print('\n==', label, flush=True)
    try: fn()
    except Exception as e:
        print('FAILED', label, repr(e)); traceback.print_exc(); FAILED.append(label)


def get(url, data=None, tries=4, timeout=600):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, url[:120], e); time.sleep(20 * (i + 1))
    raise RuntimeError('failed: ' + url)


SERVERS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter',
           'https://maps.mail.ru/osm/tools/overpass/api/interpreter']


def overpass(q):
    for i in range(6):
        url = SERVERS[i % len(SERVERS)]
        try:
            d = json.loads(get(url, urllib.parse.urlencode({'data': '[out:json][timeout:900][maxsize:2000000000];' + q}).encode(), tries=1, timeout=960))
            print('  overpass ok', url.split('/')[2], len(d.get('elements', [])), 'elements')
            return d['elements']
        except Exception as e:
            print('  overpass', url.split('/')[2], 'try', i + 1, e); time.sleep(30)
    raise RuntimeError('overpass failed')


def save(name, obj):
    with open(os.path.join(RAW, name), 'w') as f:
        json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
    print('  wrote', name, os.path.getsize(os.path.join(RAW, name)) // 1000, 'KB')


def r5(g):
    return json.loads(json.dumps(mapping(g)), parse_float=lambda v: round(float(v), 5))


def rel_polygon(el):
    outer, inner = [], []
    for m in el.get('members', []):
        if m.get('type') != 'way' or not m.get('geometry'): continue
        line = LineString([(p['lon'], p['lat']) for p in m['geometry']])
        (inner if m.get('role') == 'inner' else outer).append(line)
    if not outer: return None
    g = unary_union(list(polygonize(unary_union(outer))))
    if inner:
        holes = list(polygonize(unary_union(inner)))
        if holes: g = g.difference(unary_union(holes))
    return g if not g.is_empty else None


way_line = lambda w: LineString([(p['lon'], p['lat']) for p in w['geometry']])


def admin():
    feats = []
    for lvl in ('5', '6'):
        for el in overpass('rel["boundary"="administrative"]["admin_level"="%s"](%s);out geom;' % (lvl, BOX)):
            t = el.get('tags', {})
            g = rel_polygon(el)
            if g is None: print('  no polygon:', t.get('name')); continue
            g = g.simplify(0.0001, preserve_topology=True)
            feats.append({'type': 'Feature', 'properties': {'osm': el['id'], 'level': int(lvl), 'name': t.get('name:en') or t.get('name'),
                          'name_te': t.get('name:te'), 'official': t.get('official_name'), 'wikidata': t.get('wikidata'),
                          'source': t.get('source'), 'edited': el.get('timestamp')}, 'geometry': r5(g)})
        print('  level', lvl, sum(1 for f in feats if f['properties']['level'] == int(lvl)))
    save('admin.geojson', {'type': 'FeatureCollection', 'features': feats})


def lakes():
    els = overpass('(way["natural"="water"](%s);rel["natural"="water"](%s);way["landuse"="reservoir"](%s);rel["landuse"="reservoir"](%s););out geom;' % (BOX, BOX, BOX, BOX))
    feats = []
    for el in els:
        t = el.get('tags', {})
        if t.get('water') in ('river', 'canal', 'stream', 'wastewater', 'pond', 'swimming_pool'): continue
        if el['type'] == 'way':
            pts = [(p['lon'], p['lat']) for p in el.get('geometry', [])]
            if len(pts) < 4 or pts[0] != pts[-1]: continue
            g = Polygon(pts).buffer(0)
        else:
            g = rel_polygon(el)
            if g is None: continue
        if g.area * 107 * 111 < 0.15: continue   # 0.15 km²: lakes and tanks, not ponds
        feats.append({'type': 'Feature', 'properties': {'name': t.get('name:en') or t.get('name') or '', 'osm': el['type'][0] + str(el['id'])},
                      'geometry': r5(g.simplify(0.0001, preserve_topology=True))})
    save('lakes.geojson', {'type': 'FeatureCollection', 'features': feats})


def roads():
    out = []
    for q, keep in (('way["highway"~"^(motorway|trunk)$"](%s);out geom;' % BOX, None),
                    ('way["highway"~"^(primary|secondary)$"]["name"](%s);out geom;' % CORE, None)):
        for el in overpass(q):
            if len(el.get('geometry', [])) < 2: continue
            t = el.get('tags', {})
            out.append({'type': 'Feature', 'properties': {'hw': t.get('highway'), 'name': t.get('name:en') or t.get('name'), 'ref': t.get('ref'),
                        'nat': t.get('nat_ref'), 'osm': el['id']}, 'geometry': r5(way_line(el).simplify(0.00004))})
    save('roads.geojson', {'type': 'FeatureCollection', 'features': out})


def rail():
    els = overpass('(rel["route"~"^(subway|light_rail)$"](%s);rel["route"="train"]["network"~"MMTS",i](%s);rel["route"="train"]["name"~"MMTS",i](%s););out geom;' % (CORE, BOX, BOX))
    routes, stop_ids = [], set()
    for el in els:
        t = el.get('tags', {})
        lines = [way_line(m) for m in el.get('members', []) if m['type'] == 'way' and m.get('geometry') and m.get('role', '') in ('', 'route', 'forward', 'backward')]
        stops = [m['ref'] for m in el.get('members', []) if m['type'] == 'node' and m.get('role', '').startswith('stop')]
        stop_ids.update(stops)
        if not lines: continue
        g = linemerge(unary_union(lines))
        routes.append({'id': el['id'], 'route': t.get('route'), 'name': t.get('name:en') or t.get('name'), 'ref': t.get('ref'),
                       'colour': t.get('colour'), 'network': t.get('network'), 'from': t.get('from'), 'to': t.get('to'),
                       'stops': stops, 'geometry': r5(g.simplify(0.00003))})
    nodes = {}
    if stop_ids:
        for i in range(0, len(stop_ids), 400):
            ids = ','.join(str(x) for x in list(stop_ids)[i:i + 400])
            for el in overpass('node(id:%s);out;' % ids):
                nodes[el['id']] = {'name': el.get('tags', {}).get('name:en') or el.get('tags', {}).get('name'), 'lon': el['lon'], 'lat': el['lat'],
                                   'tags': {k: v for k, v in el.get('tags', {}).items() if k in ('railway', 'public_transport', 'station', 'subway', 'train')}}
    stations = overpass('node["railway"="station"](%s);out;' % CORE)
    save('osm_rail.json', {'routes': routes, 'stops': nodes,
                           'stations': [{'id': e['id'], 'lon': e['lon'], 'lat': e['lat'], 'tags': e.get('tags', {})} for e in stations]})
    print('  routes', sorted({(r['route'], r['name']) for r in routes}))


def places():
    els = overpass('node["place"~"^(city|town|suburb|quarter|neighbourhood|locality|village|hamlet)$"](%s);out;' % BOX)
    save('osm_places.json', {'elements': [{'id': e['id'], 'lon': round(e['lon'], 5), 'lat': round(e['lat'], 5),
          'tags': {k: v for k, v in e.get('tags', {}).items() if k in ('name', 'name:en', 'name:te', 'name:ur', 'alt_name', 'place', 'wikidata')}} for e in els]})


def landmarks():
    names = sorted({l['osm'] for l in LANDMARKS} | {l['name'] for l in LANDMARKS})
    rx = '|'.join(re.escape(n) for n in names)
    els = overpass('nwr["name"~"^(%s)$"](%s);out center tags;' % (rx, BOX))
    save('osm_landmarks.json', {'elements': [{'type': e['type'], 'id': e['id'], 'lon': e.get('lon') or e.get('center', {}).get('lon'),
          'lat': e.get('lat') or e.get('center', {}).get('lat'), 'tags': {'name': e.get('tags', {}).get('name')}} for e in els]})


def ckan_resource_urls(package):
    d = json.loads(get('https://data.opencity.in/api/3/action/package_show?id=' + package))['result']
    return [(r.get('name'), r.get('url'), r.get('last_modified') or r.get('created')) for r in d['resources']]


def pincodes():
    feats, meta = [], []
    for package, want in (('india-pincode-maps-2025', r'(?i)hyderabad|all india'),):
        for name, url, mod in ckan_resource_urls(package):
            if not re.search(want, name or ''): continue
            print('  resource', name, mod, url)
            p = os.path.join(TMP, os.path.basename(urllib.parse.urlparse(url).path))
            open(p, 'wb').write(get(url))
            print('  size', os.path.getsize(p) // 1000, 'KB')
            src = '/vsizip/' + p if p.lower().endswith('.kmz') else p
            out = os.path.join(TMP, 'pin_%d.geojson' % len(meta))
            subprocess.run(['ogr2ogr', '-f', 'GeoJSON', '-t_srs', 'EPSG:4326', '-spat', str(W), str(S), str(E), str(N), '-nlt', 'PROMOTE_TO_MULTI', out, src], check=True)
            fs = json.load(open(out))['features']
            print('  features', len(fs), '· fields', sorted(fs[0]['properties']) if fs else [])
            if fs: print('  sample', {k: v for k, v in fs[0]['properties'].items() if v not in (None, '')})
            for f in fs:
                if not f.get('geometry'): continue
                g = shape(f['geometry']).buffer(0).simplify(0.0001, preserve_topology=True)
                if g.is_empty: continue
                feats.append({'type': 'Feature', 'properties': dict({k: v for k, v in f['properties'].items() if v not in (None, '') and k.lower() != 'description'},
                              _src=name), 'geometry': r5(g)})
            meta.append({'name': name, 'modified': mod, 'url': url, 'features': len(fs)})
    save('pincodes.geojson', {'type': 'FeatureCollection', 'sources': meta, 'features': feats})


def constituencies():
    base = 'https://raw.githubusercontent.com/datameet/maps/master/'
    area = box(W, S, E, N)
    for path, out in (('website/docs/data/geojson/ac.geojson', 'assembly.geojson'),
                      ('parliamentary-constituencies/india_pc_2019_simplified.geojson', 'loksabha.geojson')):
        fs = json.loads(get(base + path))['features']
        keep = [{'type': 'Feature', 'properties': f['properties'], 'geometry': r5(shape(f['geometry']).buffer(0).simplify(0.0001, preserve_topology=True))}
                for f in fs if f.get('geometry') and shape(f['geometry']).intersects(area)]
        save(out, {'type': 'FeatureCollection', 'features': keep})


if __name__ == '__main__':
    only = sys.argv[1:]
    for label, fn in (('admin', admin), ('lakes', lakes), ('roads', roads), ('rail', rail), ('places', places),
                      ('landmarks', landmarks), ('pincodes', pincodes), ('constituencies', constituencies)):
        if not only or label in only: step(label, fn)
    print('\nfailed:', FAILED or 'none')
