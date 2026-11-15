"""Chicagoland beyond the City, for the card's Representatives section: every state House, state Senate and
congressional district in the region's box (Illinois and Indiana), and Indiana's legislators, into raw/region/.
Run from GitHub Actions (fetch-region-basemap.yml runs a city's fetch_region.py after the shared fetches); the
sandbox can't reach these hosts.

  congress.geojson, upper.geojson, lower.geojson   Census TIGERweb (Legislative MapServer 0, 1, 2), STATE 17 and 18,
                                                   with STATE and BASENAME (the district number)
  in.csv                                           Open States' current Indiana legislators (Illinois's il.csv and the
                                                   House Clerk's list come from fetch_representatives.py)"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'region')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}
S, W, N, E = json.load(open(os.path.join(HERE, 'region.json')))['bbox']
TW = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/'


def get(url, tries=6):
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                return r.read()
        except Exception as e:
            print('  retry', a + 1, url[:100], e, flush=True); time.sleep(10 * (a + 1))
    raise SystemExit('failed: ' + url)


def tiger(path):
    feats, start = [], 0
    while True:
        q = {'where': "STATE IN ('17','18')", 'outFields': 'STATE,BASENAME,NAME', 'outSR': 4326, 'f': 'geojson', 'geometryPrecision': 5,
             'maxAllowableOffset': 0.0001, 'geometry': '%s,%s,%s,%s' % (W, S, E, N), 'geometryType': 'esriGeometryEnvelope',
             'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects', 'resultOffset': start, 'resultRecordCount': 200}
        d = json.loads(get(TW + path + '/query?' + urllib.parse.urlencode(q)))
        if 'error' in d: raise SystemExit(d['error'])
        feats += d.get('features', [])
        if len(d.get('features', [])) < 200:
            return {'type': 'FeatureCollection', 'source': 'U.S. Census Bureau TIGERweb (' + path + ')', 'features': feats}
        start += 200; time.sleep(2)


for name, path in [('congress', 'Legislative/MapServer/0'), ('upper', 'Legislative/MapServer/1'), ('lower', 'Legislative/MapServer/2')]:
    fc = tiger(path)
    json.dump(fc, open(os.path.join(OUT, name + '.geojson'), 'w'), separators=(',', ':'))
    print(name, len(fc['features']), 'districts', sorted({f['properties']['STATE'] for f in fc['features']}), flush=True)
    time.sleep(3)
open(os.path.join(OUT, 'in.csv'), 'wb').write(get('https://data.openstates.org/people/current/in.csv'))
print('in.csv saved')
