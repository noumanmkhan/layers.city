"""Fetch the inputs for New York's Parking & Charging layers into raw/parking/. Run from GitHub Actions (Fetch New York
City data, fetch-nyc.yml, which runs a pushed fetch script; monthly with fetch-nyc-parking.yml); the sandbox can't reach
these hosts. Each source is written only when it comes back whole, so a failed source keeps its last copy.

- municipal.json: NYC DOT's municipal garages and fields (the hand-kept list in cities/nyc/parking.json), each placed:
  an address through NYC Planning's GeoSearch; a block face (on/from/to) as the middle of its two OpenStreetMap
  intersections; a corner (on/at) as that intersection; a name (osm) as an OpenStreetMap car park of that name; or the
  position given (xy). near picks the closest match where names repeat across boroughs. shift nudges a point (two
  facilities at one address). The log says how each was placed.
- ev_afdc.json: public and private EV charging stations in a box around the city from the Alternative Fuels Data
  Center station API (U.S. Department of Energy). The API moved from developer.nrel.gov to developer.nlr.gov; both are
  tried. NLR_API_KEY (a repository secret) is used if set, else the shared DEMO_KEY."""
import json, math, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'parking')
os.makedirs(OUT, exist_ok=True)
BOX = (40.47, -74.27, 40.93, -73.68)   # south, west, north, east: the five boroughs plus a margin
UA = {'User-Agent': 'city-layers-pipeline (layers.city; go@layers.city)'}
OVERPASS = ('https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter', 'https://overpass.private.coffee/api/interpreter')
ok = []


def get(url, data=None, timeout=180, tries=4):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            print('  retry', attempt + 1, url[:100], str(e)[:120], flush=True)
            time.sleep(10 * (attempt + 1))
    return None


def overpass(q):
    body = urllib.parse.urlencode({'data': '[out:json][timeout:120];' + q}).encode()
    for attempt in range(6):
        d = get(OVERPASS[attempt % 3], body, timeout=150, tries=1)
        if d is not None: return d.get('elements', [])
        time.sleep(10)
    return None


def save(name, obj):
    json.dump(obj, open(os.path.join(OUT, name), 'w'), ensure_ascii=False, separators=(',', ':'), indent=None)
    ok.append(name)


dist = lambda a, b: math.hypot((a[0] - b[0]) * 84.4, (a[1] - b[1]) * 111.2)
bbox = f'{BOX[0]},{BOX[1]},{BOX[2]},{BOX[3]}'


def corner(a, b, near):
    """The OpenStreetMap node where streets named a and b meet, nearest to near."""
    els = overpass(f'way["name"="{a}"]({bbox})->.a;way["name"="{b}"]({bbox})->.b;node(w.a)(w.b);out;')
    pts = [(e['lon'], e['lat']) for e in (els or [])]
    return min(pts, key=lambda p: dist(p, near)) if pts else None


def geosearch(q, near):
    d = get('https://geosearch.planninglabs.nyc/v2/search?' + urllib.parse.urlencode({'text': q, 'size': 3}), tries=3)
    pts = [f['geometry']['coordinates'] for f in (d or {}).get('features', [])]
    return (pts[0], (d['features'][0]['properties'].get('label') or '')) if pts else (None, '')


# ---- NYC DOT municipal garages and fields
cfg = json.load(open(os.path.join(HERE, 'parking.json')))
CENTRE = (-73.94, 40.70)
placed, missing = [], []
for f in cfg['facilities']:
    near = f.get('near') or CENTRE
    at, how = None, ''
    if f.get('xy'):
        at, how = f['xy'], 'given position'
    elif f.get('q'):
        at, label = geosearch(f['q'], near)
        how = 'GeoSearch: ' + label
    elif f.get('on') and f.get('from'):
        a, b = corner(f['on'], f['from'], near), corner(f['on'], f['to'], near)
        if a and b and dist(a, b) < 3: at, how = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], f"middle of {f['on']} from {f['from']} to {f['to']}"
        time.sleep(2)
    elif f.get('on') and f.get('at'):
        at = corner(f['on'], f['at'], near); how = f"corner of {f['on']} and {f['at']}"
        time.sleep(2)
    elif f.get('osm'):
        els = overpass(f'nwr["amenity"="parking"]["name"~"{f["osm"]}",i]({bbox});out center;') or []
        pts = [(e.get('lon') or e['center']['lon'], e.get('lat') or e['center']['lat']) for e in els if e.get('lon') or e.get('center')]
        if pts: at = min(pts, key=lambda p: dist(p, near)); how = 'OpenStreetMap car park named like ' + f['osm']
    if at and f.get('near') and dist(at, f['near']) > 2.5:
        print(f"  {f['name']}: placed {dist(at, f['near']):.1f} km from its rough position, kept the rough position"); at, how = f['near'], 'rough position'
    if at and f.get('shift'): at = [at[0] + f['shift'][0], at[1] + f['shift'][1]]
    if not at: missing.append(f['name']); continue
    placed.append(dict(f, xy=[round(at[0], 5), round(at[1], 5)], how=how))
    print(f"  {f['name']}: {how}", flush=True)
if placed:
    save('municipal.json', {'source': cfg['source'], 'asof': cfg['asof'], 'facilities': placed, 'missing': missing})
print('Municipal:', len(placed), 'placed;', 'not placed:', missing or 'none')

# ---- EV chargers: AFDC station API
key = os.environ.get('NLR_API_KEY') or 'DEMO_KEY'
qs = urllib.parse.urlencode({'api_key': key, 'fuel_type': 'ELEC', 'country': 'US', 'state': 'NY,NJ', 'status': 'all', 'access': 'all', 'limit': 'all'})
KEEP = ('id', 'station_name', 'street_address', 'city', 'latitude', 'longitude', 'access_code', 'restricted_access', 'status_code',
        'access_days_time', 'ev_level1_evse_num', 'ev_level2_evse_num', 'ev_dc_fast_num', 'ev_connector_types', 'ev_network',
        'ev_pricing', 'ev_charging_units', 'facility_type', 'date_last_confirmed', 'open_date', 'updated_at', 'groups_with_access_code')


def slim(s):
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
                              'states': ev.get('total_results'), 'fuel_stations': st})
        print('AFDC EV stations:', len(st), 'in the box, of', ev.get('total_results'), 'in New York and New Jersey')
        break

print('Saved:', ', '.join(ok) or 'nothing')
if not ok: raise SystemExit('no source answered')
