"""Universities, colleges and hospitals for the institution toggles under Landmarks.
Input: raw/institutions_osm.json (fetch_layers.py). Output: docs/vancouver/data/institutions.geojson

A curated list placed by OpenStreetMap: each entry names the OSM object whose centre marks it, and the script stops
if one has gone. Describe only: no ratings, rankings or wait times. The rules are Toronto's (October 9, 2026),
applied October 16:

Universities: public, or private nonprofit with BC degree-granting authority and over 1,000 students, one point per
  campus. UBC's Point Grey campus is outside the City's limits (in the University Endowment Lands) but is shown:
  it is the city's university, and the map's regional view covers it. Left out: satellite sites of universities
  based elsewhere (Northeastern, Adler, Fairleigh Dickinson), for-profit universities (University Canada West),
  small downtown outposts (UBC Robson Square, the Learning Exchange) and theological colleges inside a campus
  (Regent, Corpus Christi, Vancouver School of Theology).
Colleges: public only (BC's public colleges and institutes): Langara, Vancouver Community College and BCIT's
  downtown campus. No private career colleges or language schools.
Hospitals: acute-care hospitals run by Vancouver Coastal Health, Providence Health Care and the Provincial Health
  Services Authority. `ed` marks an emergency department (the health authorities' ED wait-times list, October
  2026); limited hours or ages are added to the line under the name.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'docs', 'vancouver', 'data')
osm = {e['osm']: e for e in json.load(open(os.path.join(HERE, 'raw', 'institutions_osm.json')))}

# (name, cat, sub, OSM id or [lon, lat], extra props)
LIST = [
    ('University of British Columbia', 'university', 'Point Grey campus · Public · University Endowment Lands', 'r1424987', {}),
    ('Simon Fraser University', 'university', 'Vancouver campus · Harbour Centre · Public', [-123.11206, 49.28467], {}),   # 515 W Hastings; OSM has no campus object
    ('Emily Carr University of Art + Design', 'university', 'Great Northern Way · Public', 'w1388920623', {}),
    ('Langara College', 'college', '49th Avenue campus', 'w23393992', {}),
    ('Langara College', 'college', 'West Broadway campus', 'n14100184758', {}),
    ('Vancouver Community College', 'college', 'Broadway campus', 'r19595511', {}),
    ('Vancouver Community College', 'college', 'Downtown campus', 'w1362914589', {}),
    ('BCIT', 'college', 'Downtown campus · British Columbia Institute of Technology', 'w116527969', {}),
    ('Vancouver General Hospital', 'hospital', 'Vancouver Coastal Health', 'r17286359', {'ed': True, 'edNote': 'Emergency for ages 17 and over'}),
    ("St. Paul's Hospital", 'hospital', 'Providence Health Care', 'w51185697', {'ed': True}),
    ('Mount Saint Joseph Hospital', 'hospital', 'Providence Health Care', 'w292380824', {'ed': True, 'edNote': 'Emergency open 8 am to 8 pm'}),
    ("BC Children's Hospital", 'hospital', 'Provincial Health Services Authority', 'n5718035521', {'ed': True, 'edNote': 'Emergency for ages 16 and under'}),
    ("BC Women's Hospital", 'hospital', 'Provincial Health Services Authority', 'w259652372', {}),
    ('UBC Hospital', 'hospital', 'Vancouver Coastal Health · University Endowment Lands', 'n8508184533', {'ed': True, 'edNote': 'Emergency open 8 am to 8 pm'}),
]

gone = [x[3] for x in LIST if isinstance(x[3], str) and x[3] not in osm]
if gone: raise SystemExit('OSM objects no longer in the fetch: ' + ', '.join(gone) + ' (check institutions.py)')
feats = []
for name, cat, sub, ref, extra in LIST:
    at = ref if isinstance(ref, list) else osm[ref]['at']
    note = extra.pop('edNote', '')   # limited hours or ages go after the operator: "Providence Health Care · Emergency 8 am to 8 pm"
    feats.append({'type': 'Feature', 'properties': {'name': name, 'cat': cat, 'sub': ' · '.join(x for x in (sub, note) if x), **extra},
                  'geometry': {'type': 'Point', 'coordinates': at}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(DATA, 'institutions.geojson'), 'w'),
          ensure_ascii=False, separators=(',', ':'))
from collections import Counter
print('institutions:', dict(Counter(f['properties']['cat'] for f in feats)), '· EDs', sum(1 for f in feats if f['properties'].get('ed')))
