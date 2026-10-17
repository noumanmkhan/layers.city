"""Fetch the inputs for the Parking layers into raw/parking/. Run from GitHub Actions (Fetch Toronto parking,
fetch-toronto-parking.yml); the sandbox can't reach these hosts. Each source is written only when it comes
back whole, so a failed source keeps its last copy.

- greenp.json: Green P car parks from the City's open data (CKAN green-p-parking, the 2019 file: the
  newest the City publishes; it is marked "Will not be refreshed"). Only the fields the map uses.
- greenp_osm.json: car parks in OpenStreetMap run by Green P / the Toronto Parking Authority, a rough check on
  how stale the 2019 list is (parking.py logs how many lots it matches; OpenStreetMap lacks too many to prune by it).
- permit_areas.geojson: on-street permit parking areas (CKAN on-street-permit-parking-area-maps), WGS84.
- ev_city.geojson: City-operated EV chargers, on-street and in Green P lots (CKAN
  city-operated-electric-vehicle-charging-station-map), with Level 2 and Level 3 port counts.
- ev_afdc.json: public and private EV charging stations from the Alternative Fuels Data Center station
  API (the same data as Natural Resources Canada's station locator), kept to a box around the city.
  The API moved from developer.nrel.gov to developer.nlr.gov when the lab was renamed; both are tried.
  NLR_API_KEY (a repository secret) is used if set, else the shared DEMO_KEY (enough for one call a month).

Green P's own website has a car park API, but it is not published as open data, so it isn't used."""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('PARKING_OUT') or os.path.join(HERE, 'raw', 'parking')
os.makedirs(OUT, exist_ok=True)
CKAN = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/'
BOX = (43.57, -79.65, 43.87, -79.10)   # south, west, north, east: the City plus a margin
UA = {'User-Agent': 'city-layers-pipeline (layers.city)'}
ok = []


def get(url, data=None, timeout=180, tries=4, raw=False):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=timeout) as r:
                b = r.read()
                return b if raw else json.loads(b)
        except Exception as e:
            print('  retry', attempt + 1, url[:110], str(e)[:120], flush=True)
            time.sleep(15 * (attempt + 1))
    return None


def save(name, obj):
    json.dump(obj, open(os.path.join(OUT, name), 'w'), ensure_ascii=False, separators=(',', ':'))
    ok.append(name)


def resource(package, pick):
    pk = get(CKAN + 'package_show?id=' + package)
    for r in (pk or {}).get('result', {}).get('resources', []):
        if pick(r): return r
    print('  no matching resource in', package)


# ---- Green P (City open data, 2019)
r = resource('green-p-parking', lambda r: (r.get('format') or '').upper() == 'JSON' and '2019' in r.get('name', ''))
d = r and get(r['url'])
if d and d.get('carparks'):
    keep = ('id', 'address', 'lat', 'lng', 'carpark_type', 'capacity', 'max_height', 'is_ttc', 'is_under_construction', 'map_marker_logo')
    save('greenp.json', {'source': 'City of Toronto open data, green-p-parking (' + r['name'] + ')', 'modified': r.get('last_modified') or r.get('created'),
                         'carparks': [{k: c.get(k) for k in keep} for c in d['carparks']]})
    print('Green P:', len(d['carparks']), 'car parks')

# ---- Green P in OpenStreetMap, to check the 2019 list
bb = f'({BOX[0]},{BOX[1]},{BOX[2]},{BOX[3]})'
q = (f'[out:json][timeout:240];(nwr["amenity"="parking"]["operator"~"Green P|Toronto Parking Authority",i]{bb};'
     f'nwr["amenity"="parking"]["brand"~"Green P",i]{bb};nwr["amenity"="parking"]["name"~"Green P",i]{bb};);out tags center;')
for attempt in range(6):
    url = ('https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter', 'https://overpass.private.coffee/api/interpreter')[attempt % 3]
    o = get(url, data=urllib.parse.urlencode({'data': q}).encode(), timeout=300, tries=1)
    if o and o.get('elements') is not None:
        els = []
        for e in o['elements']:
            c = e if e['type'] == 'node' else e.get('center')
            if not c: continue
            t = e.get('tags', {})
            els.append({'osm': e['type'][0] + str(e['id']), 'at': [round(c['lon'], 6), round(c['lat'], 6)],
                        **{k: t[k] for k in ('name', 'ref', 'operator', 'brand', 'capacity', 'parking', 'access', 'fee', 'addr:housenumber', 'addr:street') if k in t}})
        save('greenp_osm.json', {'source': 'OpenStreetMap contributors (ODbL) via Overpass API', 'elements': els})
        print('Green P in OpenStreetMap:', len(els))
        break
    time.sleep(30 * (attempt + 1))

# ---- Permit parking areas
r = resource('on-street-permit-parking-area-maps', lambda r: (r.get('format') or '').upper() == 'GEOJSON' and '4326' in r.get('name', ''))
d = r and get(r['url'])
if d and d.get('features'):
    for f in d['features']:
        f['properties'] = {'name': f['properties'].get('AREA_NAME') or f['properties'].get('AREA_LONG_CODE')}
    d['modified'] = r.get('last_modified') or r.get('created')
    save('permit_areas.geojson', d)
    print('Permit areas:', len(d['features']))

# ---- City-operated EV chargers
r = resource('city-operated-electric-vehicle-charging-station-map', lambda r: (r.get('format') or '').upper() == 'GEOJSON' and '4326' in r.get('name', ''))
d = r and get(r['url'])
if d and d.get('features'):
    d['modified'] = r.get('last_modified') or r.get('created')
    save('ev_city.geojson', d)
    print('City EV chargers:', len(d['features']))

# ---- EV chargers: AFDC station API
key = os.environ.get('NLR_API_KEY') or 'DEMO_KEY'
qs = urllib.parse.urlencode({'api_key': key, 'fuel_type': 'ELEC', 'country': 'CA', 'state': 'ON', 'status': 'all', 'access': 'all', 'limit': 'all'})
KEEP = ('id', 'station_name', 'street_address', 'city', 'latitude', 'longitude', 'access_code', 'restricted_access', 'status_code',
        'access_days_time', 'ev_level1_evse_num', 'ev_level2_evse_num', 'ev_dc_fast_num', 'ev_connector_types', 'ev_network',
        'ev_pricing', 'ev_charging_units', 'facility_type', 'date_last_confirmed', 'open_date', 'updated_at', 'groups_with_access_code')
def slim(s):
    """Charging units keep only the connectors that have ports (the API lists every type, mostly empty)."""
    s['ev_charging_units'] = [{'charging_level': u.get('charging_level'), 'port_count': u.get('port_count'),
                               'connectors': {k: c for k, c in (u.get('connectors') or {}).items() if c.get('port_count')}}
                              for u in (s.get('ev_charging_units') or [])]
    return s


for host in ('developer.nlr.gov', 'developer.nrel.gov'):
    ev = get(f'https://{host}/api/alt-fuel-stations/v1.json?{qs}', timeout=300, tries=2)
    if ev and isinstance(ev.get('fuel_stations'), list) and ev['fuel_stations']:
        st = [slim({k: s.get(k) for k in KEEP}) for s in ev['fuel_stations']
              if s.get('longitude') and BOX[0] <= s['latitude'] <= BOX[2] and BOX[1] <= s['longitude'] <= BOX[3]]
        save('ev_afdc.json', {'source': f'Alternative Fuels Data Center station API ({host})', 'fetched': time.strftime('%Y-%m-%d'),
                              'ontario': ev.get('total_results'), 'fuel_stations': st})
        print('AFDC EV stations:', len(st), 'in the box, of', ev.get('total_results'), 'in Ontario')
        break

print('Saved:', ', '.join(ok) or 'nothing')
if not ok: raise SystemExit('no source answered')
