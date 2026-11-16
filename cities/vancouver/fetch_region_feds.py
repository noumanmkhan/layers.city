"""Every British Columbia federal riding (2023 Representation Order) from Open North's Represent, into
raw/fed2023_bc.geojson, so the Federal layer and the card can cover all of Metro Vancouver (layers.py cuts them to the
region; fetch_layers.py's fed2023.geojson covers only the City and its edges). Runs in GitHub Actions
(fetch-vancouver.yml runs a changed fetch script); the sandbox can't reach Represent. Represent allows 60 requests a
minute."""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_lib as F

REP = 'https://represent.opennorth.ca'
SET = '/boundaries/federal-electoral-districts-2023-representation-order/'


def feds():
    objs = json.loads(F.get(REP + SET + '?' + urllib.parse.urlencode({'limit': 1000})))['objects']
    bc = [o for o in objs if str(o.get('external_id', '')).startswith('59')]
    print('   BC ridings:', len(bc), 'of', len(objs))
    feats = []
    for o in sorted(bc, key=lambda o: o['name']):
        time.sleep(1.1)
        g = json.loads(F.get(REP + o['url'] + 'simple_shape'))
        feats.append({'type': 'Feature', 'properties': {'name': o['name'], 'id': o['url'].rstrip('/').rsplit('/', 1)[-1]}, 'geometry': g})
    F.save('fed2023_bc.geojson', {'type': 'FeatureCollection', 'features': feats})
    print('   ridings:', [f['properties']['name'] for f in feats])


F.step('federal ridings (BC)', feds)
