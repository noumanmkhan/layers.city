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

CFG = json.load(open(os.path.join(ROOT, 'cities', city, 'along.json'), encoding='utf-8'))
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
EXPRESS = set(CFG['express']) if 'express' in CFG else None
for rid, r in S['routes'].items():
    fam = r[3] or []
    # night-only routes (the families say overnight and nothing else): a daytime trip never uses them. A route that
    # also runs by day (frequent, express or regular: a 24-hour trunk route) stays.
    if 'night' in fam and not set(fam) & {'freq', 'exp', 'reg'}: continue
    routes[rid] = [r[0], r[1], r[2], r[4]]   # short name, long name, mode, typical gap between vehicles (min)
    # 5th, only when 1: an express route, timed at the router's EXPRESS speed. By default the Routes data's express
    # family; along.json "express" lists the route numbers instead where the agency's "Express" isn't faster.
    if (r[0] in EXPRESS) if EXPRESS is not None else ('exp' in fam): routes[rid].append(1)
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
import math, re, hashlib
from shapely.geometry import shape
DATA = os.path.join(ROOT, 'docs', city, 'data')
lat0 = sum(s[1] for s in stops) / len(stops)
ABOUT_N = 24
KX, KY = 111320 * math.cos(math.radians(lat0)), 110540
pois, seen, pids = [], set(), set()
about = {}        # place id -> [text, credit, link, checked]: shown when someone opens a place (cities' discover layer)
byname = {}       # (kind, name as matched) -> index in pois, for "attach"
# along.json "attachStrip": words dropped from both names before matching ("High Park" and "High", a branch and its library)
ATTACH_RX = re.compile(r'\b(' + '|'.join(re.escape(w.lower()) for w in CFG.get('attachStrip', [])) + r')\b') if CFG.get('attachStrip') else None
def match_name(n):
    n = re.sub(r"[^a-z0-9 ]+", ' ', n.lower().replace("'", ''))
    return ' '.join((ATTACH_RX.sub(' ', n) if ATTACH_RX else n).split())
def pid_of(kind, name, word):
    # a short id that stays the same across rebuilds, for shared links that name the places someone kept
    h = int(hashlib.sha1(f"{kind}|{name}|{word or ''}".encode()).hexdigest()[:8], 16)
    return ''.join('0123456789abcdefghijklmnopqrstuvwxyz'[(h // 36 ** i) % 36] for i in range(5))
def keep_about(pid, pr):
    if pr.get('text') or pr.get('link'):
        about[pid] = [pr.get('text', ''), pr.get('credit', ''), pr.get('link', ''), pr.get('checked', '')]
        return True
    return False
for src in CFG['pois']:
    fp = os.path.join(DATA, src['file'] + '.geojson')
    if not os.path.exists(fp): print(f"  along: no {src['file']} layer"); continue
    n0 = len(pois)
    for f in json.load(open(fp))['features']:
        pr, g = f['properties'], f['geometry']
        if not g: continue
        if src.get('cats') and pr.get(src.get('catField', 'cat')) not in src['cats']: continue
        kind = pr.get(src['kindField']) if src.get('kindField') else src['kind']
        name = (pr.get(src.get('name', 'name')) or '').strip()
        if not name or (src.get('skip') and re.search(src['skip'], name)): continue
        if src.get('rename'): name = re.sub(src['rename'][0], src['rename'][1], name)
        if src.get('suffix') and name.endswith(src['suffix']): name = name[:-len(src['suffix'])]
        word = pr.get(src['label']) if src.get('label') else src.get('word', '')
        if src.get('sub') and pr.get(src['sub']): word = pr[src['sub']]
        if src.get('height') and pr.get(src['height']): word = f"{src.get('word', '')} · {round(pr[src['height']])} m"
        if src.get('attach'):
            # the publisher's text for a place another layer already lists (a park, a library): put it on that place
            mn = match_name(name)
            hit = next((byname[(k, mn)] for k in src.get('attachTo', {}).get(kind, [kind]) if (k, mn) in byname), None)
            if hit is not None:
                c = pois[hit][3]
                if abs(c[0] - g['coordinates'][0]) * KX + abs(c[1] - g['coordinates'][1]) * KY < 1500:
                    if keep_about(pois[hit][4], pr) and len(pois[hit]) < 6: pois[hit].append(1)
                    if kind in src.get('promote', []): pois[hit][0], pois[hit][2] = kind, word or ''   # a viewpoint stays one
                    continue
        key = (name + '|' + (word if kind == 'campus' else kind if src.get('kindField') else '')).lower()
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
        pid = pid_of(kind, name, word)
        if pid in pids:   # the same kind, name and word somewhere else (two parks of one name): the later one adds where it is
            pid = pid_of(kind, name, f"{word or ''}@{pts[0][0]:.3f},{pts[0][1]:.3f}")
        pids.add(pid)
        item = [kind, name, word or '', [round(c, 5) for p in pts for c in p[:2]], pid]
        if src.get('about') and keep_about(pid, pr): item.append(1)   # 6th: has text to open
        byname.setdefault((kind, match_name(name)), len(pois))
        pois.append(item)
    print(f"  along: {len(pois) - n0} {src.get('kind') or 'places'} from {src['file']}")
kinds = list(CFG.get('order', []))   # the order places are listed in; build order is CFG['pois']
for s_ in CFG['pois']:
    for k in ([s_['kind']] if s_.get('kind') else s_.get('cats', [])):
        if k not in kinds: kinds.append(k)
p2 = os.path.join(OUT, 'pois.json')
json.dump({'kinds': kinds, 'about': ABOUT_N if about else 0, 'pois': pois}, open(p2, 'w'), separators=(',', ':'), ensure_ascii=False)
print(f'  along: {len(pois)} places, {os.path.getsize(p2)/1e6:.2f} MB')
# The texts, split into ABOUT_N small files by place id, so opening a place loads one of them (about/<n>.json).
ad = os.path.join(OUT, 'about')
if os.path.isdir(ad):
    for f in os.listdir(ad): os.remove(os.path.join(ad, f))
if about:
    os.makedirs(ad, exist_ok=True)
    parts = [{} for _ in range(ABOUT_N)]
    for pid, a in about.items(): parts[int(pid, 36) % ABOUT_N][pid] = a
    for i, part in enumerate(parts):
        json.dump(part, open(os.path.join(ad, f'{i}.json'), 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print(f'  along: {len(about)} places with text, in {ABOUT_N} files')

# ---- the page ----
sys.path.insert(0, os.path.join(ROOT, 'engine'))
from theme import SCRIPT as THEME_SCRIPT, css as theme_css
DARK = ['body{--water:#18232B;--m-city:#24272D;--m-out:#1C1F24;--m-edge:#3A3E45;--m-hoodline:#30343A;--m-major:#3A3E45;--m-halo:#15171B;'
        '--pill-line:#373B42;--sub:#9AA0A8;--hover:#262A30;--k-street:#D9894A;--k-heritage:#B8956E;--k-park:#5CB46C;--k-campus:#6D9BDB;--k-library:#A48BD6;--k-tower:#9AA4AE;'
        '--k-view:#4FB3C4;--k-art:#E070B0;--k-history:#D6A84E;--k-arts:#D07AA6;--k-nature:#9DBB63;--k-rec:#A8A29E;--k-faith:#8AA8C6}',
        '.rb:not(.tram):not(.exp){background:var(--card)}']
page = CFG['page']
# expBadge: the routes the Routes page draws as express (badge colours), which needn't be the ones timed as express
rs = dict(page, skipModes=CFG.get('skipModes', []), expBadge=sorted(k for k, r in S['routes'].items() if 'exp' in (r[3] or []) and k in routes))
tpl = open(os.path.join(ROOT, 'engine', 'along', 'page.html'), encoding='utf-8').read()
css_p = os.path.join(ROOT, 'cities', city, 'factsheet.css')
html = (tpl.replace('{{RS}}', json.dumps(rs, ensure_ascii=False))
        .replace('{{router}}', open(os.path.join(ROOT, 'engine', 'along', 'router.js'), encoding='utf-8').read())
        .replace('{{report}}', open(os.path.join(ROOT, 'engine', 'report.js'), encoding='utf-8').read())
        .replace('{{css}}', open(css_p, encoding='utf-8').read() if os.path.exists(css_p) else '')
        .replace('{{canonical}}', f'https://layers.city/{city}/along/')
        .replace('{{robots}}', '\n<meta name="robots" content="noindex">' if CFG.get('unlisted') else '')
        .replace('{{title}}', page['title']).replace('{{city}}', page['city'])
        .replace('{{description}}', page['description']).replace('{{lede}}', page['lede'])
        .replace('{{credits}}', page['credits']).replace('{{mapLink}}', page.get('mapLink', 'Open the map'))
        .replace('{{themeScript}}', THEME_SCRIPT).replace('{{themeCss}}', theme_css(DARK)))
open(os.path.join(ROOT, 'docs', city, 'along', 'index.html'), 'w', encoding='utf-8').write(html)
# The router on its own too, byte for byte what the page runs, for apps (DATA_CONTRACT.md section 18).
open(os.path.join(ROOT, 'docs', city, 'along', 'router.js'), 'wb').write(open(os.path.join(ROOT, 'engine', 'along', 'router.js'), 'rb').read())
print(f'  along: page and router.js written')
# ...and city.json's "along" block, whose version changes with these files.
sys.path.insert(0, os.path.join(ROOT, 'engine', 'along'))
from along_meta import write_block
b = write_block(ROOT, city)
print(f"  along: city.json along block {b['version'] if b else '(none)'}")
