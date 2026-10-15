"""Points for the card's Nearby section -> docs/dallas/data/nearby.json (the same shape as Toronto's and Chicago's).
Inputs: raw/city/ and raw/osm_playgrounds.json, raw/osm_tennis.json (fetch_more.py), docs/dallas/data/institutions.geojson.

library     Dallas Public Library branches and the Central Library (City of Dallas GIS).
centre      City of Dallas recreation centers, community and neighborhood (City of Dallas GIS).
er          Hospitals with an emergency department, from the institutions layer.
park        Dallas Park and Recreation parks (City of Dallas GIS): open parks only, one point each, leaving out medians,
            cemeteries, golf courses, the gun club and future parks.
pool        City community pools and indoor pools (City of Dallas GIS, 2023 lists).
spray       City spray grounds, counted.
dogpark     The City's dog parks.
playground, tennis
            From OpenStreetMap, inside the city: playgrounds; tennis courts, merged so courts within 80 m of each other
            count as one place. Left out when the OSM file is missing.
Describe only: the card names the nearest of each and counts what is within the radius in city.json; nothing is ranked."""
import json, math, os, re
from shapely.geometry import shape, Point
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
DATA = os.path.join(HERE, '..', '..', 'docs', 'dallas', 'data')
CITY = unary_union([shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(DATA, 'sides.geojson')))['features']]).buffer(0.002)
inside = lambda c: CITY.contains(Point(c))
metres = lambda a, b: math.hypot((a[0] - b[0]) * 93600, (a[1] - b[1]) * 111200)
xy = lambda g: [round(g.x, 5), round(g.y, 5)]
feats = lambda n: json.load(open(os.path.join(RAW, 'city', n)))['features']
SMALL = {'Ii', 'Iii', 'Iv', 'Mlk', 'Jr', 'Dr', 'Ii.'}


def title(s):
    s = re.sub(r"\b([A-Za-z])([A-Za-z']*)", lambda m: m.group(1).upper() + m.group(2).lower(), s.strip())
    s = re.sub(r"(\w)'S\b", r"\1's", s)
    return re.sub(r'\b(Mlk|Ii|Iii|Iv)\b', lambda m: m.group(1).upper(), s)


groups = {k: [] for k in ('library', 'centre', 'er', 'pool', 'spray', 'park', 'dogpark', 'playground', 'tennis')}
for f in feats('libraries.geojson'):
    n = title(f['properties']['LIBRARY']).replace('Branch Library', 'branch').replace('Library', '').strip()
    if 'Central' in n: n = 'J. Erik Jonsson Central Library'
    groups['library'].append(xy(shape(f['geometry'])) + [n])
for f in feats('rec_centers.geojson'):
    n = title(f['properties']['Name'])
    groups['centre'].append(xy(shape(f['geometry'])) + [n if re.search(r'center|centre', n, re.I) else n + ' Recreation Center'])
for name, key in (('pools.geojson', 'pool'), ('indoor_pools.geojson', 'pool'), ('spray.geojson', 'spray')):
    if not os.path.exists(os.path.join(RAW, 'city', name)): continue
    for f in feats(name):
        if not f.get('geometry'): continue
        n = title(f['properties'].get('NAME') or '')
        if key == 'pool' and n and not re.search(r'pool|aquatic|natatorium', n, re.I): n += ' Pool'
        groups[key].append(xy(shape(f['geometry'])) + [n])
SKIP = re.compile(r'median|cemetery|golf|gun club|future', re.I)
for f in feats('parks.geojson'):
    p = f['properties']
    if (p.get('ParkStatus') or '').strip() != 'Park' or SKIP.search(p.get('PARK_TYPE') or '') or not f.get('geometry'): continue
    groups['park'].append(xy(shape(f['geometry']).representative_point()))
for f in feats('dog_parks.geojson'):
    n = f['properties']['Name'].strip()
    groups['dogpark'].append(xy(shape(f['geometry'])) + [n if re.search(r'park|dog', n, re.I) else n + ' Dog Park'])
for name, key in (('osm_playgrounds.json', 'playground'), ('osm_tennis.json', 'tennis')):
    p = os.path.join(RAW, name)
    if not os.path.exists(p): continue
    for e in json.load(open(p))['elements']:
        if (e.get('tags', {}).get('access') or '') in ('private', 'customers', 'members', 'no'): continue
        c = e.get('center') or {'lat': e.get('lat'), 'lon': e.get('lon')}
        if c.get('lat') is None: continue
        c = [round(c['lon'], 5), round(c['lat'], 5)]
        if not inside(c): continue
        if key == 'tennis' and any(metres(c, t) < 80 for t in groups['tennis']): continue   # one point per group of courts
        groups[key].append(c)
for f in json.load(open(os.path.join(DATA, 'institutions.geojson')))['features']:
    if f['properties'].get('ed'): groups['er'].append(f['geometry']['coordinates'] + [f['properties']['name']])
groups = {k: v for k, v in groups.items() if v}
json.dump({'groups': groups}, open(os.path.join(DATA, 'nearby.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('nearby:', {k: len(v) for k, v in groups.items()})
