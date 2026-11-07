"""Fetch the inputs for San Francisco's Fun maps page into raw/fun/. Run from GitHub Actions (*Fetch San Francisco fun
maps*; the sandbox can't reach DataSF or Overpass). Only small summaries are committed.

  osm_places.json   OpenStreetMap shops and amenities in the city's bounding box (engine/fun/osm.py). ODbL.
  sr311.json        311 Cases (DataSF vw6y-z8j6, PDDL): the last complete year's requests counted by analysis
                    neighborhood (keyed by the neighborhood's code in neighbourhoods.geojson) and request type
                    ("Service: subtype"). Requests about people (encampments, tent counts, human waste, needles)
                    and the catch-all general requests are dropped before counting, so no map can show them.
  tickets.json      SFMTA Parking Citations & Fines (DataSF ab4h-6ztd, PDDL): the last complete year's citations by
                    analysis neighborhood (the file carries it), with fines, the three most common violations and the
                    busiest address. Plates are never requested.

Usage: python3 cities/sf/fetch_fun.py [osm] [311] [tickets]   (no argument: all three; each part runs on its own)"""
import json, os, re, sys, time, traceback, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'engine'))
from fun.osm import places   # noqa: E402

OUT = os.path.join(HERE, 'raw', 'fun')
API = 'https://data.sf.gov/resource/'
UA = {'User-Agent': 'layers.city pipeline (go@layers.city)'}
BBOX = (37.70, -122.52, 37.84, -122.35)   # s, w, n, e: the city (Treasure Island included)
YEAR = date.today().year - 1
SPAN = f"'{YEAR}-01-01T00:00:00' AND '{YEAR}-12-31T23:59:59'"
HOODS = {f['properties']['name']: f['properties']['code']
         for f in json.load(open(os.path.join(HERE, '..', '..', 'docs', 'sf', 'data', 'neighbourhoods.geojson')))['features']}
os.makedirs(OUT, exist_ok=True)

# 311 requests about people, or too vague to say anything: never counted.
DROP_SERVICE = re.compile(r'encampment|tent count|general request|rpd general|homeless|welfare check|311 external', re.I)
DROP_SUBTYPE = re.compile(r'human|waste.*(feces|urine)|feces|urine|needle|syringe|person|people|encamp|tent\b|homeless|aggressive|lying', re.I)


def soql(rid, **params):
    q = urllib.parse.urlencode({**{'$' + k: v for k, v in params.items()}, '$limit': 50000})
    for attempt in range(4):
        try:
            req = urllib.request.Request(API + rid + '.json?' + q, headers=UA)
            with urllib.request.urlopen(req, timeout=600) as r:
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
    rows = soql('vw6y-z8j6', select='analysis_neighborhood,service_name,service_subtype,count(*) AS n',
                where=f'requested_datetime BETWEEN {SPAN}', group='analysis_neighborhood,service_name,service_subtype')
    by, total, dropped, unplaced = defaultdict(Counter), 0, Counter(), 0
    for r in rows:
        n = int(r['n'])
        svc, sub = (r.get('service_name') or '').strip(), (r.get('service_subtype') or '').strip()
        if not svc or DROP_SERVICE.search(svc) or DROP_SUBTYPE.search(sub):
            dropped[svc] += n
            continue
        code = HOODS.get(r.get('analysis_neighborhood'))
        if code is None:
            unplaced += n
            continue
        typ = f'{svc}: {sub}' if sub and sub.lower() != svc.lower() and sub.lower() != 'other' else svc
        by[code][typ] += n
        total += n
    print(f'  {total:,} requests kept in {len(by)} neighborhoods; {unplaced:,} with no neighborhood; dropped {sum(dropped.values()):,}:',
          dropped.most_common(8), flush=True)
    city = Counter()
    for c in by.values():
        city.update(c)
    print('  top types:', city.most_common(25), flush=True)
    save('sr311.json', {'year': YEAR, 'source': '311 Cases (DataSF)', 'total': total,
                        'by_ward': {str(k): dict(v) for k, v in sorted(by.items())}})


VIOLATIONS = {'STR CLEAN': 'street cleaning', 'MTR OUT DT': 'expired meter outside downtown', 'METER DTN': 'expired meter downtown',
              'RES/OT': 'overstaying in a residential permit area', 'FAIL DISPL': 'no permit displayed', 'NO PLATES': 'no plates',
              'YEL ZONE': 'parking in a yellow zone', 'PRK GRADE': 'wheels not curbed on a hill', 'DBL PARK': 'double parking',
              'RED ZONE': 'parking in a red zone', 'TWAWY ZN#1': 'tow-away zone', 'BUS ZONE': 'parking in a bus zone'}


def violation(v):
    v = re.sub(r'\s+', ' ', v or '').strip()
    return VIOLATIONS.get(v.upper(), v.lower())


def part_tickets():
    hoods = soql('ab4h-6ztd', select='analysis_neighborhood,count(*) AS n,sum(fine_amount) AS f',
                 where=f'citation_issued_datetime BETWEEN {SPAN}', group='analysis_neighborhood')
    total = sum(int(r['n']) for r in hoods)
    nb = {}
    for r in hoods:
        if r.get('analysis_neighborhood') in HOODS:
            nb[r['analysis_neighborhood']] = {'tickets': int(r['n']), 'fines': round(float(r.get('f') or 0)), 'inf': Counter(), 'top': None}
    inf = soql('ab4h-6ztd', select='analysis_neighborhood,violation_desc,count(*) AS n',
               where=f'citation_issued_datetime BETWEEN {SPAN}', group='analysis_neighborhood,violation_desc')
    for r in inf:
        if r.get('analysis_neighborhood') in nb:
            nb[r['analysis_neighborhood']]['inf'][violation(r.get('violation_desc'))] += int(r['n'])
    tops = soql('ab4h-6ztd', select='analysis_neighborhood,citation_location,count(*) AS n,sum(fine_amount) AS f,avg(latitude) AS la,avg(longitude) AS lo',
                where=f'citation_issued_datetime BETWEEN {SPAN}', group='analysis_neighborhood,citation_location',
                having='count(*) >= 200', order='n DESC')
    for r in tops:
        d = nb.get(r.get('analysis_neighborhood'))
        loc = re.sub(r'\s+', ' ', r.get('citation_location') or '').strip()
        if d and loc and not d['top']:
            try:
                at = [round(float(r['lo']), 5), round(float(r['la']), 5)]
            except (KeyError, TypeError, ValueError):
                at = None
            d['top'] = [loc.title(), int(r['n']), round(float(r.get('f') or 0)), at]
    placed = sum(v['tickets'] for v in nb.values())
    print(f'  {total:,} citations in {YEAR}, {placed:,} in a neighborhood; ${sum(v["fines"] for v in nb.values()):,} in fines', flush=True)
    save('tickets.json', {'year': YEAR, 'source': 'SFMTA Parking Citations & Fines (DataSF)', 'tickets': total, 'geocoded': placed,
                          'by_nbhd': {k: {'tickets': v['tickets'], 'fines': v['fines'], 'inf': v['inf'].most_common(3), 'top': v['top']}
                                      for k, v in sorted(nb.items())}})


PARTS = {'osm': part_osm, '311': part_311, 'tickets': part_tickets}
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
