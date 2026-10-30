"""Fetch San Francisco's hazard, Slow Streets, soft-story and ferry layers into cities/sf/raw/extras/ (and Slow Streets
into raw/slow_streets.geojson for the bike lanes build). Runs in GitHub Actions (fetch-sf.yml).

- tsunami.geojson: California Geological Survey's Tsunami Hazard Area for emergency planning, San Francisco
  (DataSF 7p2k-c3z6, the 2021 update): where to leave in a tsunami warning.
- seismic.geojson: the State's Seismic Hazard Zones for San Francisco (DataSF re79-p8j5): areas mapped for
  liquefaction or earthquake-induced landslides, where new building needs a geotechnical study.
- soft_story.json: the Mandatory Soft Story Retrofit Program's buildings (DataSF beah-shgi): wood-frame buildings of
  three or more stories and five or more homes over a soft first floor, with tier and status.
- slow_streets.geojson (raw/): SFMTA's Slow Streets (DataSF hkz3-itiu), implemented ones, in the bike network's
  fields (bikes.json "extra").
- osm_ferries.json: OpenStreetMap ferry routes and terminals across the Bay (ODbL): San Francisco Bay Ferry, Golden
  Gate Ferry, the Angel Island and Alcatraz boats."""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, save, step, overpass, RAW, REGION, FAILED

SOC = 'https://data.sfgov.org'
P = 'extras'
os.makedirs(os.path.join(RAW, P), exist_ok=True)
b = lambda box: '(%s,%s,%s,%s)' % (box[1], box[0], box[3], box[2])


def geo(i):
    for url in [f'{SOC}/resource/{i}.geojson?$limit=50000', f'{SOC}/api/v3/views/{i}/query.geojson?accessType=DOWNLOAD']:
        try:
            d = json.loads(get(url, tries=2))
            if d.get('features') and d['features'][0].get('geometry'): return d
            print('  no features from', url)
        except Exception as e:
            print('  ', url, e)
    raise RuntimeError('no geojson for ' + i)


def tsunami():
    d = geo('7p2k-c3z6'); save(os.path.join(P, 'tsunami.geojson'), d)
    print('  tsunami', len(d['features']), [f['properties'].get('evacuate') for f in d['features']][:3])


def seismic():
    d = geo('re79-p8j5'); save(os.path.join(P, 'seismic.geojson'), d)
    print('  seismic', len(d['features']), sorted(d['features'][0]['properties']))


def soft_story():
    rows = json.loads(get(f'{SOC}/resource/beah-shgi.json?$limit=50000', tries=3))
    rows = [{k: v for k, v in r.items() if not k.startswith(':@')} for r in rows]
    save(os.path.join(P, 'soft_story.json'), {'fetched': time.strftime('%Y-%m-%d'), 'rows': rows})
    from collections import Counter
    print('  soft story', len(rows), Counter(r.get('status') for r in rows).most_common(12), Counter(r.get('tier') for r in rows))


def slow_streets():
    d = geo('hkz3-itiu')
    from collections import Counter
    print('  slow streets', len(d['features']), Counter(f['properties'].get('status') for f in d['features']))
    feats = []
    for f in d['features']:
        p = f['properties']
        if (p.get('status') or '').lower() != 'implemented' or not f.get('geometry'): continue
        feats.append({'type': 'Feature', 'geometry': f['geometry'],
                      'properties': {'streetname': p.get('streetname') or '', 'street_': '', 'from_st': p.get('f_st') or '', 'to_st': p.get('t_st') or '',
                                     'facility_t': 'SLOW STREET', 'install_yr': (p.get('install_date') or '')[:4]}})
    json.dump({'type': 'FeatureCollection', 'fetched': time.strftime('%Y-%m-%d'), 'features': feats},
              open(os.path.join(RAW, 'slow_streets.geojson'), 'w'), separators=(',', ':'))
    print('  kept', len(feats), 'implemented segments')


def ferries():
    overpass(f'[out:json][timeout:300];(relation["route"="ferry"]{b(REGION)};way["route"="ferry"]{b(REGION)};);out geom;', os.path.join(P, 'osm_ferries.json'))
    overpass(f'[out:json][timeout:300];(nwr["amenity"="ferry_terminal"]{b(REGION)};);out tags center;', os.path.join(P, 'osm_ferry_terminals.json'))


for label, fn in [('tsunami', tsunami), ('seismic', seismic), ('soft_story', soft_story), ('slow_streets', slow_streets), ('ferries', ferries)]:
    print('==', label); step(label, fn); time.sleep(1)
print('FAILED:', FAILED or 'none')
