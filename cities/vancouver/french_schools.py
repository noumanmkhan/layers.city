"""French-language and French immersion schools for the two school toggles in Places (Toronto's, October 14, 2026).
Inputs: french_schools.csv (the curated list), raw/ods/schools.geojson (the City's Schools, OGL – Vancouver) and
raw/schools/geocode.json (fetch_schools.py: Nominatim positions for the schools the City's file doesn't list).
Output: docs/vancouver/data/french_schools.geojson, one point per school, "cat" frschool or immersion.

- French-language schools: the Conseil scolaire francophone de la Colombie-Britannique (CSF), for children with a
  right to French-language education; its six schools in the City and their addresses from csf.bc.ca (October 2026).
- French immersion: Vancouver School Board schools teaching mostly in French to children from English-speaking
  homes. Elementary schools from the VSB's Early French Immersion page (January 2026; Laura Secord also has Late
  immersion in grades 6–7, Henry Hudson takes grades 6–7 only while it winds down), secondary from its French
  Immersion page (Churchill, Kitsilano and Van Tech).
- Placed by the City's point for the school (city_name), else the CSV's lat/lon, else the geocode. Two schools at
  one address (Rose-des-Vents and Jules-Verne) are nudged apart so both pins show."""
import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'docs', 'vancouver', 'data', 'french_schools.geojson')
city = {f['properties']['school_name']: f['geometry']['coordinates'] for f in json.load(open(os.path.join(HERE, 'raw', 'ods', 'schools.geojson')))['features']}
gp = os.path.join(HERE, 'raw', 'schools', 'geocode.json')
geo = json.load(open(gp)) if os.path.exists(gp) else {}
LEVEL = {'elementary': 'Elementary', 'secondary': 'Secondary'}
feats, missing, seen = [], [], {}
for s in csv.DictReader(open(os.path.join(HERE, 'french_schools.csv'), encoding='utf-8')):
    at = city.get(s['city_name']) if s['city_name'] else None
    if not at and s['lat']: at = [float(s['lon']), float(s['lat'])]
    if not at and (geo.get(s['address']) or {}).get('at'): at = geo[s['address']]['at']
    if not at: missing.append(s['name']); continue
    lon, lat = round(at[0], 5), round(at[1], 5)
    n = seen.get((lon, lat), 0); seen[(lon, lat)] = n + 1
    if s['cat'] == 'immersion':
        sub = [s['board'], 'Secondary immersion' if s['level'] == 'secondary' else (s['program'] + ' immersion' if s['program'] in ('Early', 'Early & Late') else 'Immersion, ' + s['program'])]
        sub[1] = sub[1].replace('Early & Late', 'Early and late')
    else:
        sub = [s['board'], LEVEL[s['level']]]
    feats.append({'type': 'Feature', 'properties': {'name': s['name'], 'cat': s['cat'], 'sub': ' · '.join(sub)},
                  'geometry': {'type': 'Point', 'coordinates': [round(lon + 0.00025 * n, 5), lat]}})
if missing: raise SystemExit('not placed (run fetch_schools.py, or add lat/lon): ' + ', '.join(missing))
json.dump({'type': 'FeatureCollection', 'features': feats}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
from collections import Counter
print('french schools:', len(feats), dict(Counter(f['properties']['cat'] for f in feats)))
