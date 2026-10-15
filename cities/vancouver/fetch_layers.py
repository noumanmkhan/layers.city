"""Fetch the inputs for Vancouver's layers beyond the first build (October 16, 2026: parity with Toronto) into raw/.
Runs in GitHub Actions (fetch-vancouver.yml); the sandbox can't reach these hosts. Each step is logged on its own and
a failed step keeps the last good file.

  ods/<dataset>.geojson   City of Vancouver Open Data (Opendatasoft, OGL – Vancouver), whole datasets as GeoJSON:
                          libraries, community-centres, parks (points), parks-facilities (table), dog-off-leash-parks,
                          schools, business-improvement-areas-bia, zoning-districts-and-labels (heritage-area and
                          First Shaughnessy zones only), road-ahead-current-road-closures,
                          road-ahead-projects-under-construction, voting-places-2026
  ods/garbage/            the two garbage-collection-zone datasets publish files, not records: their attachments
  ods/meta.json           each dataset's last-modified date
  prov_districts.geojson  BC provincial electoral districts (DataBC WFS, OGL – British Columbia), the ones that touch
                          Metro Vancouver
  fed2023.geojson         Federal electoral districts, 2023 Representation Order, in and around the City, from Open
                          North's Represent (as Toronto's), simple shapes
  institutions_osm.json   Universities, colleges and hospitals in Metro Vancouver from OpenStreetMap, to place the
                          curated list in institutions.py
"""
import json, os, sys, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_lib as F

ODS = 'https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/'
OUT = os.path.join(F.RAW, 'ods'); os.makedirs(os.path.join(OUT, 'garbage'), exist_ok=True)
meta = {}
DATASETS = {
    'libraries': None, 'community-centres': None, 'parks': None, 'dog-off-leash-parks': None, 'schools': None,
    'business-improvement-areas-bia': None,
    'zoning-districts-and-labels': None,   # filtered below to the historic-area and First Shaughnessy zones
    'road-ahead-current-road-closures': None, 'road-ahead-projects-under-construction': None, 'voting-places-2026': None,
}


def ods(ds, where=None):
    q = ('?' + urllib.parse.urlencode({'where': where})) if where else ''
    d = json.loads(F.get(ODS + ds + '/exports/geojson' + q))
    if not d.get('features'): raise RuntimeError(f'{ds}: no features')
    if ds == 'zoning-districts-and-labels':
        from collections import Counter
        print('   zoning:', dict(Counter((f['properties'].get('zoning_category'), f['properties'].get('zoning_district')) for f in d['features']
                                        if not str(f['properties'].get('zoning_district')).startswith('CD-1')).most_common()))
        d['features'] = [f for f in d['features'] if str(f['properties'].get('zoning_district') or '').startswith(('HA', 'FSD', 'FM'))
                         or str(f['properties'].get('zoning_category') or '').startswith(('HA', 'FSD'))]
    json.dump(d, open(os.path.join(OUT, ds + '.geojson'), 'w'), separators=(',', ':'), ensure_ascii=False)
    m = json.loads(F.get(ODS + ds))['metas']['default']
    meta[ds] = {'modified': m.get('modified'), 'records': m.get('records_count'), 'license': m.get('license')}
    print('  ', ds, len(d['features']), 'features, modified', (m.get('modified') or '')[:10])


for ds, where in DATASETS.items():
    F.step('ods ' + ds, lambda ds=ds, where=where: ods(ds, where))
    time.sleep(1)


def facilities():   # a table with no geometry
    rows = json.loads(F.get(ODS + 'parks-facilities/exports/json'))
    json.dump(rows, open(os.path.join(OUT, 'parks-facilities.json'), 'w'), separators=(',', ':'))
    from collections import Counter
    print('   parks-facilities', len(rows), dict(Counter(r['facilitytype'] for r in rows).most_common(60)))
F.step('ods parks-facilities', facilities)




def garbage():
    for ds in ('garbage-collection-schedule-zones-for-single-family-homes-and-duplexes',
               'garbage-collection-schedule-zones-for-multi-unit-residential-buildings'):
        info = json.loads(F.get(ODS + ds))
        m = info['metas']['default']
        print('  ', ds, 'modified', m.get('modified'), '| description:', (m.get('description') or '')[:600])
        att = json.loads(F.get(ODS + ds + '/attachments')).get('attachments', [])
        print('   attachments:', [(a.get('id'), a.get('title'), a.get('href')) for a in att])
        for a in att:
            name = ds[:40] + '__' + (a.get('id') or 'file')
            try:
                F.download(a['href'], os.path.join(OUT, 'garbage', name))
            except Exception as e:
                print('   ! attachment', a.get('href'), e)
F.step('garbage zones', garbage)
json.dump(meta, open(os.path.join(OUT, 'meta.json'), 'w'), indent=1)

# ---------- BC provincial electoral districts (DataBC) ----------
WFS = ('https://openmaps.gov.bc.ca/geo/pub/wfs?service=WFS&version=2.0.0&request=GetFeature&outputFormat=json&srsName=EPSG:4326'
       '&typeName=WHSE_ADMIN_BOUNDARIES.EBC_PROV_ELECTORAL_DIST_SVW&bbox=49.0,-123.45,49.6,-122.2,urn:ogc:def:crs:EPSG:4326')


def prov():
    d = json.loads(F.get(WFS))
    for f in d['features']:
        f['properties'] = {k: f['properties'].get(k) for k in ('ED_NAME', 'ED_ABBREVIATION', 'ELECTORAL_DISTRICT_ID', 'BOUNDARY_SET_ID')}
    F.save('prov_districts.geojson', d)
    print('   districts:', sorted(f['properties']['ED_NAME'] for f in d['features']))
F.step('provincial districts', prov)

# ---------- Federal ridings (2023 Representation Order) via Represent, as Toronto's ----------
REP = 'https://represent.opennorth.ca'
SET = '/boundaries/federal-electoral-districts-2023-representation-order/'


def fed():
    seen = {}
    s, w, n, e = 49.19, -123.24, 49.33, -123.01
    for i in range(9):
        for j in range(9):
            lat, lon = s + (n - s) * i / 8, w + (e - w) * j / 8
            r = json.loads(F.get(REP + SET + '?' + urllib.parse.urlencode({'contains': f'{lat:.5f},{lon:.5f}'})))
            for o in r.get('objects', []): seen[o['url']] = o['name']
            time.sleep(1.1)   # Represent allows 60 requests a minute
    feats = []
    for url, name in sorted(seen.items(), key=lambda kv: kv[1]):
        g = json.loads(F.get(REP + url + 'simple_shape'))
        feats.append({'type': 'Feature', 'properties': {'name': name, 'id': url.rstrip('/').rsplit('/', 1)[-1]}, 'geometry': g})
        time.sleep(1.1)
    F.save('fed2023.geojson', {'type': 'FeatureCollection', 'features': feats})
    print('   ridings:', [f['properties']['name'] for f in feats])
F.step('federal ridings', fed)

# ---------- Universities, colleges, hospitals (OpenStreetMap) ----------


def institutions():
    s, w, n, e = 49.0, -123.3, 49.4, -122.5
    q = f"""[out:json][timeout:240];
(nwr["amenity"~"^(university|college|hospital)$"]["name"]({s},{w},{n},{e});
 nwr["healthcare"="hospital"]["name"]({s},{w},{n},{e}););
out tags center;"""
    d = F.overpass(q, 'institutions_osm_full.json')
    els = []
    for el in d.get('elements', []):
        t, c = el.get('tags', {}), (el if el['type'] == 'node' else el.get('center'))
        if not c: continue
        els.append({'osm': el['type'][0] + str(el['id']), 'name': t['name'], 'at': [round(c['lon'], 5), round(c['lat'], 5)],
                    'amenity': t.get('amenity') or t.get('healthcare'), 'operator': t.get('operator'), 'emergency': t.get('emergency'),
                    'website': t.get('website'), 'addr': ' '.join(x for x in (t.get('addr:housenumber'), t.get('addr:street')) if x)})
    os.remove(os.path.join(F.RAW, 'institutions_osm_full.json'))
    F.save('institutions_osm.json', sorted(els, key=lambda x: (x['amenity'] or '', x['name'])))
    for x in sorted(els, key=lambda x: (x['amenity'] or '', x['name'])): print('   ', x['amenity'], '|', x['name'], '|', x['operator'], '|', x['emergency'], x['at'])
F.step('institutions', institutions)
print('done; failed:', F.FAILED or 'none')
