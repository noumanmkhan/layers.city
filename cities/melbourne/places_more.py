"""Melbourne's Hospitals, Colleges & universities, Schools, Libraries & community centres, Places of worship, Bike
lanes and New development layers -> docs/melbourne/data/institutions.geojson, schools.geojson, community.geojson,
faith.geojson, bikes.geojson and changes.geojson. The same shapes as Toronto's and Chicago's. Inputs: raw/more/
(fetch_more.py).

- Hospitals: OpenStreetMap hospitals tagged with an emergency department, across Greater Melbourne (the ERs a
  person in the City would go to are mostly in the City and the next suburbs). Universities and TAFEs: OSM campuses
  in the City, one point per campus, by name.
- Schools: the Department of Education's School Locations (CC BY 4.0), every government, Catholic and independent
  school in the City and within about a kilometre of it, by level (primary; secondary and Prep-12), with the sector
  as a group.
- Libraries & community centres: OSM, in the City: public libraries (council, State Library) and community centres,
  hubs and neighbourhood houses; university and private libraries, social clubs and halls left out.
- Places of worship: OSM, in the City, named ones only, one point per place; Toronto's rules (facilities, never
  people; denomination only when OSM gives one or the name says it).
- Bike lanes: OSM ways in the City: separated lanes and bike-only paths beside roads (protected), painted lanes,
  shared lanes, and shared paths and trails.
- New development: the City of Melbourne's Development Activity Monitor (CC BY 4.0): applications, approvals,
  projects under construction, and those completed in the last two years. It gives no dates beyond the year a
  project was completed, so the popup says when the City's list was last updated."""
import csv, json, math, os, re
from collections import Counter
from shapely.geometry import shape, Point, LineString, mapping
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(HERE, 'raw', 'more')
DATA = os.path.join(ROOT, 'docs', 'melbourne', 'data')
CITY = unary_union([shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(DATA, 'suburbs.geojson')))['features']])
NEAR = CITY.buffer(0.012)   # about a kilometre past the edge
REGION = unary_union([shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(DATA, 'region_areas.geojson')))['features']] + [CITY])


def write(name, obj):
    open(os.path.join(DATA, name), 'w').write(json.dumps(obj, separators=(',', ':'), ensure_ascii=False))


def at(e):
    c = e.get('center') or e
    return (round(c['lon'], 5), round(c['lat'], 5)) if c.get('lon') is not None else None


def metres(a, b):
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * 111320 * k, (a[1] - b[1]) * 110540)


def pt(c): return {'type': 'Point', 'coordinates': list(c)}


def one_each(items, radius=150):
    """One point per place: the same name within radius metres is the same place (a node inside its building)."""
    kept = []
    for it in items:
        if any(k['name'].lower() == it['name'].lower() and metres(k['at'], it['at']) < radius for k in kept): continue
        kept.append(it)
    return kept


osm_city = json.load(open(os.path.join(RAW, 'osm_city.json')))['elements']
osm_region = json.load(open(os.path.join(RAW, 'osm_region.json')))['elements']

# ---------- Hospitals (ERs) and campuses -> institutions.geojson ----------
inst = []
for e in osm_region:
    t = e.get('tags', {}); c = at(e)
    if not c or not t.get('name'): continue
    if t.get('amenity') == 'hospital' and t.get('emergency') == 'yes' and REGION.contains(Point(c)):
        inst.append({'name': t['name'], 'at': c, 'cat': 'hospital', 'sub': 'Emergency department', 'ed': 1})
CAMPUS = re.compile(r'universit|RMIT|TAFE|institute of technology|polytechnic|college of|conservatorium|academy', re.I)
NOT = re.compile(r'^RMIT University$|Royal Australasian College|Australian National University|School of |residential college|hall of residence|student accommodation|\bhouse\b|library|building \d|carpark|car park', re.I)
for e in osm_region:
    t = e.get('tags', {}); c = at(e)
    if not c or not t.get('name') or t.get('amenity') not in ('university', 'college'): continue
    if not CITY.contains(Point(c)) or not CAMPUS.search(t['name']) or NOT.search(t['name']): continue
    if e['type'] == 'node': continue   # campuses are drawn as areas; nodes are offices and buildings inside them
    tafe = t['amenity'] == 'college' or re.search(r'TAFE|polytechnic|Kangan', t['name'], re.I)
    inst.append({'name': t['name'], 'at': c, 'cat': 'college' if tafe else 'university', 'sub': 'TAFE' if tafe else 'University'})
inst = one_each(inst, 600)
feats = []
for i in inst:
    p = {'name': i['name'], 'cat': i['cat'], 'sub': i['sub']}
    if i.get('ed'): p['ed'] = 1
    feats.append({'type': 'Feature', 'properties': p, 'geometry': pt(i['at'])})
write('institutions.geojson', {'type': 'FeatureCollection', 'features': feats})
print('institutions:', dict(Counter(f['properties']['cat'] for f in feats)), [f['properties']['name'] for f in feats if f['properties']['cat'] != 'hospital'])

# ---------- Schools ----------
rows = list(csv.DictReader(open(os.path.join(RAW, 'school_locations.csv'), encoding='cp1252')))
YEARS = {'Primary': 'Prep–Year 6', 'Secondary': 'Year 7–12', 'Pri/Sec': 'Prep–Year 12', 'Special': 'Specialist school', 'Language': 'English language school'}
GRP = {'Government': 'gov', 'Catholic': 'cath', 'Independent': 'ind'}
feats = []
for r in rows:
    try: c = (round(float(r['X']), 5), round(float(r['Y']), 5))
    except ValueError: continue
    if not NEAR.contains(Point(c)) or r['School_Status'] not in ('O', 'Open', ''): continue
    lvl = 'secondary' if r['School_Type'] in ('Secondary', 'Pri/Sec') else 'elementary'
    addr = ', '.join(x for x in (r['Address_Line_1'].strip().title().replace("'S ", "'s "), r['Address_Town'].strip().title()) if x)
    sector = r['Education_Sector']
    feats.append({'type': 'Feature', 'properties': {'name': r['School_Name'].strip(), 'cat': lvl, 'grp': GRP.get(sector, 'ind'),
                  'sub': f'{sector} · {YEARS.get(r["School_Type"], r["School_Type"])}', 'g': YEARS.get(r['School_Type'], r['School_Type']),
                  'b': sector, 'a': addr}, 'geometry': pt(c)})
year = re.findall(r'20\d\d', open(os.path.join(RAW, 'datavic.json')).read() and json.dumps([v['title'] for v in json.load(open(os.path.join(RAW, 'datavic.json'))).values() if 'School Locations' in v['title']]))
write('schools.geojson', {'type': 'FeatureCollection', 'asof': max(year) if year else None,
                          'count': dict(Counter(f['properties']['cat'] for f in feats)), 'features': feats})
print('schools:', len(feats), dict(Counter((f['properties']['cat'], f['properties']['grp']) for f in feats)))

# ---------- Libraries & community centres ----------
COUNCIL = re.compile(r'city of|council|library service|state library', re.I)
UNI = re.compile(r'Dalton McCaughey|universit|RMIT|UMSU|ACU|college|institute|NGV|law library|legal aid|reading room|little|toy|braille', re.I)
HUB = re.compile(r'community (centre|center|hub|house)|neighbou?rhood (house|centre|learning)|learning centre|\bhub\b', re.I)
CLUB = re.compile(r'club|church|parish|RSL|hall\b|society|house$|compost|food forest|men.s shed|cooperative|association|brotherhood', re.I)
items = []
for e in osm_city:
    t = e.get('tags', {}); c = at(e); n = (t.get('name') or '').strip()
    if not c or not n or not CITY.contains(Point(c)): continue
    if t.get('amenity') == 'library' and not UNI.search(n + ' ' + (t.get('operator') or '')) and (COUNCIL.search(t.get('operator') or '') or n.endswith('Library') or 'Library' in n):
        items.append({'name': n, 'at': c, 'cat': 'library'})
    elif t.get('amenity') == 'community_centre' and (COUNCIL.search(t.get('operator') or '') or HUB.search(n)) and not CLUB.search(n):
        items.append({'name': n, 'at': c, 'cat': 'centre'})
items = one_each(items)
feats = [{'type': 'Feature', 'properties': {'name': i['name'], 'cat': i['cat']}, 'geometry': pt(i['at'])} for i in items]
write('community.geojson', {'type': 'FeatureCollection', 'count': dict(Counter(f['properties']['cat'] for f in feats)), 'features': feats})
print('community:', [(f['properties']['cat'], f['properties']['name']) for f in feats])

# ---------- Places of worship ----------
CAT = {'muslim': 'mosque', 'sikh': 'gurdwara', 'jewish': 'synagogue', 'hindu': 'hindu', 'buddhist': 'buddhist', 'christian': 'church'}
NOUN = {'mosque': 'Mosque', 'gurdwara': 'Gurdwara', 'synagogue': 'Synagogue', 'hindu': 'Hindu temple', 'buddhist': 'Buddhist temple', 'church': 'Church'}
FAITH = {'hare_krishna': 'Hare Krishna', 'taoist': 'Taoist', 'unitarian_universalist': 'Unitarian', 'multifaith': 'Multifaith'}
# Toronto's church families, fitted to Australia: Uniting for the United Church, Anglican for Episcopal.
CHURCH = [('orthodox', ('orthodox', 'coptic', 'armenian')), ('catholic', ('catholic',)), ('anglican', ('anglican', 'episcopal')),
          ('uniting', ('uniting',)), ('lutheran', ('lutheran',)), ('baptist', ('baptist',)), ('presbyterian', ('presbyterian',)),
          ('evangelical', ('evangelical', 'pentecostal', 'gospel', 'apostolic', 'assemblies_of_god', 'charismatic', 'churches_of_christ'))]
NAMED = [('orthodox', r'orthodox|coptic|armenian'), ('catholic', r'catholic|our lady|basilica|st\.? patrick.s cathedral|mary star|st\.? francis'),
         ('anglican', r'anglican|st\.? paul.s cathedral'), ('uniting', r'uniting'), ('lutheran', r'lutheran'), ('baptist', r'baptist'),
         ('presbyterian', r'presbyterian|scots.? church'), ('evangelical', r'pentecostal|gospel|assembl(y|ies) of god|hillsong|c3 church|citylife|planetshakers')]
def church_group(den, name):
    d = (den or '').lower()
    if d and d not in ('protestant', 'christian', 'nondenominational', 'non-denominational'):
        return next((g for g, keys in CHURCH if any(k in d for k in keys)), 'other')
    return next((g for g, rx in NAMED if re.search(rx, name, re.I)), 'other' if d else '')
wor = []
for e in osm_city:
    t = e.get('tags', {}); c = at(e); n = (t.get('name') or '').strip()
    if t.get('amenity') != 'place_of_worship' or not c or not n or not CITY.contains(Point(c)): continue
    wor.append({'name': n, 'at': c, 'rel': t.get('religion', ''), 'den': t.get('denomination', ''), 'node': e['type'] == 'node'})
wor.sort(key=lambda w: (not w['node'], w['name']))
feats = []
for w in one_each(wor):
    cat = CAT.get(w['rel'], 'otherfaith')
    sub = ' · '.join(x for x in ((NOUN.get(cat) or FAITH.get(w['rel']) or 'Place of worship'), w['den'].replace('_', ' ').capitalize()) if x)
    p = {'name': w['name'], 'cat': cat, 'sub': sub}
    if cat == 'church':
        g = church_group(w['den'], w['name'])
        if g: p['grp'] = g
    feats.append({'type': 'Feature', 'properties': p, 'geometry': pt(w['at'])})
write('faith.geojson', {'type': 'FeatureCollection', 'features': feats})
print('worship:', dict(Counter(f['properties']['cat'] for f in feats)), dict(Counter(f['properties'].get('grp') for f in feats if f['properties']['cat'] == 'church')))

# ---------- Bike lanes ----------
osm_b = json.load(open(os.path.join(RAW, 'osm_bikes.json')))
asof_b = (osm_b.get('osm3s') or {}).get('timestamp_osm_base', '')[:10] or None
def kind(t):
    sides = [t.get('cycleway'), t.get('cycleway:both'), t.get('cycleway:left'), t.get('cycleway:right')]
    if t.get('highway') == 'cycleway':
        if t.get('foot') in ('designated', 'yes') and t.get('segregated') != 'yes': return 'trail', 'Shared path'
        return 'prot', 'Separated bike path'
    if t.get('highway') == 'path': return 'trail', 'Shared path'
    if any(s in ('track', 'separate') for s in sides): return 'prot', 'Separated bike lane'
    if any(s == 'lane' for s in sides): return 'paint', 'Painted bike lane'
    if any(s in ('shared_lane', 'share_busway') for s in sides): return 'shared', 'Shared lane'
    return None, None
feats, km = [], Counter()
for e in osm_b['elements']:
    if e['type'] != 'way' or not e.get('geometry'): continue
    t = e.get('tags', {}); k, d = kind(t)
    if not k: continue
    g = LineString([(p['lon'], p['lat']) for p in e['geometry']]).intersection(CITY)
    if g.is_empty or g.length < 0.0002: continue
    g = g.simplify(0.00001)
    km[k] += g.length * 88
    p = {'t': k, 'd': d}
    if t.get('name'): p['n'] = t['name']
    gm = mapping(g)
    rnd = lambda o: [rnd(v) for v in o] if isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]
    feats.append({'type': 'Feature', 'properties': p, 'geometry': {'type': gm['type'], 'coordinates': rnd(gm['coordinates'])}})
feats = [f for f in feats if f['geometry']['type'] in ('LineString', 'MultiLineString')]
write('bikes.geojson', {'type': 'FeatureCollection', 'asof': asof_b, 'counts': dict(Counter(f['properties']['t'] for f in feats)),
                        'km': {k: round(v) for k, v in km.items()}, 'features': feats})
print('bikes:', len(feats), {k: round(v) for k, v in km.items()}, os.path.getsize(os.path.join(DATA, 'bikes.geojson')) // 1024, 'KB')

# ---------- New development ----------
cat = json.load(open(os.path.join(RAW, 'com_catalog.json')))
asof_d = (cat.get('development-activity-monitor', {}).get('modified') or '')[:10]
this_year = int(asof_d[:4]) if asof_d else 2026
STAGE = {'APPLIED': 'proposed', 'APPROVED': 'approved', 'UNDER CONSTRUCTION': 'building', 'COMPLETED': 'finished'}
USES = [('office_flr', 'office'), ('retail_flr', 'shops'), ('education_flr', 'education'), ('hospital_flr', 'hospital'),
        ('community_flr', 'community'), ('recreation_flr', 'recreation'), ('industrial_flr', 'industrial')]
feats = []
for f in json.load(open(os.path.join(RAW, 'development-activity-monitor.geojson')))['features']:
    p = f['properties']; s = STAGE.get(p['status'])
    if not s or not f.get('geometry'): continue
    if s == 'finished' and not (p.get('year_completed') and int(p['year_completed']) >= this_year - 1): continue
    c = f['geometry']['coordinates']
    if not CITY.contains(Point(c)): continue
    m = re.match(r'^(.*?)\s+([A-Z][A-Z ]+)\s+VIC\s+\d{4}$', p.get('street_address') or '')
    addr = (m.group(1) + ', ' + m.group(2).title()) if m else (p.get('street_address') or '')
    bits = []
    if p.get('floors_above'): bits.append(f'{p["floors_above"]} storeys')
    if p.get('resi_dwellings'): bits.append(f'{p["resi_dwellings"]:,} homes')
    if p.get('student_beds'): bits.append(f'{p["student_beds"]:,} student beds')
    if p.get('hotel_rooms'): bits.append(f'{p["hotel_rooms"]:,} hotel rooms')
    for k, w in USES:
        if p.get(k) and p[k] >= 500: bits.append(f'{w} {int(p[k]):,} m²')
    pr = {'k': 'building', 's': s, 'date': asof_d, 'dl': 'c' + str(p['year_completed']) if s == 'finished' else 'listed', 'a': addr,
          'd': ' · '.join(bits), 'n': p.get('town_planning_application') or p.get('development_key'), 'status': p['status'].capitalize()}
    if p.get('resi_dwellings'): pr['units'] = p['resi_dwellings']
    feats.append({'type': 'Feature', 'properties': pr, 'geometry': pt((round(c[0], 5), round(c[1], 5)))})
write('changes.geojson', {'type': 'FeatureCollection', 'asof': asof_d, 'window': 2, 'features': feats})
print('changes:', len(feats), dict(Counter(f['properties']['s'] for f in feats)), 'as of', asof_d)
