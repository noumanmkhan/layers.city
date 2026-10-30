"""Fetch San Francisco's raw inputs into cities/sf/raw/. Runs in GitHub Actions (.github/workflows/fetch-sf.yml);
the sandbox can't reach these hosts. Each step logs its own failure and the rest carry on. Needs gdal-bin.
Dataset ids were checked by scouting/sf/scout.py (October 30, 2026).

- DataSF (data.sfgov.org; PDDL / CC0 / public domain): Analysis Neighborhoods (the 41 units), SF Find Neighborhoods (117),
  Supervisor Districts (2022), Historic Districts (Planning), Cultural Districts
- MTC/ABAG open data (bayareametro ArcGIS): the 101 incorporated cities and the 9 counties, clipped to the shoreline
- U.S. Census Bureau 2024 cartographic boundaries: states and counties around the region; California State Senate
  and Assembly districts (2021 Citizens Redistricting Commission lines)
- California Department of Technology GIS: congressional districts enacted by Proposition 50 (AB 604), for the 2026 elections
- GTFS: BART, Caltrain and Muni (no key needed)
- OpenStreetMap via Overpass (ODbL): place names and main streets in the city, highways across the region, SMART, ACE,
  Capitol Corridor and VTA light rail, rail stations, and landmark positions (names.py)
"""
import csv, io, json, os, sys, time, zipfile
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import *
from names import LANDMARKS

SOC = 'https://data.sfgov.org'
CB = 'https://www2.census.gov/geo/tiger/GENZ2024/shp/'
MTC = 'https://services3.arcgis.com/i2dkYWmb4wHvYPda/ArcGIS/rest/services'
DATASF = [('analysis_neighborhoods', 'p5b7-5n3h'), ('sffind', 'pty2-tcw4'), ('supervisors', 'f2zs-jevy'),
          ('historic_districts', '63x5-g3m4'), ('cultural_districts', '5xmc-5bjj')]


def datasf(only=None):
    """Each dataset as GeoJSON: the resource API first, the geospatial export for map-type datasets."""
    for name, i in DATASF:
        if only and name not in only: continue
        for url in [f'{SOC}/resource/{i}.geojson?$limit=50000', f'{SOC}/api/geospatial/{i}?method=export&format=GeoJSON']:
            try:
                d = json.loads(get(url, tries=2))
                if d.get('features') and d['features'][0].get('geometry') and d['features'][0].get('properties'):
                    save(name + '.geojson', d)
                    print(' ', name, len(d['features']), 'features ·', sorted(d['features'][0]['properties'])[:20])
                    break
            except Exception as e:
                print('  ', name, url, e)
        else:
            FAILED.append(name)
        time.sleep(2)


def region():
    arcgis(f'{MTC}/region_incorporatedplace_clp/FeatureServer/0', 'cities.geojson')
    arcgis(f'{MTC}/region_county_clp/FeatureServer/0', 'bay_counties.geojson')


def census():
    z = download(CB + 'cb_2024_us_state_500k.zip', os.path.join(TMP, 'state.zip'))
    shp_to_geojson(z, "STUSPS IN ('CA','NV','OR')", 'states.geojson', spat=FRAME)
    z = download(CB + 'cb_2024_us_county_500k.zip', os.path.join(TMP, 'county.zip'))
    shp_to_geojson(z, "STATEFP = '06'", 'counties.geojson', spat=FRAME)
    for kind, out in [('sldu', 'senate.geojson'), ('sldl', 'assembly.geojson')]:
        z = download(CB + f'cb_2024_06_{kind}_500k.zip', os.path.join(TMP, kind + '.zip'))
        shp_to_geojson(z, '1=1', out, spat=CITY)


def congress():
    """AB 604 (Proposition 50) districts, from the State's GIS service; the Statewide Database zip as a fallback."""
    try:
        arcgis('https://services3.arcgis.com/uknczv4rpevve42E/arcgis/rest/services/'
               'AB_604_-_California_Congressional_Districts_2027-2032_as_enacted_by_Proposition_50_view/FeatureServer/0', 'congress.geojson')
    except Exception as e:
        print('  state service failed, trying the Statewide Database zip', e)
        z = download('https://statewidedatabase.org/pub/data/d25/AB604%202025-08-16.zip', os.path.join(TMP, 'ab604.zip'))
        shp_to_geojson(z, '1=1', 'congress.geojson')


def gtfs():
    """BART, Caltrain and Muni: each route's shapes with trip counts, and every station or stop with its routes
    (Muni: rail, streetcar and cable car only; its buses come with the bus layer later)."""
    out = {}
    for key, url, types in [('bart', 'https://www.bart.gov/dev/schedules/google_transit.zip', None),
                            ('caltrain', 'https://data.trilliumtransit.com/gtfs/caltrain-ca-us/caltrain-ca-us.zip', None),
                            ('muni', 'https://muni-gtfs.apps.sfmta.com/data/muni_gtfs-current.zip', {'0', '5', '7', '900'})]:
        z = zipfile.ZipFile(io.BytesIO(get(url, tries=3)))
        rd = lambda n: list(csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig')))
        routes = {r['route_id']: r for r in rd('routes.txt') if types is None or r['route_type'] in types}
        trips = [t for t in rd('trips.txt') if t['route_id'] in routes]
        shape_n = Counter((t['route_id'], t['shape_id']) for t in trips if t.get('shape_id'))
        want = {s for _, s in shape_n}
        shapes = defaultdict(list)
        for p in rd('shapes.txt'):
            if p['shape_id'] in want:
                shapes[p['shape_id']].append((int(p['shape_pt_sequence']), round(float(p['shape_pt_lon']), 6), round(float(p['shape_pt_lat']), 6)))
        trip_route = {t['trip_id']: t['route_id'] for t in trips}
        stop_routes = defaultdict(set)
        for st in rd('stop_times.txt'):
            r = trip_route.get(st['trip_id'])
            if r: stop_routes[st['stop_id']].add(r)
        stops = {s['stop_id']: s for s in rd('stops.txt')}
        stations = {}
        for sid, rs in stop_routes.items():
            s = stops[sid]; k = s.get('parent_station') or sid
            p = stops.get(k, s)
            st = stations.setdefault(k, {'id': k, 'name': p['stop_name'], 'lon': float(p['stop_lon']), 'lat': float(p['stop_lat']), 'routes': set()})
            st['routes'] |= rs
        out[key] = {'feed': rd('feed_info.txt')[:1] if 'feed_info.txt' in z.namelist() else [],
                    'routes': {rid: {'short': r.get('route_short_name') or '', 'long': r.get('route_long_name') or '', 'type': r['route_type'],
                                     'color': r.get('route_color') or '',
                                     'shapes': {sid: [[x, y] for _, x, y in sorted(shapes[sid])] for (ri, sid) in shape_n if ri == rid},
                                     'counts': {sid: c for (ri, sid), c in shape_n.items() if ri == rid}} for rid, r in routes.items()},
                    'stations': [dict(s, routes=sorted(s['routes'])) for s in stations.values()]}
        print(' ', key, len(routes), 'routes', Counter(r['route_type'] for r in routes.values()), '·', len(stations), 'stations ·', len(shapes), 'shapes ·',
              [(r.get('route_short_name'), r.get('route_long_name')) for r in list(routes.values())[:20]])
    save('gtfs_rail.json', out)


b = lambda bb: f'({bb[1]},{bb[0]},{bb[3]},{bb[2]})'


def osm():
    overpass(f'[out:json][timeout:300];(node["place"~"^(neighbourhood|suburb|quarter|island)$"]{b(CITY)};'
             f'way["place"~"^(neighbourhood|suburb|quarter|island)$"]{b(CITY)};);out tags center;', 'osm_places.json')
    overpass(f'[out:json][timeout:300];way["highway"~"^(trunk|primary|secondary)$"]["name"]{b(CITY)};out tags geom;', 'osm_streets.json')
    overpass(f'[out:json][timeout:600];way["highway"~"^(motorway|trunk)$"]{b(REGION)};out tags geom;', 'osm_highways.json')
    overpass(f'[out:json][timeout:600];(relation["route"~"^(train|light_rail|tram)$"]["network"~"SMART|ACE|Capitol Corridor|VTA|Amtrak|San Joaquins",i]{b(REGION)};'
             f'relation["route"~"^(train|light_rail)$"]["operator"~"SMART|Sonoma-Marin|Altamont|Capitol Corridor|Santa Clara Valley|Amtrak",i]{b(REGION)};);out geom;',
             'osm_rail.json')
    overpass(f'[out:json][timeout:300];node["railway"~"^(station|halt)$"]{b(REGION)};out;', 'osm_stations.json')
    names = sorted({l['osm'] for l in LANDMARKS})
    rx = '|'.join(n.replace('(', '\\\\(').replace(')', '\\\\)').replace('.', '\\\\.') for n in names)
    overpass(f'[out:json][timeout:300];nwr["name"~"^({rx})$"]{b(REGION)};out tags center;', 'osm_landmarks.json')


if __name__ == '__main__':
    want = [a for a in sys.argv[1:] if not a.startswith('--')]
    for label, fn in [('datasf', datasf), ('region', region), ('census', census), ('congress', congress), ('gtfs', gtfs), ('osm', osm)]:
        if want and label not in want: continue
        print('==', label); step(label, fn)
    print('FAILED:', FAILED or 'none')
