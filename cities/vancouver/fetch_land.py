"""Fetch the land around Metro Vancouver (census divisions, coarse) and retry the landmark lookup, into raw/.
Runs in GitHub Actions (fetch-vancouver.yml). fetch.py's per-subdivision query for the surrounding divisions
was too heavy for Statistics Canada's service (HTTP 500); whole divisions, simplified to ~100 m, are enough
for land that is only ever shown faded beyond the region."""
import json, os, re, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_lib as F
from names import LANDMARKS, KNOWN_AS

GEO = 'https://geo.statcan.gc.ca/geo_wa/rest/services/2021/Cartographic_boundary_files/MapServer/'
feats = []
for cd in ('5909', '5931', '5929', '5927', '5917', '5919', '5921', '5923', '5926'):
    def one(cd=cd):
        q = urllib.parse.urlencode({'where': "CDUID = '%s'" % cd, 'outFields': 'CDUID,CDNAME', 'outSR': 4326, 'f': 'geojson',
                                    'returnGeometry': 'true', 'maxAllowableOffset': 0.001})
        d = json.loads(F.get(GEO + '4/query?' + q))
        if 'error' in d: raise RuntimeError(d['error'])
        feats.extend(d['features']); print('  CD', cd, [f['properties'].get('CDNAME') for f in d['features']])
    F.step('census division ' + cd, one); time.sleep(2)
F.save('cds_around.geojson', {'type': 'FeatureCollection', 'features': feats})

def landmarks():
    names = sorted({l.get('osm', l['name']) for l in LANDMARKS} | {k['osm'] for k in KNOWN_AS})
    rx = '|'.join(re.escape(n) for n in names)
    F.overpass(f'[out:json][timeout:300];nwr["name"~"^({rx})$"](49.15,-123.30,49.35,-123.00);out tags center;', 'osm_landmarks.json')
F.step('osm landmarks', landmarks)
print('done; failed:', F.FAILED or 'none')
