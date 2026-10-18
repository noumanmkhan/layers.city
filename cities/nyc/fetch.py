"""Fetch New York City's raw inputs into cities/nyc/raw/. Runs in GitHub Actions (.github/workflows/fetch-nyc.yml);
the sandbox can't reach these hosts. Each step logs its own failure and the rest carry on. Needs gdal-bin.
Dataset ids were checked by scouting/nyc/scout.py (October 18, 2026).

- NYC Open Data (Department of City Planning, quarterly): boroughs, community districts, 2020 NTAs, City Council,
  State Assembly and Senate, congressional and school districts; LPC historic districts; SBS business improvement districts
- U.S. Census Bureau 2024 cartographic boundaries: states, counties and county subdivisions (towns, cities, villages,
  townships) in New York, New Jersey, Connecticut and Pennsylvania, for the regional view
- MTA GTFS: the subway (with the Staten Island Railway), the Long Island Rail Road and Metro-North
- OpenStreetMap via Overpass (ODbL): place names, main streets in the city, highways across the region, NJ Transit
  and PATH rail, and the landmarks list (names.py)
"""
import csv, io, json, os, sys, time, zipfile
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import *
from names import LANDMARKS

SOC = 'https://data.cityofnewyork.us'
CB = 'https://www2.census.gov/geo/tiger/GENZ2024/shp/'
DCP = [('boroughs', 'gthc-hcne'), ('community_districts', '5crt-au7u'), ('ntas', '9nt8-h7nd'), ('council', '872g-cjhh'),
       ('assembly', '5yfv-9hkp'), ('senate', 'afns-vxeu'), ('congress', 'j3u5-usz2'), ('school_districts', '8ugf-3d8u'),
       ('historic_districts', 'skyk-mpzq'), ('bids', '7jdm-inj8')]

def socrata(only=None):
    """Each dataset as GeoJSON: the resource API first, the geospatial export for map-type datasets."""
    for name, i in DCP:
        if only and name not in only: continue
        for url in [f'{SOC}/resource/{i}.geojson?$limit=50000', f'{SOC}/api/geospatial/{i}?method=export&format=GeoJSON']:
            try:
                d = json.loads(get(url, tries=2))
                # Map-type datasets answer the resource API with empty features: take the export instead.
                if d.get('features') and d['features'][0].get('geometry') and d['features'][0].get('properties'):
                    save(name + '.geojson', d)
                    print(' ', name, len(d['features']), 'features ·', sorted(d['features'][0]['properties'])[:20])
                    break
            except Exception as e:
                print('  ', name, url, e)
        else:
            FAILED.append(name)
        time.sleep(2)

def census():
    z = download(CB + 'cb_2024_us_state_500k.zip', os.path.join(TMP, 'state.zip'))
    shp_to_geojson(z, "STUSPS IN ('NY','NJ','CT','PA','MA','RI','VT','DE')", 'states.geojson', spat=FRAME)
    z = download(CB + 'cb_2024_us_county_500k.zip', os.path.join(TMP, 'county.zip'))
    shp_to_geojson(z, "STATEFP IN ('36','34','09','42')", 'counties.geojson', spat=FRAME)
    feats = []
    for st in ('36', '34', '09'):
        z = download(CB + f'cb_2024_{st}_cousub_500k.zip', os.path.join(TMP, f'cousub{st}.zip'))
        shp_to_geojson(z, '1=1', f'cousub_{st}.geojson', spat=REGION)
        feats += json.load(open(os.path.join(RAW, f'cousub_{st}.geojson')))['features']
        os.remove(os.path.join(RAW, f'cousub_{st}.geojson'))
    save('cousubs.geojson', {'type': 'FeatureCollection', 'features': feats})
    print('  county subdivisions', len(feats), Counter(f['properties'].get('LSAD') for f in feats).most_common())

def mta():
    """Subway (and SIR), LIRR and Metro-North: each route's shapes with trip counts, and every station with its routes."""
    out = {}
    for key, url in [('subway', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip'),
                     ('lirr', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfslirr.zip'),
                     ('mnr', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfsmnr.zip')]:
        z = zipfile.ZipFile(io.BytesIO(get(url, tries=3)))
        rd = lambda n: list(csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig')))
        routes = {r['route_id']: r for r in rd('routes.txt')}
        trips = rd('trips.txt')
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
        print(' ', key, len(routes), 'routes ·', len(stations), 'stations ·', len(shapes), 'shapes')
    save('mta_rail.json', out)

b = lambda bb: f'({bb[1]},{bb[0]},{bb[3]},{bb[2]})'

def osm():
    overpass(f'[out:json][timeout:300];(node["place"~"^(neighbourhood|suburb|quarter|island)$"]{b(CITY)};'
             f'way["place"~"^(neighbourhood|suburb|quarter|island)$"]{b(CITY)};);out tags center;', 'osm_places.json')
    overpass(f'[out:json][timeout:300];way["highway"~"^(trunk|primary|secondary)$"]["name"]{b(CITY)};out tags geom;', 'osm_streets.json')
    overpass(f'[out:json][timeout:600];way["highway"~"^(motorway|trunk)$"]{b(REGION)};out tags geom;', 'osm_highways.json')
    rail()
    stations()
    landmarks()

def rail():
    """NJ Transit rail and light rail, PATH, and the AirTrains: route relations with their members' geometry (out geom)."""
    overpass(f'[out:json][timeout:600];(relation["route"~"^(train|subway|light_rail|monorail)$"]["network"~"NJ Transit|PATH|AirTrain|NJT|Light Rail",i]{b(REGION)};'
             f'relation["route"~"^(train|subway|light_rail|monorail)$"]["operator"~"NJ Transit|Port Authority|PATH",i]{b(REGION)};);out geom;',
             'osm_rail.json')

def stations():
    overpass(f'[out:json][timeout:300];node["railway"~"^(station|halt)$"]{b(REGION)};out;', 'osm_stations.json')

def landmarks():
    names = sorted({l['osm'] for l in LANDMARKS})
    rx = '|'.join(n.replace('(', '\\\\(').replace(')', '\\\\)').replace('.', '\\\\.') for n in names)
    overpass(f'[out:json][timeout:300];nwr["name"~"^({rx})$"]{b(REGION)};out tags center;', 'osm_landmarks.json')

if __name__ == '__main__':
    want = [a for a in sys.argv[1:] if not a.startswith('--')]
    for label, fn in [('socrata', socrata), ('census', census), ('mta', mta), ('osm', osm)]:
        if want and label not in want: continue
        print('==', label); step(label, fn)
    print('FAILED:', FAILED or 'none')
