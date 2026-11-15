"""Fetch the basemap for a city's region beyond (and including) the city from OpenStreetMap via the Overpass API,
into cities/<city>/raw/region_basemap/. Usage: python3 engine/region/fetch_basemap.py <city>
The area and tiling come from cities/<city>/region.json ("bbox": [S, W, N, E], optional "tiles": {"roads": [nx, ny], ...}).
Run from GitHub Actions (fetch-region-basemap.yml): Overpass can't be reached from most sandboxes.

  roads.json    arterials and collectors: highway=trunk|primary|secondary|tertiary (no ramps), with name and ref
  parks.json    leisure=park|nature_reserve and boundary=protected_area, as polygons
  landuse.json  residential, commercial/retail, industrial, farmland, woods, cemeteries, quarries

One city kept its own copy before this existed; new cities use this one.
Multipolygon relations are assembled into polygons here (shapely), so raw/ holds plain [lng, lat] rings.
The area is fetched in tiles, one request at a time (Overpass rejects bursts), and deduplicated by OSM id."""
import json, math, os, sys, time, urllib.parse, urllib.request
from shapely.geometry import LineString, Polygon, MultiPolygon, mapping
from shapely.ops import linemerge, polygonize, unary_union

CITY = sys.argv[1]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'cities', CITY)
CFG = json.load(open(os.path.join(ROOT, 'region.json')))
OUT = os.path.join(ROOT, 'raw', 'region_basemap')
S, W, N, E = CFG['bbox']
TILES = dict({'roads': [2, 2], 'parks': [2, 2], 'landuse': [3, 3]}, **CFG.get('tiles', {}))
ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
M2 = 111_320 ** 2 * math.cos(math.radians((S + N) / 2))   # m² per degree² here
UA = {'User-Agent': 'layers.city-pipeline (go@layers.city)'}


def tiles(nx, ny):
    for i in range(nx):
        for j in range(ny):
            yield (round(S + (N - S) * j / ny, 4), round(W + (E - W) * i / nx, 4),
                   round(S + (N - S) * (j + 1) / ny, 4), round(W + (E - W) * (i + 1) / nx, 4))


def overpass(body):
    data = urllib.parse.urlencode({'data': '[out:json][timeout:600];' + body}).encode()
    for attempt in range(8):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=900) as r:
                return json.load(r)
        except Exception as e:
            print('  retry', attempt + 1, url, e, flush=True)
            time.sleep(20 * (attempt + 1))
    raise SystemExit('Overpass request failed')


def fetch(name, filters, nx, ny):
    """Every element matching the filters, over the area in nx*ny tiles, keyed by type/id."""
    els = {}
    for b in tiles(nx, ny):
        bb = '(%s,%s,%s,%s)' % b
        q = '(' + ''.join(f + bb + ';' for f in filters) + ');out tags geom;'
        res = overpass(q)
        for el in res.get('elements', []):
            els[el['type'] + str(el['id'])] = el
        print(' ', name, b, len(res.get('elements', [])), 'elements', flush=True)
        time.sleep(5)
    return list(els.values())


R5 = lambda c: [round(c[0], 5), round(c[1], 5)]


def poly_of(el):
    """A closed way or a multipolygon relation as a shapely (Multi)Polygon, or None."""
    if el['type'] == 'way':
        g = el.get('geometry') or []
        if len(g) < 4 or (g[0]['lat'], g[0]['lon']) != (g[-1]['lat'], g[-1]['lon']):
            return None
        p = Polygon([(q['lon'], q['lat']) for q in g])
        return p.buffer(0) if not p.is_valid else p
    outer, inner = [], []
    for m in el.get('members', []):
        if m.get('type') != 'way' or not m.get('geometry'):
            continue
        ls = LineString([(q['lon'], q['lat']) for q in m['geometry']]) if len(m['geometry']) > 1 else None
        if ls is None:
            continue
        (inner if m.get('role') == 'inner' else outer).append(ls)
    if not outer:
        return None
    o = unary_union(list(polygonize(linemerge(unary_union(outer)))))
    if inner:
        i = unary_union(list(polygonize(linemerge(unary_union(inner)))))
        o = o.difference(i)
    o = o if o.is_valid else o.buffer(0)
    return None if o.is_empty else o


def polys(els, keep, min_m2):
    out = []
    for el in els:
        t = el.get('tags', {})
        k = keep(t)
        if not k:
            continue
        g = poly_of(el)
        if g is None or g.area * M2 < min_m2:      # degrees² to m² at this latitude
            continue
        g = g.simplify(0.00002, preserve_topology=True)
        if g.is_empty:
            continue
        gj = mapping(g)
        rings = lambda p: [[R5(c) for c in r] for r in p]
        coords = [rings(gj['coordinates'])] if gj['type'] == 'Polygon' else [rings(p) for p in gj['coordinates']]
        out.append({'id': el['type'][0] + str(el['id']), 'k': k, 'name': t.get('name', ''), 'poly': coords})
    return out


def save(name, items, extra=None):
    os.makedirs(OUT, exist_ok=True)
    doc = {'source': 'OpenStreetMap contributors (ODbL) via Overpass API', 'fetched': time.strftime('%Y-%m-%d'),
           'bbox': [S, W, N, E], 'items': items}
    doc.update(extra or {})
    with open(os.path.join(OUT, name + '.json'), 'w') as f:
        json.dump(doc, f, separators=(',', ':'))
    print('wrote', name, len(items), round(os.path.getsize(os.path.join(OUT, name + '.json')) / 1e6, 1), 'MB', flush=True)


# ---------- roads ----------
els = fetch('roads', ['way["highway"~"^(trunk|primary|secondary|tertiary)$"]'], *TILES['roads'])
roads = [{'id': el['id'], 'hw': el['tags']['highway'], 'name': el['tags'].get('name', ''), 'ref': el['tags'].get('ref', ''),
          'c': [R5((q['lon'], q['lat'])) for q in el['geometry']]}
         for el in els if el.get('geometry') and len(el['geometry']) > 1]
save('roads', roads)

# ---------- parks ----------
def park_kind(t):
    if t.get('leisure') == 'park':
        return 'park'
    if t.get('leisure') == 'nature_reserve' or t.get('boundary') == 'protected_area':
        return 'reserve'
    return None
els = fetch('parks', ['way["leisure"~"^(park|nature_reserve)$"]', 'relation["leisure"~"^(park|nature_reserve)$"]',
                      'way["boundary"="protected_area"]', 'relation["boundary"="protected_area"]'], *TILES['parks'])
save('parks', polys(els, park_kind, 1500))

# ---------- land use ----------
LU = {'residential': 'res', 'commercial': 'com', 'retail': 'com', 'industrial': 'ind', 'farmland': 'farm',
      'farmyard': 'farm', 'orchard': 'farm', 'vineyard': 'farm', 'meadow': 'farm', 'forest': 'wood',
      'cemetery': 'cem', 'quarry': 'quarry'}
def lu_kind(t):
    if t.get('natural') == 'wood':
        return 'wood'
    return LU.get(t.get('landuse'))
lu_tags = '|'.join(LU)
els = fetch('landuse', ['way["landuse"~"^(%s)$"]' % lu_tags, 'relation["landuse"~"^(%s)$"]' % lu_tags,
                        'way["natural"="wood"]', 'relation["natural"="wood"]'], *TILES['landuse'])
save('landuse', polys(els, lu_kind, 4000))
