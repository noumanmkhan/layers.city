"""San Francisco's place layers and the card's Nearby points, from raw/places/ (fetch_places.py) and faith.geojson.
Writes into docs/sf/data/:
  institutions.geojson  hospitals with an emergency department, universities and City College (Landmarks' toggles
                        and the Colleges layer)
  community.geojson     San Francisco Public Library branches and Rec & Park recreation centers
  schools.geojson       SFUSD's district-run schools, elementary (with K-8) and middle and high, from the State's directory
  parks.geojson         Rec & Park properties, with amenities: playground, dog play area
  sports.geojson        Rec & Park courts, fields, pools and skateparks, one point per park with its sports
  nearby.json           the points the card counts and names within its radius
Rules, as the other cities': describe only, never rank; public and nonprofit institutions; one point per place.

Hospitals: a curated list (HOSPITALS) of the city's general acute hospitals with an emergency department, placed by
  OpenStreetMap; long-term care (Laguna Honda), outpatient campuses (UCSF Mount Zion) and clinics are left out.
Universities and colleges: a curated list (UNIS) placed by OpenStreetMap; for-profit schools (Academy of Art,
  FIDM, University of Phoenix) and graduate-only institutes are left out."""
import json, math, os, re
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'places')
DATA = os.path.join(HERE, '..', '..', 'docs', 'sf', 'data')
load = lambda n: json.load(open(os.path.join(RAW, n)))
pt = lambda x, y: {'type': 'Point', 'coordinates': [round(float(x), 5), round(float(y), 5)]}


def fc(feats, **top):
    return dict({'type': 'FeatureCollection'}, **top, features=feats)


def write(name, obj):
    json.dump(obj, open(os.path.join(DATA, name), 'w'), separators=(',', ':'), ensure_ascii=False)


def osm_pts(name):
    out = []
    for e in load(name)['elements']:
        c = e.get('center') or e
        if c.get('lon') is None or not e.get('tags', {}).get('name'): continue
        out.append((e['tags']['name'], c['lon'], c['lat'], e['type'] == 'node'))
    return out


# ---------- Hospitals (OSM name pattern -> name shown, sub) ----------
HOSPITALS = [
    (r'^San Francisco General Hospital$|Zuckerberg', 'Zuckerberg San Francisco General', 'Public · the City’s hospital and trauma center'),
    (r'^UC Medical Center Moffett', 'UCSF Medical Center at Parnassus', 'UCSF Health · Public (University of California)'),
    (r'^UCSF Medical Center at Mission Bay$', 'UCSF Medical Center at Mission Bay', 'UCSF Health, with Benioff Children’s Hospital · Public (University of California)'),
    (r'^CPMC Van Ness Campus$', 'CPMC Van Ness Campus', 'Sutter Health · Nonprofit'),
    (r'^CPMC Mission Bernal Campus$', 'CPMC Mission Bernal Campus', 'Sutter Health · Nonprofit'),
    (r'^CPMC Davies Campus$', 'CPMC Davies Campus', 'Sutter Health · Nonprofit'),
    (r'^Kaiser Permanente Medical Center Geary', 'Kaiser Permanente San Francisco', 'Kaiser Permanente · Nonprofit'),
    (r'^Saint Francis Memorial Hospital$', 'Saint Francis Memorial Hospital', 'Dignity Health · Nonprofit'),
    (r"^Saint Mary's Medical Center$", 'Saint Mary’s Medical Center', 'Dignity Health · Nonprofit'),
    (r'^Chinese Hospital$', 'Chinese Hospital', 'Nonprofit'),
    (r'^San Francisco VA Medical Center$', 'San Francisco VA Medical Center', 'U.S. Department of Veterans Affairs · for veterans'),
]
UNIS = [
    (r'^University of California, San Francisco$', 'UCSF', 'Parnassus Heights · Public (health sciences)', 'university'),
    (r'^San Francisco State University$', 'San Francisco State University', 'Lake Merced · Public (CSU)', 'university'),
    (r'^University of San Francisco$', 'University of San Francisco', 'Lone Mountain · Private nonprofit', 'university'),
    (r'^University of California College of the Law', 'UC Law San Francisco', 'Civic Center · Public (law school)', 'university'),
    (r'^Golden Gate University$', 'Golden Gate University', 'Financial District · Private nonprofit', 'university'),
    (r'^California College of the Arts$', 'California College of the Arts', 'Design District · Private nonprofit', 'university'),
    (r'^California Institute of Integral Studies$', 'California Institute of Integral Studies', 'Mid-Market · Private nonprofit', 'university'),
    (r'^City College of San Francisco \(CCSF\) Ocean Campus$', 'City College of San Francisco', 'Ocean Campus, Sunnyside · Public', 'college'),
]


def pick(pts, rx):
    hits = [p for p in pts if re.search(rx, p[0])]
    hits.sort(key=lambda p: not p[3])   # a hand-placed node before a building's middle
    return hits[0] if hits else None


hosp_pts, col_pts, inst, missing = osm_pts('osm_hospitals.json'), osm_pts('osm_colleges.json'), [], []
for rx, name, sub in HOSPITALS:
    h = pick(hosp_pts, rx)
    if not h: missing.append(name); continue
    inst.append({'type': 'Feature', 'properties': {'name': name, 'cat': 'hospital', 'sub': sub}, 'geometry': pt(h[1], h[2])})
for rx, name, sub, cat in UNIS:
    h = pick(col_pts, rx)
    if not h: missing.append(name); continue
    inst.append({'type': 'Feature', 'properties': {'name': name, 'sub': sub, 'cat': cat}, 'geometry': pt(h[1], h[2])})
write('institutions.geojson', fc(inst))
print('institutions:', dict(Counter(f['properties']['cat'] for f in inst)), '· not found in OSM:', missing)

# ---------- Libraries and recreation centers ----------
comm = []
for r in load('city_facilities.json'):
    n = (r.get('common_name') or '').strip()
    if r.get('department_name') != 'Public Library' or not r.get('latitude') or not re.search(r'Librar|Branch', n) or 'Support' in n: continue
    comm.append({'type': 'Feature', 'properties': {'name': n, 'cat': 'library', 'sub': 'San Francisco Public Library'}, 'geometry': pt(r['longitude'], r['latitude'])})
FAC = load('park_facilities.json')
seen = set()
for r in FAC:
    if r.get('facility_type') != 'Rec Center' or not r.get('latitude'): continue
    park = (r.get('property_name') or '').strip()
    n = (r.get('facility_name') or '').strip()
    if not n or re.fullmatch(r'(?i)rec(reation)? ?(center|ctr)\.?', n): n = park
    n = re.sub(r'(?i)\brec(reation)?\.? ?(center|ctr)\.?$', 'Recreation Center', n)
    if 'Recreation Center' not in n and 'Rec Center' not in n: n += ' Recreation Center'
    if n in seen: continue
    seen.add(n)
    comm.append({'type': 'Feature', 'properties': {'name': n, 'cat': 'centre', 'sub': 'Recreation center · Rec & Park'}, 'geometry': pt(r['longitude'], r['latitude'])})
write('community.geojson', fc(comm, count=dict(Counter(f['properties']['cat'] for f in comm))))
print('community:', dict(Counter(f['properties']['cat'] for f in comm)))

# ---------- Schools: SFUSD's own (not charter, private or preschool) ----------
GR = {'P': -1, 'TK': -1, 'K': 0}
gnum = lambda g: GR.get((g or '').strip().upper(), int(g) if (g or '').strip().isdigit() else None)
gtext = lambda g: 'TK' if (g or '').upper() in ('P', 'TK') else (g or '').upper()
schools = []
for r in load('schools.json'):
    if r.get('status') != 'Active' or r.get('district') != 'San Francisco Unified' or r.get('charter_yesno') in (True, 'true') or not r.get('latitude'): continue
    et = r.get('entity_type') or ''
    if 'Preschool' in et or 'Private' in et: continue
    lo, hi = gnum(r.get('low_grade')), gnum(r.get('high_grade'))
    if hi is None: continue
    kind = 'Elementary school' if hi <= 5 else 'K–8 school' if lo is not None and lo <= 0 and hi == 8 else 'Middle school' if hi <= 8 else \
           'Continuation high school' if 'Continuation' in et else 'High school' if lo is not None and lo >= 9 else 'Middle and high school'
    cat = 'elementary' if hi <= 5 or kind == 'K–8 school' else 'secondary'
    name = re.sub(r'\s+', ' ', r['school']).strip()
    # The State's directory files names surname first: "Brown Jr. (Willie L) Middle" -> "Willie L Brown Jr. Middle".
    name = re.sub(r'^(.+?) \(([^)]+)\)', r'\2 \1', name)
    name = re.sub(r', A Public School$', '', re.sub(r'\bSch\b', 'School', name))
    grades = '%s–%s' % (gtext(r.get('low_grade')), gtext(r.get('high_grade')))
    a = (r.get('street_address') or '').strip()
    schools.append({'type': 'Feature', 'properties': {'name': name, 'cat': cat, 'sub': kind + ' · Grades ' + grades, 'g': grades, 'b': kind, 'a': a},
                    'geometry': pt(r['longitude'], r['latitude'])})
write('schools.geojson', fc(schools, asof='2026', count=dict(Counter(f['properties']['cat'] for f in schools))))
print('schools:', dict(Counter(f['properties']['cat'] for f in schools)), dict(Counter(f['properties']['b'] for f in schools)))

# ---------- Parks, with amenities ----------
LEAVE = {'Library', 'Concession', 'Other Non-Park Property'}
by_prop = defaultdict(set)
for r in FAC:
    t = r.get('facility_type') or ''
    if re.match(r"Child(ren)?'?s Play Area", t): by_prop[r.get('property_id')].add('play')
    if t == 'Dog Play Area': by_prop[r.get('property_id')].add('dog')
rnd = lambda o: [rnd(x) for x in o] if isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]
parks, park_pt = [], {}
for f in load('parks.geojson')['features']:
    p = f['properties']
    if p.get('propertytype') in LEAVE or p.get('ownership') == 'Public Library' or not f.get('geometry'): continue
    if not (-122.53 < float(p.get('longitude') or 0) < -122.35 and 37.70 < float(p.get('latitude') or 0) < 37.84): continue   # Camp Mather and Sharp Park, outside the city
    g = shape(f['geometry']).buffer(0)
    if g.is_empty: continue
    g = g.simplify(0.00002, preserve_topology=True)
    num = p.get('property_id')
    am = [a for a in ('play', 'dog') if a in by_prop.get(num, ())]
    pr = {'n': re.sub(r'\s*-\s*Section \d+$', '', (p.get('property_name') or '').strip()), 'u': num}   # Golden Gate Park's sections
    if p.get('propertytype'): pr['t'] = p['propertytype']
    if am: pr['a'] = am
    rp = g.representative_point(); park_pt[num] = (pr['n'], rp.x, rp.y, am)
    gm = mapping(g)
    parks.append({'type': 'Feature', 'properties': pr, 'geometry': {'type': gm['type'], 'coordinates': rnd(gm['coordinates'])}, '_a': g.area})
parks.sort(key=lambda f: -f.pop('_a'))
asof = max((f['properties'].get('data_as_of') or '')[:10] for f in load('parks.geojson')['features'])
write('parks.geojson', fc(parks, asof={'parks': asof}, count=len(parks)))
print('parks:', len(parks), Counter(a for f in parks for a in f['properties'].get('a', [])))

# ---------- Sports & rec: one point per park, with its sports ----------
SPORT = {'Basketball Court': ['basketball'], 'Tennis Court': ['tennis'], 'Tennis/Pickleball Court': ['tennis', 'pickleball'],
         'Pickleball Courts': ['pickleball'], 'Ball Field': ['diamond'], 'Soccer Field': ['field'], 'Multi-Use Turf': ['field'],
         'Swimming Pool': ['pool'], 'Skatepark': ['skatepark']}
spots = defaultdict(lambda: {'cats': Counter(), 'pts': []})
for r in FAC:
    cs = SPORT.get(r.get('facility_type'))
    if not cs or not r.get('latitude'): continue
    s = spots[r.get('property_id')]
    s['pts'].append((float(r['longitude']), float(r['latitude'])))
    for c in cs: s['cats'][c] += 1
NOUN = {'pool': ('pool', 'pools'), 'diamond': ('ball field', 'ball fields'), 'field': ('sports field', 'sports fields'), 'tennis': ('tennis court', 'tennis courts'),
        'pickleball': ('pickleball court', 'pickleball courts'), 'basketball': ('basketball court', 'basketball courts'), 'skatepark': ('skatepark', 'skateparks')}
ORDER = ['pool', 'diamond', 'field', 'tennis', 'pickleball', 'basketball', 'skatepark']
names = {r.get('property_id'): r.get('property_name') for r in FAC}
sports = []
for num, s in spots.items():
    nm = park_pt.get(num, ('',))[0] or names.get(num) or 'Rec & Park facility'
    x = sum(a for a, _ in s['pts']) / len(s['pts']); y = sum(b for _, b in s['pts']) / len(s['pts'])
    cats = [c for c in ORDER if s['cats'][c]]
    has = ', '.join('%d %s' % (s['cats'][c], NOUN[c][0] if s['cats'][c] == 1 else NOUN[c][1]) for c in cats)
    sports.append({'type': 'Feature', 'properties': {'name': nm, 'cat': cats[0], 'cats': cats, 'sub': 'Rec & Park', 'has': has}, 'geometry': pt(x, y)})
write('sports.geojson', fc(sports, asof='October 2026', count=len(sports), counts={c: sum(1 for f in sports if c in f['properties']['cats']) for c in ORDER}))
print('sports:', len(sports), {c: sum(1 for f in sports if c in f['properties']['cats']) for c in ORDER})

# ---------- Nearby points for the card ----------
G = defaultdict(list)
for f in comm: G[f['properties']['cat']].append(f['geometry']['coordinates'] + [f['properties']['name']])
for f in sports:
    for c in ('pool', 'tennis', 'basketball'):
        if c in f['properties']['cats']: G[c].append(f['geometry']['coordinates'] + [f['properties']['name']])
done = set()
for num, (n, x, y, am) in park_pt.items():
    if n in done and not am: continue   # a park in sections (Golden Gate Park) counts once, unless a section has its own playground
    done.add(n)
    G['park'].append([round(x, 5), round(y, 5), n])
    if 'play' in am: G['playground'].append([round(x, 5), round(y, 5), n])
    if 'dog' in am: G['dogrun'].append([round(x, 5), round(y, 5), n])
for f in schools:
    G['school_e' if f['properties']['cat'] == 'elementary' else 'school_s'].append(f['geometry']['coordinates'] + [f['properties']['name']])
if os.path.exists(os.path.join(DATA, 'faith.geojson')):
    for f in json.load(open(os.path.join(DATA, 'faith.geojson')))['features']:
        p = f['properties']
        G[p['cat']].append(f['geometry']['coordinates'] + [p['name']])
        if p['cat'] == 'church' and p.get('grp'): G['church:' + p['grp']].append(f['geometry']['coordinates'] + [p['name']])
write('nearby.json', {'groups': dict(G)})
print('nearby:', {k: len(v) for k, v in G.items()})
