"""Fetch the inputs for Chicago's Fun maps page into raw/fun/. Run from GitHub Actions (*Fetch Chicago fun maps*; the
sandbox can't reach the Data Portal or Overpass). Only small summaries are committed.

  osm_places.json   OpenStreetMap shops and amenities in the city's bounding box (engine/fun/osm.py). ODbL.
  sr311.json        311 Service Requests (City of Chicago Data Portal v6vf-nfxy): the last complete year's requests
                    counted by community area (its number, as in community_areas.geojson) and request type.
                    Dropped before counting: aircraft noise complaints (all filed at O'Hare's community area, so
                    they'd only say where the airport is), information-only calls, and anything about people.

Usage: python3 cities/chicago/fetch_fun.py [osm] [311]   (no argument: both; each part runs on its own)"""
import json, os, re, sys, time, traceback, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'engine'))
from fun.osm import places   # noqa: E402

OUT = os.path.join(HERE, 'raw', 'fun')
API = 'https://data.cityofchicago.org/resource/'
UA = {'User-Agent': 'layers.city pipeline (go@layers.city)'}
BBOX = (41.64, -87.94, 42.03, -87.52)   # s, w, n, e: the city, O'Hare included
YEAR = date.today().year - 1
SPAN = f"'{YEAR}-01-01T00:00:00' AND '{YEAR}-12-31T23:59:59'"
AREAS = {f['properties']['code'] for f in json.load(open(os.path.join(HERE, '..', '..', 'docs', 'chicago', 'data', 'community_areas.geojson')))['features']}
os.makedirs(OUT, exist_ok=True)

DROP = re.compile(r'aircraft noise|information only|homeless|wellness|shelter|person|people|panhandl|human', re.I)


def soql(rid, **params):
    q = urllib.parse.urlencode({**{'$' + k: v for k, v in params.items()}, '$limit': 50000})
    for attempt in range(4):
        try:
            req = urllib.request.Request(API + rid + '.json?' + q, headers=UA)
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.load(r)
        except Exception as ex:
            print(f'  {rid} try {attempt + 1} failed: {ex}', flush=True)
            if attempt == 3:
                raise
            time.sleep(30)


def save(name, obj):
    with open(os.path.join(OUT, name), 'w') as f:
        json.dump(obj, f, separators=(',', ':'))


def part_osm():
    places(BBOX, os.path.join(OUT, 'osm_places.json'))


def part_311():
    rows = soql('v6vf-nfxy', select='community_area,sr_type,count(*) AS n', where=f'created_date BETWEEN {SPAN}',
                group='community_area,sr_type')
    by, total, dropped, unplaced = defaultdict(Counter), 0, Counter(), 0
    for r in rows:
        n, typ = int(r['n']), re.sub(r'\s+', ' ', r.get('sr_type') or '').strip()
        if not typ or DROP.search(typ):
            dropped[typ] += n
            continue
        try:
            area = int(float(r.get('community_area')))
        except (TypeError, ValueError):
            area = None
        if area not in AREAS:
            unplaced += n
            continue
        by[area][typ] += n
        total += n
    print(f'  {total:,} requests kept in {len(by)} community areas; {unplaced:,} with no area; dropped {sum(dropped.values()):,}:',
          dropped.most_common(8), flush=True)
    city = Counter()
    for c in by.values():
        city.update(c)
    print('  top types:', city.most_common(30), flush=True)
    save('sr311.json', {'year': YEAR, 'source': '311 Service Requests (City of Chicago Data Portal)', 'total': total,
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
