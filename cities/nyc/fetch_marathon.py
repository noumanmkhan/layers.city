"""Fetch the City's TCS New York City Marathon closure notice (marathon.json) and place its street closures on NYC
DOT's street centerline, for fetch_closures.py to add to the day's special events. Run from GitHub Actions
(fetch-nyc.yml when it changes; daily in fetch-closures.yml); the sandbox can't reach nyc.gov.

The notice (NYC Citywide Event Coordination and Management) is a PDF table by borough: AREA/STREET, BOUNDARIES,
RESTRICTION, TIME AFFECTED. Read here:
  - "Street Closed" and "Closed" rows become closures; "No Parking", "Closed to Trucks", "Intermittent Closures",
    "Exit Closed" and "Traffic Delays" rows don't close the street to everyone, so they stay off the map.
  - Times like "Sun. Nov. 2, 6am to 9:30pm", "Sat. Nov. 1, 11pm to Sunday Nov. 2, 4:00pm" or "Sat. Nov. 1 to Sun.
    Nov. 2" (whole days) become local start and end times in the race year.
  - "Central Park West 77th Street to 86th Street" doesn't say where the street ends and the boundary begins, so each
    split is tried on the centerline until one places. Names are matched as the centerline spells them: "120th
    Street" is Manhattan's E and W 120 ST, "Fingerboard" is FINGERBOARD RD, and a few misspellings are fixed (FIX).
  - Bridges named without boundaries (Verrazzano, Pulaski, Queensboro, Willis and Madison Avenue) are their
    centerline roadways by exact name, without ramps or paths.
  - Central Park's drives and traverses, the expressways (BQE, Major Deegan ramps) and a few Staten Island streets
    the centerline doesn't name stay unplaced; they are listed as misses.
  - The borough headings in the PDF run together (Brooklyn's rows sit under the Bronx heading), so placement tries
    every borough.

Writes raw/closures/marathon_<year>.txt (the notice's text) and marathon_<year>.json ({year, source, fetched, name,
permits, misses}), for the race year once the City has posted it, and for marathon.json's "test" year (a past
notice, to check the parser; fetch_closures.py only ever uses the race year).
"""
import io, json, os, re, time, urllib.parse, urllib.request
from pypdf import PdfReader
from shapely.geometry import LineString, Point
from shapely.ops import linemerge
from centerline import BORO, CL_API, TYPES, UA, core, norm, fetch_lines, meet, path

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'marathon.json')))
OUT = os.path.join(HERE, 'raw', 'closures'); os.makedirs(OUT, exist_ok=True)
BROWSER = {'User-Agent': 'Mozilla/5.0 (city-layers-pipeline; layers.city; go@layers.city)'}
MONTH = {'oct': 10, 'nov': 11}
CLOSE = {'street closed': 'closed', 'closed': 'closed'}
ROW = re.compile(r'^(?P<body>.+?)\s+(?P<restr>Street Closed|Closed to Trucks|Intermittent Closures|Traffic Delays|Exit Closed|'
                 r'No Parking(?: \([^)]*\))?|Closed)\s+(?P<when>(?:Fri|Sat|Sun|Mon)[a-z]*\.?\s+(?:Oct|Nov)\.?\s+\d.*)$', re.I)
DATE = r'(?:Fri|Sat|Sun|Mon)[a-z]*\.?\s+(?:Oct|Nov)[a-z]*\.?\s+\d{1,2}'
TIME = r'\d{1,2}(?::\d{2})?\s*[ap]m'
WHEN = re.compile(r'^(?P<d1>' + DATE + r')(?:,\s*(?P<t1>' + TIME + r'))?(?:\s+to\s+(?:(?P<d2>' + DATE + r')(?:,\s*(?P<t2>' + TIME + r'))?|(?P<t2b>' + TIME + r')))?\s*$', re.I)
ABBR = [(r'\bMt\.?\s', 'Mount '), (r'\bPk\b', 'Park'), (r'\bFt\.?\s', 'Fort '), (r'\bExp\.?$', 'Expressway'), (r'\bTerr\b', 'Terrace'),
        (r'\bPlz\b', 'Plaza'), (r'\bE\.\s', 'East '), (r'\bW\.\s', 'West '), (r'\bSt\.\s+(?=[A-Z])', 'Saint '), (r'\bPl\.$', 'Place')]
# The bridges by their centerline names exactly (not their ramps, entrances or bike and foot paths).
BRIDGES = {'verraz': 'VERRAZZANO BRG', 'queensboro': 'ED KOCH QUEENSBORO BRG', 'pulaski': 'PULASKI BRG',
           'willis avenue bridge': 'WILLIS AVE  BRIDGE', 'madison avenue bridge': 'MADISON AVE  BRIDGE'}
BRIDGE_NAME = {'verraz': 'Verrazzano-Narrows Bridge', 'queensboro': 'Ed Koch Queensboro Bridge', 'pulaski': 'Pulaski Bridge',
               'willis avenue bridge': 'Willis Avenue Bridge', 'madison avenue bridge': 'Madison Avenue Bridge'}
# Central Park's drives (Manhattan's EAST DR, not Prospect Park's) and its transverse roads, named in the notice
# without boundaries: the whole road. The transverses' centerline names vary, so they're found by pattern and told
# apart by their street number or their old "Transverse Road No. 1-4" names.
DRIVES = {'central park east drive': 'EAST DR', 'central park west drive': 'WEST DR', 'central park center drive': 'CENTER DR'}
DRIVE_NAME = {'central park east drive': 'East Drive, Central Park', 'central park west drive': 'West Drive, Central Park',
              'central park center drive': 'Center Drive, Central Park'}
TRANSVERSES = {'65th traverse': ('65', 'ONE', '1'), '79th traverse': ('79', 'TWO', '2'), '86th traverse': ('86', 'THREE', '3'),
               '96th traverse': ('97', 'FOUR', '4'), '97th traverse': ('97', 'FOUR', '4')}
TRANSVERSE_NAME = {'65th traverse': '65th Street Transverse', '79th traverse': '79th Street Transverse', '86th traverse': '86th Street Transverse',
                   '96th traverse': '97th Street Transverse', '97th traverse': '97th Street Transverse'}
NAMES = {**BRIDGE_NAME, **DRIVE_NAME, **TRANSVERSE_NAME}


def transverse_key(full):
    """Which transverse a centerline name is ("65 ST TRANSVERSE", "TRANSVERSE RD NUMBER ONE"), or None."""
    f = ' ' + re.sub(r'\s+', ' ', full.upper()) + ' '
    if 'TRANSVERSE' not in f and 'TRAVERSE' not in f: return None
    for k, (num, word, digit) in TRANSVERSES.items():
        if f' {num} ' in f or f' {word} ' in f or f'NO {digit} ' in f or f'NO. {digit} ' in f or f'NUMBER {word} ' in f:
            return k
    return None


# The notice's spellings that aren't the centerline's.
FIX = {'MCGUINESS BLVD': 'MCGUINNESS BLVD', 'MCCLEAN': 'MC CLEAN AVE', 'MCCLEAN AVE': 'MC CLEAN AVE', 'MT MORRIS PARK W': 'MOUNT MORRIS PARK W',
       'FERRY TERMINAL': 'FERRY TERMINAL DR', 'EAST DRIVE': 'EAST DR', 'EAST DR': 'EAST DR', 'FDR DR': 'FDR DR',
       '59 ST BRIDGE': 'ED KOCH QUEENSBORO BRG', 'WILLIS AVE BRIDGE': 'WILLIS AVE BRIDGE', 'VERRAZANO BRIDGE': 'VERRAZZANO BRG',
       'COLUMBUS CIRCLE': 'COLUMBUS CIR', 'FINGERBOARD AVE': 'FINGERBOARD RD'}
# Where the notice names a street past its end: 59th Street is Central Park South between Fifth and Eighth Avenues, and
# Eighth Avenue ends at Columbus Circle.
ALT = {'59 ST': ['CENTRAL PARK S', 'COLUMBUS CIR'], '8 AVE': ['COLUMBUS CIR']}
MAXLEN = 15000   # metres: the course's longest closed stretches (Fourth Avenue) run past the 8 km fetch_closures allows


def fetch_pdf(year):
    for u in CFG['notice']:
        u = u.format(year=year)
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=BROWSER), timeout=90) as r: b = r.read()
            if b[:4] == b'%PDF': return u, b
        except Exception as e:
            print('  no notice at', u, '-', e)
    return None, None


def clean(s):
    s = re.sub(r'\([^)]*\)', ' ', s)
    for a, b in ABBR: s = re.sub(a, b, s)
    return re.sub(r'\s+', ' ', s).strip(' -/')


def when(s, year):
    m = WHEN.match(re.sub(r'\s+', ' ', s.strip()))
    if not m: return None, None
    def day(d):
        mm = re.search(r'(Oct|Nov)[a-z]*\.?\s+(\d{1,2})', d, re.I)
        return '%d-%02d-%02d' % (year, MONTH[mm.group(1).lower()], int(mm.group(2)))
    def hm(t):
        mm = re.match(r'(\d{1,2})(?::(\d{2}))?\s*([ap]m)', t.strip(), re.I)
        h = int(mm.group(1)) % 12 + (12 if mm.group(3).lower() == 'pm' else 0)
        return '%02d:%s' % (h, mm.group(2) or '00')
    d1 = day(m['d1']); d2 = day(m['d2']) if m['d2'] else d1
    t1 = hm(m['t1']) if m['t1'] else '00:00'
    t2 = hm(m['t2']) if m['t2'] else hm(m['t2b']) if m['t2b'] else '23:59'
    return d1 + 'T' + t1, d2 + 'T' + t2


def rows_of(text):
    """Table rows, with a row broken over two lines joined back ("... 8:45am to" + "10:30pm")."""
    out, buf = [], ''
    for line in text.splitlines():
        s = re.sub(r'\s+', ' ', line).strip()
        if not s or s.startswith('PAGE ') or s.startswith('AREA/STREET') or s.startswith('=== page'): continue
        if buf and (re.match(r'^' + TIME, s, re.I) or re.match(r'^Nov\.?\s+\d', s) or buf.endswith(' to')):
            buf += ' ' + s
        else:
            if buf: out.append(buf)
            buf = s
    if buf: out.append(buf)
    return out


def prepare(lines):
    """Manhattan's (and some Brooklyn) streets come in East and West halves ("E 120 ST", "W 120 ST"); the notice
    names them bare ("120th Street"), so each pair is also kept under the bare name where no street has it."""
    extra = {}
    for (b, k), segs in lines.items():
        if k[:2] in ('E ', 'W ') and (b, k[2:]) not in lines: extra.setdefault((b, k[2:]), []).extend(segs)
    lines.update(extra)
    idx = {}
    for b, k in lines: idx.setdefault(b, set()).add(k)
    return lines, idx


def keys(idx, b, s):
    """The centerline names in borough b the notice's text s could mean: its own spelling, a known fix, or the
    name with a street type added ("Fingerboard" -> FINGERBOARD RD)."""
    n = norm(s); n = FIX.get(n, n); have = idx.get(b, set())
    if n in have: return [n] + [k for k in ALT.get(n, []) if k in have]
    return sorted(k for k in have if k.startswith(n + ' ') and k[len(n) + 1:].split(' ')[0] in TYPES.values() and len(k[len(n) + 1:].split()) <= 2)


def run(lines, idx, on, a, z):
    """(coords, None, _), or (None, why, score): how much of the split named real streets, to report the likeliest."""
    got_on, score = False, 0
    for b in BORO.values():
        for o in keys(idx, b, on):
            got_on = True
            score = max(score, 1 + bool(keys(idx, b, a)) + bool(keys(idx, b, z)))
            for ka in keys(idx, b, a):
                pa = meet(lines, b, o, ka)
                if pa is None: continue
                for kz in keys(idx, b, z):
                    pz = meet(lines, b, o, kz)
                    if pz is None: continue
                    c = path(lines[(b, o)], pa, pz)
                    if c and 10 < LineString(c).length * 85000 < MAXLEN: return [[round(x, 6), round(y, 6)] for x, y in c], None, 9
    if not got_on: return None, 'no centerline for ' + norm(on), 0
    return None, 'no stretch on %s between %s and %s' % (norm(on), norm(a), norm(z)), score


def place(body, year, start, end, lines, idx, bridges):
    """One row's closure: [(coords, street, extent)] and, if nothing placed, why."""
    body = clean(body)
    if ' to ' not in body and '/' in body: body = re.sub(r'\s*/\s*', ' to ', body, count=1)   # "Nassau Avenue Bedford Ave/ Lorimer Street"
    if ' to ' not in body:
        key = next((k for k in list(BRIDGES) + list(DRIVES) + list(TRANSVERSES) if k in body.lower()), None)
        segs = bridges.get(key) if key else None
        if not segs: return [], 'no boundaries and not a known bridge or park road' + (' (none on the centerline by that name)' if key else '')
        parts = [bridge_line(segs)]
        # Named, without the notice's "Upper Level" / "Lower Level": both levels share one centerline.
        return [([[round(x, 6), round(y, 6)] for x, y in g.coords], NAMES[key], '') for g in parts], None
    left, z = body.split(' to ', 1)
    z = re.split(r'\s*/\s*', z)[0]
    w = left.split(' ')
    best = (-1, 'no split placed')
    for k in range(1, len(w)):
        on, a = ' '.join(w[:k]), re.split(r'\s*/\s*', ' '.join(w[k:]))[0]
        coords, why, lvl = run(lines, idx, on, a, z)
        if coords: return [(coords, on, a + ' to ' + z)], None
        if lvl > best[0]: best = (lvl, why)
    return [], best[1]


def bridge_line(segs):
    """One line per bridge, end to end: the route over its roadways between the two ends farthest apart, joining
    segment ends within 8 m (a closure is one line; the parallel roadways and decks would otherwise list the bridge
    dozens of times)."""
    import heapq
    ends = [c for g in segs for c in (g.coords[0], g.coords[-1])]
    rep = list(range(len(ends)))
    def find(i):
        while rep[i] != i: rep[i] = rep[rep[i]]; i = rep[i]
        return i
    for i in range(len(ends)):
        for j in range(i + 1, len(ends)):
            if Point(ends[i]).distance(Point(ends[j])) * 85000 < 8: rep[find(i)] = find(j)
    adj = {}
    for k, g in enumerate(segs):
        a, z, c = find(2 * k), find(2 * k + 1), list(g.coords)
        adj.setdefault(a, []).append((z, g.length, c)); adj.setdefault(z, []).append((a, g.length, c[::-1]))
    def far(s0):
        dist, prev, q = {s0: 0}, {}, [(0, s0)]
        while q:
            d, n = heapq.heappop(q)
            if d > dist[n]: continue
            for m, w, c in adj[n]:
                if d + w < dist.get(m, 1e9): dist[m] = d + w; prev[m] = (n, c); heapq.heappush(q, (d + w, m))
        return max(dist, key=dist.get), prev
    a, _ = far(next(iter(adj)))           # the farthest node from anywhere, then the farthest from that: the longest route
    z, prev = far(a)
    edges, n = [], z
    while n != a: n, c = prev[n]; edges.append(c)
    edges.reverse()                       # walked back from z: each edge runs from the node before it, so a to z in order
    c = edges[0] + [pt for e in edges[1:] for pt in e[1:]]
    return LineString(c)


def bridge_lines(rows):
    """{notice key: [LineString]} from centerline rows (full_street_name, boroughcode, the_geom), and the same
    segments under (borough, name) for streets that meet a bridge."""
    by, named = {}, {}
    for r in rows:
        full = r.get('full_street_name') or ''
        key = next((k for k, v in BRIDGES.items() if v == full), None) or \
              (next((k for k, v in DRIVES.items() if v == full), None) if r.get('boroughcode') == '1' else None) or \
              (transverse_key(full) if r.get('boroughcode') == '1' else None)
        g = r.get('the_geom') or {}
        for part in (g.get('coordinates') or []) if g.get('type') == 'MultiLineString' else [g.get('coordinates')] if g.get('type') == 'LineString' else []:
            if key and part and len(part) > 1:
                L = LineString(part); by.setdefault(key, []).append(L)
                named.setdefault((r.get('boroughcode'), norm(r['full_street_name'])), []).append(L)
    return by, named

ORDINAL = lambda s: re.sub(r'\b(\d+)\b(?!(?:st|nd|rd|th))', lambda m: m.group(1) + ('th' if 10 <= int(m.group(1)) % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(int(m.group(1)) % 10, 'th')), s)

for year in [CFG['year'], CFG.get('test')]:
    if not year: continue
    url, pdf = fetch_pdf(year)
    if not pdf: print(year, ': no notice yet'); continue
    text = '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(pdf)).pages)
    open(os.path.join(OUT, f'marathon_{year}.txt'), 'w').write(text)
    parsed, skipped = [], []
    for r in rows_of(text):
        m = ROW.match(r)
        if not m: skipped.append(r); continue
        start, end = when(m['when'], year)
        kind = CLOSE.get(m['restr'].lower())
        if not kind: continue
        if not start: skipped.append(r); continue
        parsed.append((m['body'], start, end))
    # Every street any split could name, then the centerline for them, and the bridges by name.
    names = set()
    for body, _, _ in parsed:
        b = clean(body)
        if ' to ' not in b: continue
        left, z = b.split(' to ', 1)
        w = left.split(' ')
        names.add(core(norm(re.split(r'\s*/\s*', z)[0])))
        for k in range(1, len(w)):
            names.add(core(norm(' '.join(w[:k])))); names.add(core(norm(re.split(r'\s*/\s*', ' '.join(w[k:]))[0])))
    names |= {'OF THE AMERICAS', 'FDR', 'CENTRAL', 'COLUMBUS'} | {core(v) for v in FIX.values()} | {v.split(' ')[0] for v in FIX.values()}
    lines = fetch_lines(names)
    q = ("full_street_name in(%s) OR (boroughcode='1' AND (upper(full_street_name) like '%%TRANSVERSE%%' OR upper(full_street_name) like '%%TRAVERSE%%'))"
         % ','.join("'" + v + "'" for v in list(BRIDGES.values()) + list(DRIVES.values())))
    rows = json.load(urllib.request.urlopen(urllib.request.Request(CL_API + '?' + urllib.parse.urlencode({'$select': 'full_street_name,boroughcode,the_geom', '$where': q, '$limit': 5000}), headers=UA), timeout=180))
    bridges, named = bridge_lines(rows)
    print('  transverse names on the centerline:', sorted({(r_.get('full_street_name'), transverse_key(r_.get('full_street_name') or '')) for r_ in rows if r_.get('boroughcode') == '1' and 'TRAV' in (r_.get('full_street_name') or '').upper() or 'TRANSV' in (r_.get('full_street_name') or '').upper()}))
    for k, v in named.items(): lines.setdefault(k, []).extend(v)
    lines, idx = prepare(lines)
    for k, segs in bridges.items(): print('  bridge', k, ':', len(segs), 'segments,', round(sum(s.length for s in segs) * 85000), 'm')
    permits, misses, seen = [], [], set()
    for i, (body, start, end) in enumerate(parsed):
        got, why = place(body, year, start, end, lines, idx, bridges)
        if not got: misses.append('%s | %s' % (body, why)); continue
        for j, (coords, on, extent) in enumerate(got):
            if (str(coords), start, end) in seen: continue      # the bridges' upper and lower levels share a centerline
            seen.add((str(coords), start, end))
            permits.append({'id': 'nycm-%d-%d-%d' % (year, i, j), 'street': ORDINAL(on), 'extent': ORDINAL(extent), 'kind': 'closed', 'both': True,
                            'start': start, 'end': end, 'who': CFG['organizer'],
                            'desc': 'Street closed for the %s (City of New York closure notice).' % CFG['name'], 'coords': coords})
    json.dump({'year': year, 'source': url, 'fetched': time.strftime('%Y-%m-%d'), 'name': CFG['name'], 'permits': permits, 'misses': misses},
              open(os.path.join(OUT, f'marathon_{year}.json'), 'w'), indent=0)
    print(year, ':', len(parsed), 'closure rows,', len(permits), 'placed,', len(misses), 'not placed,', len(skipped), 'lines not read as rows')
    for m in misses: print('   not placed:', m)
    for s in skipped[:30]: print('   skipped:', s)
