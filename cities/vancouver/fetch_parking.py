"""Public EV chargers for Vancouver -> raw/parking/ev_afdc.json, for parking.py. Runs in GitHub Actions
(*Fetch Vancouver parking*, monthly, or when this script changes); the sandbox can't reach the API.

Source: the Alternative Fuels Data Center's nearest-stations API (U.S. Department of Energy; the lab's host moved from
developer.nrel.gov to developer.nlr.gov): every electric station, public and private, within 8 miles of the city's
middle (the whole city fits), with the fields parking.py reads. Key: repo secret NLR_API_KEY, else DEMO_KEY.

EV chargers only for now: City-run car parks aren't on this map yet.
"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'parking')
os.makedirs(OUT, exist_ok=True)
KEEP = ('id', 'station_name', 'street_address', 'city', 'latitude', 'longitude', 'access_code', 'restricted_access', 'status_code',
        'access_days_time', 'ev_level1_evse_num', 'ev_level2_evse_num', 'ev_dc_fast_num', 'ev_connector_types', 'ev_network',
        'ev_pricing', 'ev_charging_units', 'facility_type', 'date_last_confirmed', 'open_date', 'updated_at', 'groups_with_access_code')


def slim(s):
    s['ev_charging_units'] = [{'charging_level': u.get('charging_level'), 'port_count': u.get('port_count'),
                               'connectors': {k: c for k, c in (u.get('connectors') or {}).items() if c.get('port_count')}}
                              for u in (s.get('ev_charging_units') or [])]
    return s


key = os.environ.get('NLR_API_KEY') or 'DEMO_KEY'
qs = urllib.parse.urlencode({'api_key': key, 'fuel_type': 'ELEC', 'country': 'CA', 'latitude': 49.255, 'longitude': -123.15, 'radius': 8,
                             'status': 'all', 'access': 'all', 'limit': 'all'})
for host in ('developer.nlr.gov', 'developer.nrel.gov'):
    for attempt in range(3):
        try:
            req = urllib.request.Request(f'https://{host}/api/alt-fuel-stations/v1/nearest.json?{qs}', headers={'User-Agent': 'layers.city data fetch'})
            d = json.load(urllib.request.urlopen(req, timeout=300))
            break
        except Exception as e:
            print(f'  {host} try {attempt + 1}: {e!r}'); d = None; time.sleep(20)
    if d and isinstance(d.get('fuel_stations'), list) and d['fuel_stations']:
        st = [slim({k: s.get(k) for k in KEEP}) for s in d['fuel_stations'] if s.get('longitude')]
        json.dump({'source': f'Alternative Fuels Data Center station API ({host})', 'fetched': time.strftime('%Y-%m-%d'),
                   'total': d.get('total_results'), 'fuel_stations': st}, open(os.path.join(OUT, 'ev_afdc.json'), 'w'), separators=(',', ':'))
        print('AFDC EV stations:', len(st))
        break
else:
    raise SystemExit('no AFDC answer; last month\'s file stays')
