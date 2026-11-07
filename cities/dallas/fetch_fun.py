"""Fetch the inputs for Dallas's Fun maps page into raw/fun/. Run from GitHub Actions (*Fetch Dallas fun maps*; the
sandbox can't reach Dallas OpenData or Overpass). Only small summaries are committed.

  osm_places.json   OpenStreetMap shops, amenities and courts in the city's bounding box (engine/fun/osm.py). ODbL.
  sr311.json        311 Service Requests (Dallas OpenData d7e7-envw, PDDL): the last complete year's requests counted by
                    City Council district and request type, counted on the portal (no addresses are fetched).
                    Dropped before counting, so no map can show them: requests about people (encampments,
                    panhandling), every police type but chronic noise, property-condition complaints (Code Concern,
                    rental registration), animal-enforcement types (loose, aggressive, lack of care, bites), whose
                    north/south split would read as an income map, and the catch-alls. Requests filed on a district
                    line ("7,8") aren't counted.

Usage: python3 cities/dallas/fetch_fun.py [osm] [311]   (no argument: both; each part runs on its own)"""
import json, os, re, sys, time, traceback, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'engine'))
from fun.osm import places   # noqa: E402

OUT = os.path.join(HERE, 'raw', 'fun')
API = 'https://www.dallasopendata.com/resource/'
UA = {'User-Agent': 'layers.city pipeline (go@layers.city)'}
BBOX = (32.61, -97.00, 33.02, -96.55)   # s, w, n, e: the city
YEAR = date.today().year - 1
SPAN = f"'{YEAR}-01-01T00:00:00' AND '{YEAR}-12-31T23:59:59'"
os.makedirs(OUT, exist_ok=True)

DROP = re.compile(r'homeless|encamp|panhandl|\bpersons?\b|\bpeople\b|welfare|code concern|\brental\b|registration|criminal|narcotic|\bvice\b|'
                  r'extra police|traffic violation|prostitut|graffiti.*gang|animal (loose|lack|aggress|bite|confin|owner|nuisance|cruel)|'
                  r'\bloose\b|aggressive|lack of care|\bbites?\b|owner surrender|complaint/compliment|miscellaneous', re.I)
KEEP_POLICE = re.compile(r'noise', re.I)


def soql(rid, **params):
    q = urllib.parse.urlencode({**{'$' + k: v for k, v in params.items()}, '$limit': 50000})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(API + rid + '.json?' + q, headers=UA), timeout=600) as r:
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
    rows = soql('d7e7-envw', select='city_council_district,department,service_request_type,count(*) AS n',
                where=f'created_date BETWEEN {SPAN}', group='city_council_district,department,service_request_type')
    by, total, dropped, split = defaultdict(Counter), 0, Counter(), 0
    for r in rows:
        n = int(r['n'])
        typ = re.sub(r'\s+', ' ', r.get('service_request_type') or '').strip()
        typ = re.sub(r'\s*-\s*[A-Z]{2,4}$', '', typ)   # department suffixes ("Dead Animal Pick Up - DAS")
        dept = (r.get('department') or '').strip()
        police = re.search(r'police|dpd', dept, re.I) and not KEEP_POLICE.search(typ)
        if not typ or DROP.search(typ) or police:
            dropped[typ] += n
            continue
        d = (r.get('city_council_district') or '').strip()
        if not re.fullmatch(r'\d{1,2}', d):
            split += n
            continue
        by[int(d)][typ] += n
        total += n
    print(f'  {total:,} requests kept in {len(by)} districts; {split:,} on a district line or with none; '
          f'dropped {sum(dropped.values()):,}:', dropped.most_common(14), flush=True)
    city = Counter()
    for c in by.values():
        city.update(c)
    print('  top types:', city.most_common(40), flush=True)
    save('sr311.json', {'year': YEAR, 'source': '311 Service Requests (Dallas OpenData)', 'total': total,
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
