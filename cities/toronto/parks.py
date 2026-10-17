"""The Parks layer: City park outlines with what's in each, raw/nearby/ -> docs/toronto/data/parks.geojson

  green_spaces.geojson   outlines and names (Green Spaces); only AREA_CLASS "Park", the parks Parks,
                         Forestry & Recreation runs, so no cemeteries, golf courses or hydro corridors.
  parks_rec.geojson      the City's parks list, a point per park with up to 20 listed amenities.
  water_play_osm.json    splash pads and wading pools (OpenStreetMap); the City's list doesn't name them.

Each park list entry is matched to an outline once, here, so the map only filters: first an outline with the
same name nearby, then the outline it sits in, then the nearest outline within 40 m (points often sit on
the street at the park's address). Splash pads match by position the same way.

  {"asof": {"parks": date, "outlines": date, "water": date}, "count": n, "features": [
     {"properties": {"n": name, "a": ["play", "water", "wc", "dog"], "u": City page id, "w": "splash"|"wading"|"both"}}]}

a   what the chips filter on, in the order of the chips; only the amenities the layer offers.
u   the park's id on toronto.ca (its LOCATIONID), when a list entry matched; the popup links to it.
w   kind of water play, for the popup's wording."""
import json, math, os, re
from shapely.geometry import shape, mapping, Point
from shapely.ops import nearest_points
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'nearby')
OUT = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'parks.geojson')
AMEN = [('play', 'Playground'), ('water', None), ('wc', 'Washroom'), ('dog', 'Dog Off-Leash Area')]
NEAR = 40                     # metres: a list point or splash pad this close to an outline belongs to it
M_LAT = 111_320               # metres per degree of latitude
M_LON = M_LAT * math.cos(math.radians(43.7))
TOL = 0.00003                 # simplification tolerance in degrees, 2-3 m: outlines only, no paths or fixtures


SMALL = {'and', 'of', 'the', 'at', 'on', 'in', 'for', 'de', 'la'}


def title(s):   # the City's names are in capitals; as in nearby.py
    words = re.sub(r'\s+', ' ', s.strip()).lower().split(' ')
    out = []
    for i, w in enumerate(words):
        w = '-'.join(p[:1].upper() + p[1:] for p in w.split('-')) if (i == 0 or w not in SMALL) else w
        out.append(re.sub(r"^(O'|Mc|L'|D')(\w)", lambda m: m.group(1) + m.group(2).upper(), w))
    out = re.sub(r'(?<![A-Za-z])([a-z])\.', lambda m: m.group(1).upper() + '.', ' '.join(out))   # E.T. Seton
    return out.replace("'S ", "'s ").replace("'S", "'s").replace('( ', '(').replace('Trca', 'TRCA')


def norm(s):
    s = re.sub(r'[^a-z0-9 ]', ' ', (s or '').lower())
    return ' '.join(w for w in s.split() if w not in ('the', 'park', 'parkette', 'and'))


def metres(a, b):   # shapely distance in degrees, scaled roughly to metres at Toronto's latitude
    return math.hypot((a.x - b.x) * M_LON, (a.y - b.y) * M_LAT)


gs = json.load(open(os.path.join(RAW, 'green_spaces.geojson')))
parks = []
for f in gs['features']:
    if f['properties'].get('class') != 'Park': continue
    g = shape(f['geometry']).buffer(0)
    if g.is_empty: continue
    parks.append({'g': g, 'name': (f['properties'].get('name') or '').strip(), 'a': set(), 'u': None, 'w': set()})
geoms = [p['g'] for p in parks]
tree = STRtree(geoms)
deg = NEAR / M_LAT


def nearest_to(pt, name=None):
    """Index of the outline this point belongs to, or None."""
    if name:   # same name within 300 m: the list's point for a big park can sit well outside its edge
        key = norm(name)
        if key:
            for i in tree.query(pt.buffer(300 / M_LAT)):
                if norm(parks[i]['name']) == key: return int(i)
    inside = [i for i in tree.query(pt) if geoms[i].contains(pt)]
    if inside: return int(min(inside, key=lambda i: geoms[i].area))   # the smallest: a parkette inside a ravine
    best, bd = None, NEAR
    for i in tree.query(pt.buffer(deg * 1.5)):
        d = metres(pt, nearest_points(pt, geoms[i].boundary)[1])
        if d <= bd: best, bd = int(i), d
    return best


rec = json.load(open(os.path.join(RAW, 'parks_rec.geojson')))
matched = missed = 0
for f in rec['features']:
    p, g = f['properties'], f['geometry']
    if not g or p.get('TYPE') != 'Park': continue
    c = g['coordinates'][0] if g['type'] == 'MultiPoint' else g['coordinates']
    i = nearest_to(Point(c), p.get('ASSET_NAME'))
    if i is None: missed += 1; continue
    matched += 1
    am = set((p.get('AMENITIES') or '').split(', '))
    parks[i]['a'].update(k for k, v in AMEN if v and v in am)
    if not parks[i]['u'] and p.get('LOCATIONID'): parks[i]['u'] = str(p['LOCATIONID'])

water_asof, wn = None, 0
wp = os.path.join(RAW, 'water_play_osm.json')
if os.path.exists(wp):
    W = json.load(open(wp)); water_asof = W.get('fetched')
    for e in W['elements']:
        i = nearest_to(Point(e['at']))
        if i is None: continue
        parks[i]['a'].add('water'); parks[i]['w'].add(e['kind']); wn += 1

feats = []
for p in parks:
    g = p['g'].simplify(TOL, preserve_topology=True)
    if g.is_empty: continue
    geo = json.loads(json.dumps(mapping(g)), parse_float=lambda x: round(float(x), 5))
    props = {'n': title(p['name'])}
    if p['a']: props['a'] = [k for k, _ in AMEN if k in p['a']]
    if p['u']: props['u'] = p['u']
    if p['w']: props['w'] = 'both' if len(p['w']) > 1 else next(iter(p['w']))
    feats.append({'type': 'Feature', 'properties': props, 'geometry': geo})
feats.sort(key=lambda f: -shape(f['geometry']).area)   # big parks first, so small ones inside draw on top
log = open(os.path.join(RAW, 'fetch.log')).read() if os.path.exists(os.path.join(RAW, 'fetch.log')) else ''
m = re.search(r'parks and recreation: .* refreshed (\d{4}-\d\d-\d\d)', log)
asof = {'parks': m.group(1) if m else None, 'outlines': (gs.get('refreshed') or '')[:10] or None, 'water': water_asof}
json.dump({'type': 'FeatureCollection', 'asof': asof, 'count': len(feats), 'features': feats},
          open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
cnt = {k: sum(k in f['properties'].get('a', []) for f in feats) for k, _ in AMEN}
print(f'parks: {len(feats)} outlines; list entries matched {matched}, unmatched {missed}; water play points placed {wn};',
      'with', cnt, f'{os.path.getsize(OUT) / 1e6:.2f} MB')
