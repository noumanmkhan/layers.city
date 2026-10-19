"""Fetch the inputs for New York's halal and kosher food shops into raw/places/. Run from GitHub Actions
(fetch-nyc.yml runs it when it changes, or by hand with script=fetch_shops.py); the sandbox can't reach these hosts.

  registry_halal.json   New York State's registered halal establishments (Halal Foods Protection Act) and
  registry_kosher.json  registered kosher establishments (Kosher Law Protection Act), from the Department of
                        Agriculture and Markets' published tables, updated weekly. One record per row, every
                        column kept: name, address, certifier, and the registrant's own answers (all meat
                        halal / soaked and salted, sells only halal / kosher food...). The State lists
                        restaurants, caterers and carts alongside shops, and has no type field: faith_shops.csv
                        is the curated list of grocers, butchers and bakeries taken from these.
  geocode.json          Positions for faith_shops.csv rows without their own lat/lon (the cache faith.py
                        reads): NYC Planning's GeoSearch inside the five boroughs, the US Census geocoder
                        elsewhere, then OpenStreetMap Nominatim. Addresses already placed are not looked up again."""
import csv, html, json, os, re, time, urllib.parse, urllib.request
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'places'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'city-layers-pipeline (layers.city; go@layers.city)'}
REGISTRIES = {
    'halal': 'https://apps.agriculture.ny.gov/FS/halal-establishment-registrations.html',
    'kosher': 'https://apps.agriculture.ny.gov/FS/kosher-establishment-registrations.html',
}
NYC = {'new york', 'manhattan', 'brooklyn', 'bronx', 'the bronx', 'staten island', 'queens'}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            print('  retry', i + 1, url, e); time.sleep(10 * (i + 1))
    raise SystemExit('failed: ' + url)


class Table(HTMLParser):
    """Every <tr> of the page's tables as a list of cell texts."""
    def __init__(self):
        super().__init__(); self.rows, self.row, self.cell = [], None, None
    def handle_starttag(self, tag, attrs):
        if tag == 'tr': self.row = []
        elif tag in ('td', 'th') and self.row is not None: self.cell = []
        elif tag == 'br' and self.cell is not None: self.cell.append(' ')
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(re.sub(r'\s+', ' ', ''.join(self.cell)).strip()); self.cell = None
        elif tag == 'tr' and self.row is not None:
            if any(self.row): self.rows.append(self.row)
            self.row = None
    def handle_data(self, d):
        if self.cell is not None: self.cell.append(d)


def key(h):
    return re.sub(r'[^a-z0-9]+', '_', h.lower()).strip('_')[:60]


for diet, url in REGISTRIES.items():
    t = Table(); t.feed(get(url))
    head = next((r for r in t.rows if any('name' in c.lower() for c in r) and len(r) > 8), None)
    if not head: raise SystemExit(diet + ': no header row found')
    cols = [key(h) for h in head]
    recs = [dict(zip(cols, r)) for r in t.rows if r is not head and len(r) == len(cols)]
    json.dump({'source': 'New York State Department of Agriculture and Markets, ' + url,
               'fetched': time.strftime('%Y-%m-%d'), 'columns': head, 'records': recs},
              open(os.path.join(OUT, f'registry_{diet}.json'), 'w'), ensure_ascii=False, indent=1)
    print(diet, len(recs), 'registrations;', len(cols), 'columns:', ' | '.join(head[:8]), '...')

# Geocoding the curated list.
path = os.path.join(OUT, 'geocode.json')
cache = json.load(open(path)) if os.path.exists(path) else {}
want = []
for r in csv.DictReader(open(os.path.join(HERE, 'faith_shops.csv'), encoding='utf-8')):
    if r.get('lat') and r.get('lon'): continue
    k = r['address'] + ', ' + r['locality']
    if k not in cache and k not in want: want.append(k)
print(len(want), 'addresses to place;', len(cache), 'already placed')


def geosearch(q):
    """NYC Planning Labs GeoSearch (NYC's own address points, public). Only an address-level hit counts: a confident
    one, or any whose house number is the one asked for (Queens' "100-28" style numbers can score low with a
    neighbourhood name instead of the borough)."""
    num = q.split(' ', 1)[0]
    u = 'https://geosearch.planninglabs.nyc/v2/search?' + urllib.parse.urlencode({'text': q, 'size': 3})
    try: j = json.loads(get(u, 2))
    except SystemExit: return None
    for f in j.get('features') or []:
        pr = f['properties']
        if pr.get('layer') != 'address': continue
        if pr.get('confidence', 0) >= 0.8 or (pr.get('housenumber') or '').replace(' ', '') == num:
            lon, lat = f['geometry']['coordinates']
            return {'at': [round(lon, 5), round(lat, 5)], 'type': 'address', 'src': 'geosearch', 'match': pr.get('label')}
    return None


QUEENS = {'rego park', 'forest hills', 'kew gardens', 'flushing', 'jackson heights', 'jamaica', 'astoria', 'long island city', 'woodside',
          'elmhurst', 'corona', 'richmond hill', 'ozone park', 'fresh meadows', 'bayside', 'whitestone', 'far rockaway', 'queens village',
          'ridgewood', 'middle village', 'hollis', 'saint albans', 'glen oaks', 'bellerose', 'little neck', 'douglaston', 'howard beach'}


def pluto(addr):
    """The City's tax lots (PLUTO): an exact street address, for city addresses GeoSearch doesn't know."""
    a = re.sub(r'\bBlvd\b', 'Boulevard', re.sub(r'\bAve\b', 'Avenue', re.sub(r'\bSt\b', 'Street', addr))).upper()
    u = 'https://data.cityofnewyork.us/resource/64uk-42ks.json?' + urllib.parse.urlencode({'$select': 'address,latitude,longitude', '$where': "address='" + a.replace("'", "''") + "'", '$limit': 2})
    try: j = json.loads(get(u, 2))
    except SystemExit: return None
    j = [x for x in j if x.get('latitude')]
    if len(j) != 1:
        # Queens "100-28" numbers: a building's lot is often filed under a neighbouring number. Take the lot on the same
        # block ("100-") and street with the nearest house number, within 10: the same block face.
        m = re.match(r'^(\d+)-(\d+) (.+)$', a)
        if not m: return None
        u = 'https://data.cityofnewyork.us/resource/64uk-42ks.json?' + urllib.parse.urlencode({'$select': 'address,latitude,longitude', '$where': "address like '" + m.group(1) + "-% " + m.group(3).replace("'", "''") + "'", '$limit': 200})
        try: c = [x for x in json.loads(get(u, 2)) if x.get('latitude')]
        except SystemExit: return None
        num = lambda x: int(re.match(r'^\d+-(\d+)', x['address']).group(1)) if re.match(r'^\d+-\d+', x['address']) else 9999
        c = sorted(c, key=lambda x: abs(num(x) - int(m.group(2))))
        if not c or abs(num(c[0]) - int(m.group(2))) > 10: return None
        j = c[:1]
    return {'at': [round(float(j[0]['longitude']), 5), round(float(j[0]['latitude']), 5)], 'type': 'address', 'src': 'pluto', 'match': j[0]['address']}


def census(q):
    u = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?' + urllib.parse.urlencode(
        {'address': q, 'benchmark': 'Public_AR_Current', 'format': 'json'})
    try: j = json.loads(get(u, 2))
    except SystemExit: return None
    m = j.get('result', {}).get('addressMatches') or []
    if not m: return None
    c = m[0]['coordinates']
    return {'at': [round(c['x'], 5), round(c['y'], 5)], 'type': 'address', 'src': 'census', 'match': m[0].get('matchedAddress')}


def nominatim(addr, loc):
    """OpenStreetMap Nominatim, for what the other two can't parse (state routes in Rockland, station concourses).
    One request a second, as its usage policy asks. Only a house-level match counts."""
    for q in (f'{addr}, {loc}, New York', re.sub(r'\bNY-(\d+)\b', r'Route \1', addr) + f', {loc}, New York'):
        u = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode({'q': q, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'us'})
        time.sleep(1.1)
        try: j = json.loads(get(u, 2))
        except SystemExit: continue
        if j and (j[0].get('addresstype') in ('building', 'house', 'shop', 'place', 'amenity') or j[0].get('type') in ('house', 'supermarket', 'bakery', 'butcher', 'convenience')):
            return {'at': [round(float(j[0]['lon']), 5), round(float(j[0]['lat']), 5)], 'type': 'address', 'src': 'nominatim', 'match': j[0].get('display_name', '')[:120]}
    return None


for k in want:
    addr, loc = k.rsplit(', ', 1)
    # GeoSearch only knows the five boroughs, so a suburb falls through to the Census geocoder.
    hit = ((geosearch(f'{addr}, {loc}, NY') or (geosearch(f'{addr}, Queens, NY') if loc.lower() in QUEENS else None)) if loc else None) \
        or (pluto(addr) if loc.lower() in NYC or loc.lower() in QUEENS else None) or census(f'{addr}, {loc}, NY') or nominatim(addr, loc)
    if hit: cache[k] = hit; print('  placed', k, '->', hit['src'], hit.get('match'))
    else: print('  NOT FOUND', k)
    time.sleep(0.5)
json.dump(cache, open(path, 'w'), ensure_ascii=False, indent=1, sort_keys=True)
