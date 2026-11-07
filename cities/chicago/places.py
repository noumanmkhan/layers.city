"""Chicago's Schools, Parks and Sports & rec layers -> docs/chicago/data/schools.geojson, parks.geojson, sports.geojson.
The same shapes as Toronto's, New York's and San Francisco's (the engine's places and parks layer kinds read them).

Schools: Chicago Public Schools' own profile list (raw/attendance/profiles.json, fetch_attendance.py: CPS school
  profiles on the City portal, this school year), every school CPS runs or charters, placed by CPS's own position.
  Elementary includes K-8; middle schools (6-8) count as secondary, as in San Francisco. Type from CPS's network:
  Charter, Options (alternative programs for students re-enrolling) or district-run. No private or parochial schools.
Parks and Sports & rec: OpenStreetMap (raw/parks/osm_parks.json, fetch_parks.py), because the Park District's own
  files on the City portal stopped in 2016. See the notes by each section.
Describe only: never rank; no ratings (CPS's school ratings are deliberately not used)."""
import json, math, os, re
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping, Point, Polygon, LineString, MultiPolygon
from shapely.ops import unary_union, polygonize, linemerge
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'docs', 'chicago', 'data')
pt = lambda x, y: {'type': 'Point', 'coordinates': [round(float(x), 5), round(float(y), 5)]}
CITY = unary_union([shape(f['geometry']) for f in json.load(open(os.path.join(DATA, 'sides.geojson')))['features']]).buffer(0.001)


def write(name, obj):
    json.dump(obj, open(os.path.join(DATA, name), 'w'), separators=(',', ':'), ensure_ascii=False)


# ---------- Schools ----------
TYPE = {'Charter': 'Charter school', 'Options': 'Options school', 'Contract': 'Contract school'}
schools = []
for r in json.load(open(os.path.join(HERE, 'raw', 'attendance', 'profiles.json'))):
    try:
        x, y = float(r['school_longitude']), float(r['school_latitude'])
    except (KeyError, TypeError, ValueError):
        continue
    g = (r.get('grades_offered') or '').replace('-', '–').strip()
    gl = (r.get('grades_offered_all') or '').split(',')
    hi = max((int(v) for v in gl if v.strip().isdigit()), default=None)
    has_k = 'K' in gl
    cat = 'elementary' if (r.get('primary_category') == 'ES' or (has_k and (hi or 0) <= 8)) else 'secondary'
    b = TYPE.get(r.get('network'), 'District school')
    name = re.sub(r'\s+', ' ', r.get('long_name') or r.get('short_name') or '').strip()
    a = re.sub(r'\b(\w)(\w*)', lambda m: m.group(1) + m.group(2).lower(), (r.get('address') or '').strip())
    a = re.sub(r'\b([NSEW])\b', lambda m: m.group(1).upper(), a)
    p = {'name': name, 'cat': cat, 'sub': b + (' · ' + g if g else ''), 'g': g, 'b': b, 'a': a}
    u = (r.get('website') or {}).get('url') if isinstance(r.get('website'), dict) else None
    if u: p['u'] = u
    schools.append({'type': 'Feature', 'properties': p, 'geometry': pt(x, y)})
year = re.sub(r'^School Year (\d{4})-\d{2}(\d{2})$', r'\1–\2', json.load(open(os.path.join(HERE, 'raw', 'attendance', 'profiles.json')))[0].get('school_year') or '')
write('schools.geojson', {'type': 'FeatureCollection', 'asof': year, 'count': dict(Counter(f['properties']['cat'] for f in schools)), 'features': schools})
print('schools:', len(schools), dict(Counter(f['properties']['cat'] for f in schools)), dict(Counter(f['properties']['b'] for f in schools)), 'year', year)


# ---------- Parks (OpenStreetMap) ----------
# Every named park and nature area with an outline whose middle is in the city. A nature area mostly inside a park
# isn't drawn twice. Amenities: a playground or dog park inside the outline. No link (no Park District page ids).
osm = json.load(open(os.path.join(HERE, 'raw', 'parks', 'osm_parks.json')))
asof_parks = osm.get('fetched')


def outline(e):
    if e['type'] == 'way':
        cs = [(p['lon'], p['lat']) for p in e.get('geometry') or []]
        return Polygon(cs).buffer(0) if len(cs) >= 4 else None
    lines = [LineString([(p['lon'], p['lat']) for p in m['geometry']]) for m in e.get('members', [])
             if m.get('type') == 'way' and m.get('role') in ('outer', '') and len(m.get('geometry') or []) >= 2]
    if not lines:
        return None
    polys = [q.buffer(0) for q in polygonize(linemerge(lines))]
    polys = [q for q in polys if not q.is_empty]
    if not polys:
        return None
    try:
        return unary_union(polys).buffer(0)
    except Exception:   # overlapping rings that GEOS won't join: keep the biggest
        return max(polys, key=lambda q: q.area)


raw_parks = []
for e in osm['elements']:
    t = e.get('tags', {})
    if t.get('leisure') not in ('park', 'nature_reserve') or 'geometry' not in e and 'members' not in e:
        continue
    g = outline(e)
    if g is None or g.is_empty or not CITY.contains(g.representative_point()):
        continue
    # The Park District's formal names put the namesake's first name in brackets: "Lincoln (Abraham) Park",
    # "Douglass (Anna and Frederick) Park". Shown as people say them: Lincoln Park, Douglass Park.
    n = re.sub(r'^(.+?) \([^)]*\)( Park| Playlot Park| Playlot)?$', lambda m: m.group(1) + (m.group(2) or ''), t['name'].strip())
    raw_parks.append((n, t['leisure'], g))
raw_parks.sort(key=lambda p: (p[1] != 'park', -p[2].area))   # parks first, biggest first
kept = []
for n, kind, g in raw_parks:
    if kind == 'nature_reserve' and any(k[2].intersection(g).area > 0.5 * g.area for k in kept):
        continue
    if any(k[0] == n and k[2].intersection(g).area > 0.5 * g.area for k in kept):
        continue   # the same park mapped twice
    kept.append((n, kind, g))
PTREE = STRtree([g for *_, g in kept])


def park_of(x, y):
    p = Point(x, y)
    for i in PTREE.query(p):
        if kept[i][2].contains(p):
            return i
    return None


at = lambda e: (e['center']['lon'], e['center']['lat']) if 'center' in e else (e.get('lon'), e.get('lat'))
amen = defaultdict(set)
SPORT = {'tennis': ['tennis'], 'pickleball': ['pickleball'], 'basketball': ['basketball'], 'baseball': ['diamond'], 'softball': ['diamond'],
         'soccer': ['field'], 'american_football': ['field'], 'football': ['field'], 'cricket': ['field'], 'rugby_union': ['field'],
         'skateboard': ['skatepark'], 'swimming': ['pool']}
fac = defaultdict(lambda: {'cats': Counter(), 'pts': []})
for e in osm['elements']:
    t = e.get('tags', {})
    if t.get('leisure') in ('park', 'nature_reserve'):
        continue
    x, y = at(e)
    if x is None:
        continue
    i = park_of(x, y)
    if i is None:
        continue   # outside every park: school fields, apartment pools, private courts
    if t.get('leisure') == 'playground': amen[i].add('play'); continue
    if t.get('leisure') == 'dog_park': amen[i].add('dog'); continue
    if t.get('leisure') == 'swimming_pool' or (t.get('leisure') == 'sports_centre' and 'swimming' in (t.get('sport') or '')):
        cats = ['pool']
    else:
        cats = sorted({c for s in re.split(r'[;,]\s*', t.get('sport') or '') for c in SPORT.get(s.strip(), [])})
    if not cats:
        continue
    fac[i]['pts'].append((x, y))
    for c in cats:
        fac[i]['cats'][c] += 1
rnd = lambda o: [rnd(v) for v in o] if isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]
parks = []
for i, (n, kind, g) in enumerate(kept):
    gs = g.simplify(0.00002, preserve_topology=True)
    pr = {'n': n, 't': 'Park' if kind == 'park' else 'Nature area'}
    am = [a for a in ('play', 'dog') if a in amen[i]]
    if am: pr['a'] = am
    gm = mapping(gs)
    parks.append({'type': 'Feature', 'properties': pr, 'geometry': {'type': gm['type'], 'coordinates': rnd(gm['coordinates'])}})
write('parks.geojson', {'type': 'FeatureCollection', 'asof': {'parks': asof_parks}, 'count': len(parks), 'features': parks})
print('parks:', len(parks), dict(Counter(a for f in parks for a in f['properties'].get('a', []))), os.path.getsize(os.path.join(DATA, 'parks.geojson')) // 1024, 'KB')

# ---------- Sports & rec: one point per park, with its sports ----------
NOUN = {'pool': ('pool', 'pools'), 'diamond': ('ball field', 'ball fields'), 'field': ('sports field', 'sports fields'), 'tennis': ('tennis court', 'tennis courts'),
        'pickleball': ('pickleball court', 'pickleball courts'), 'basketball': ('basketball court', 'basketball courts'), 'skatepark': ('skatepark', 'skateparks')}
ORDER = ['pool', 'diamond', 'field', 'tennis', 'pickleball', 'basketball', 'skatepark']
sports = []
for i, s in fac.items():
    cats = [c for c in ORDER if s['cats'][c]]
    x = sum(a for a, _ in s['pts']) / len(s['pts']); y = sum(b for _, b in s['pts']) / len(s['pts'])
    has = ', '.join('%d %s' % (s['cats'][c], NOUN[c][0] if s['cats'][c] == 1 else NOUN[c][1]) for c in cats)
    sports.append({'type': 'Feature', 'properties': {'name': kept[i][0], 'cat': cats[0], 'cats': cats, 'sub': 'In the park', 'has': has}, 'geometry': pt(x, y)})
counts = {c: sum(1 for f in sports if c in f['properties']['cats']) for c in ORDER}
write('sports.geojson', {'type': 'FeatureCollection', 'asof': asof_parks, 'count': len(sports), 'counts': counts, 'features': sports})
print('sports:', len(sports), counts)
