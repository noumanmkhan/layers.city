"""Fetch the basemap for a city's region beyond (and including) the city from OpenStreetMap via the Overpass API,
into cities/<city>/raw/region_basemap/. Usage: python3 engine/region/fetch_basemap.py <city>
The area and tiling come from cities/<city>/region.json ("bbox": [S, W, N, E], optional "tiles": {"roads": [nx, ny], ...}).
Run from GitHub Actions (fetch-region-basemap.yml): Overpass can't be reached from most sandboxes.

  roads.json    arterials and collectors: highway=trunk|primary|secondary|tertiary (no ramps), with name and ref
  parks.json    leisure=park|nature_reserve and boundary=protected_area, as polygons
  landuse.json  residential, commercial/retail, industrial, farmland, woods, cemeteries, quarries

One city kept its own copy before this existed; new cities use this one.
Multipolygon relations are assembled into polygons here (shapely), so raw/ holds plain [lng, lat] rings.
The area is fetched in tiles, one request at a time (Overpass rejects bursts), and deduplicated by OSM id. Each tile is
cached in raw/region_basemap/.tiles/ until its file is written, and relations spanning more than region.json
"relationMaxSpan" degrees (default 1) are skipped (New York: the Appalachian Trail's protected corridor)."""
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


# Relations whose box spans more than this many degrees (a long-distance trail's protected corridor, a state-wide
# planning overlay) are skipped: their full geometry makes Overpass fail the whole tile, and basemap.py would drop
# them anyway (parkMaxKm2). Relations are listed first with their boxes, then fetched by id.
MAX_SPAN = CFG.get('relationMaxSpan', 1.0)
CACHE = os.path.join(OUT, '.tiles')


def fetch(name, filters, nx, ny):
    """Every element matching the filters, over the area in nx*ny tiles, keyed by type/id. Each tile's result is kept
    in raw/region_basemap/.tiles/ until the file is written, so a rerun after a failure picks up where it stopped."""
    els = {}
    os.makedirs(CACHE, exist_ok=True)
    ways, rels = [f for f in filters if not f.startswith('relation')], [f for f in filters if f.startswith('relation')]
    for i, b in enumerate(tiles(nx, ny)):
        cp = os.path.join(CACHE, '%s-%d-%d.json' % (name, nx, i))
        if os.path.exists(cp) and not os.environ.get('REFETCH'):
            got = json.load(open(cp))
        else:
            bb = '(%s,%s,%s,%s)' % b
            got = overpass('(' + ''.join(f + bb + ';' for f in ways) + ');out tags geom;').get('elements', []) if ways else []
            if rels:
                listed = overpass('(' + ''.join(f + bb + ';' for f in rels) + ');out tags bb;').get('elements', [])
                ids = [el['id'] for el in listed if 'bounds' in el and
                       el['bounds']['maxlat'] - el['bounds']['minlat'] <= MAX_SPAN and el['bounds']['maxlon'] - el['bounds']['minlon'] <= MAX_SPAN]
                if len(ids) < len(listed):
                    print('  skipped', len(listed) - len(ids), 'relations over', MAX_SPAN, 'degrees:',
                          [el.get('tags', {}).get('name') for el in listed if el['id'] not in ids][:5], flush=True)
                for k in range(0, len(ids), 40):
                    got += overpass('relation(id:%s);out tags geom;' % ','.join(map(str, ids[k:k + 40]))).get('elements', [])
                    time.sleep(3)
            json.dump(got, open(cp, 'w'))
            time.sleep(5)
        for el in got:
            els[el['type'] + str(el['id'])] = el
        print(' ', name, b, len(got), 'elements', flush=True)
    return list(els.values())


def clear_cache(name):
    for f in os.listdir(CACHE) if os.path.isdir(CACHE) else []:
        if f.startswith(name + '-'): os.remove(os.path.join(CACHE, f))


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


# ---------- or from Geofabrik's extracts ----------
# region.json "pbf": [Geofabrik .osm.pbf URLs] reads parks and land use from the state extracts with osmium instead of
# Overpass (New York's region: Overpass took four hours for half its parks). Same items, same filters.
PBF = None
def from_pbf(name, expr, keep, min_m2):
    global PBF
    import subprocess, shapely.geometry
    tmp = os.path.join('/tmp', 'region-pbf-' + CITY); os.makedirs(tmp, exist_ok=True)
    if PBF is None:
        parts = []
        for i, u in enumerate(CFG['pbf']):
            f = os.path.join(tmp, 'src%d.osm.pbf' % i)
            if not os.path.exists(f):
                subprocess.run(['curl', '-sSfL', '--retry', '5', '-o', f, u], check=True)
            cut = os.path.join(tmp, 'cut%d.osm.pbf' % i)
            subprocess.run(['osmium', 'extract', '-b', '%s,%s,%s,%s' % (W, S, E, N), '-s', 'smart', '-O', '-o', cut, f], check=True)
            parts.append(cut)
        PBF = os.path.join(tmp, 'region.osm.pbf')
        subprocess.run(['osmium', 'merge', '-O', '-o', PBF] + parts, check=True)
        print('pbf ready', round(os.path.getsize(PBF) / 1e6), 'MB', flush=True)
    filt, seq = os.path.join(tmp, name + '.osm.pbf'), os.path.join(tmp, name + '.geojsonseq')
    subprocess.run(['osmium', 'tags-filter', '-O', '-o', filt, PBF] + expr, check=True)
    subprocess.run(['osmium', 'export', '-O', '-f', 'geojsonseq', '--geometry-types=polygon', '-a', 'type,id', '-o', seq, filt], check=True)
    out, skipped = [], 0
    rings = lambda p: [[R5(c) for c in r] for r in p]
    for line in open(seq):
        f = json.loads(line.strip().lstrip('\x1e'))
        t = f['properties']; k = keep(t)
        if not k: continue
        g = shapely.geometry.shape(f['geometry'])
        x0, y0, x1, y1 = g.bounds
        if x1 - x0 > MAX_SPAN or y1 - y0 > MAX_SPAN: skipped += 1; continue
        if not g.is_valid: g = g.buffer(0)
        if g.is_empty or g.area * M2 < min_m2: continue
        g = g.simplify(0.00002, preserve_topology=True)
        if g.is_empty: continue
        gj = mapping(g)
        coords = [rings(gj['coordinates'])] if gj['type'] == 'Polygon' else [rings(q) for q in gj['coordinates']]
        out.append({'id': t.get('@type', 'x')[0] + str(t.get('@id', '')), 'k': k, 'name': t.get('name', ''), 'poly': coords})
    print(' ', name, 'from the extracts:', len(out), 'polygons; skipped', skipped, 'over', MAX_SPAN, 'degrees', flush=True)
    return out


# A rerun keeps files already fetched (REFETCH=1 fetches everything again).
done = lambda n: os.path.exists(os.path.join(OUT, n + '.json')) and not os.environ.get('REFETCH')

# ---------- roads ----------
if not done('roads'):
    els = fetch('roads', ['way["highway"~"^(trunk|primary|secondary|tertiary)$"]'], *TILES['roads'])
    save('roads', [{'id': el['id'], 'hw': el['tags']['highway'], 'name': el['tags'].get('name', ''), 'ref': el['tags'].get('ref', ''),
                    'c': [R5((q['lon'], q['lat'])) for q in el['geometry']]}
                   for el in els if el.get('geometry') and len(el['geometry']) > 1])
    clear_cache('roads')


# ---------- parks ----------
def park_kind(t):
    if t.get('leisure') == 'park':
        return 'park'
    if t.get('leisure') == 'nature_reserve' or t.get('boundary') == 'protected_area':
        return 'reserve'
    return None
if not done('parks'):
    if CFG.get('pbf'):
        save('parks', from_pbf('parks', ['wr/leisure=park,nature_reserve', 'wr/boundary=protected_area'], park_kind, 1500))
    else:
        els = fetch('parks', ['way["leisure"~"^(park|nature_reserve)$"]', 'relation["leisure"~"^(park|nature_reserve)$"]',
                              'way["boundary"="protected_area"]', 'relation["boundary"="protected_area"]'], *TILES['parks'])
        save('parks', polys(els, park_kind, 1500))
    clear_cache('parks')

# ---------- land use ----------
LU = {'residential': 'res', 'commercial': 'com', 'retail': 'com', 'industrial': 'ind', 'farmland': 'farm',
      'farmyard': 'farm', 'orchard': 'farm', 'vineyard': 'farm', 'meadow': 'farm', 'forest': 'wood',
      'cemetery': 'cem', 'quarry': 'quarry'}
def lu_kind(t):
    if t.get('natural') == 'wood':
        return 'wood'
    return LU.get(t.get('landuse'))
lu_tags = '|'.join(LU)
if not done('landuse'):
    if CFG.get('pbf'):
        save('landuse', from_pbf('landuse', ['wr/landuse=' + ','.join(LU), 'wr/natural=wood'], lu_kind, 4000))
    else:
        els = fetch('landuse', ['way["landuse"~"^(%s)$"]' % lu_tags, 'relation["landuse"~"^(%s)$"]' % lu_tags,
                                'way["natural"="wood"]', 'relation["natural"="wood"]'], *TILES['landuse'])
        save('landuse', polys(els, lu_kind, 4000))
    clear_cache('landuse')