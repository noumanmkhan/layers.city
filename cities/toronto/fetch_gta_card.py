"""Inputs for the What's here card beyond the City of Toronto (Halton, Peel, York, Durham), into raw/gta_card/.
Run from GitHub Actions (fetch-gta-card.yml); the sandbox can't reach these hosts.

  ridings_fed.geojson   federal electoral districts (2023 Representation Order) in Ontario, Open North Represent
  ridings_prov.geojson  Ontario electoral districts (Representation Act 2015, as amended), Open North Represent
  places.json           OpenStreetMap points in the GTA's box, via Overpass: libraries, community centres, hospitals
                        with an emergency department, playgrounds and named places of worship (with religion and
                        denomination), one [lon, lat, name, extra] per place (areas as their centre)

gta_card.py turns these into docs/toronto/data/gta_ridings.geojson and gta_nearby.json."""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'gta_card')
UA = {'User-Agent': 'layers.city-pipeline (go@layers.city)'}
S, W, N, E = 43.25, -80.2, 44.55, -78.4
os.makedirs(OUT, exist_ok=True)


def get(url, data=None, tries=6, timeout=300):
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            print('  retry', a + 1, url[:90], e, flush=True)
            time.sleep(10 * (a + 1))
    raise SystemExit('failed: ' + url)


# ---------- ridings ----------
REP = 'https://represent.opennorth.ca'
for name, path, keep in [
        ('ridings_fed', '/boundaries/federal-electoral-districts-2023-representation-order/', lambda o: str(o.get('external_id', '')).startswith('35')),
        ('ridings_prov', '/boundaries/ontario-electoral-districts-representation-act-2015/', lambda o: True)]:
    objs = json.loads(get(REP + path + '?limit=1000'))['objects']
    objs = [o for o in objs if keep(o)]
    print(name, len(objs), 'districts', flush=True)
    feats = []
    for o in objs:
        g = json.loads(get(REP + o['url'] + 'simple_shape'))
        feats.append({'type': 'Feature', 'properties': {'name': o['name'], 'id': o.get('external_id')}, 'geometry': g})
        time.sleep(1.1)   # Represent allows 60 requests a minute
    json.dump({'type': 'FeatureCollection', 'source': 'Open North Represent (' + path.strip('/') + ')', 'features': feats},
              open(os.path.join(OUT, name + '.geojson'), 'w'), separators=(',', ':'))

# ---------- places (OpenStreetMap) ----------
Q = """[out:json][timeout:600];
(
  nwr["amenity"="library"]({b});
  nwr["amenity"="community_centre"]({b});
  nwr["leisure"="sports_centre"]["name"~"[Cc]ommunity|[Rr]ecreation|[Cc]entre|[Cc]enter|[Cc]omplex|[Aa]rena"]({b});
  nwr["amenity"="hospital"]({b});
  nwr["leisure"="playground"]({b});
  nwr["amenity"="place_of_worship"]["name"]({b});
);
out tags center;"""
b = '%s,%s,%s,%s' % (S, W, N, E)
res = None
for ep in ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']:
    try:
        res = json.loads(get(ep, urllib.parse.urlencode({'data': Q.format(b=b)}).encode(), tries=4, timeout=900)); break
    except SystemExit as e:
        print(e)
if res is None:
    raise SystemExit('Overpass failed')
out = {k: [] for k in ('library', 'centre', 'hospital', 'playground', 'worship')}
for el in res.get('elements', []):
    t = el.get('tags', {})
    c = (el.get('lon'), el.get('lat')) if el['type'] == 'node' else ((el.get('center') or {}).get('lon'), (el.get('center') or {}).get('lat'))
    if c[0] is None:
        continue
    p = [round(c[0], 5), round(c[1], 5), t.get('name', '')]
    if t.get('amenity') == 'library':
        out['library'].append(p)
    elif t.get('amenity') == 'community_centre' or t.get('leisure') == 'sports_centre':
        out['centre'].append(p)
    elif t.get('amenity') == 'hospital':
        out['hospital'].append(p + [{'emergency': t.get('emergency', ''), 'type': t.get('healthcare:speciality', '')}])
    elif t.get('leisure') == 'playground':
        out['playground'].append(p)
    elif t.get('amenity') == 'place_of_worship':
        out['worship'].append(p + [{'religion': t.get('religion', ''), 'denomination': t.get('denomination', '')}])
json.dump({'source': 'OpenStreetMap contributors (ODbL) via Overpass API', 'fetched': time.strftime('%Y-%m-%d'),
           'bbox': [S, W, N, E], 'groups': out}, open(os.path.join(OUT, 'places.json'), 'w'), separators=(',', ':'))
print('places:', {k: len(v) for k, v in out.items()})
