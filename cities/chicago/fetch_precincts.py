"""Fetch Chicago's election precincts (City Data Portal "Boundaries - Ward Precincts (2025-)", i8fv-xe4b).

Approved by the Chicago Board of Election Commissioners on December 9, 2025; first used March 17, 2026.
Precincts decide which polling place a voter is assigned to. The Board publishes no precinct-to-polling-place
list (its lookup needs a voter's name), so the card names the precinct and links to the Board's lookup.
Runs in Actions (fetch-chicago.yml); writes raw/precincts.geojson.
"""
import json, os, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'https://data.cityofchicago.org/resource/i8fv-xe4b.geojson?$limit=5000'

with urllib.request.urlopen(urllib.request.Request(URL, headers={'User-Agent': 'layers.city map'}), timeout=120) as r:
    fc = json.load(r)
feats = [f for f in fc['features'] if f.get('geometry')]
print('precincts', len(feats), 'wards', len({f['properties'].get('ward') for f in feats}))
print('sample', feats[0]['properties'])
os.makedirs(os.path.join(HERE, 'raw'), exist_ok=True)
with open(os.path.join(HERE, 'raw', 'precincts.geojson'), 'w') as f:
    json.dump({'type': 'FeatureCollection', 'features': feats}, f, separators=(',', ':'))
