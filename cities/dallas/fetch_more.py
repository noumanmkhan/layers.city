"""Second round of Dallas fetches, for the features Toronto and Chicago have. Runs in GitHub Actions.
Each step logs its own failure and the rest carry on. Writes into raw/ (see SOURCES.md):

- representatives/: Open States' Texas legislators (tx.csv), the Clerk of the U.S. House member list (house.xml),
  and the congressional districts members were elected on (PLANC2193, in effect until January 2027)
- city/: City of Dallas layers (ArcGIS Online, services2.arcgis.com/rwnOSbfKSwyTBcwN): libraries, recreation
  centers, parks, pools and spray grounds, dog parks, hospitals, landmark historic districts, historic overlay,
  sanitation days of service and brush routes, school districts, bike facilities, trails; and the City's
  historical markers (Dallas Open Data adn6-n59j)
- disd/: Dallas ISD trustee single-member districts (adopted December 16, 2021)
- institutions/: IPEDS colleges and universities in Texas, CMS hospitals in Dallas (geocoded), OSM campuses and hospitals
- osm_landmarks.json, osm_nearby.json: OpenStreetMap features by name for the landmarks list, and playgrounds,
  tennis courts and parks inside the city
"""
import csv, io, json, os, sys, time, urllib.parse, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import *
from names import LANDMARKS

AGO = 'https://services2.arcgis.com/rwnOSbfKSwyTBcwN/ArcGIS/rest/services/'
for d in ('representatives', 'city', 'disd', 'institutions'):
    os.makedirs(os.path.join(RAW, d), exist_ok=True)


def reps():
    for name, url in [('tx.csv', 'https://data.openstates.org/people/current/tx.csv'), ('house.xml', 'https://clerk.house.gov/xml/lists/MemberData.xml')]:
        b = get(url); open(os.path.join(RAW, 'representatives', name), 'wb').write(b); print('  wrote', name, len(b))
    pkg = json.loads(get('https://data.capitol.texas.gov/api/3/action/package_show?id=planc2193'))['result']
    res = [r for r in pkg['resources'] if (r.get('name') or '').lower() == 'planc2193.zip']
    z = download(res[0]['url'], os.path.join(TMP, 'planc2193.zip'))
    shp_to_geojson(z, '1=1', os.path.join('representatives', 'us_house_2021.geojson'), spat=FRAME)


def layer(svc, i, name, **kw):
    try:
        return arcgis(f'{AGO}{svc}/FeatureServer/{i}', os.path.join('city', name), **kw)
    except Exception as e:
        print('  FAILED', svc, e)


def city():
    for svc, i, name in [('Libraries', 0, 'libraries.geojson'), ('Recreation_Centers', 0, 'rec_centers.geojson'),
                         ('Dallas_Parks_Source_File', 0, 'parks.geojson'), ('Community_Pool_2023', 0, 'pools.geojson'),
                         ('Spray_Ground_2023', 0, 'spray.geojson'), ('Dog_Parks', 0, 'dog_parks.geojson'), ('Hospitals', 0, 'hospitals.geojson'),
                         ('Dallas_Landmark_Historic_Districts', 0, 'historic_districts.geojson'), ('NEW_DAY_OF_SERVICE_', 0, 'days_of_service.geojson'),
                         ('City_of_Dallas_School_Districts_2022', 0, 'school_districts.geojson'), ('Dallas_Bike_Facilities_view', 0, 'bike_facilities.geojson'),
                         ('Dallas_Trails_Source_File', 0, 'trails.geojson'), ('HistoricZoningPolys', 0, 'historic_zoning.geojson'),
                         ('Indoor_Pool_2023', 0, 'indoor_pools.geojson')]:
        layer(svc, i, name)
    # The CRM hosted layers: days of service and brush routes, by layer name.
    meta = json.loads(get(AGO + 'CRMHostedLayers/FeatureServer?f=json'))
    for l in meta['layers']:
        if l['name'] in ('Days Of Service', 'Brush Routes', 'Tennis Center', 'Cultural POI'):
            layer('CRMHostedLayers', l['id'], 'crm_' + l['name'].lower().replace(' ', '_') + '.geojson')
    b = get('https://www.dallasopendata.com/resource/adn6-n59j.json?$limit=5000')
    open(os.path.join(RAW, 'city', 'historical_markers.json'), 'wb').write(b); print('  historical markers', len(json.loads(b)))


def disd():
    for name, url in [('trustees_2021.geojson', 'https://services.arcgis.com/RfrtTbYxQ8YIhjWT/arcgis/rest/services/DISD_Trustee_SMD_Adopted_Dec_16_2021/FeatureServer/0')]:
        arcgis(url, os.path.join('disd', name))


def institutions():
    for year in (2025, 2024, 2023):
        try:
            z = get(f'https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip', tries=1)
            if z[:2] == b'PK': break
        except Exception: pass
    else:
        raise RuntimeError('no IPEDS HD file')
    zf = zipfile.ZipFile(io.BytesIO(z))
    n = [x for x in zf.namelist() if x.lower().endswith('.csv')][0]
    rows = [r for r in csv.DictReader(io.TextIOWrapper(zf.open(n), encoding='utf-8-sig', errors='replace')) if r.get('STABBR') == 'TX']
    with open(os.path.join(RAW, 'institutions', 'ipeds_hd.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print('  IPEDS', year, len(rows), 'in Texas')
    raw = get('https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0/download?format=csv')
    hosp = [r for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))) if r.get('State') == 'TX' and r.get('County/Parish', '').upper() in ('DALLAS', 'COLLIN', 'DENTON')]
    with open(os.path.join(RAW, 'institutions', 'cms_hospitals.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(hosp[0].keys())); w.writeheader(); w.writerows(hosp)
    print('  CMS hospitals', len(hosp))
    geo = {}
    for r in hosp:
        addr = f"{r['Address']}, {r['City/Town']}, TX {r['ZIP Code']}"
        try:
            m = json.loads(get('https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?' + urllib.parse.urlencode(
                {'address': addr, 'benchmark': 'Public_AR_Current', 'format': 'json'})))['result']['addressMatches']
        except Exception: m = []
        geo[r['Facility ID']] = {'address': addr, 'at': [round(m[0]['coordinates']['x'], 5), round(m[0]['coordinates']['y'], 5)] if m else None}
        time.sleep(0.4)
    json.dump(geo, open(os.path.join(RAW, 'institutions', 'cms_geocoded.json'), 'w'), indent=1)
    print('  geocoded', sum(1 for g in geo.values() if g['at']), 'of', len(geo))
    b = lambda bb: f'({bb[1]},{bb[0]},{bb[3]},{bb[2]})'
    overpass(f'[out:json][timeout:240];nwr["amenity"~"^(university|college|hospital)$"]{b(CITY)};out tags center;', os.path.join('institutions', 'osm.json'))


def osm():
    b = lambda bb: f'({bb[1]},{bb[0]},{bb[3]},{bb[2]})'
    names = sorted({l['osm'] for l in LANDMARKS})
    rx = '|'.join(n.replace('(', '\\\\(').replace(')', '\\\\)').replace('.', '\\\\.') for n in names)
    overpass(f'[out:json][timeout:300];nwr["name"~"^({rx})$"]{b(REGION)};out tags center;', 'osm_landmarks.json')
    overpass(f'[out:json][timeout:300];(nwr["leisure"="playground"]{b(CITY)};nwr["leisure"="pitch"]["sport"="tennis"]{b(CITY)};'
             f'nwr["leisure"="park"]["name"]{b(CITY)};nwr["leisure"="dog_park"]{b(CITY)};);out tags center;', 'osm_nearby.json')


if __name__ == '__main__':
    for label, fn in [('reps', reps), ('city', city), ('disd', disd), ('institutions', institutions), ('osm', osm)]:
        print('==', label); step(label, fn)
    print('FAILED:', FAILED or 'none')
