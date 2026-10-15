"""Bike lanes: build docs/<city>/data/bikes.geojson from cities/<city>/raw/bikes.geojson (engine/fetch_bikes.py)
for the "bikes" lines layer. Classes and readable type names come from cities/<city>/bikes.json.

One feature per segment, with:
  t   class: prot (separated from traffic), paint (painted lane), shared (sharrows, signed routes, greenways),
      trail (off-street multi-use trails)
  d   the City's type, in plain words ("Two-way cycle track")
  n   street or trail name, fr / to its ends where the City gives them, y year installed (Toronto)
bikes.json "subField" adds a second field to the type ("Protected Bike Lanes|OSS"), used where the pair is listed.
Segments of a type not listed in bikes.json "classes" are left out and printed, so a new type shows up in the log.
Lines are simplified to about 2 m and coordinates rounded to 5 decimals (about 1 m).
Top level: "asof" (the City's last update of the data, else the fetch date), "counts" per class, "km" per class.

Usage: python3 engine/bikes.py <city>
"""
import collections, json, math, os, re, sys
from shapely.geometry import mapping, shape

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
city = sys.argv[1]
CFG = json.load(open(os.path.join(ROOT, 'cities', city, 'bikes.json')))
RAW = os.path.join(ROOT, 'cities', city, 'raw', 'bikes.geojson')
OUT = os.path.join(ROOT, 'docs', city, 'data', 'bikes.geojson')
if not os.path.exists(RAW): sys.exit(f'{city}: no bike network fetched yet (fetch-bikes.yml)')
R = json.load(open(RAW))
# bikes.json "extra" (Vancouver): another raw file in the same shape and types (OpenStreetMap's bike paths in the University
# Endowment Lands, beyond the City's data), kept only inside "extraClip" (a units file code) and added to the network.
if CFG.get('extra') and os.path.exists(os.path.join(ROOT, 'cities', city, CFG['extra'])):
    ex = json.load(open(os.path.join(ROOT, 'cities', city, CFG['extra'])))['features']
    clip = CFG.get('extraClip')
    if clip:
        from shapely.geometry import mapping as _m
        ug = next(shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(ROOT, 'docs', city, 'data', clip['file'] + '.geojson')))['features']
                  if f['properties'].get('code') == clip['code'])
        kept = []
        for f in ex:
            g = shape(f['geometry']).intersection(ug)
            if g.is_empty or g.length == 0: continue
            for part in getattr(g, 'geoms', [g]):
                if part.geom_type == 'LineString': kept.append({'type': 'Feature', 'properties': f['properties'], 'geometry': _m(part)})
        ex = kept
    R['features'] = R['features'] + ex
    print(f'{city}: +{len(ex)} segments from {CFG["extra"]}')
CLS = {v: k for k, vs in CFG['classes'].items() for v in vs}
LAB = CFG.get('labels', {})
ABBR = {'ST': 'St', 'AVE': 'Ave', 'AV': 'Ave', 'RD': 'Rd', 'BLVD': 'Blvd', 'DR': 'Dr', 'PKWY': 'Pkwy', 'PL': 'Pl', 'CT': 'Ct', 'TER': 'Ter',
        'HWY': 'Hwy', 'LN': 'Ln', 'WAY': 'Way', 'N': 'N', 'S': 'S', 'E': 'E', 'W': 'W', 'JR': 'Jr', 'MLK': 'MLK'}


def tcase(s):
    if not s: return s
    out = []
    for w in re.sub(r'\s+', ' ', str(s)).strip().split(' '):
        u = w.upper()
        if u in ABBR: out.append(ABBR[u])
        elif re.match(r'^\d+(ST|ND|RD|TH)$', u): out.append(u[:-2] + u[-2:].lower())
        elif re.match(r'^[\d-]+[A-Z]?$', u): out.append(u)
        else: out.append('-'.join(p[:1] + p[1:].lower() for p in u.split('-')))
    return ' '.join(out)


def clean(s):
    s = re.sub(r'\s+', ' ', str(s or '')).strip()
    if not s or s.upper() in ('NONE', 'NULL', 'N/A', 'NA'): return None
    return tcase(s) if CFG.get('titleCase') else s


def rnd(c):
    return [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 5), round(c[1], 5)]


def length_km(g):
    lat0 = math.radians(g.centroid.y)
    kx, ky = 111.32 * math.cos(lat0), 110.54
    parts = g.geoms if g.geom_type.startswith('Multi') else [g]
    tot = 0.0
    for p in parts:
        c = list(p.coords)
        tot += sum(math.hypot((c[i][0] - c[i - 1][0]) * kx, (c[i][1] - c[i - 1][1]) * ky) for i in range(1, len(c)))
    return tot


feats, skipped = [], collections.Counter()
counts, km = collections.Counter(), collections.Counter()
for f in R['features']:
    p = f['properties']
    typ = (p.get(CFG['typeField']) or '').strip()
    if CFG.get('subField'):   # Vancouver: the type alone is too coarse ("Protected Bike Lanes" holds off-street paths too)
        sub = (p.get(CFG['subField']) or '').strip()
        typ = typ + '|' + sub if typ + '|' + sub in CLS else typ
    t = CLS.get(typ)
    if not t:
        skipped[typ or '(blank)'] += 1
        continue
    g = shape(f['geometry'])
    if g.is_empty: continue
    g = g.simplify(0.00002, preserve_topology=False)
    if g.is_empty or g.length == 0: continue
    q = {'t': t, 'd': LAB.get(typ) or typ[:1] + typ[1:].lower()}
    n, fr, to = clean(p.get(CFG['name'])), clean(p.get(CFG.get('from'))), clean(p.get(CFG.get('to')))
    if n: q['n'] = n
    if fr and fr != n: q['fr'] = fr
    if to and to != n and to != fr: q['to'] = to
    if CFG.get('year'):
        y = re.search(r'(19|20)\d\d', str(p.get(CFG['year']) or ''))
        if y and int(y.group(0)) > 1900: q['y'] = int(y.group(0))
    m = mapping(g)
    feats.append({'type': 'Feature', 'properties': q, 'geometry': {'type': m['type'], 'coordinates': rnd(m['coordinates'])}})
    counts[t] += 1; km[t] += length_km(g)

# Draw order inside the file: shared first, separated last, so the most protected stretch sits on top.
ORDER = {'trail': 0, 'shared': 1, 'paint': 2, 'prot': 3}
feats.sort(key=lambda f: ORDER.get(f['properties']['t'], 9))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
out = {'type': 'FeatureCollection', 'asof': R.get('updated') or R.get('fetched'), 'fetched': R.get('fetched'),
       'counts': dict(counts), 'km': {k: round(v) for k, v in km.items()}, 'features': feats}
json.dump(out, open(OUT, 'w'), separators=(',', ':'))
print(f'{city}: {len(feats)} segments', dict(counts), 'km', out['km'], 'asof', out['asof'], f'{os.path.getsize(OUT) // 1024} KB')
if skipped: print('  left out (type not in bikes.json classes):', dict(skipped))
