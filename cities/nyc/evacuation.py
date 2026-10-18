"""Build tmp/evacuation.geojson (simplified by run.sh into docs/nyc/data/evacuation.geojson) from NYC Emergency
Management's hurricane evacuation zones (raw/places/evacuation_zones.geojson, fetch_places.py), and add the 60
evacuation centers to docs/nyc/data/nearby.json as the named group "evaccenter" (run after places.py, which writes it).

The source has eight areas: zones 1 to 6, "X" (land in no zone) and "7" (water). Only 1 to 6 are kept, each one
feature with `zone` (1 to 6, 1 the first told to leave) and `name` ("Zone 1"). Zones are where to leave from when
the City orders it, by storm strength; they don't say a place floods."""
import json, os
from shapely.geometry import shape, mapping

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'places')
DATA = os.path.join(HERE, '..', '..', 'docs', 'nyc', 'data')
os.makedirs(os.path.join(HERE, 'tmp'), exist_ok=True)

out = []
for f in json.load(open(os.path.join(RAW, 'evacuation_zones.geojson')))['features']:
    z = (f['properties'].get('hurricane_') or '').strip()
    if z not in {'1', '2', '3', '4', '5', '6'}: continue
    g = shape(f['geometry']).buffer(0)
    lp = g.representative_point()
    out.append({'type': 'Feature', 'properties': {'zone': int(z), 'name': 'Zone ' + z, 'lp': [round(lp.x, 5), round(lp.y, 5)]}, 'geometry': mapping(g)})
out.sort(key=lambda f: f['properties']['zone'])
json.dump({'type': 'FeatureCollection', 'features': out}, open(os.path.join(HERE, 'tmp', 'evacuation.geojson'), 'w'))

centers = [[round(c['geometry']['coordinates'][0], 5), round(c['geometry']['coordinates'][1], 5), c['properties']['bldg_name'].strip()]
           for c in json.load(open(os.path.join(RAW, 'evacuation_centers.geojson')))['features'] if c.get('geometry')]
NB = os.path.join(DATA, 'nearby.json')
nb = json.load(open(NB))
nb['groups']['evaccenter'] = centers
json.dump(nb, open(NB, 'w'), separators=(',', ':'), ensure_ascii=False)
print('evacuation:', len(out), 'zones', [f['properties']['zone'] for f in out], '·', len(centers), 'centers')
