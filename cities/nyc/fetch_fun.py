"""Fetch the inputs for New York's Fun maps page into raw/fun/, boiled down so only a small summary gets committed.

  film_permits.json  Film Permits (NYC Open Data tg4x-b46p, Mayor's Office of Media and Entertainment): "Shooting Permit"
                     rows from the last 12 complete months the feed holds, counted per community district and joint
                     interest area (a permit naming several splits evenly), by category and by month, plus the streets
                     most often named for held parking, placed on the DOT centerline.

The window counts back from the feed's newest permit, not today, because the feed can lag by months. A permit lists board
numbers under one borough even when it crosses into another, so a number that doesn't exist in that borough is dropped
(and counted in "dropped"), and a number that does exist there may rarely be the wrong borough's."""
import calendar, json, os, re, sys, time, urllib.parse, urllib.request
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from centerline import BORO, core, fetch_lines, norm, stretch   # noqa: E402

API = 'https://data.cityofnewyork.us/resource/tg4x-b46p.json'
UA = {'User-Agent': 'city-layers-pipeline (layers.city)'}
OUT = os.path.join(HERE, 'raw', 'fun')
DISTRICTS = os.path.join(HERE, '..', '..', 'docs', 'nyc', 'data', 'districts.geojson')
TOP_STREETS = 25
SEG = re.compile(r'^(.+?)\s+between\s+(.+?)\s+and\s+(.+)$', re.I)


def soql(**params):
    url = API + '?' + urllib.parse.urlencode({'$' + k: v for k, v in params.items()})
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
                return json.load(r)
        except Exception as e:
            print('  retry', i + 1, e, flush=True)
            time.sleep(10 * (i + 1))
    raise RuntimeError('failed: ' + url)


def window(newest):
    """The 12 months ending with the last one before the newest permit's month, as ('YYYY-MM-01', 'YYYY-MM-01')."""
    y, m = int(newest[:4]), int(newest[5:7])
    return f'{y - 1}-{m:02d}-01', f'{y}-{m:02d}-01'


def month_name(ym):
    return f'{calendar.month_name[int(ym[5:7])]} {ym[:4]}'


def pretty(s):
    """"WEST   51 STREET" -> "West 51st Street"; "5 AVENUE" -> "5th Avenue"."""
    def nth(m):
        n = int(m.group(1))
        return f'{n}{"th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")}'
    return re.sub(r'\b(\d+)\b', nth, re.sub(r'\s+', ' ', s).strip().title())


def segments(text):
    """{(on, a, z)} named in a permit's parkingheld, one each however often it repeats, cross streets in a fixed order."""
    out = set()
    for part in (text or '').split(','):
        m = SEG.match(part.strip())
        if m:
            a, z = sorted((re.sub(r'\s+', ' ', m.group(2)).strip().upper(), re.sub(r'\s+', ' ', m.group(3)).strip().upper()))
            out.add((re.sub(r'\s+', ' ', m.group(1)).strip().upper(), a, z))
    return out


codes = {f['properties']['code'] for f in json.load(open(DISTRICTS))['features']}
newest = soql(select='max(startdatetime) as d', where="eventtype='Shooting Permit'")[0]['d']
start, end = window(newest)
print(f'newest permit {newest[:10]}; window {start} to before {end}', flush=True)

rows, offset = [], 0
while True:
    got = soql(select='eventid,startdatetime,borough,communityboard_s,category,parkingheld', order='eventid', limit=10000, offset=offset,
               where=f"eventtype='Shooting Permit' AND startdatetime>='{start}' AND startdatetime<'{end}'")
    rows += got
    offset += len(got)
    if len(got) < 10000:
        break
print(f'{len(rows)} permits', flush=True)

BORO_N = {k: int(v) for k, v in BORO.items()}
by_unit = defaultdict(lambda: {'n': 0.0, 'cats': Counter()})
cats, months, street_n = Counter(), Counter(), Counter()
dropped = unplaced = 0
for r in rows:
    cat = (r.get('category') or 'Other').strip()
    cats[cat] += 1
    months[r['startdatetime'][:7]] += 1
    b = r.get('borough')
    toks = [t.strip() for t in (r.get('communityboard_s') or '').split(',') if t.strip()]
    here = [BORO_N[b] * 100 + int(t) for t in toks if b in BORO_N and t.isdigit() and BORO_N[b] * 100 + int(t) in codes]
    dropped += len(toks) - len(here)
    if not here:
        unplaced += 1
    for c in set(here):
        by_unit[c]['n'] += 1 / len(set(here))
        by_unit[c]['cats'][cat] += 1 / len(set(here))
    if b in BORO_N:
        for s in segments(r.get('parkingheld')):
            street_n[(b, *s)] += 1
print(f'{len(by_unit)} areas; {dropped} board numbers dropped; {unplaced} permits with no area', flush=True)

# Place the most-named stretches on the centerline, working down until TOP_STREETS have landed.
candidates = street_n.most_common(TOP_STREETS * 4)
lines = fetch_lines({core(norm(x)) for k, _ in candidates for x in k[1:]})
streets, missed = [], []
for (b, on, a, z), n in candidates:
    if len(streets) >= TOP_STREETS:
        break
    coords, why = stretch(lines, BORO[b], on, a, z)
    if coords:
        streets.append({'name': pretty(on), 'from': pretty(a), 'to': pretty(z), 'boro': b, 'n': n, 'coords': coords})
    else:
        missed.append(f'{on} ({a} / {z}): {why}')
print(f'placed {len(streets)} streets; missed {len(missed)}', *missed[:10], sep='\n  ', flush=True)

last = sorted(months)[-1]
os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, 'film_permits.json')
with open(path, 'w') as f:
    json.dump({'source': 'NYC Open Data tg4x-b46p', 'newest': newest[:10], 'first': month_name(start), 'last': month_name(last),
               'permits': len(rows), 'unplaced': unplaced, 'dropped': dropped,
               'by_unit': {str(k): {'n': round(v['n'], 1), 'cats': {c: round(x, 1) for c, x in v['cats'].most_common()}}
                           for k, v in sorted(by_unit.items())},
               'cats': dict(cats.most_common()), 'months': {k: months[k] for k in sorted(months)},
               'streets': streets}, f, separators=(',', ':'))
print('wrote', path, os.path.getsize(path), 'bytes')
