"""Fetch Dallas's raw inputs into cities/dallas/raw/. Runs in GitHub Actions (.github/workflows/fetch-dallas.yml);
the sandbox can't reach these hosts. Each step logs its own failure and the rest carry on. Needs gdal-bin.

- U.S. Census Bureau 2024 cartographic boundaries: Texas places (cities, towns, CDPs) and counties
- U.S. Census Bureau TIGERweb hydrography: the lakes (Ray Hubbard, Lewisville, Grapevine, Joe Pool, White Rock…)
- Texas Legislative Council (Capitol Data Portal): State House PLANH2316, State Senate PLANS2168, U.S. House PLANC2333
- City of Dallas GIS: the 14 City Council districts (adopted June 27, 2022)
- City of Fort Worth GIS: its 10 City Council districts (2–11)
- OpenStreetMap via Overpass (ODbL): place names, main streets in Dallas, highways across the region, DART and
  regional rail lines and stations
"""
import json, os, re, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import *

CB = 'https://www2.census.gov/geo/tiger/GENZ2024/shp/'


def census():
    z = download(CB + 'cb_2024_48_place_500k.zip', os.path.join(TMP, 'place.zip'))
    shp_to_geojson(z, '1=1', 'places.geojson', spat=FRAME)
    z = download(CB + 'cb_2024_us_county_500k.zip', os.path.join(TMP, 'county.zip'))
    shp_to_geojson(z, "STATEFP = '48'", 'counties.geojson', spat=FRAME)
    z = download(CB + 'cb_2024_us_state_500k.zip', os.path.join(TMP, 'state.zip'))
    shp_to_geojson(z, "STUSPS IN ('TX','OK')", 'states.geojson', spat=FRAME)


def lakes():
    svc = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Hydro/MapServer'
    layers = json.loads(get(svc + '?f=json'))['layers']
    area = next(l for l in layers if 'area' in l['name'].lower())
    feats, off = [], 0
    while True:
        q = {'where': 'AREAWATER > 400000', 'outFields': 'NAME,MTFCC,AREAWATER', 'outSR': 4326, 'f': 'geojson',
             'geometryPrecision': 5, 'maxAllowableOffset': 0.00004, 'geometry': ','.join(map(str, FRAME)),
             'geometryType': 'esriGeometryEnvelope', 'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects',
             'resultOffset': off, 'resultRecordCount': 200}
        d = json.loads(get(f"{svc}/{area['id']}/query?" + urllib.parse.urlencode(q)))
        feats += d.get('features', [])
        if len(d.get('features', [])) < 200: break
        off += 200
    save('lakes.geojson', {'type': 'FeatureCollection', 'features': feats})
    big = sorted(feats, key=lambda f: -f['properties']['AREAWATER'])[:25]
    print('  largest:', [(f['properties']['NAME'], f['properties']['AREAWATER'] // 1_000_000) for f in big])


def plans():
    for plan, out in [('planh2316', 'tx_house.geojson'), ('plans2168', 'tx_senate.geojson'), ('planc2333', 'us_house.geojson')]:
        pkg = json.loads(get('https://data.capitol.texas.gov/api/3/action/package_show?id=' + plan))['result']
        print(' ', plan, pkg.get('title'), [(r.get('name'), r.get('format')) for r in pkg['resources']][:12])
        res = [r for r in pkg['resources'] if r['url'].lower().endswith('.zip') and '_blk' not in r['url'].lower()]
        if not res: raise RuntimeError('no shapefile for ' + plan)
        z = download(res[0]['url'], os.path.join(TMP, plan + '.zip'))
        shp_to_geojson(z, '1=1', out, spat=FRAME)


def councils():
    for url in ['https://egis.dallascityhall.com/arcgis/rest/services/Basemap/CouncilAreas/MapServer/0',
                'https://services2.arcgis.com/rwnOSbfKSwyTBcwN/ArcGIS/rest/services/CouncilBoundaries/FeatureServer/0']:
        try:
            if len(arcgis(url, 'dallas_council.geojson')) >= 14: break
        except Exception as e:
            print('  council source failed', url, e)
    arcgis('https://mapit.fortworthtexas.gov/ags/rest/services/CIVIC/OpenData_Boundaries/MapServer/2', 'fortworth_council.geojson')


def osm():
    b = lambda bb: f'({bb[1]},{bb[0]},{bb[3]},{bb[2]})'
    overpass(f'[out:json][timeout:300];(node["place"~"^(neighbourhood|suburb|quarter|village|hamlet|town)$"]{b(REGION)};'
             f'way["place"~"^(neighbourhood|suburb|quarter)$"]{b(REGION)};relation["place"~"^(neighbourhood|suburb|quarter)$"]{b(REGION)};);out tags center;',
             'osm_places.json')
    overpass(f'[out:json][timeout:300];way["highway"~"^(trunk|primary|secondary|tertiary)$"]["name"]{b(CITY)};out tags geom;', 'osm_streets.json')
    overpass(f'[out:json][timeout:400];way["highway"~"^(motorway|trunk)$"]{b(REGION)};out tags geom;', 'osm_highways.json')
    overpass(f'[out:json][timeout:400];(relation["route"~"^(light_rail|train|tram)$"]{b(REGION)};);out tags geom;', 'osm_rail.json')
    overpass(f'[out:json][timeout:300];(node["railway"~"^(station|halt|tram_stop)$"]{b(REGION)};node["public_transport"="station"]{b(REGION)};);out tags;',
             'osm_stations.json')


def scout_voting():
    """List what the counties publish for the November 3, 2026 election (scouting; read the log)."""
    for q in ['Dallas County vote center', 'Dallas County Election Day vote centers', 'Tarrant County vote center',
              'Collin County vote center', 'Denton County polling locations', 'Denton County voter precincts']:
        try:
            d = json.loads(get('https://www.arcgis.com/sharing/rest/search?' + urllib.parse.urlencode(
                {'q': q, 'f': 'json', 'num': 15, 'sortField': 'modified', 'sortOrder': 'desc'})))
            print('ARCGIS', q)
            for r in d.get('results', []):
                print('   ', r.get('type'), '|', r.get('title'), '|', r.get('owner'), '|', r.get('url') or '', '|', r.get('id'))
        except Exception as e:
            print('  search failed', q, e)
    pages = ['https://www.dallascountyvotes.org/', 'https://www.dallascountyvotes.org/voters/election/',
             'https://www.dallascounty.org/government/elections/', 'https://www.tarrantcountytx.gov/en/elections.html',
             'https://www.tarrantcountytx.gov/en/elections/voting-locations.html',
             'https://www.collincountytx.gov/Elections', 'https://www.collincountytx.gov/Elections/Election-Information',
             'https://www.votedenton.gov/', 'https://www.votedenton.gov/election-day-voting-locations/']
    for u in pages:
        try:
            html = get(u, tries=2).decode('utf-8', 'replace')
            links = sorted(set(re.findall(r'href="([^"]+)"', html)))
            keep = [l for l in links if re.search(r'(?i)vote|poll|location|center|precinct|\.pdf|2026|nov', l)]
            print('PAGE', u, len(links), 'links')
            for l in keep[:80]: print('   ', l)
        except Exception as e:
            print('  page failed', u, e)
    for name, url in [('dallas_ed.pdf', 'https://www.dallascounty.org/elections/VoteCenters/Election%20Day%20Vote%20Centers.pdf'),
                      ('dallas_ev.pdf', 'https://www.dallascounty.org/elections/VoteCenters/Early%20Voting%20Vote%20Centers.pdf'),
                      ('tarrant_ev.pdf', 'https://www.tarrantcountytx.gov/content/dam/main/elections/2026/1126/locations/1126_EV_Sched.pdf')]:
        try:
            download(url, os.path.join(RAW, 'voting', name))
        except Exception as e:
            print('  pdf failed', name, e)


os.makedirs(os.path.join(RAW, 'voting'), exist_ok=True)
for label, fn in [('census', census), ('lakes', lakes), ('plans', plans), ('councils', councils), ('osm', osm), ('scout voting', scout_voting)]:
    print('==', label); step(label, fn)
print('FAILED:', FAILED or 'none')
