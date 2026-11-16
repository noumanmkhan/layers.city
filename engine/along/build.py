"""Build a city's "Along the way" page: pick two places, see a likely transit route between them and what you pass.

Reads the Routes page's published data (docs/<city>/routes/data/: stops.json and r/<route>.json, written by
engine/routes/build.py) and writes docs/<city>/along/data/graph.json: every stop (position, name) and every route
pattern as an ordered list of stops with distances along it. The page finds routes in the browser (engine/along/
router.js), so the places people type never leave it.

Usage: python3 engine/along/build.py <city>
"""
import json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
city = sys.argv[1]
RD = os.path.join(ROOT, 'docs', city, 'routes', 'data')
OUT = os.path.join(ROOT, 'docs', city, 'along', 'data')
os.makedirs(OUT, exist_ok=True)

S = json.load(open(os.path.join(RD, 'stops.json')))
stops, sidx, pats = [], {}, {}
for st in S['stops']:
    sid, name, lng, lat, side, head, serve = st[:7]
    i = len(stops); sidx[sid] = i
    stops.append([round(lng, 5), round(lat, 5), name, sid])
    for rid, lst in serve.items():
        for k, d in lst:
            pats.setdefault((rid, k), []).append((d, i))

routes, plist = {}, []
for rid, r in S['routes'].items():
    if 'night' in (r[3] or []): continue   # overnight routes: a daytime trip never uses them
    routes[rid] = [r[0], r[1], r[2], r[4]]   # short name, long name, mode, typical gap between vehicles (min)
for (rid, k), lst in pats.items():
    if rid not in routes: continue
    lst.sort()
    seq, dist = [], []
    for d, i in lst:
        if seq and seq[-1] == i: continue
        seq.append(i); dist.append(int(d))
    if len(seq) < 2: continue
    plist.append([rid, k, seq, dist])

out = {'asof': S.get('asof'), 'routes': routes, 'stops': stops, 'patterns': plist}
p = os.path.join(OUT, 'graph.json')
json.dump(out, open(p, 'w'), separators=(',', ':'), ensure_ascii=False)
print(f'  along: {len(stops)} stops, {len(plist)} patterns, {os.path.getsize(p)/1e6:.2f} MB')

# ---- what's a short walk from each stop: points from the map's published layers (cities/<city>/along.json "pois") ----
import math, re
from shapely.geometry import shape
CFG = json.load(open(os.path.join(ROOT, 'cities', city, 'along.json'), encoding='utf-8'))
DATA = os.path.join(ROOT, 'docs', city, 'data')
lat0 = sum(s[1] for s in stops) / len(stops)
KX, KY = 111320 * math.cos(math.radians(lat0)), 110540
pois, seen = [], set()
for src in CFG['pois']:
    fp = os.path.join(DATA, src['file'] + '.geojson')
    if not os.path.exists(fp): print(f"  along: no {src['file']} layer"); continue
    n0 = len(pois)
    for f in json.load(open(fp))['features']:
        pr, g = f['properties'], f['geometry']
        if not g: continue
        if src.get('cats') and pr.get('cat') not in src['cats']: continue
        name = (pr.get(src.get('name', 'name')) or '').strip()
        if not name or (src.get('skip') and re.search(src['skip'], name)): continue
        if src.get('rename'): name = re.sub(src['rename'][0], src['rename'][1], name)
        if src.get('suffix') and name.endswith(src['suffix']): name = name[:-len(src['suffix'])]
        word = pr.get(src['label']) if src.get('label') else src.get('word', '')
        if src.get('sub') and pr.get(src['sub']): word = pr[src['sub']]
        if src.get('height') and pr.get(src['height']): word = f"{src.get('word', '')} · {round(pr[src['height']])} m"
        key = (name + '|' + (word if src['kind'] == 'campus' else '')).lower()
        if key in seen: continue
        shp = shape(g)
        if g['type'] == 'Point':
            pts = [g['coordinates']]
        else:
            if src.get('minHa') and shp.area * KX * KY / 1e4 < src['minHa']: continue
            # the edge every ~120 m, and a point inside: distance to a place is distance to the nearest of them
            pts = [list(shp.representative_point().coords[0])]
            for poly in (shp.geoms if hasattr(shp, 'geoms') else [shp]):
                ring = poly.exterior
                L = ring.length * KX
                k = max(4, int(L / 120))
                pts += [list(ring.interpolate(i / k, normalized=True).coords[0]) for i in range(k)]
        seen.add(key)
        pois.append([src['kind'], name, word or '', [round(c, 5) for p in pts for c in p[:2]]])
    print(f"  along: {len(pois) - n0} {src['kind']} from {src['file']}")
p2 = os.path.join(OUT, 'pois.json')
json.dump({'kinds': [s['kind'] for s in CFG['pois']], 'pois': pois}, open(p2, 'w'), separators=(',', ':'), ensure_ascii=False)
print(f'  along: {len(pois)} places, {os.path.getsize(p2)/1e6:.2f} MB')

# ---- the page ----
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from theme import SCRIPT as THEME_SCRIPT, css as theme_css
DARK = ['body{--water:#18232B;--m-city:#24272D;--m-out:#1C1F24;--m-edge:#3A3E45;--m-hoodline:#30343A;--m-major:#3A3E45;--m-halo:#15171B;'
        '--pill-line:#373B42;--sub:#9AA0A8;--hover:#262A30;--k-street:#D9894A;--k-heritage:#B8956E;--k-park:#5CB46C;--k-campus:#6D9BDB;--k-library:#A48BD6;--k-tower:#9AA4AE}',
        '.rb:not(.tram):not(.exp){background:var(--card)}']
page = CFG['page']
rs = dict(page, skipModes=CFG.get('skipModes', []))
tpl = open(os.path.join(ROOT, 'engine', 'along', 'page.html'), encoding='utf-8').read()
css_p = os.path.join(ROOT, 'cities', city, 'factsheet.css')
html = (tpl.replace('{{RS}}', json.dumps(rs, ensure_ascii=False))
        .replace('{{router}}', open(os.path.join(ROOT, 'engine', 'along', 'router.js'), encoding='utf-8').read())
        .replace('{{css}}', open(css_p, encoding='utf-8').read() if os.path.exists(css_p) else '')
        .replace('{{canonical}}', f'https://layers.city/{city}/along/')
        .replace('{{robots}}', '\n<meta name="robots" content="noindex">' if CFG.get('unlisted') else '')
        .replace('{{title}}', page['title']).replace('{{city}}', page['city'])
        .replace('{{description}}', page['description']).replace('{{lede}}', page['lede'])
        .replace('{{credits}}', page['credits']).replace('{{mapLink}}', page.get('mapLink', 'Open the map'))
        .replace('{{themeScript}}', THEME_SCRIPT).replace('{{themeCss}}', theme_css(DARK)))
open(os.path.join(ROOT, 'docs', city, 'along', 'index.html'), 'w', encoding='utf-8').write(html)
print(f'  along: page written')
