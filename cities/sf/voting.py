"""Build docs/sf/data/voting.geojson: where San Franciscans vote on November 3, 2026, for the card's where-to-vote box.

Inputs (fetch_voting.py, raw/voting/): the Department of Elections' polling place list (rows.json, from its xlsx: one
row per precinct, "Pct 1101", with the polling place's name, address and cross streets; "Pct 1103 MB" marks a
mail-ballot precinct, which has no polling place), the 2022 precincts (precincts.geojson, DataSF d6x4-hefw) and the
sites placed by the Census geocoder (sites.json). Addresses the geocoder missed are placed from the City's own address
points (raw/addresses.json, fetch_addresses.py).

New York's shape: one feature per precinct, `c` and `p` the precinct number, `s` its polling place and `e` the City Hall
Voting Center (where anyone can vote early, from October 5), as indexes into a top-level `sites` list of
[name, address, x, y]. A mail-ballot precinct has no `s`. Top level: asof (the list's date), election, sites."""
import json, os, re
from shapely.geometry import shape, mapping

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HERE, 'raw', 'voting')
OUT = os.path.join(HERE, '..', '..', 'docs', 'sf', 'data', 'voting.geojson')
ASOF = '2026-09-29'   # the list's own date (its file name); change with the list
CITY_HALL = ['City Hall Voting Center', '1 Dr Carlton B Goodlett Pl (ground floor, outside Room 48)', -122.41925, 37.77925]

rows = json.load(open(os.path.join(V, 'rows.json')))
head = rows[0]
col = {k: next(i for i, c in enumerate(head) if c.startswith(k)) for k in ('Election Precinct', 'Polling Place Name', 'Polling Place Address', 'Polling Place Entrance', 'ADA')}
placed = json.load(open(os.path.join(V, 'sites.json')))['sites']

# The City's address points for anything the geocoder missed: "1199 MASON ST" -> position.
SUF = {'St': 'ST', 'Ave': 'AVE', 'Dr': 'DR', 'Way': 'WAY', 'Blvd': 'BLVD', 'Pl': 'PL', 'Ter': 'TER', 'Ct': 'CT', 'Ln': 'LN'}
eas = {}
for st, n, x, y in json.load(open(os.path.join(HERE, 'raw', 'addresses.json')))['rows']:
    eas[(st, n)] = (x, y)
def from_eas(a):
    m = re.match(r'(\d+)\s+(.*)$', a.strip())
    if not m: return None
    st = m.group(2).split()
    st = [SUF.get(w, w) for w in st]
    s = ' '.join(st).upper().replace('THE EMBARCADERO', 'THE EMBARCADERO')
    for cand in (s, s.replace('N STATE DR', 'STATE DR'), re.sub(r'^(\d+)(ST|ND|RD|TH)\b', lambda k: k.group(1).zfill(2) + k.group(2), s)):
        if (cand, int(m.group(1))) in eas: return eas[(cand, int(m.group(1)))]
    return None

def tidy(s):
    s = re.sub(r'\s+', ' ', s or '').strip()
    return re.sub(r'\b[Bb]tw\b\.?', 'between', s)

sites, idx, by_pct, mail, missing = [CITY_HALL], {}, {}, set(), []
for r in rows[1:]:
    m = re.match(r'Pct\s+(\d+)(\s+MB)?', r[col['Election Precinct']])
    if not m: continue
    pct = m.group(1)
    if m.group(2) or not r[col['Polling Place Address']]: mail.add(pct); continue
    name, addr = r[col['Polling Place Name']], r[col['Polling Place Address']]
    xy = placed.get(addr) or from_eas(addr)
    if not xy: missing.append(addr)
    where = tidy(r[col['Polling Place Entrance']])
    a = addr + (f' ({where})' if where else '')
    if r[col['ADA']].lower().startswith('no'): a += ' · not listed as accessible'
    k = (name, a)
    if k not in idx:
        idx[k] = len(sites); sites.append([name, a] + ([round(xy[0], 6), round(xy[1], 6)] if xy else []))
    by_pct[pct] = idx[k]

feats, nomatch = [], []
for f in json.load(open(os.path.join(V, 'precincts.geojson')))['features']:
    pct = str(f['properties'].get('prec_2022') or '').strip()
    g = shape(f['geometry']).buffer(0).simplify(0.00002, preserve_topology=True)
    p = {'c': pct, 'p': pct, 'e': 0}
    if pct in by_pct: p['s'] = by_pct[pct]
    elif pct not in mail: nomatch.append(pct)
    m = mapping(g)
    rnd = lambda o: [rnd(x) for x in o] if isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]
    feats.append({'type': 'Feature', 'geometry': {'type': m['type'], 'coordinates': rnd(m['coordinates'])}, 'properties': p})
json.dump({'type': 'FeatureCollection', 'asof': ASOF, 'election': '2026-11-03', 'sites': sites, 'features': feats},
          open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
listed = set(by_pct) | mail
print(f'voting: {len(feats)} precincts, {len(sites) - 1} polling places, {len(mail)} mail-ballot precincts;'
      f' unplaced {missing}; precincts with no row {nomatch}; rows with no precinct shape {sorted(listed - {f["properties"]["c"] for f in feats})}')
