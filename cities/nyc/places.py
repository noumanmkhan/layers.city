"""New York City's place layers and the card's Nearby points, from raw/places/ (fetch_places.py) and faith.geojson.
Writes into docs/nyc/data/:
  institutions.geojson  hospitals, universities and CUNY community colleges (Landmarks' toggles and Colleges layer)
  community.geojson     the three public library systems' branches and older adult (senior) centers
  schools.geojson       NYC Public Schools, elementary (with K-8) and middle and high, from the Facilities Database
  parks.geojson         NYC Parks properties that are parks, with amenities: playground, spray shower, dog run
  sports.geojson        NYC Parks athletic facilities, pools and skateparks, one point per park with its sports
  nearby.json           the points the card counts and names within its radius
Rules, as the other cities': describe only, never rank; public and nonprofit institutions; one point per place.

Hospitals: the Facilities Database's general hospitals (types HOSPITAL and ACUTE CARE HOSPITAL), one per name;
  specialty hospitals without an emergency department for the public are dropped by name (cancer, special surgery,
  rehabilitation, psychiatric). Emergency departments aren't marked: no open list gives them for New York.
Universities and colleges: a curated list (UNIS below) placed by the Facilities Database's own campus points;
  for-profit and graduate-only schools are left out, so are hospitals' nursing programs."""
import json, math, os, re
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'places')
DATA = os.path.join(HERE, '..', '..', 'docs', 'nyc', 'data')
load = lambda n: json.load(open(os.path.join(RAW, n)))
pt = lambda x, y: {'type': 'Point', 'coordinates': [round(float(x), 5), round(float(y), 5)]}
fac = load('facdb.json')
SMALL = {'of', 'and', 'the', 'at', 'for', 'in', 'on', 'de', 'la'}
KEEP = {'NYU', 'CUNY', 'SUNY', 'NYC', 'LIU', 'BMCC', 'PS', 'IS', 'MS', 'HS', 'JHS', 'NYCHA', 'II', 'III', 'IV', 'NY', 'BPL', 'QPL', 'NYPL', 'STEM', 'STEAM'}


def tcase(s):
    out = []
    for i, w in enumerate((s or '').split()):
        u = w.upper()
        if u in KEEP or re.match(r'^\d', w): out.append(u if u in KEEP else w)
        elif i and w.lower() in SMALL: out.append(w.lower())
        else: out.append(w[:1].upper() + w[1:].lower() if "'" not in w else "'".join(p[:1].upper() + p[1:].lower() for p in w.split("'")))
    return ' '.join(out).replace("'S ", "'s ").replace("’S ", "’s ")


def fc(feats, **top):
    return dict({'type': 'FeatureCollection'}, **top, features=feats)


def write(name, obj):
    json.dump(obj, open(os.path.join(DATA, name), 'w'), separators=(',', ':'), ensure_ascii=False)


# ---------- Hospitals ----------
hosp, seen = [], set()
for r in fac:
    if r.get('factype') not in ('HOSPITAL', 'ACUTE CARE HOSPITAL') or not r.get('latitude'): continue
    n = r['facname'].strip()
    if re.search(r'CANCER|SPECIAL SURGERY|REHAB|PSYCHIATR|BEHAVIORAL|LONG TERM|NURSING|EXTENSION|CLINIC\b|RESIDENTIAL', n): continue
    k = re.sub(r'\W+', '', n)
    if k in seen: continue
    seen.add(k)
    hosp.append({'type': 'Feature', 'properties': {'name': tcase(n), 'cat': 'hospital', 'sub': tcase(r.get('opname') or '')},
                 'geometry': pt(r['longitude'], r['latitude'])})

# ---------- Universities and colleges (curated; FacDB name pattern -> name shown, sub, cat) ----------
UNIS = [
    (r'^COLUMBIA UNIVERSITY', 'Columbia University', 'Morningside Heights · Private nonprofit', 'university'),
    (r'^BARNARD', 'Barnard College', 'Morningside Heights · Private nonprofit', 'university'),
    (r'^NEW YORK UNIVERSITY', 'New York University', 'Washington Square · Private nonprofit', 'university'),
    (r'^THE NEW SCHOOL', 'The New School', 'Greenwich Village · Private nonprofit', 'university'),
    (r'^FORDHAM', 'Fordham University', 'Private nonprofit', 'university'),
    (r'^PACE UNIVERSITY - NYC', 'Pace University', 'Lower Manhattan · Private nonprofit', 'university'),
    (r"^ST\.? JOHN'S UNIVERSITY$", "St. John's University", 'Jamaica, Queens · Private nonprofit', 'university'),
    (r'^PRATT INSTITUTE$', 'Pratt Institute', 'Clinton Hill · Private nonprofit', 'university'),
    (r'^COOPER UNION', 'Cooper Union', 'East Village · Private nonprofit', 'university'),
    (r'^JUILLIARD', 'The Juilliard School', 'Lincoln Center · Private nonprofit', 'university'),
    (r'^YESHIVA UNIVERSITY', 'Yeshiva University', 'Washington Heights · Private nonprofit', 'university'),
    (r'^LONG ISLAND UNIV-BROOKLYN', 'LIU Brooklyn', 'Downtown Brooklyn · Private nonprofit', 'university'),
    (r'^WAGNER COLLEGE', 'Wagner College', 'Grymes Hill · Private nonprofit', 'university'),
    (r'^MANHATTAN UNIVERSITY', 'Manhattan University', 'Riverdale · Private nonprofit', 'university'),
    (r'^MARYMOUNT MANHATTAN', 'Marymount Manhattan College', 'Upper East Side · Private nonprofit', 'university'),
    (r'^ST FRANCIS COLLEGE', 'St. Francis College', 'Downtown Brooklyn · Private nonprofit', 'university'),
    (r'^TOURO UNIVERSITY$', 'Touro University', 'Private nonprofit', 'university'),
    (r'^MERCY UNIVERSITY-BRONX', 'Mercy University (Bronx)', 'Private nonprofit', 'university'),
    (r'^MERCY UNIV\.-MANHATTAN', 'Mercy University (Manhattan)', 'Private nonprofit', 'university'),
    (r'^UNIVERSITY OF MT ST VINCENT', 'University of Mount Saint Vincent', 'Riverdale · Private nonprofit', 'university'),
    (r'^CORNELL UNIV MEDICAL', 'Weill Cornell Medicine', 'Upper East Side · Private nonprofit', 'university'),
    (r'^CUNY BERNARD M\. BARUCH', 'Baruch College (CUNY)', 'Gramercy · Public', 'university'),
    (r'^CUNY BROOKLYN COLLEGE', 'Brooklyn College (CUNY)', 'Midwood · Public', 'university'),
    (r'^CUNY CITY COLLEGE', 'City College of New York (CUNY)', 'Hamilton Heights · Public', 'university'),
    (r'^CUNY HUNTER COLLEGE', 'Hunter College (CUNY)', 'Upper East Side · Public', 'university'),
    (r'^CUNY JOHN JAY', 'John Jay College (CUNY)', "Hell's Kitchen · Public", 'university'),
    (r'^CUNY LEHMAN', 'Lehman College (CUNY)', 'Bedford Park · Public', 'university'),
    (r'^MEDGAR EVERS', 'Medgar Evers College (CUNY)', 'Crown Heights · Public', 'university'),
    (r'^CUNY NYC COLLEGE OF TECHNOLOGY', 'New York City College of Technology (CUNY)', 'Downtown Brooklyn · Public', 'university'),
    (r'^CUNY QUEENS COLLEGE', 'Queens College (CUNY)', 'Flushing · Public', 'university'),
    (r'^CUNY COLLEGE OF STATEN ISLAND', 'College of Staten Island (CUNY)', 'Willowbrook · Public', 'university'),
    (r'^CUNY YORK COLLEGE', 'York College (CUNY)', 'Jamaica · Public', 'university'),
    (r'^CUNY GRADUATE SCHOOL', 'CUNY Graduate Center', 'Midtown · Public', 'university'),
]
CC = re.compile(r'BOROUGH MANHATTAN|BRONX COMMUNITY|HOSTOS|KINGSBOROUGH|LAGUARDIA|QUEENSBOROUGH|GUTTMAN')
CC_NAME = [('BOROUGH MANHATTAN', 'Borough of Manhattan Community College', 'Tribeca'), ('BRONX COMMUNITY', 'Bronx Community College', 'University Heights'),
           ('HOSTOS', 'Hostos Community College', 'Mott Haven'), ('KINGSBOROUGH', 'Kingsborough Community College', 'Manhattan Beach'),
           ('LAGUARDIA', 'LaGuardia Community College', 'Long Island City'), ('QUEENSBOROUGH', 'Queensborough Community College', 'Bayside'),
           ('GUTTMAN', 'Guttman Community College', 'Midtown')]
colleges = [r for r in fac if r.get('facsubgrp') == 'COLLEGES OR UNIVERSITIES' and r.get('latitude')]
inst, missing = [], []
for rx, name, sub, cat in UNIS:
    hits = [r for r in colleges if re.search(rx, r['facname'])]
    if not hits: missing.append(name); continue
    for r in hits[:2] if name.startswith('Fordham') else hits[:1]:
        nm = name + (' (Lincoln Center)' if 'LINCOLN' in r['facname'] and name.startswith('Fordham') and len(hits) > 1 and r is hits[1] else '')
        inst.append({'type': 'Feature', 'properties': {'name': nm, 'sub': sub, 'cat': cat}, 'geometry': pt(r['longitude'], r['latitude'])})
for key, name, area in CC_NAME:
    r = next((r for r in colleges if key in r['facname'] and 'COMMUNITY' in (r.get('factype') or '')), None) or next((r for r in colleges if key in r['facname']), None)
    if not r: missing.append(name); continue
    inst.append({'type': 'Feature', 'properties': {'name': name + ' (CUNY)', 'sub': area + ' · Public', 'cat': 'college'}, 'geometry': pt(r['longitude'], r['latitude'])})
write('institutions.geojson', fc(hosp + inst))
print('institutions:', len(hosp), 'hospitals,', sum(1 for f in inst if f['properties']['cat'] == 'university'), 'universities,',
      sum(1 for f in inst if f['properties']['cat'] == 'college'), 'colleges · not found in FacDB:', missing)

# ---------- Libraries and older adult centers ----------
SYS = {'New York Public Library': 'NYPL', 'Brooklyn Public Library': 'BPL', 'Queens Public Library': 'QPL'}
comm = []
for r in fac:
    if not r.get('latitude'): continue
    if r.get('factype') == 'PUBLIC LIBRARY' and r.get('opname') in SYS:
        comm.append({'type': 'Feature', 'properties': {'name': tcase(r['facname']), 'cat': 'library', 'sub': r['opname']}, 'geometry': pt(r['longitude'], r['latitude'])})
    elif r.get('factype') in ('SENIOR CENTER', 'NYCHA COMMUNITY CENTER - SENIOR CENTER'):
        comm.append({'type': 'Feature', 'properties': {'name': tcase(r['facname']), 'cat': 'centre', 'sub': 'Older adult center · ' + tcase(r.get('opname') or '')}, 'geometry': pt(r['longitude'], r['latitude'])})
write('community.geojson', fc(comm, count=dict(Counter(f['properties']['cat'] for f in comm))))
print('community:', dict(Counter(f['properties']['cat'] for f in comm)))

# ---------- Schools ----------
LEVEL = {'ELEMENTARY SCHOOL - PUBLIC': ('elementary', 'Elementary school'), 'K-8 SCHOOL - PUBLIC': ('elementary', 'K–8 school'),
         'JUNIOR HIGH-INTERMEDIATE-MIDDLE SCHOOL - PUBLIC': ('secondary', 'Middle school'), 'HIGH SCHOOL - PUBLIC': ('secondary', 'High school'),
         'SECONDARY SCHOOL - PUBLIC': ('secondary', 'Middle and high school'), 'K-12 ALL GRADES SCHOOL - PUBLIC': ('secondary', 'K–12 school')}
schools = []
for r in fac:
    lv = LEVEL.get(r.get('factype'))
    if not lv or not r.get('latitude') or r.get('opname') != 'NYC Department of Education': continue
    d = r.get('schooldist')
    schools.append({'type': 'Feature', 'properties': {'name': tcase(r['facname']), 'cat': lv[0], 'sub': lv[1] + (' · District %s' % int(float(d)) if d else ''),
                                                       'g': lv[1], 'b': 'District %s' % int(float(d)) if d else '', 'a': tcase(r.get('address') or '')},
                    'geometry': pt(r['longitude'], r['latitude'])})
write('schools.geojson', fc(schools, asof='2026', count=dict(Counter(f['properties']['cat'] for f in schools))))
print('schools:', dict(Counter(f['properties']['cat'] for f in schools)))

# ---------- Parks, with amenities ----------
PARK_TYPES = {'Neighborhood Park', 'Community Park', 'Flagship Park', 'Playground', 'Jointly Operated Playground', 'Nature Area',
              'Recreational Field/Courts', 'Waterfront Facility', 'Historic House Park', 'Garden'}
by_prop = defaultdict(set)
for f in load('playgrounds.geojson')['features']: by_prop[f['properties'].get('gispropnum')].add('play')
for f in load('spray.geojson')['features']: by_prop[f['properties'].get('propnum')].add('water')
for f in load('dog_runs.geojson')['features']: by_prop[f['properties'].get('gispropnum')].add('dog')
parks, park_pt = [], {}
for f in load('parks.geojson')['features']:
    p = f['properties']
    if p.get('typecategory') not in PARK_TYPES or not f.get('geometry') or str(p.get('retired')).lower() == 'true': continue
    g = shape(f['geometry']).buffer(0)
    if g.is_empty: continue
    g = g.simplify(0.00002, preserve_topology=True)
    num = p.get('gispropnum')
    am = [a for a in ('play', 'water', 'dog') if a in by_prop.get(num, ())]
    pr = {'n': (p.get('signname') or p.get('name311') or '').strip(), 'u': num}
    if am: pr['a'] = am
    rp = g.representative_point(); park_pt[num] = (pr['n'], rp.x, rp.y, am)
    gm = mapping(g)
    rnd = lambda o: [rnd(x) for x in o] if isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]
    parks.append({'type': 'Feature', 'properties': pr, 'geometry': {'type': gm['type'], 'coordinates': rnd(gm['coordinates'])}, '_a': g.area})
parks.sort(key=lambda f: -f.pop('_a'))
write('parks.geojson', fc(parks, asof={'parks': '2026-10-16'}, count=len(parks)))
print('parks:', len(parks), Counter(a for f in parks for a in f['properties'].get('a', [])))

# ---------- Sports & rec: one point per park, with its sports ----------
SPORT = [('basketball', 'basketball', 'basketball court'), ('tennis', 'tennis', 'tennis court'), ('pickleball', 'pickleball', 'pickleball court'),
         ('cricket', 'cricket', 'cricket pitch')]
DIAMOND = ('adult_baseball', 'adult_softball', 'll_baseb_12andunder', 'll_baseb_13andolder', 'll_softball')
FIELD = ('adult_football', 'flagfootball', 'lacrosse', 'nonregulation_soccer', 'soccer', 'rugby', 'frisbee')
yes = lambda v: v is True or str(v).lower() == 'true'
spots = defaultdict(lambda: {'cats': Counter(), 'pts': []})
for f in load('athletic.geojson')['features']:
    p = f['properties']
    if (p.get('featurestatus') or 'Active') != 'Active' or not f.get('geometry'): continue
    s = spots[p.get('gispropnum')]
    c = shape(f['geometry']).centroid; s['pts'].append((c.x, c.y))
    for k, cat, _ in SPORT:
        if yes(p.get(k)): s['cats'][cat] += 1
    if any(yes(p.get(k)) for k in DIAMOND): s['cats']['diamond'] += 1
    if any(yes(p.get(k)) for k in FIELD): s['cats']['field'] += 1
for name, cat in (('pools.geojson', 'pool'), ('skateparks.geojson', 'skatepark')):
    for f in load(name)['features']:
        if not f.get('geometry'): continue
        s = spots[f['properties'].get('gispropnum')]
        c = shape(f['geometry']).centroid; s['pts'].append((c.x, c.y)); s['cats'][cat] += 1
NOUN = {'pool': ('pool', 'pools'), 'diamond': ('ball diamond', 'ball diamonds'), 'field': ('field', 'fields'), 'tennis': ('tennis court', 'tennis courts'),
        'pickleball': ('pickleball court', 'pickleball courts'), 'basketball': ('basketball court', 'basketball courts'),
        'skatepark': ('skatepark', 'skateparks'), 'cricket': ('cricket pitch', 'cricket pitches')}
ORDER = ['pool', 'diamond', 'field', 'tennis', 'pickleball', 'basketball', 'skatepark', 'cricket']
sports = []
for num, s in spots.items():
    if not s['cats'] or not s['pts']: continue
    nm = park_pt.get(num, ('',))[0] or 'NYC Parks facility'
    x = sum(a for a, _ in s['pts']) / len(s['pts']); y = sum(b for _, b in s['pts']) / len(s['pts'])
    cats = [c for c in ORDER if s['cats'][c]]
    has = ', '.join('%d %s' % (s['cats'][c], NOUN[c][0] if s['cats'][c] == 1 else NOUN[c][1]) for c in cats)
    sports.append({'type': 'Feature', 'properties': {'name': nm, 'cat': cats[0], 'cats': cats, 'sub': 'NYC Parks', 'has': has,
                                                     'u': 'https://www.nycgovparks.org/parks/%s' % num if num else ''},
                   'geometry': pt(x, y)})
write('sports.geojson', fc(sports, asof='October 2026', count=len(sports), counts={c: sum(1 for f in sports if c in f['properties']['cats']) for c in ORDER}))
print('sports:', len(sports), {c: sum(1 for f in sports if c in f['properties']['cats']) for c in ORDER})

# ---------- Nearby points for the card ----------
G = defaultdict(list)
for f in comm: G[f['properties']['cat']].append(f['geometry']['coordinates'] + [f['properties']['name']])
for f in sports:
    for c in ('pool', 'tennis', 'basketball'):
        if c in f['properties']['cats']: G[c].append(f['geometry']['coordinates'] + [f['properties']['name']])
for num, (n, x, y, am) in park_pt.items():
    G['park'].append([round(x, 5), round(y, 5), n])
    if 'play' in am: G['playground'].append([round(x, 5), round(y, 5), n])
    if 'water' in am: G['spray'].append([round(x, 5), round(y, 5), n])
    if 'dog' in am: G['dogrun'].append([round(x, 5), round(y, 5), n])
for f in schools:
    G['school_e' if f['properties']['cat'] == 'elementary' else 'school_s'].append(f['geometry']['coordinates'] + [f['properties']['name']])
if os.path.exists(os.path.join(DATA, 'faith.geojson')):
    for f in json.load(open(os.path.join(DATA, 'faith.geojson')))['features']:
        p = f['properties']
        G[p['cat']].append(f['geometry']['coordinates'] + [p['name']])
        if p['cat'] == 'church' and p.get('group'): G['church:' + p['group']].append(f['geometry']['coordinates'] + [p['name']])
write('nearby.json', {'groups': dict(G)})
print('nearby:', {k: len(v) for k, v in G.items()})
