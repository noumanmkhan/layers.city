"""Bike share stations: build docs/<city>/data/bikeshare.geojson from cities/<city>/raw/bikeshare.json
(engine/fetch_bikeshare.py) for the "docks" layer, nested under Bike lanes.

One point per installed station, with:
  n   name, tidied (double spaces closed up; suffixes in bikeshare.json "nameDrop" removed, e.g. " - SMART")
  d   number of docks (the feed's capacity), when given
  e   1 when the station charges e-bikes
  nc  1 when the kiosk takes no credit card (rental_methods lists no "creditcard"); left out when the feed gives no methods
Top level: "asof" (the feed's date at fetch time), "system" (the operator's name), "count", "docks", "charging".
No live counts of bikes or free docks: they change by the minute, and a snapshot would be wrong.

Usage: python3 engine/bikeshare.py <city>
"""
import json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
city = sys.argv[1]
CFG = json.load(open(os.path.join(ROOT, 'cities', city, 'bikeshare.json')))
RAW = os.path.join(ROOT, 'cities', city, 'raw', 'bikeshare.json')
OUT = os.path.join(ROOT, 'docs', city, 'data', 'bikeshare.geojson')
if not os.path.exists(RAW): sys.exit(f'{city}: no bike share stations fetched yet (fetch-bikes.yml)')
R = json.load(open(RAW))
DROP = [re.compile(p, re.I) for p in CFG.get('nameDrop', [])]


def tidy(s):
    s = re.sub(r'\s+', ' ', str(s or '')).strip()
    for p in DROP: s = p.sub('', s).strip()
    s = re.sub(r'\s*/\s*', ' / ', s)
    return s


feats, skipped = [], []
for s in R['stations']:
    if s.get('installed') is False or s.get('is_virtual_station'):
        skipped.append(s.get('name')); continue
    try: lat, lon = float(s['lat']), float(s['lon'])
    except (KeyError, TypeError, ValueError):
        skipped.append(s.get('name')); continue
    if not (-90 < lat < 90 and -180 < lon < 180) or (lat == 0 and lon == 0):
        skipped.append(s.get('name')); continue
    q = {'n': tidy(s.get('name')) or str(s['station_id'])}
    if isinstance(s.get('capacity'), (int, float)) and s['capacity'] > 0: q['d'] = int(s['capacity'])
    if s.get('is_charging_station'): q['e'] = 1
    rm = s.get('rental_methods')
    if rm and 'creditcard' not in [m.lower() for m in rm]: q['nc'] = 1
    feats.append({'type': 'Feature', 'properties': q, 'geometry': {'type': 'Point', 'coordinates': [round(lon, 5), round(lat, 5)]}})

feats.sort(key=lambda f: f['properties']['n'])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
out = {'type': 'FeatureCollection', 'asof': R.get('updated') or R.get('fetched'), 'fetched': R.get('fetched'), 'system': CFG.get('system'),
       'count': len(feats), 'docks': sum(f['properties'].get('d', 0) for f in feats),
       'charging': sum(1 for f in feats if f['properties'].get('e')), 'features': feats}
json.dump(out, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
print(f"{city}: {len(feats)} stations, {out['docks']} docks, {out['charging']} charge e-bikes,",
      sum(1 for f in feats if f['properties'].get('nc')), 'without a card kiosk · asof', out['asof'], f'{os.path.getsize(OUT) // 1024} KB')
if skipped: print('  left out (not installed, virtual or no position):', len(skipped), skipped[:10])
