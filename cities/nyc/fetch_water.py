"""Fetch the region's rivers, bays and lakes into cities/nyc/raw/water.geojson: the Census Bureau's TIGER area
hydrography (TIGERweb Hydro), water areas over 0.4 km² in the map's frame. The cartographic boundaries the base is
drawn from run to the middle of the Hudson and the other rivers, so build.py cuts this water out of the land around
the city. Dallas's fetch.py does the same for its lakes. Runs in GitHub Actions (fetch-nyc.yml)."""
import json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, save, FRAME

svc = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Hydro/MapServer'
layers = json.loads(get(svc + '?f=json'))['layers']
area = next(l for l in layers if 'area' in l['name'].lower())
feats, off = [], 0
while True:
    q = {'where': 'AREAWATER > 400000', 'outFields': 'NAME,MTFCC,AREAWATER', 'outSR': 4326, 'f': 'geojson',
         'geometryPrecision': 5, 'maxAllowableOffset': 0.00004, 'geometry': ','.join(map(str, FRAME)),
         'geometryType': 'esriGeometryEnvelope', 'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects',
         'resultOffset': off, 'resultRecordCount': 200}
    d = json.loads(get(f"{svc}/{area['id']}/query?" + urllib.parse.urlencode(q)))
    feats += d.get('features', [])
    print('  got', len(feats))
    if len(d.get('features', [])) < 200: break
    off += 200
save('water.geojson', {'type': 'FeatureCollection', 'features': feats})
big = sorted(feats, key=lambda f: -f['properties']['AREAWATER'])[:30]
print('largest:', [(f['properties']['NAME'], f['properties']['AREAWATER'] // 1_000_000) for f in big])
