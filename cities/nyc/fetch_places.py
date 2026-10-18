"""Fetch New York City's places for the Outdoors, Education, Community and card layers into cities/nyc/raw/places/.
Runs in GitHub Actions (fetch-nyc.yml). Dataset ids checked by scouting/nyc/scout.py (October 18, 2026).

- dsny_frequencies.geojson: DSNY Frequencies (rv63-53db): refuse, recycling, organics and bulk days by section
- parks.geojson: NYC Parks Properties (enfh-gkve)
- athletic.geojson, pools, dog_runs, spray, skateparks, playgrounds: NYC Parks directories (qnem-b8re, y5rm-wagw,
  hxx3-bwgv, ckaz-6gaa, 8knb-zsb6, j55h-3upk)
- facdb.json: the City Planning Facilities Database (ji82-xba5), only the groups the map uses: libraries, hospitals and
  clinics, higher education, schools, community and senior centres, recreation centres
- school_zones_es/ms/hs.geojson: DOE School Zones 2024-2025 (cmjf-yawu, t26j-jbq7, ruu9-egea)
- worship_osm.json: OpenStreetMap places of worship in the five boroughs (ODbL)"""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, save, step, overpass, RAW, CITY, FAILED

SOC = 'https://data.cityofnewyork.us/resource/'
P = 'places'
os.makedirs(os.path.join(RAW, P), exist_ok=True)
GEO = [('dsny_frequencies', 'rv63-53db'), ('parks', 'enfh-gkve'), ('athletic', 'qnem-b8re'), ('pools', 'y5rm-wagw'),
       ('dog_runs', 'hxx3-bwgv'), ('spray', 'ckaz-6gaa'), ('skateparks', '8knb-zsb6'), ('playgrounds', 'j55h-3upk'),
       ('school_zones_es', 'cmjf-yawu'), ('school_zones_ms', 't26j-jbq7'), ('school_zones_hs', 'ruu9-egea')]
FACDB_GROUPS = ['LIBRARIES', 'HEALTH CARE', 'HIGHER EDUCATION', 'SCHOOLS (K-12)', 'YOUTH SERVICES', 'HUMAN SERVICES', 'PARKS AND PLAZAS',
                'CULTURAL INSTITUTIONS', 'ADULT SERVICES', 'CAMPS']


def socrata():
    for name, i in GEO:
        def one(name=name, i=i):
            d = json.loads(get(f'{SOC}{i}.geojson?$limit=50000', tries=3))
            save(os.path.join(P, name + '.geojson'), d)
            f = d['features'][0] if d['features'] else {}
            print('  ', name, len(d['features']), '·', (f.get('geometry') or {}).get('type'), str((f.get('geometry') or {}).get('coordinates'))[:60], '·', sorted(f.get('properties', {}))[:30])
        step(name, one); time.sleep(1)


def facdb():
    rows, off = [], 0
    where = 'facgroup in(' + ','.join("'%s'" % g for g in FACDB_GROUPS) + ')'
    while True:
        q = urllib.parse.urlencode({'$where': where, '$limit': 50000, '$offset': off})
        got = json.loads(get(f'{SOC}ji82-xba5.json?{q}', tries=3))
        rows += got
        if len(got) < 50000: break
        off += len(got)
    save(os.path.join(P, 'facdb.json'), rows)
    from collections import Counter
    print('  facdb', len(rows), Counter((r.get('facgroup'), r.get('facsubgrp')) for r in rows).most_common(60))


def worship():
    b = f'({CITY[1]},{CITY[0]},{CITY[3]},{CITY[2]})'
    overpass(f'[out:json][timeout:300];nwr["amenity"="place_of_worship"]["name"]{b};out tags center;', os.path.join(P, 'worship_osm.json'))


for label, fn in [('socrata', socrata), ('facdb', facdb), ('worship', worship)]:
    print('==', label); step(label, fn)
print('FAILED:', FAILED or 'none')
