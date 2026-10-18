"""The Sports & rec layer: City pools, rinks, fields and courts, raw/nearby/ -> docs/toronto/data/sports.geojson

  rec_facilities.json  "Registered Programs and Drop In Courses Offering" (Parks, Forestry & Recreation): its
                       Facilities tab, one row per facility (each pool tank, ice pad, diamond, field and court),
                       and its Locations tab. Its Location ID is the parks list's LOCATIONID.
  parks_rec.geojson    the City's parks list: a position per location, its toronto.ca page, and the only
                       source that says which parks have pickleball courts.

One point per location with at least one of the sports below; the map shows the ones with any picked sport.
A location the parks list doesn't place takes its parent location's position, else a City park outline of
the same name (green_spaces.geojson); a few school yards and hydro fields with neither are left out.

  {"asof": "October 15, 2026", "count": n, "counts": {sport: locations}, "features": [{"properties": {
     "name": "Christie Pits Park", "cat": first sport (the pin's glyph), "cats": [every sport there],
     "sub": "Park" | "Community centre", "has": "3 ball diamonds, 1 outdoor pool, ...", "addr": "750 Bloor St W",
     "u": its page on toronto.ca}}]}"""
import json, os, re
from shapely.geometry import shape

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'nearby')
OUT = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'sports.geojson')

# Chip order; a pin shows the first sport it has. Each sport: the City's FacilityType pattern, then how a facility
# is counted in the popup (singular, plural), split by kind where the type says indoor or outdoor.
SPORTS = ['pool', 'rink', 'diamond', 'field', 'tennis', 'pickleball', 'basketball', 'skatepark', 'cricket']
KINDS = [  # (sport, FacilityType pattern, singular, plural)
    ('pool', r'^Indoor Pool Tank', 'indoor pool', None),     # counted by tank (lap, leisure, teach), so not counted
    ('pool', r'^Outdoor Pool Tank', 'outdoor pool', None),
    ('rink', r'^Indoor Ice Pad', 'indoor ice pad', 'indoor ice pads'),
    ('rink', r'^Outdoor Ice Pad', 'outdoor rink', 'outdoor rinks'),
    ('rink', r'^Skate Trail', 'skating trail', 'skating trails'),
    ('diamond', r'^Baseball Diamond', 'ball diamond', 'ball diamonds'),
    ('field', r'^Soccer Field', 'soccer field', 'soccer fields'),
    ('field', r'^Football Field', 'football field', 'football fields'),
    ('field', r'^Rugby Field', 'rugby field', 'rugby fields'),
    ('field', r'^Multipurpose Field', 'multipurpose field', 'multipurpose fields'),
    ('tennis', r'^Indoor Tennis Court', 'indoor tennis court', 'indoor tennis courts'),
    ('tennis', r'^Outdoor Tennis Court', 'tennis court', 'tennis courts'),
    ('basketball', r'^Basketball Court', 'basketball court', 'basketball courts'),
    ('skatepark', r'^Skateboard Area', 'skatepark', None),
    ('cricket', r'^Cricket Pitch', 'cricket pitch', 'cricket pitches'),
]
# Locations the parks list doesn't place and whose name isn't an outline's: Location Name -> outline name.
ALIAS = {'Sunnyside Bathing Pavilion and Gus Ryder Outdoor Pool': 'Sunnyside Park'}
SMALL = {'and', 'of', 'the', 'at', 'on', 'in', 'for', 'de', 'la'}


def title(s):   # the City's names are in capitals; as in parks.py
    words = re.sub(r'\s+', ' ', s.strip()).lower().split(' ')
    out = []
    for i, w in enumerate(words):
        w = '-'.join(p[:1].upper() + p[1:] for p in w.split('-')) if (i == 0 or w not in SMALL) else w
        out.append(re.sub(r"^(O'|Mc|L'|D')(\w)", lambda m: m.group(1) + m.group(2).upper(), w))
    out = re.sub(r'(?<![A-Za-z])([a-z])\.', lambda m: m.group(1).upper() + '.', ' '.join(out))
    return out.replace("'S ", "'s ").replace("'S", "'s").replace('( ', '(').replace('Trca', 'TRCA')


def norm(s):
    s = re.sub(r'[^a-z0-9 ]', ' ', (s or '').lower())
    return ' '.join(w for w in s.split() if w not in ('the', 'park', 'parkette', 'and'))


rec = json.load(open(os.path.join(RAW, 'rec_facilities.json')))
plist = json.load(open(os.path.join(RAW, 'parks_rec.geojson')))
pos = {str(f['properties']['LOCATIONID']): f for f in plist['features']}
locs = {str(l['Location ID']): l for l in rec['locations']}
outline = {}
for f in json.load(open(os.path.join(RAW, 'green_spaces.geojson')))['features']:
    if f.get('geometry'):   # parks first; "Otter Creek Centre - Building Grounds" is found as "Otter Creek Centre"
        k = norm(re.sub(r'\s+-\s+.*$', '', f['properties'].get('name') or ''))
        if k not in outline or f['properties'].get('class') == 'Park': outline[k] = f


def place(lid):
    """The parks-list entry for a location (or its parent), else a point inside a same-named park outline."""
    for i in (lid, str((locs.get(lid) or {}).get('Parent Location ID') or '')):
        if i in pos:
            f = pos[i]; c = f['geometry']['coordinates']
            return (c[0] if isinstance(c[0], list) else c), f['properties']   # a few are MultiPoints
    n = (locs.get(lid) or {}).get('Location Name')
    o = outline.get(norm(ALIAS.get(n, n)))
    if o:
        p = shape(o['geometry']).representative_point(); return [p.x, p.y], None
    return None, None


def address(lid, pl):
    if pl and pl.get('ADDRESS') not in (None, 'None'): return pl['ADDRESS']
    l = locs.get(lid) or {}
    bits = [l.get(k) for k in ('Street No', 'Street No Suffix', 'Street Name', 'Street Type', 'Street Direction')]
    return re.sub(r'\s+', ' ', ' '.join(str(b) for b in bits if b not in (None, 'None', ''))).strip()


at = {}   # location id -> {(sport, singular, plural): count}
for f in rec['facilities']:
    t = f.get('FacilityType') or ''
    for sport, rx, one, many in KINDS:
        if re.search(rx, t):
            k = at.setdefault(str(f['Location ID']), {}); key = (sport, one, many); k[key] = k.get(key, 0) + 1
            break
for lid, f in pos.items():   # pickleball is only in the parks list, without a count
    if 'Pickleball Court' in (f['properties'].get('AMENITIES') or '').split(', '):
        at.setdefault(lid, {})[('pickleball', 'pickleball courts', None)] = 0

feats, skipped, seen = [], [], {}
for lid, kinds in at.items():
    xy, pl = place(lid)
    name = (pl or {}).get('ASSET_NAME') or (locs.get(lid) or {}).get('Location Name')
    if not xy or not name:
        skipped.append((lid, name)); continue
    xy = [round(xy[0], 5), round(xy[1], 5)]
    cats = [s for s in SPORTS if any(k[0] == s for k in kinds)]
    order = sorted(kinds, key=lambda k: (SPORTS.index(k[0]), [x[2] for x in KINDS].index(k[1]) if k[0] != 'pickleball' else 0))
    has = ', '.join(k[1] if not k[2] else f'{n} {k[1] if n == 1 else k[2]}' for k in order for n in [kinds[k]])
    ltype = (pl or {}).get('TYPE') or (locs.get(lid) or {}).get('Location Type') or ''
    sub = 'Community centre' if 'Centre' in ltype or 'Arena' in ltype else 'Park' if ltype in ('Park', 'park') else ''
    props = {'name': title(name), 'cat': cats[0], 'cats': cats, 'sub': sub, 'has': has[:1].upper() + has[1:], 'addr': address(lid, pl)}
    if pl and (pl.get('URL') or '').startswith('https://'): props['u'] = pl['URL']
    key = (props['name'], tuple(xy))   # child locations that land on their parent's point merge into one pin
    if key in seen:
        p = seen[key]['properties']
        p['cats'] = [s for s in SPORTS if s in p['cats'] or s in cats]; p['cat'] = p['cats'][0]
        p['has'] = p['has'] + ', ' + has
        continue
    seen[key] = {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': xy}, 'properties': props}
    feats.append(seen[key])

feats.sort(key=lambda f: f['properties']['name'])
counts = {s: sum(s in f['properties']['cats'] for f in feats) for s in SPORTS}
import datetime   # shown in the popup's fine print, e.g. "October 15, 2026"
d = (rec.get('refreshed') or '')[:10]
asof = datetime.date.fromisoformat(d).strftime('%B %-d, %Y') if d else ''
json.dump({'type': 'FeatureCollection', 'asof': asof, 'count': len(feats), 'counts': counts, 'features': feats},
          open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
print('sports & rec:', len(feats), 'locations as of', asof, counts)
print('  left out (no position):', len(skipped), [n for _, n in skipped][:12])
