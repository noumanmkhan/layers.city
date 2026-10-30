"""Fetch San Francisco's places for the Outdoors, Education, Community and card layers into cities/sf/raw/places/.
Runs in GitHub Actions (fetch-sf.yml). Dataset ids checked by scouting/sf/scout.py (October 30, 2026).

- parks.geojson: Recreation and Parks Department Park Properties (gtr9-ntp6), with outlines
- park_facilities.json: Rec & Park facilities (ib5c-xgwu): playgrounds, dog play areas, pools, courts, fields,
  recreation centers and clubhouses, each with its park's property id
- schools.json: Schools (7e7j-59qk): California Department of Education's school directory for the city, public and private
- city_facilities.json: City-owned and leased facilities (nc68-ngbr), only the Public Library's (its branches)
- osm_hospitals.json, osm_colleges.json: OpenStreetMap hospitals and colleges and universities in the city (ODbL), for
  their positions; which ones the map shows is a curated list in places.py
- osm_worship.json: OpenStreetMap places of worship in the city (ODbL)"""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, save, step, overpass, RAW, CITY, FAILED

SOC = 'https://data.sfgov.org'
P = 'places'
os.makedirs(os.path.join(RAW, P), exist_ok=True)
b = lambda box: '(%s,%s,%s,%s)' % (box[1], box[0], box[3], box[2])


def parks():
    for url in [f'{SOC}/resource/gtr9-ntp6.geojson?$limit=50000', f'{SOC}/api/v3/views/gtr9-ntp6/query.geojson?accessType=DOWNLOAD']:
        try:
            d = json.loads(get(url, tries=2))
            if d.get('features') and d['features'][0].get('geometry'):
                save(os.path.join(P, 'parks.geojson'), d)
                print('  parks', len(d['features']), sorted(d['features'][0]['properties'])[:30]); return
        except Exception as e:
            print('  ', url, e)
    raise RuntimeError('no parks')


def rows(i, name, where=None, drop=('shape', 'geom', 'point')):
    q = {'$limit': 50000}
    if where: q['$where'] = where
    d = json.loads(get(f'{SOC}/resource/{i}.json?' + urllib.parse.urlencode(q), tries=3))
    d = [{k: v for k, v in r.items() if k not in drop and not k.startswith(':@')} for r in d]
    save(os.path.join(P, name), d)
    print('  ', name, len(d), sorted(d[0]) if d else '')


def osm():
    overpass(f'[out:json][timeout:300];nwr["amenity"="hospital"]{b(CITY)};out tags center;', os.path.join(P, 'osm_hospitals.json'))
    overpass(f'[out:json][timeout:300];nwr["amenity"~"^(university|college)$"]{b(CITY)};out tags center;', os.path.join(P, 'osm_colleges.json'))
    overpass(f'[out:json][timeout:300];nwr["amenity"="place_of_worship"]{b(CITY)};out tags center;', os.path.join(P, 'osm_worship.json'))


step('parks', parks); time.sleep(1)
step('park_facilities', lambda: rows('ib5c-xgwu', 'park_facilities.json')); time.sleep(1)
step('schools', lambda: rows('7e7j-59qk', 'schools.json')); time.sleep(1)
step('city_facilities', lambda: rows('nc68-ngbr', 'city_facilities.json', "department_name like '%Library%'")); time.sleep(1)
step('osm', osm)
print('FAILED:', FAILED or 'none')
