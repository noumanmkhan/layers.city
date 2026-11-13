"""The Parks layer: the Park Board's park outlines with what's in each, raw/ods/ -> docs/vancouver/data/parks.geojson

  park-polygons.geojson    park boundaries (City of Vancouver Open Data, OGL – Vancouver; fetch_layers.py)
  parks.geojson            the parks list, a point per park with its id, name and whether it has washrooms
  parks-facilities.json    what each park has, by park id: playgrounds, spray parks, wading pools, off-leash areas…
  dog-off-leash-parks.geojson  the off-leash areas, a point each, for parks the facilities table misses
  meta.json                each dataset's last-modified date

Outlines are grouped by park id (or name where a dataset has no id), so a park drawn in several pieces is one
feature. Amenities come by park id; a park with no id match falls back to the same name, then to the list point
inside its outline. Same output as Toronto's parks.py (contract: parks.geojson):

  {"asof": {"parks": date, "outlines": date}, "count": n, "features": [
     {"properties": {"n": name, "a": ["play", "water", "wc", "dog"], "u": park id, "w": "splash"|"wading"|"both"}}]}

u   the park's id, the number in its ParkFinder page (app.vancouver.ca/ParkFinder/parks/<u>); the popup links to it."""
import json, os, re
from collections import defaultdict
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
ODS = os.path.join(HERE, 'raw', 'ods')
OUT = os.path.join(HERE, '..', '..', 'docs', 'vancouver', 'data', 'parks.geojson')
TOL = 0.00003                 # simplification tolerance in degrees, 2-3 m: outlines only
ORDER = ['play', 'water', 'wc', 'dog']


def load(name):
    return json.load(open(os.path.join(ODS, name), encoding='utf-8'))


def key(s):
    return re.sub(r'[^a-z0-9]', '', re.sub(r'\bpark\b', '', (s or '').lower()))


def field(props, *names):
    for n in names:
        if props.get(n) not in (None, ''): return props[n]
    return None


# The parks list: id -> name, point, washrooms
plist = {}
for f in load('parks.geojson')['features']:
    p = f['properties']
    plist[int(p['parkid'])] = {'n': p['name'], 'pt': shape(f['geometry']) if f.get('geometry') else None, 'wc': p.get('washrooms') == 'Y'}
by_name = {key(v['n']): k for k, v in plist.items()}

# What each park has
has = defaultdict(set)
water = defaultdict(set)
for r in load('parks-facilities.json'):
    t, pid = r['facilitytype'], int(r['parkid'])
    if t == 'Playgrounds': has[pid].add('play')
    elif t == 'Dogs Off-Leash Areas': has[pid].add('dog')
    elif t == 'Water/Spray Parks': has[pid].add('water'); water[pid].add('splash')
    elif t == 'Wading Pool': has[pid].add('water'); water[pid].add('wading')
for pid, v in plist.items():
    if v['wc']: has[pid].add('wc')
for f in load('dog-off-leash-parks.geojson')['features']:
    pid = by_name.get(key(f['properties'].get('park_name')))
    if pid is not None: has[pid].add('dog')

# Outlines, grouped into one shape per park
groups = defaultdict(list)
for f in load('park-polygons.geojson')['features']:
    if not f.get('geometry'): continue
    p = f['properties']
    pid = field(p, 'park_id', 'parkid', 'park_number')
    if pid is None and re.search(r'/parks/(\d+)', p.get('park_url') or ''):
        pid = re.search(r'/parks/(\d+)', p['park_url']).group(1)   # the ParkFinder page's number is the park id
    nm = field(p, 'park_name', 'name', 'parkname')
    try: pid = int(pid)
    except (TypeError, ValueError): pid = None
    groups[('id', pid) if pid is not None else ('n', key(nm))].append((shape(f['geometry']), nm))

feats, unmatched = [], []
for (kind, k), parts in groups.items():
    g = unary_union([s for s, _ in parts]).buffer(0)
    if g.is_empty: continue
    nm = next((n for _, n in parts if n), None)
    pid = k if kind == 'id' and k in plist else by_name.get(key(nm))
    if pid is None:
        pid = next((i for i, v in plist.items() if v['pt'] is not None and g.contains(v['pt'])), None)
    if pid is not None and not nm: nm = plist[pid]['n']
    if not nm: unmatched.append(k); continue
    if pid is None: unmatched.append(nm)
    pr = {'n': nm}
    if pid is not None: pr['u'] = pid
    elif kind == 'id': pr['u'] = k   # has a ParkFinder page but isn't in the parks list
    a = [x for x in ORDER if pid is not None and x in has[pid]]
    if a: pr['a'] = a
    w = water.get(pid, set())
    if w: pr['w'] = 'both' if len(w) == 2 else next(iter(w))
    s = g.simplify(TOL, preserve_topology=True)
    gm = mapping(s)
    rnd = lambda c: [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 6), round(c[1], 6)]
    feats.append({'type': 'Feature', 'properties': pr, 'geometry': {'type': gm['type'], 'coordinates': rnd(gm['coordinates'])}, '_a': g.area})
feats.sort(key=lambda f: -f.pop('_a'))

meta = load('meta.json')
day = lambda m: (m or {}).get('modified', '')[:10]
out = {'type': 'FeatureCollection', 'asof': {'parks': day(meta.get('parks')), 'outlines': day(meta.get('park-polygons'))},
       'count': len(feats), 'features': feats}
json.dump(out, open(OUT, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
from collections import Counter
print('parks:', len(feats), dict(Counter(x for f in feats for x in f['properties'].get('a', []))),
      '| no list match:', len(unmatched), unmatched[:12])
