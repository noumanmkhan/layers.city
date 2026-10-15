"""Positions for the French schools the City's Schools file doesn't list (the CSF's), into raw/schools/geocode.json,
from OpenStreetMap Nominatim (one request a second, as its usage policy asks; a cache, so known addresses aren't
asked again). Run from GitHub Actions (fetch-vancouver.yml); the sandbox can't reach Nominatim."""
import csv, json, os, sys, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_lib as F

OUT = os.path.join(F.RAW, 'schools'); os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, 'geocode.json')
cache = json.load(open(path)) if os.path.exists(path) else {}
for s in csv.DictReader(open(os.path.join(HERE, 'french_schools.csv'), encoding='utf-8')):
    a = s['address']
    if s['city_name'] or s['lat'] or a in cache: continue
    q = urllib.parse.urlencode({'street': a, 'city': 'Vancouver', 'state': 'British Columbia', 'country': 'Canada',
                                'format': 'jsonv2', 'limit': 1})
    time.sleep(1.2)
    hits = json.loads(F.get('https://nominatim.openstreetmap.org/search?' + q))
    cache[a] = {'at': [round(float(hits[0]['lon']), 6), round(float(hits[0]['lat']), 6)], 'type': hits[0].get('type'),
                'display': hits[0].get('display_name')} if hits else {}
    print(a, '->', cache[a])
json.dump(cache, open(path, 'w'), indent=1, ensure_ascii=False)
