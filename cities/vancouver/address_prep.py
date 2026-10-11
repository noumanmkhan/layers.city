"""How addresses work, Vancouver's inputs for engine/addresses.py (run.sh runs this first).
Input: raw/public_streets.geojson (fetch_streets.py: every block of every public street, with its hundred-block
address, e.g. "2300 W 47TH AV"; OGL – Vancouver), and the main streets already built (docs/.../streets.geojson).

Writes docs/vancouver/data/streets_ew.geojson, read by engine/addresses.py (not drawn by the page on its own):
  - the dividing line: Ontario St (south of False Creek) and Carrall St (downtown), from the City's blocks;
  - every main street that carries W or E ("W Broadway", "E 41st Ave"), from OpenStreetMap (raw/osm_streets.json).
And raw/address_axes.json: how block numbers run south of False Creek, read off the blocks themselves:
  "ns": [[latitude, number]...] for north-south streets (numbers rise going south, about 100 an avenue);
  "ew": [[longitude, signed number]...] for east-west streets (west negative, 0 at Ontario St);
  "area": [west, south, east, north] where they hold. Downtown's grid is turned 45 degrees and numbered on its
  own, so the readout stops at False Creek.

Checked: on north-south streets the hundreds are the avenue plus 15 (4000 Main St is at 25th Avenue, King
Edward; 6400 at 49th); east-west, Ontario St is 0 and Granville St about 1500 W."""
import json, os, re, statistics
from collections import defaultdict
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, linemerge

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
DATA = os.path.join(HERE, '..', '..', 'docs', 'vancouver', 'data')
SOUTH = 49.268   # False Creek: the south-of-the-creek grid starts below this latitude
SUF = {'AV': 'Ave', 'ST': 'St', 'DR': 'Dr', 'BLVD': 'Blvd', 'RD': 'Rd', 'CRES': 'Cres', 'PL': 'Pl', 'WAY': 'Way', 'HWY': 'Hwy',
       'DIVERSION': 'Diversion', 'MALL': 'Mall', 'ST.': 'St'}


def nice(s):
    """'W 47TH AV' -> 'W 47th Ave'; 'KING EDWARD AV' -> 'King Edward Ave'."""
    w = s.split()
    out = []
    for i, x in enumerate(w):
        if i == len(w) - 1 and x in SUF: out.append(SUF[x])
        elif x in ('W', 'E', 'N', 'S', 'SW', 'SE', 'NW', 'NE') and i == 0: out.append(x)
        elif re.fullmatch(r'\d+(ST|ND|RD|TH)', x): out.append(x.lower())
        else: out.append(x.capitalize() if len(x) > 2 or x.isalpha() else x)
    return ' '.join(out)


blocks = []
for f in json.load(open(os.path.join(RAW, 'public_streets.geojson')))['features']:
    h = (f['properties'].get('hblock') or '').strip()
    m = re.match(r'(\d+)(?:-\d+)? (.*)$', h)
    if m and f['geometry']: blocks.append((int(m.group(1)), m.group(2), shape(f['geometry'])))
main = {f['properties']['name'] for f in json.load(open(os.path.join(DATA, 'streets.geojson')))['features']}

feats, by = [], defaultdict(list)
for n, st, g in blocks:   # the dividing streets aren't arterials, so they come from the City's blocks
    name = nice(st)
    if name in ('Ontario St', 'Carrall St'): by[name].append(g)
# The W and E main streets from OpenStreetMap, as drawn (the City's blocks stop short at every intersection).
import sys; sys.path.insert(0, HERE)
from names import street_name
from shapely.geometry import LineString
for w_ in json.load(open(os.path.join(RAW, 'osm_streets.json')))['elements']:
    name = street_name(w_['tags'].get('name', ''))
    w = name.split()
    if len(w) > 1 and w[0] in ('W', 'E') and ' '.join(w[1:]) in main and len(w_.get('geometry', [])) > 1:
        by[name].append(LineString([(p['lon'], p['lat']) for p in w_['geometry']]))
for name, gs in sorted(by.items()):
    m = linemerge(unary_union(gs))
    m = m.simplify(0.00003)
    feats.append({'type': 'Feature', 'properties': {'name': name}, 'geometry': mapping(m)})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(DATA, 'streets_ew.geojson'), 'w'), separators=(',', ':'))

# Block numbers against position, south of False Creek: the median number in each thin band, then made
# monotonic (diagonals like Kingsway and the odd mis-numbered block pull single bands about).
ns, ew = defaultdict(list), defaultdict(list)
for n, st, g in blocks:
    c = g.centroid
    if c.y > SOUTH: continue
    w = st.split()
    if w[0] in ('W', 'E'): ew[round(c.x / 0.004) * 0.004].append(-n if w[0] == 'W' else n)
    elif w[-1] != 'AV' and not st.startswith(('KINGSWAY', 'SW MARINE', 'SE MARINE')): ns[round(c.y / 0.004) * 0.004].append(n)


def axis(bins, rising):
    pts = [[round(k, 4), statistics.median(v)] for k, v in sorted(bins.items()) if len(v) >= 5]
    # rising: numbers grow with the coordinate (east-west); otherwise they fall as latitude grows (going north).
    out, best = [], None
    for k, v in (pts if rising else pts[::-1]):
        best = v if best is None else max(best, v)
        out.append([k, round(best, -2)])
    return sorted(out)


axes = {'ns': axis(ns, False), 'ew': axis(ew, True)}
xs = [k for k in ew]; ys = [k for k in ns]
area = [round(min(xs), 3), round(min(ys), 3), round(max(xs), 3), SOUTH]
json.dump({'ns': axes['ns'], 'ew': axes['ew'], 'area': area}, open(os.path.join(RAW, 'address_axes.json'), 'w'), separators=(',', ':'))
print('streets_ew:', len(feats), 'streets ·', sum(n.startswith('W ') for n in by), 'W,', sum(n.startswith('E ') for n in by), 'E')
print('axes: ns', len(axes['ns']), 'bands', axes['ns'][0], '…', axes['ns'][-1], '· ew', len(axes['ew']), axes['ew'][0], '…', axes['ew'][-1], '· area', area)
