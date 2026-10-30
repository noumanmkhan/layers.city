"""Fetch the inputs for San Francisco's Parking & Charging layers into raw/parking/. Runs in GitHub Actions
(fetch-sf.yml, which runs a pushed fetch script); the sandbox can't reach these hosts. Each source is written only when
it comes back whole, so a failed source keeps its last copy.

- garages.json: SFMTA-managed off-street parking (DataSF vqzx-t7c4): the City's garages and lots (SFMTA, Port,
  Rec & Park, Caltrans), with capacity and entrance position.
- rpp_areas.geojson: Residential Parking Permit areas, dissolved here from SFMTA's eligibility parcels (DataSF
  i886-hxz9, about 83,000 lots, each with its area letter in rppeligib): the lots of one letter joined into one shape,
  simplified. The parcels themselves aren't kept (too big for the repo).
- ev_afdc.json: EV charging stations within 9 miles of the city's middle from the Alternative Fuels Data Center's
  nearest-stations API (U.S. Department of Energy), public and private (parking.py keeps the public ones). NLR_API_KEY
  (a repository secret) is used if set, else the shared DEMO_KEY."""
import json, os, sys, time, urllib.parse
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, save, step, RAW, FAILED

SOC = 'https://data.sfgov.org'
P = 'parking'
os.makedirs(os.path.join(RAW, P), exist_ok=True)


def garages():
    rows = json.loads(get(f'{SOC}/resource/vqzx-t7c4.json?$limit=5000', tries=3))
    # The shape is the facility's point: kept as xy for the lots with no entrance position.
    rows = [dict({k: v for k, v in r.items() if k != 'shape' and not k.startswith(':@')},
                 **({'xy': r['shape']['coordinates']} if isinstance(r.get('shape'), dict) and r['shape'].get('type') == 'Point' else {})) for r in rows]
    if not rows: raise RuntimeError('no rows')
    save(os.path.join(P, 'garages.json'), {'fetched': time.strftime('%Y-%m-%d'), 'rows': rows})
    print('  garages', len(rows), Counter(r.get('owner') for r in rows), Counter(r.get('facility_type') for r in rows))


def rpp():
    feats, off = [], 0
    while True:
        q = urllib.parse.urlencode({'$select': 'rppeligib,shape', '$where': 'rppeligib IS NOT NULL', '$limit': 20000, '$offset': off, '$order': ':id'})
        d = json.loads(get(f'{SOC}/resource/i886-hxz9.geojson?' + q, tries=3))
        feats += d['features']; off += len(d['features'])
        print('  parcels so far', len(feats), flush=True)
        if len(d['features']) < 20000: break
    by = defaultdict(list)
    vals = Counter()
    for f in feats:
        v = (f['properties'].get('rppeligib') or '').strip().upper()
        vals[v] += 1
        if 1 <= len(v) <= 2 and v.isalpha() and f.get('geometry'):   # A to Z, then AA to EE and HV (Hayes Valley)
            try: by[v].append(shape(f['geometry']).buffer(0))
            except Exception: pass
    print('  values', dict(vals.most_common(40)))
    rnd = lambda o: [rnd(x) for x in o] if isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]
    out = []
    for v, gs in sorted(by.items()):
        # Lots of one area, with the streets between them: grow 12 m, join, shrink back; drop slivers.
        g = unary_union([x.buffer(0.00013) for x in gs]).buffer(-0.0001).simplify(0.00004, preserve_topology=True)
        if g.geom_type == 'MultiPolygon':
            from shapely.geometry import MultiPolygon
            g = MultiPolygon([p for p in g.geoms if p.area > 2e-7]) if any(p.area > 2e-7 for p in g.geoms) else g
        m = mapping(g)
        out.append({'type': 'Feature', 'properties': {'name': v, 'lots': len(gs)}, 'geometry': {'type': m['type'], 'coordinates': rnd(m['coordinates'])}})
    save(os.path.join(P, 'rpp_areas.geojson'), {'type': 'FeatureCollection', 'fetched': time.strftime('%Y-%m-%d'), 'features': out})
    print('  areas', len(out), [(f['properties']['name'], f['properties']['lots']) for f in out])


KEEP = ('id', 'station_name', 'street_address', 'city', 'latitude', 'longitude', 'access_code', 'restricted_access', 'status_code',
        'access_days_time', 'ev_level1_evse_num', 'ev_level2_evse_num', 'ev_dc_fast_num', 'ev_connector_types', 'ev_network',
        'ev_pricing', 'ev_charging_units', 'facility_type', 'date_last_confirmed', 'open_date', 'updated_at', 'groups_with_access_code')


def slim(s):
    s['ev_charging_units'] = [{'charging_level': u.get('charging_level'), 'port_count': u.get('port_count'),
                               'connectors': {k: c for k, c in (u.get('connectors') or {}).items() if c.get('port_count')}}
                              for u in (s.get('ev_charging_units') or [])]
    return s


def ev():
    key = os.environ.get('NLR_API_KEY') or 'DEMO_KEY'
    qs = urllib.parse.urlencode({'api_key': key, 'fuel_type': 'ELEC', 'latitude': 37.7585, 'longitude': -122.4445, 'radius': 9,
                                 'status': 'all', 'access': 'all', 'limit': 'all'})
    for host in ('developer.nlr.gov', 'developer.nrel.gov'):
        try:
            d = json.loads(get(f'https://{host}/api/alt-fuel-stations/v1/nearest.json?{qs}', tries=2, timeout=300))
        except Exception as e:
            print('  ', host, e); continue
        if isinstance(d.get('fuel_stations'), list) and d['fuel_stations']:
            st = [slim({k: s.get(k) for k in KEEP}) for s in d['fuel_stations'] if s.get('longitude')]
            save(os.path.join(P, 'ev_afdc.json'), {'source': f'Alternative Fuels Data Center station API ({host})', 'fetched': time.strftime('%Y-%m-%d'),
                                                   'total': d.get('total_results'), 'fuel_stations': st})
            print('  AFDC EV stations:', len(st)); return
    raise RuntimeError('no AFDC answer')


step('garages', garages)
step('rpp', rpp)
step('ev', ev)
print('FAILED:', FAILED or 'none')
if len(FAILED) == 3: raise SystemExit('no source answered')
