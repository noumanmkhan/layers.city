"""What's changing here: build docs/<city>/data/changes.geojson from cities/<city>/raw/changes/
(engine/fetch_changes.py) for the "changes" layer and the card's Changing nearby section.

Big changes only: new buildings that aren't single houses, demolitions of buildings that aren't houses,
and (Toronto) rezoning, site plan and subdivision applications. Each item gets:
  - a kind: rezoning, siteplan, subdivision (applications), building (new building), demolition;
  - a stage: proposed (an application or permit under review), approved (approved or permit issued, work
    not started), building (permit inspections under way: work started), finished (closed or occupancy
    granted, in the window); anything withdrawn, refused, cancelled, expired or suspended is left out;
  - its date, address, a short description and, for Toronto applications, the City's application page.

The window: everything still open (applications open up to `open_years` old), plus anything approved in the
last `approved_years` (judged by the application date: the open data has no decision date) and anything
finished in the last `years`. Items within 35 m of each other are one site: the furthest-along item leads
and the others are listed under it ("also"). Nothing is ranked: stages describe where a project is.

Usage: python3 engine/changes.py <city>
"""
import collections, datetime as dt, json, math, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
city = sys.argv[1]
CFG = json.load(open(os.path.join(ROOT, 'cities', city, 'changes.json')))
RAW = os.path.join(ROOT, 'cities', city, 'raw', 'changes')
OUT = os.path.join(ROOT, 'docs', city, 'data', 'changes.geojson')
B = CFG.get('build', {})
TODAY = dt.date.today()
ago = lambda y: (TODAY - dt.timedelta(days=round(365.25 * y))).isoformat()
WIN, OPEN_Y, APPR_Y = B.get('years', 2), B.get('open_years', 6), B.get('approved_years', 4)
ORDER = {'proposed': 0, 'approved': 1, 'building': 2, 'finished': 3}
ABBR = {'ST': 'St', 'AVE': 'Ave', 'RD': 'Rd', 'BLVD': 'Blvd', 'DR': 'Dr', 'CRES': 'Cres', 'CRT': 'Crt', 'PL': 'Pl', 'TER': 'Ter', 'PKWY': 'Pkwy',
        'LANE': 'Lane', 'GT': 'Gt', 'SQ': 'Sq', 'WAY': 'Way', 'CIR': 'Cir', 'HTS': 'Hts', 'GDNS': 'Gdns', 'TRL': 'Trl', 'PK': 'Park', 'CT': 'Ct', 'HWY': 'Hwy'}


def title_case(w):
    w = w.strip()
    if not w: return ''
    def one(x):
        if x in ABBR: return ABBR[x]
        if x.isdigit(): return x
        m = re.match(r'^(\d+)(ST|ND|RD|TH)$', x)
        return m.group(1) + m.group(2).lower() if m else x.capitalize()
    return ' '.join(one(x) for x in w.upper().split())


def address(num, name, typ='', d=''):
    num = (num or '').strip()
    name = title_case(name or '')
    name = re.sub(r'\b(\d+)(St|Nd|Rd|Th)\b', lambda m: m.group(1) + m.group(2).lower(), name)
    parts = [num, title_case(d) if d and len(d.strip()) == 1 and city == 'chicago' else '', name, ABBR.get((typ or '').strip().upper(), title_case(typ or '')),
             (d or '').strip().upper() if d and city != 'chicago' else '']
    return ' '.join(p for p in parts if p)


def sentence(t):
    """Chicago's descriptions are in capitals: lower-case them, keep units and codes readable."""
    t = t.lower()
    t = re.sub(r'(^|[.!?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), t)
    for k in ('cbc', 'cbrc', 'sf', 'ft', 'd.u.', 'du', 'sfr'):
        t = re.sub(r'\b' + re.escape(k) + r'\b', k.upper() if k not in ('ft',) else k, t)
    return t


def short(t, n=170):
    t = re.sub(r'\s+', ' ', (t or '').strip())
    t = re.sub(r'\[.*$', '', t).strip()          # Toronto revisions append the original text in brackets
    if len(t) <= n: return t
    cut = t[:n]
    m = max(cut.rfind('. '), cut.rfind('; '))
    return (cut[:m + 1] if m > 60 else cut.rsplit(' ', 1)[0] + '…').strip()


items = []

# ---------- Toronto: development applications ----------
p = os.path.join(RAW, 'devapps.json')
if os.path.exists(p):
    S = B['devapps']
    for r in json.load(open(p))['rows']:
        kind = S['types'].get(r['APPLICATION_TYPE'])
        stage = S['stages'].get(r['STATUS'].strip())
        sub = (r['DATE_SUBMITTED'] or '')[:10]
        if not kind or not stage or not r['ll']: continue
        if stage == 'proposed' and sub < ago(OPEN_Y): continue
        if stage == 'approved' and sub < ago(APPR_Y): continue
        ll = r['ll'].get('2019') or r['ll'].get(2019)
        items.append({'k': kind, 's': stage, 'date': sub, 'dl': 'applied', 'a': address(r['STREET_NUM'], r['STREET_NAME'], r['STREET_TYPE'], r['STREET_DIRECTION']),
                      'd': short(r['DESCRIPTION']), 'u': r['APPLICATION_URL'].replace('http://', 'https://'), 'n': r['APPLICATION#'], 'at': ll,
                      'status': r['STATUS'].strip()})

# ---------- Toronto: building permits ----------
p = os.path.join(RAW, 'permits.json')
if os.path.exists(p) and city == 'toronto':
    S = B['permits']
    for r in json.load(open(p))['rows']:
        stage = S['stages'].get(r['STATUS'].strip())
        if not stage: continue
        if stage == 'finished' and (r['COMPLETED_DATE'] or '')[:10] < ago(WIN): continue
        kind = 'demolition' if r['WORK'] == 'Demolition' else 'building'
        try: units = int(float(r['DWELLING_UNITS_CREATED'] or 0))
        except ValueError: units = 0
        date, dl = ((r['COMPLETED_DATE'], 'finished') if stage == 'finished' else (r['ISSUED_DATE'], 'issued') if r['ISSUED_DATE'] else (r['APPLICATION_DATE'], 'applied'))
        items.append({'k': kind, 's': stage, 'date': (date or '')[:10], 'dl': dl, 'a': address(r['STREET_NUM'], r['STREET_NAME'], r['STREET_TYPE'], r['STREET_DIRECTION']),
                      'd': short(r['DESCRIPTION']), 'n': r['PERMIT_NUM'], 'at': r['ll'], 'units': units or None, 'use': r['STRUCTURE_TYPE'] if kind == 'building' else r['CURRENT_USE'],
                      'status': r['STATUS'].strip()})

# ---------- Chicago: building permits ----------
if os.path.exists(p) and city == 'chicago':
    S = B['permits']
    rx = {k: re.compile(S[k], re.I) for k in ('always', 'accessory', 'core', 'house', 'multi', 'noise')}
    for r in json.load(open(p))['rows']:
        t = (r.get('work_description') or '').upper()
        if not r.get('latitude') or rx['always'].search(t): continue
        if rx['accessory'].search(t) and not rx['core'].search(t): continue     # a garage, deck or fence on its own
        house, multi = rx['house'], rx['multi']
        kind = 'demolition' if 'WRECK' in r['permit_type'] else 'building'
        if house.search(t) and not multi.search(t): continue
        st, ms = (r.get('permit_status') or ''), (r.get('permit_milestone') or '')
        stage = S['stages'].get(st + '|' + ms) or S['stages'].get(st)
        if not stage: continue
        if kind == 'demolition' and stage == 'building': stage = 'approved' if 'ISSUED' in ms else 'building'
        m = re.search(r'(\d+)\s*(?:D\.?\s?U\.?|DWELLING UNITS?|RESIDENTIAL UNITS?|UNITS?)\b', t)
        clean = rx['noise'].sub(' ', t).strip(' .:-*;,/')
        items.append({'k': kind, 's': stage, 'date': (r.get('issue_date') or '')[:10], 'dl': 'finished' if stage == 'finished' else 'issued',
                      'a': address(r.get('street_number'), r.get('street_name'), '', r.get('street_direction')), 'd': short(sentence(clean)),
                      'n': r.get('permit_'), 'at': [round(float(r['longitude']), 6), round(float(r['latitude']), 6)],
                      'units': int(m.group(1)) if m else None, 'cost': int(float(r['reported_cost'])) if r.get('reported_cost') else None, 'status': st.title()})

# ---------- one site per place ----------
def metres(a, b):
    return math.hypot((a[0] - b[0]) * 111320 * math.cos(math.radians(a[1])), (a[1] - b[1]) * 110570)

sites, grid = [], collections.defaultdict(list)
cell = lambda ll: (round(ll[0] / .0006), round(ll[1] / .0004))
for it in sorted(items, key=lambda i: (-ORDER[i['s']], -int(i['date'].replace('-', '') or 0))):
    c = cell(it['at']); host = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for s in grid[(c[0] + dx, c[1] + dy)]:
                if metres(s['at'], it['at']) <= 35: host = s; break
            if host: break
        if host: break
    if host: host.setdefault('also', []).append(it)
    else: sites.append(it); grid[c].append(it)

feats = []
for s in sites:
    pr = {k: s[k] for k in ('k', 's', 'date', 'dl', 'a', 'd') if s.get(k)}
    for k in ('u', 'n', 'units', 'status'):
        if s.get(k): pr[k] = s[k]
    # A demolition and a new building on one site: say both ("Demolition, then new building").
    if s.get('also'):
        pr['also'] = [[a['k'], a['s'], a['date'][:7], a.get('u') or ''] for a in s['also'][:6]]
        if not s.get('u'):
            u = next((a['u'] for a in s['also'] if a.get('u')), None)
            if u: pr['u'] = u
    feats.append({'type': 'Feature', 'properties': pr, 'geometry': {'type': 'Point', 'coordinates': s['at']}})
fetched = max((json.load(open(os.path.join(RAW, f)))['fetched'] for f in os.listdir(RAW) if f.endswith('.json')), default=TODAY.isoformat())
json.dump({'type': 'FeatureCollection', 'asof': fetched, 'window': WIN, 'features': feats}, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
print(f'{city}: {len(items)} items → {len(feats)} sites · {os.path.getsize(OUT) // 1024} KB')
print('  by kind/stage:', dict(collections.Counter((f['properties']['k'], f['properties']['s']) for f in feats).most_common()))
