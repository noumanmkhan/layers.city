"""Bike share stations: fetch a city's GBFS station list into cities/<city>/raw/bikeshare.json for engine/bikeshare.py.
Runs in GitHub Actions (fetch-bikes.yml); the sandbox can't reach the feed. The feed is set in cities/<city>/bikeshare.json:
"gbfs" (the system's gbfs.json, which lists its other feeds) and "lang".

Reads station_information (where each station is and what it offers) and, once, station_status, only for whether each
station is installed: a station listed but not installed (planned, or taken out) is dropped by the build. Live bike and
dock counts are not kept. The log counts stations by physical_configuration and payment methods, so a new kind shows up.
Usage: python3 engine/fetch_bikeshare.py <city>
"""
import collections, datetime as dt, json, os, sys, time, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
city = sys.argv[1]
CFG = json.load(open(os.path.join(ROOT, 'cities', city, 'bikeshare.json')))
OUT = os.path.join(ROOT, 'cities', city, 'raw', 'bikeshare.json')
UA = {'User-Agent': 'city-layers-pipeline (layers.city)'}
KEEP = ['station_id', 'name', 'lat', 'lon', 'capacity', 'physical_configuration', 'is_charging_station', 'rental_methods', 'is_virtual_station']


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r: return json.loads(r.read())
        except Exception as e:
            print('  retry', i + 1, url[:140], e); time.sleep(15 * (i + 1))
    raise RuntimeError('failed: ' + url)


root = get(CFG['gbfs'])
langs = root.get('data', {})
feeds = (langs.get(CFG.get('lang', 'en')) or next(iter(langs.values())))['feeds']
url = {f['name']: f['url'] for f in feeds}
print('feeds:', sorted(url))
info = get(url['station_information'])
stations = info['data']['stations']
installed = {}
if 'station_status' in url:
    try:
        st = get(url['station_status'])
        installed = {s['station_id']: bool(s.get('is_installed', True)) for s in st['data']['stations']}
    except Exception as e:
        print('  no station_status:', e)
out = []
for s in stations:
    q = {k: s[k] for k in KEEP if k in s}
    if s['station_id'] in installed: q['installed'] = installed[s['station_id']]
    out.append(q)
updated = dt.datetime.fromtimestamp(info.get('last_updated', time.time()), dt.timezone.utc).date().isoformat()
print('stations:', len(out), '· not installed:', sum(1 for q in out if q.get('installed') is False))
print('configurations:', dict(collections.Counter(q.get('physical_configuration') for q in out).most_common()))
print('charging:', sum(1 for q in out if q.get('is_charging_station')))
print('rental methods:', dict(collections.Counter(','.join(sorted(q.get('rental_methods') or [])) for q in out).most_common()))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({'fetched': dt.date.today().isoformat(), 'updated': updated, 'source': url['station_information'], 'stations': out},
          open(OUT, 'w'), separators=(',', ':'))
print('wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')
