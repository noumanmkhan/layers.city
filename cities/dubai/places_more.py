"""Dubai's place layers from OpenStreetMap (raw/pois.geojson, extract_osm.py). Run after build.py.
Writes into docs/dubai/data/ (parks into tmp/ for mapshaper):
  - parks: named parks and gardens of 0.5 ha or more, and the beaches (r: 1), in the city; outlines
  - institutions: hospitals with an emergency department (OSM emergency=yes), universities and colleges
  - schools: every school OpenStreetMap maps in the city, one category, never ranked (no ratings are fetched)
  - community: libraries and community centres
  - faith: places of worship by faith (mosques, churches, Hindu temples, gurdwaras, others)
  - sports: stadiums, sports centres and clubs, golf courses
  - heritage: historic sites and museums
Facilities only, never people. OpenStreetMap is mapped by volunteers: each layer's note says it may be incomplete."""
import json, os, re
from collections import Counter
from shapely.geometry import shape, Point
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'docs', 'dubai', 'data') + '/'
TMP = os.path.join(HERE, 'tmp') + '/'
base = json.load(open(TMP + 'base.geojson'))['features']
CITY = shape(next(f for f in base if f['properties']['kind'] == 'city')['geometry'])
IN = prep(CITY.buffer(0.003))
fs = json.load(open(os.path.join(HERE, 'raw', 'pois.geojson'), encoding='utf-8'))['features']
nm = lambda p: (p.get('name:en') or (p.get('name') if re.search(r'[A-Za-z]', p.get('name') or '') else None) or '').strip()
fc = lambda f, **k: dict({'type': 'FeatureCollection', 'features': f}, **k)
pt = lambda f, p: {'type': 'Feature', 'properties': p, 'geometry': f['geometry']}
def save(name, feats, **k):
    json.dump(fc(feats, **k), open(OUT + name + '.geojson', 'w'), separators=(',', ':'), ensure_ascii=False)
    print(name, len(feats), Counter(f['properties'].get('cat') for f in feats) if feats and 'cat' in feats[0]['properties'] else '')

inside = [f for f in fs if IN.contains(Point(f['geometry']['coordinates']))]

def dedupe(feats, km=0.6):
    """One point per name: OSM often has a building and a node for the same place."""
    out = []
    for f in feats:
        n, c = f['properties']['name'].lower().rstrip(' ,'), f['geometry']['coordinates']
        if any(g['properties']['name'].lower().rstrip(' ,') == n and abs(g['geometry']['coordinates'][0] - c[0]) * 101 < km and abs(g['geometry']['coordinates'][1] - c[1]) * 111 < km for g in out): continue
        out.append(f)
    return out

# ---------- Parks and beaches (outlines) ----------
parks = []
for f in inside:
    p = f['properties']; s = p.get('_shape')
    if not s: continue
    beach = p.get('natural') == 'beach'
    if p.get('leisure') in ('park', 'garden', 'nature_reserve') and nm(p) and p.get('_km2', 0) >= 0.005 and p.get('access') != 'private':
        parks.append({'type': 'Feature', 'properties': {'n': nm(p), 'o': 1}, 'geometry': s})
    elif beach and p.get('_km2', 0) >= 0.005:
        parks.append({'type': 'Feature', 'properties': {'n': nm(p) or 'Beach', 'o': 1, 'r': 1}, 'geometry': s})
json.dump(fc(parks), open(TMP + 'parks.geojson', 'w'), separators=(',', ':'), ensure_ascii=False)
print('parks', sum('r' not in f['properties'] for f in parks), '· beaches', sum('r' in f['properties'] for f in parks))

# ---------- Hospitals with an ER, campuses ----------
inst = []
for f in inside:
    p = f['properties']; n = nm(p)
    if not n: continue
    if p.get('amenity') == 'hospital' and re.search(r'(?i)hospital', n) and not re.search(r'(?i)clinic|dental|\bLLC\b|\d{5}', n):
        # Every hospital OpenStreetMap maps; the emergency department only where it's tagged (OSM marks few of them)
        inst.append(pt(f, dict({'name': n, 'cat': 'hospital', 'sub': 'Emergency department' if p.get('emergency') == 'yes' else 'Hospital'},
                               **({'ed': 1} if p.get('emergency') == 'yes' else {}))))
    elif p.get('amenity') in ('university', 'college') and re.search(r'(?i)universit|college|institute|business school', n) \
            and not re.search(r'(?i)\bblock\b|hostel|accommodation|parking|gate|trading|beauty|english speaking|kings college|school primary', n):
        inst.append(pt(f, {'name': n, 'cat': 'university', 'sub': 'University or college'}))
save('institutions', dedupe(inst))

# ---------- Schools: one category, no ratings ----------
sch = [pt(f, {'name': nm(f['properties']), 'cat': 'elementary', 'sub': 'School'}) for f in inside
       if f['properties'].get('amenity') == 'school' and nm(f['properties'])]
sch = dedupe(sch)
save('schools', sch, count=len(sch), asof='OpenStreetMap, November 16, 2026')

# ---------- Libraries and community centres ----------
com = []
for f in inside:
    p = f['properties']; n = nm(p)
    if not n: continue
    if p.get('amenity') == 'library' and re.search(r'(?i)librar', n) and n != 'Library Building': com.append(pt(f, {'name': n, 'cat': 'library'}))
    elif p.get('amenity') == 'community_centre' and re.search(r'(?i)community (centre|center)|cultural', n): com.append(pt(f, {'name': n, 'cat': 'centre'}))
com = dedupe(com)
save('community', com, count=len(com))

# ---------- Places of worship ----------
FAITH = {'muslim': ('mosque', 'Mosque'), 'christian': ('church', 'Church'), 'hindu': ('hindu', 'Hindu temple'),
         'sikh': ('gurdwara', 'Gurdwara'), 'buddhist': ('buddhist', 'Buddhist temple')}
fa = []
for f in inside:
    p = f['properties']; n = nm(p)
    if p.get('amenity') != 'place_of_worship' or not n or re.search(r'(?i)prayer room|musalla|musallah|mussala', n): continue
    cat, word = FAITH.get(p.get('religion'), ('otherfaith', 'Place of worship'))
    fa.append(pt(f, {'name': n, 'cat': cat, 'sub': word}))
save('faith', dedupe(fa))

# ---------- Sports & rec ----------
SP = []
for f in inside:
    p = f['properties']; n = nm(p)
    if not n: continue
    if p.get('leisure') == 'stadium': SP.append(pt(f, {'name': n, 'cat': 'sports', 'cats': ['sports'], 'sub': 'Stadium'}))
    elif p.get('leisure') == 'golf_course': SP.append(pt(f, {'name': n, 'cat': 'field', 'cats': ['field'], 'sub': 'Golf course'}))
    elif p.get('leisure') == 'sports_centre' and p.get('access') != 'private': SP.append(pt(f, {'name': n, 'cat': 'tennis', 'cats': ['tennis'], 'sub': 'Sports centre or club'}))
    elif p.get('leisure') == 'water_park': SP.append(pt(f, {'name': n, 'cat': 'pool', 'cats': ['pool'], 'sub': 'Water park'}))
SP = dedupe(SP)
save('sports', SP, count=len(SP), asof='OpenStreetMap, November 16, 2026', counts=dict(Counter(f['properties']['cat'] for f in SP)))

# ---------- Heritage sites and museums ----------
her = []
for f in inside:
    p = f['properties']; n = nm(p)
    if not n: continue
    # Heritage: forts, old houses, archaeological sites, the historic districts; not palaces or statues
    if re.search(r'(?i)palace|statue|salute|illusion|^monument$|roundabout|horses|boat model|woo-hoo|nobel|^expo|art dubai', n): continue
    if p.get('historic') in ('fort', 'castle', 'building', 'archaeological_site', 'house', 'heritage', 'tower', 'mosque', 'district') or \
            (p.get('historic') and re.search(r'(?i)house|fort|site|tower|heritage|village|school|majlis', n)):
        her.append(pt(f, {'name': n, 'cat': 'culture', 'sub': 'Heritage site'}))
    elif p.get('tourism') == 'museum':
        her.append(pt(f, {'name': n, 'cat': 'culture', 'sub': 'Museum'}))
save('heritage_sites', dedupe(her))
