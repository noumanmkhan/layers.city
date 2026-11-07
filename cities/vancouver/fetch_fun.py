"""Fetch the inputs for Vancouver's Fun maps page into raw/fun/. Run from GitHub Actions (*Fetch Vancouver fun maps*;
the sandbox can't reach the City's portal or Overpass). Only small summaries are committed.

  osm_places.json   OpenStreetMap shops, amenities and courts in the city's bounding box, the UEL included
                    (engine/fun/osm.py). ODbL.
  sr311.json        3-1-1 Service Requests (City of Vancouver Open Data, Open Government Licence – Vancouver): the
                    last complete year's requests counted by local area (keyed by the area's code in
                    local_areas.geojson; the City's names are matched without spaces, hyphens or case) and request
                    type. Requests about people (encampments, welfare checks, needles, human waste) and the obsolete
                    "ZZ" types are dropped before counting, so no map can show them. Stanley Park and the UEL have none.

Usage: python3 cities/vancouver/fetch_fun.py [osm] [311]   (no argument: both; each part runs on its own)"""
import json, os, re, sys, time, traceback, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'engine'))
from fun.osm import places   # noqa: E402

OUT = os.path.join(HERE, 'raw', 'fun')
ODS = 'https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/'
UA = {'User-Agent': 'layers.city pipeline (go@layers.city)'}
BBOX = (49.19, -123.27, 49.32, -123.02)   # s, w, n, e: the city, Stanley Park and the UEL
YEAR = date.today().year - 1
norm = lambda s: re.sub(r'[^a-z]', '', (s or '').lower())
AREAS = {norm(f['properties']['name']): f['properties']['code']
         for f in json.load(open(os.path.join(HERE, '..', '..', 'docs', 'vancouver', 'data', 'local_areas.geojson')))['features']}
os.makedirs(OUT, exist_ok=True)

DROP = re.compile(r'homeless|encamp|\btents?\b|shelter|welfare|\bpersons?\b|\bpeople\b|needle|syringe|sharps|human|feces|urine|overdose|panhandl|integrated response|^zz', re.I)


def get(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
                return json.load(r)
        except Exception as ex:
            print(f'  try {attempt + 1} failed: {ex}', flush=True)
            if attempt == 3:
                raise
            time.sleep(30)


def save(name, obj):
    with open(os.path.join(OUT, name), 'w') as f:
        json.dump(obj, f, separators=(',', ':'))


def part_osm():
    places(BBOX, os.path.join(OUT, 'osm_places.json'))


def part_311():
    q = urllib.parse.urlencode({'select': 'local_area, service_request_type, count(*) as n',
                                'where': f"service_request_open_timestamp >= date'{YEAR}-01-01' and service_request_open_timestamp < date'{YEAR + 1}-01-01'",
                                'group_by': 'local_area, service_request_type'})
    rows = get(ODS + '3-1-1-service-requests/exports/json?' + q)
    by, total, dropped, unplaced = defaultdict(Counter), 0, Counter(), Counter()
    for r in rows:
        n, typ = int(r.get('n') or 0), re.sub(r'\s+', ' ', r.get('service_request_type') or '').strip()
        if not typ or DROP.search(typ):
            dropped[typ] += n
            continue
        code = AREAS.get(norm(r.get('local_area')))
        if code is None:
            unplaced[r.get('local_area')] += n
            continue
        by[code][typ] += n
        total += n
    print(f'  {total:,} requests kept in {len(by)} local areas; not placed: {unplaced.most_common(6)}; dropped {sum(dropped.values()):,}:',
          dropped.most_common(10), flush=True)
    city = Counter()
    for c in by.values():
        city.update(c)
    print('  top types:', city.most_common(40), flush=True)
    save('sr311.json', {'year': YEAR, 'source': '3-1-1 Service Requests (City of Vancouver Open Data)', 'total': total,
                        'by_ward': {str(k): dict(v) for k, v in sorted(by.items())}})


PARTS = {'osm': part_osm, '311': part_311}
failed = []
for name in (sys.argv[1:] or PARTS):
    print(f'== {name}', flush=True)
    try:
        PARTS[name]()
    except Exception:
        traceback.print_exc()
        failed.append(name)
if failed:
    print('failed parts:', failed)
