"""Place each headquarters in cities/sf/tech_hq.json with the US Census Bureau's geocoder (public domain), into
cities/sf/raw/tech_geocoded.json. Runs in GitHub Actions (fetch-sf.yml). One request a second; an address the Census
geocoder can't match is tried once more on OpenStreetMap Nominatim (ODbL), and anything still unmatched is printed."""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, RAW

HERE = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(HERE, 'tech_hq.json')))
out, miss = {}, []
for name, tick, cat, addr, city, year in cfg['companies']:
    one = f'{addr}, {city}, CA'
    hit = None
    try:
        d = json.loads(get('https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?' + urllib.parse.urlencode(
            {'address': one, 'benchmark': 'Public_AR_Current', 'format': 'json'}), tries=3))
        m = d['result']['addressMatches']
        if m: hit = {'at': [round(m[0]['coordinates']['x'], 5), round(m[0]['coordinates']['y'], 5)], 'src': 'census', 'matched': m[0]['matchedAddress']}
    except Exception as e:
        print('  census failed', one, e)
    if not hit:
        time.sleep(1.1)
        try:
            d = json.loads(get('https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode({'q': one, 'format': 'json', 'limit': 1}), tries=2))
            if d: hit = {'at': [round(float(d[0]['lon']), 5), round(float(d[0]['lat']), 5)], 'src': 'osm', 'matched': d[0].get('display_name', '')[:120]}
        except Exception as e:
            print('  nominatim failed', one, e)
    if hit: out[name] = hit; print(f'  {name}: {hit["src"]} {hit["matched"]}')
    else: miss.append(name); print(f'  {name}: NOT PLACED ({one})')
    time.sleep(1.1)
json.dump({'fetched': time.strftime('%Y-%m-%d'), 'places': out, 'missing': miss}, open(os.path.join(RAW, 'tech_geocoded.json'), 'w'), indent=0)
print('placed', len(out), 'of', len(cfg['companies']), '· missing', miss)
