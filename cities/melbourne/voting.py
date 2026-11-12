"""Where to vote in the Victorian state election (November 28, 2026) -> docs/melbourne/data/voting.geojson.

Victorians can vote at any voting centre in the state, early or on election day, so the file is the card's
"county of vote centers" shape (engine/map.js, Where to vote): one area, k "vic", covering the City and the 30
other metropolitan councils, and "centers" [x, y, name, room, address, k, kind] for every early voting centre
(kind 3: all of them are election day centres too, from this election) and election day centre (kind 1) in and
near Greater Melbourne. From the VEC's venues spreadsheet and the places fetch_voting.py found for its addresses
(cities/melbourne/raw/voting/). A venue the address search couldn't place is left out and counted in the log."""
import json, os, re
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(HERE, 'raw', 'voting')
OUT = os.path.join(ROOT, 'docs', 'melbourne', 'data')

sheets = json.load(open(os.path.join(RAW, 'venues.json')))['sheets']
sites = json.load(open(os.path.join(RAW, 'sites.json')))
m = re.search(r'correct as at (\d+)\w* (\w{3})\w* ', ' '.join(str(c) for r in sheets['Definitions'] for c in r if c))
MONTHS = {'Oct': '10', 'Nov': '11', 'Dec': '12'}
asof = f'2026-{MONTHS[m.group(2)]}-{int(m.group(1)):02d}' if m else None

# The area: the City's suburbs and the region's councils, so a pin anywhere in Greater Melbourne gets the box.
parts = [shape(f['geometry']).buffer(0) for n in ('suburbs', 'region_areas')
         for f in json.load(open(os.path.join(OUT, n + '.geojson')))['features']]
area = unary_union(parts).buffer(0.0005).simplify(0.0008)
near = area.buffer(0.06)   # centres just past the edge are still the nearest for someone on it

def tidy(name): return re.sub(r'\s*\((?:EVC|VC|JEVC|HJEVC|JVC|HJVC)\)\s*$', '', str(name or '')).strip()

centres, missing = {}, 0
for sheet, bit in (('EVCs', 3), ('VCs', 1)):
    h = sheets[sheet][0]; ix = {k: h.index(k) for k in h if k}
    for r in sheets[sheet][1:]:
        line, sub, pc = (str(r[ix[c]] or '').strip() for c in ('Address Line 1', 'Suburb', 'Post Code'))
        key = f'{line}|{sub}|{pc}'
        s = sites.get(key)
        if not s or s[0] is None: missing += 1; continue
        if not near.contains(Point(s[0], s[1])): continue
        if key in centres: centres[key][6] |= bit; continue
        centres[key] = [s[0], s[1], tidy(r[ix['Venue Name']]), '', f'{line}, {sub}', 'vic', bit]

C = sorted(centres.values(), key=lambda c: (c[1], c[0]))
fc = {'type': 'FeatureCollection', 'asof': asof, 'election': '2026-11-28', 'centers': C,
      'counts': {'vic': {'ev': sum(1 for c in C if c[6] & 2), 'ed': sum(1 for c in C if c[6] & 1)}},
      'features': [{'type': 'Feature', 'properties': {'k': 'vic'}, 'geometry': mapping(area)}]}
s = json.dumps(fc, separators=(',', ':'))
s = re.sub(r'(\d+\.\d{6})\d+', r'\1', s)
open(os.path.join(OUT, 'voting.geojson'), 'w').write(s)
print(f'voting.geojson: {len(C)} centres ({fc["counts"]["vic"]}), {missing} venue rows not placed, as of {asof}, {len(s) // 1000} KB')
