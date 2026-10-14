"""French-language and French immersion schools for the two school toggles in Places.
Inputs: french_schools.csv (the curated list) and raw/schools/school_locations_4326.csv (the City's
School locations - all types, open data, for coordinates).
Output: docs/toronto/data/french_schools.geojson, one point per school, "cat" frschool or immersion.

The rules (decided October 14, 2026):
- Two kinds, never mixed: French-language schools (Conseil scolaire Viamonde and Conseil scolaire
  catholique MonAvenir) teach in French for children with a francophone parent or by admission;
  French immersion schools (TDSB, TCDSB) teach mostly in French to children from English-speaking homes.
- Each school is placed by the City's point for it, matched by its exact City name (city_name). The
  City's file is out of date on the French boards: it lists some of their newer schools under English
  boards or as private, so matching is by name and address, never by the City's board field.
- The lists come from the boards: TDSB's 2026-27 Early and Middle Immersion location maps, TCDSB's
  French as a Second Language page, and the French boards' school lists. One point per school with
  all its programs. Bannockburn PS (TDSB Early Immersion, 12 Bannockburn Ave) isn't in the City's file
  yet, so it's left out until it is.
- Schools sharing a building (Toronto Ouest and Saint-Frère-André at 330 Lansdowne) get one point each,
  nudged apart so both show.
"""
import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'french_schools.geojson')
city = {}
for r in csv.DictReader(open(os.path.join(HERE, 'raw', 'schools', 'school_locations_4326.csv'), encoding='utf-8-sig')):
    city.setdefault(r['NAME'].strip(), []).append(r)

LEVEL = {'elementary': 'Elementary', 'secondary': 'Secondary'}
PROGRAM = {'Early': 'Early immersion', 'Middle': 'Middle immersion', 'Early & Middle': 'Early and middle immersion',
           'Immersion from JK': 'Immersion from JK', 'Immersion': 'Immersion'}
feats, missing, seen = [], [], {}
for s in csv.DictReader(open(os.path.join(HERE, 'french_schools.csv'), encoding='utf-8')):
    hits = [r for r in city.get(s['city_name'], []) if r['ADDRESS_FULL'] == s['city_address']] or city.get(s['city_name'], [])
    if not hits:
        missing.append(s['name']); continue
    lon, lat = json.loads(hits[0]['geometry'])['coordinates'][0]
    n = seen.get((lon, lat), 0); seen[(lon, lat)] = n + 1
    sub = [s['board'], PROGRAM.get(s['program']) if s['cat'] == 'immersion' else LEVEL[s['level']]]
    if s['cat'] == 'immersion' and s['level'] == 'secondary':
        sub[1] = 'Secondary immersion'
    feats.append({'type': 'Feature', 'properties': {'name': s['name'], 'cat': s['cat'], 'sub': ' · '.join(x for x in sub if x)},
                  'geometry': {'type': 'Point', 'coordinates': [round(lon + 0.00025 * n, 5), round(lat, 5)]}})
if missing:
    raise SystemExit('not in the City file: ' + ', '.join(missing))
json.dump({'type': 'FeatureCollection', 'features': feats}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
from collections import Counter
print('french schools:', len(feats), dict(Counter(f['properties']['cat'] for f in feats)))
