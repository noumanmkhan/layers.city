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
    split is tried on the centerline until one places. Bridges named without boundaries are matched by name.
  - The borough headings in the PDF run together (Brooklyn's rows sit under the Bronx heading), so placement tries
    every borough.

Writes raw/closures/marathon_<year>.txt (the notice's text) and marathon_<year>.json ({year, source, fetched, name,
permits, misses}), for the race year once the City has posted it, and for marathon.json's "test" year (a past
notice, to check the parser; fetch_closures.py only ever uses the race year).
"""
import io, json, os, re, time, urllib.parse, urllib.request
from pypdf import PdfReader
from shapely.geometry import LineString
from centerline import CL_API, UA, core, norm, fetch_lines, stretch

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
BRIDGES = [('verraz', "upper(full_street_name) like '%VERRAZ%'"), ('pulaski', "upper(full_street_name) like '%PULASKI%'"),
           ('queensboro', "upper(full_street_name) like '%QUEENSBORO%'"), ('willis avenue bridge', "upper(full_street_name) like '%WILLIS AVE%BR%'"),
           ('madison avenue bridge', "upper(full_street_name) like '%MADISON AVE%BR%'")]


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


def place(body, year, start, end, lines, bridges):
    """One row's closure: [(coords, street, extent)] and, if nothing placed, why."""
    body = clean(body)
    if ' to ' not in body:
        key = next((k for k, _ in BRIDGES if k in body.lower()), None)
        segs = bridges.get(key) if key else None
        if not segs: return [], 'no boundaries and not a known bridge'
        return [([[round(x, 6), round(y, 6)] for x, y in s.coords], body, '') for s in segs], None
    left, z = body.split(' to ', 1)
    z = re.split(r'\s*/\s*', z)[0]
    w = left.split(' ')
    why = 'no split placed'
    for k in range(1, len(w)):
        on, a = ' '.join(w[:k]), re.split(r'\s*/\s*', ' '.join(w[k:]))[0]
        coords, why = stretch(lines, None, on, a, z)
        if coords: return [(coords, on, a + ' to ' + z)], None
    return [], why


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
    lines = fetch_lines(names)
    bridges = {}
    for key, where in BRIDGES:
        got = json.load(urllib.request.urlopen(urllib.request.Request(CL_API + '?' + urllib.parse.urlencode({'$select': 'full_street_name,the_geom', '$where': where, '$limit': 500}), headers=UA), timeout=180))
        segs = []
        for g in got:
            geo = g.get('the_geom') or {}
            for part in (geo.get('coordinates') or []) if geo.get('type') == 'MultiLineString' else [geo.get('coordinates')] if geo.get('type') == 'LineString' else []:
                if part and len(part) > 1: segs.append(LineString(part))
        bridges[key] = segs
        print('  bridge', key, ':', len(segs), 'segments,', round(sum(s.length for s in segs) * 85000), 'm of centerline;', sorted({g.get('full_street_name') for g in got})[:6])
    permits, misses = [], []
    for i, (body, start, end) in enumerate(parsed):
        got, why = place(body, year, start, end, lines, bridges)
        if not got: misses.append('%s | %s' % (body, why)); continue
        for j, (coords, on, extent) in enumerate(got):
            permits.append({'id': 'nycm-%d-%d-%d' % (year, i, j), 'street': ORDINAL(on), 'extent': ORDINAL(extent), 'kind': 'closed', 'both': True,
                            'start': start, 'end': end, 'who': CFG['organizer'],
                            'desc': 'Street closed for the %s (City of New York closure notice).' % CFG['name'], 'coords': coords})
    json.dump({'year': year, 'source': url, 'fetched': time.strftime('%Y-%m-%d'), 'name': CFG['name'], 'permits': permits, 'misses': misses},
              open(os.path.join(OUT, f'marathon_{year}.json'), 'w'), indent=0)
    print(year, ':', len(parsed), 'closure rows,', len(permits), 'placed,', len(misses), 'not placed,', len(skipped), 'lines not read as rows')
    for m in misses: print('   not placed:', m)
    for s in skipped[:30]: print('   skipped:', s)
