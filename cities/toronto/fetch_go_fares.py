"""GO Transit fares between the map's GO train stations, from Metrolinx's own schedule data (GTFS).
Run from GitHub Actions (the sandbox can't reach Metrolinx); writes raw/go_fares.json, which the Venues pages
(engine/venues.py, through "railTable" in venues.json) quote as "GO fare $x.xx" for each trip from the GTA.

GO's GTFS prices a trip by fare zone: stops.txt gives each stop a zone_id, fare_rules.txt maps an origin and
destination zone to a fare_id, and fare_attributes.txt gives its price. The script logs what the feed holds, so a
change of format (GTFS fares v2: fare_products, fare_leg_rules) shows up in the log instead of a wrong figure.

Only stations on the map (docs/toronto/data/go_stations.geojson) are kept, matched by name."""
import csv, datetime as dt, io, json, os, re, sys, time, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, 'raw', 'go_fares.json')
URL = 'https://assets.metrolinx.com/raw/upload/Documents/Metrolinx/Open%20Data/GO-GTFS.zip'
UA = {'User-Agent': 'city-layers-pipeline (layers.city)'}


def download(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, e); time.sleep(10 * (i + 1))
    sys.exit('could not download ' + url)


def rows(z, name):
    if name not in z.namelist():
        return []
    return list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding='utf-8-sig')))


def norm(s):
    s = s.lower().replace('&', 'and')
    s = re.sub(r'\b(go|station|stn|rail|train)\b', ' ', s)
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


z = zipfile.ZipFile(io.BytesIO(download(URL)))
print('files:', sorted(z.namelist()))
fa, fr, stops = rows(z, 'fare_attributes.txt'), rows(z, 'fare_rules.txt'), rows(z, 'stops.txt')
print('fare_attributes:', len(fa), 'rows', list(fa[0]) if fa else None, fa[:3])
print('fare_rules:', len(fr), 'rows', list(fr[0]) if fr else None, fr[:3])
for extra in ('fare_products.txt', 'fare_leg_rules.txt', 'fare_media.txt', 'areas.txt', 'stop_areas.txt'):
    if extra in z.namelist():
        print(extra, rows(z, extra)[:3])
if not fa or not fr:
    sys.exit('no zone fares in the feed: see the log above')

price = {f['fare_id']: float(f['price']) for f in fa if f.get('price')}
pair = {}
for r in fr:
    o, d = r.get('origin_id'), r.get('destination_id')
    if o and d and r['fare_id'] in price:
        pair[(o, d)] = price[r['fare_id']]

# The map's GO stations, matched to a stop and its fare zone (a parent station, or its first zoned platform).
mapped = [f['properties']['name'] for f in json.load(open(os.path.join(ROOT, 'docs', 'toronto', 'data', 'go_stations.geojson')))['features']]
zone_by_norm = {}
for s in stops:
    if s.get('zone_id'):
        zone_by_norm.setdefault(norm(s['stop_name']), s['zone_id'])
zones, missing = {}, []
for name in mapped:
    zn = zone_by_norm.get(norm(name))
    if zn is None:
        missing.append(name)
    else:
        zones[name] = zn
print('matched', len(zones), 'of', len(mapped), 'stations; missing:', missing)

fares = {}
for a, za in zones.items():
    for b, zb in zones.items():
        if a != b and (za, zb) in pair:
            fares.setdefault(a, {})[b] = round(pair[(za, zb)], 2)
print('pairs:', sum(len(v) for v in fares.values()))
for a in ('Brampton Innovation District GO', 'Oakville GO', 'Allandale Waterfront GO'):
    print(' ', a, '-> Union Station:', fares.get(a, {}).get('Union Station'))

json.dump({'source': URL, 'asof': dt.date.today().isoformat(), 'currency': 'CAD',
           'note': 'GO Transit fare between two stations, from fare_attributes.txt and fare_rules.txt in GO GTFS.',
           'zones': zones, 'fares': fares}, open(OUT, 'w'), indent=0, sort_keys=True)
print('wrote', OUT)
