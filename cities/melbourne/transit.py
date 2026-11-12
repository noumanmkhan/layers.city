"""Trains, trams and V/Line from Transport Victoria's GTFS (raw/ptv_rail.json, fetch.py).
- Metro trains: one line per route, coloured by its line group (the colours on Metro's own network map), stations
  merged by name. -> tmp/train_lines.geojson, docs/.../train_stations.geojson
- Trams: one line per route, all in tram green, each carrying its number as a badge; stops aren't drawn (there are
  about 1,600), so the stations file is empty. -> tmp/tram_lines.geojson, docs/.../tram_stops.geojson
- V/Line: each line's most common pattern, the whole run and the piece inside Greater Melbourne. -> tmp/vline_*.geojson
Prints the badge map for city.json and the CSS rules for city.css when they change."""
import json, math, os, re, sys
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping, LineString, MultiLineString
from shapely.ops import unary_union, linemerge

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, 'raw') + '/'
OUT = os.path.join(HERE, '..', '..', 'docs', 'melbourne', 'data') + '/'
TMP = os.path.join(HERE, 'tmp') + '/'
KM = 88.2
dist_km = lambda a, b: math.hypot((a[0] - b[0]) * KM, (a[1] - b[1]) * 111.2)
fc = lambda feats: {'type': 'FeatureCollection', 'features': feats}
feat = lambda g, p: {'type': 'Feature', 'properties': p, 'geometry': mapping(g)}
pt = lambda x, y, p: {'type': 'Feature', 'properties': p, 'geometry': {'type': 'Point', 'coordinates': [round(x, 5), round(y, 5)]}}
dump = lambda n, f: json.dump(fc(f), open(TMP + n + '.geojson', 'w'), separators=(',', ':'))
write = lambda n, f: json.dump(fc(f), open(OUT + n + '.geojson', 'w'), separators=(',', ':'))
D = json.load(open(R + 'ptv_rail.json'))
base = json.load(open(OUT + 'base.geojson')) if os.path.exists(OUT + 'base.geojson') else None


def lines_of(g):
    if g.geom_type == 'LineString': return [g]
    return [x for p in getattr(g, 'geoms', []) for x in lines_of(p)]


def route_geom(r, share=0.15):
    top = max(r['counts'].values())
    shp = [LineString(r['shapes'][s]) for s, c in r['counts'].items() if c >= top * share and len(r['shapes'][s]) > 1]
    u = lines_of(unary_union(shp))
    m = linemerge(u) if len(u) > 1 else u[0]
    parts = [p for p in getattr(m, 'geoms', [m]) if p.length * KM > 0.05]
    return MultiLineString(parts) if len(parts) > 1 else parts[0]


clean_stn = lambda n: re.sub(r'\s*(Railway )?Station.*$', '', re.sub(r'\s*\(.*\)$', '', n)).strip()

# ---------- Metro trains ----------
# Each line in its GTFS colour, which is its line group's (the Metro Tunnel lines share one, as do Sandringham,
# Werribee and Williamstown since the tunnel reshaped the cross-city group in 2025). The class is the group's.
GROUP = {'34ACE1': 'tunnel', '152C6B': 'burnley', 'BE1014': 'clifton', 'FFBE00': 'northern', '028430': 'frankston',
         'F178AF': 'crosscity', '95979A': 'racecourse'}
GROUP_ORDER = ['tunnel', 'burnley', 'clifton', 'northern', 'frankston', 'crosscity', 'racecourse']
metro = D.get('2', {})
by, stn_lines, stn_pts, colours = defaultdict(list), defaultdict(set), defaultdict(list), {}
for rid, r in metro['routes'].items():
    name = (r['short'] or r['long']).replace(' Line', '').strip()
    grp = GROUP.get(r['color'].upper())
    if not grp: print('  no group for', name, r['color']); continue
    colours[grp] = '#' + r['color'].upper()
    # One shape per line: its longest common pattern. GTFS patterns of one line rarely share exact points (platforms,
    # the City Loop or not), so a union keeps near-duplicate strands, and the badges then can't tell where the line ends.
    top = max(r['counts'].values())
    best = max((s for s, c in r['counts'].items() if c >= top * 0.3), key=lambda s: len(r['shapes'][s]))
    by[(name, grp)].append(LineString(r['shapes'][best]))
    for s in metro['stations']:
        if rid in s['routes']:
            n = clean_stn(s['name'])
            stn_lines[n].add(name); stn_pts[n].append((s['lon'], s['lat']))
lid = lambda n: re.sub(r'\W', '', n.lower())
lines = [feat(unary_union(gs), {'line': lid(n), 'group': g, 'name': n + ' line'}) for (n, g), gs in by.items()]
lines.sort(key=lambda f: -GROUP_ORDER.index(f['properties']['group']))
train_badges = {lid(n): n for n, _ in by}
dump('train_lines', lines)
print('metro lines', len(lines), sorted(n for n, _ in by), colours)
TERMINI = {'Alamein', 'Belgrave', 'Glen Waverley', 'Lilydale', 'Hurstbridge', 'Mernda', 'Cranbourne', 'East Pakenham', 'Pakenham',
           'Sunbury', 'Craigieburn', 'Upfield', 'Frankston', 'Werribee', 'Williamstown', 'Sandringham', 'Stony Point', 'Flemington Racecourse'}
hubs = {'Flinders Street', 'Southern Cross'}
stations = []
for n, pts in stn_pts.items():
    x = sum(p[0] for p in pts) / len(pts); y = sum(p[1] for p in pts) / len(pts)
    p = {'name': n, 'lines': sorted(stn_lines[n]), 'terminus': n in TERMINI}
    if n in hubs: p['hub'] = True
    stations.append(pt(x, y, p))
write('train_stations', stations)
print('train stations', len(stations), '· e.g.', sorted(f['properties']['name'] for f in stations)[:12])

# ---------- Trams ----------
trams = D.get('3', {})
tl, badges, tram_colour = [], {}, {}
by = defaultdict(list)
for rid, r in trams['routes'].items():
    if not r['counts']: continue
    num = (r['short'] or '').strip()
    if not num: continue
    by[num].append(route_geom(r, 0.1))
    by[num + '|name'] = r['long']; tram_colour[num] = '#' + r['color'].upper()
for num in sorted({k for k in by if '|' not in k}, key=lambda s: (int(re.sub(r'\D', '', s) or 0), s)):
    g = unary_union(by[num])
    lid = 't' + re.sub(r'\W', '', num.lower())
    badges[lid] = num
    tl.append(feat(g, {'line': lid, 'name': 'Route ' + num + ' · ' + re.sub(r'\s+-\s+', ' – ', by[num + '|name'] or '')}))
dump('tram_lines', tl)
write('tram_stops', [])
print('tram routes', len(tl), list(badges.values()))

# ---------- V/Line ----------
vl = D.get('1', {})
gm = unary_union([shape(f['geometry']) for f in base['features'] if f['properties'].get('kind') in ('city', 'neighbour')]).buffer(0.01) if base else None
v_lines, v_inner, v_stn = [], [], {}
by = defaultdict(list)
VL_NAME = {'Traralgon': 'Gippsland'}
for rid, r in vl['routes'].items():
    if not r['counts'] or r['short'] == 'Pakenham': continue   # Pakenham: V/Line's own listing of its trains on the Metro line
    by[VL_NAME.get(r['short'], r['short'])].append(r)
for key, rs in by.items():
    r = max(rs, key=lambda r: sum(r['counts'].values()))
    s = max(r['counts'], key=lambda s: (r['counts'][s], len(r['shapes'][s])))
    g = LineString(r['shapes'][s])
    far = re.split(r'\s+-\s+', max(rs, key=lambda r: max(len(v) for v in r['shapes'].values()))['long'])[0].split('/')[0]
    p = {'line': 'VL', 'name': 'V/Line ' + key + ' line', 'to': far, 'color': '#8F1A95', 'offset': 0}
    v_lines.append(feat(g, p))
    if gm is not None:
        gi = g.intersection(gm)
        if not gi.is_empty: v_inner.append(feat(gi, p))
    for st in vl['stations']:
        if any(rid in st['routes'] for rid in [k for k, v in vl['routes'].items() if v in rs]):
            n = clean_stn(st['name'])
            v_stn.setdefault(n, {'pts': [], 'lines': set()})
            v_stn[n]['pts'].append((st['lon'], st['lat'])); v_stn[n]['lines'].add('V/Line')
dump('vline_lines', v_lines); dump('vline_lines_inner', v_inner)
metro_at = {f['properties']['name']: f['geometry']['coordinates'] for f in stations}
vs = []
for n, d in v_stn.items():
    if n in metro_at and n != 'Southern Cross': continue   # a Metro station too: already drawn and named by the trains layer
    c = metro_at.get(n) or [sum(p[0] for p in d['pts']) / len(d['pts']), sum(p[1] for p in d['pts']) / len(d['pts'])]
    vs.append(pt(c[0], c[1], dict({'name': n, 'lines': ['V/Line']}, **({'hub': True} if n == 'Southern Cross' else {}))))
write('vline_stations', vs)
print('V/Line lines', sorted(by), '· stations', len(vs))
json.dump({'trains': train_badges, 'trams': badges}, open(TMP + 'badges.json', 'w'))
css = ["/* Generated by transit.py: each train line in its group's colour; each tram route in its own (PTV's tram network map), thinner. */"]
for f in lines:
    css.append('.sub-line.l%s{stroke:var(--l-%s)}' % (f['properties']['line'], f['properties']['group']))
for lid, num in badges.items():
    css.append('.sub-line.l%s{stroke:%s;stroke-width:2.5px}' % (lid, tram_colour[num]))
open(TMP + 'tram_css.txt', 'w').write('\n'.join(css))
