"""What's changing here: build docs/<city>/data/changes.geojson from cities/<city>/raw/changes/
(engine/fetch_changes.py) for the "changes" layer and the card's Changing nearby section.

Big changes only (Vancouver: issued permits only, all "approved"): new buildings that aren't single houses, demolitions of buildings that aren't houses,
and (Toronto) rezoning, site plan and subdivision applications, (New York) land-use applications that rezone,
(San Francisco) every project in Planning's Development Pipeline with 3+ homes or 10,000+ sq ft of other space. Each item gets:
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
    t = t[:1].upper() + t[1:]
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
        # Permits never closed out stay "Inspection" for years: under way only if issued in the last open_years,
        # issued-not-started only within approved_years, under review only within open_years.
        if stage == 'building' and (r['ISSUED_DATE'] or '')[:10] < ago(OPEN_Y): continue
        if stage == 'approved' and (r['ISSUED_DATE'] or r['APPLICATION_DATE'] or '')[:10] < ago(APPR_Y): continue
        if stage == 'proposed' and (r['APPLICATION_DATE'] or '')[:10] < ago(OPEN_Y): continue
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
        if stage == 'building' and (r.get('issue_date') or '')[:10] < ago(OPEN_Y): continue
        if kind == 'demolition' and stage == 'building': stage = 'approved' if 'ISSUED' in ms else 'building'
        m = re.search(r'(\d+)\s*(?:D\.?\s?U\.?|DWELLING UNITS?|RESIDENTIAL UNITS?|UNITS?)\b', t)
        clean = rx['noise'].sub(' ', t).strip(' .:-*;,/')
        items.append({'k': kind, 's': stage, 'date': (r.get('issue_date') or '')[:10], 'dl': 'issued',   # Chicago's permits carry no completion date
                      'a': address(r.get('street_number'), r.get('street_name'), '', r.get('street_direction')), 'd': short(sentence(clean)),
                      'n': r.get('permit_'), 'at': [round(float(r['longitude']), 6), round(float(r['latitude']), 6)],
                      'units': int(m.group(1)) if m else None, 'cost': int(float(r['reported_cost'])) if r.get('reported_cost') else None, 'status': st.title()})

# ---------- Vancouver: issued building permits ----------
if os.path.exists(p) and city == 'vancouver':
    # Every permit in the file is issued (the City publishes no applications): stage "approved", dated by its issue.
    # Kept: new buildings filed as high-density housing or commercial that aren't multiplexes, and demolitions of
    # anything but houses. Houses, laneway houses, duplexes and multiplexes are the small jobs Toronto leaves out.
    HOUSES = {'Single Detached House', 'Single Detached House w/Sec Suite', 'Duplex', 'Duplex w/Secondary Suite', 'Laneway House',
              'Dwelling Unit', 'Infill', 'Infill Single Detached House', 'Secondary Suite', 'Lock -off Unit', 'Not Applicable'}
    UNITS = re.compile(r'(\d+)\s*(?:-\s*)?(?:secured\s+|market\s+|rental\s+|social\s+|residential\s+|dwelling\s+|strata\s+|housing\s+)*units?\b', re.I)
    for r in json.load(open(p))['rows']:
        if r.get('lat') is None: continue
        desc = re.sub(r'\s+', ' ', r.get('projectdescription') or '').strip()
        uses = set(r.get('specificusecategory') or [])
        if r['typeofwork'] == 'New Building':
            if desc.startswith('Low Density Housing') or re.search(r'multiplex|laneway', desc, re.I) or uses <= HOUSES: continue
            kind = 'building'
        else:
            if not uses or uses <= HOUSES | {'Multiple Conversion Dwelling'}: continue
            kind = 'demolition'
        d = re.sub(r'^.*?-\s*(New Building|Demolition / Deconstruction)\s*-\s*', '', desc)
        d = re.sub(r'\*+[^*]*\*+|Building Permit for BP-\d{4}-\d+|\bBP-\d{4}-\d+\b|\(?Revision.*$|This is a CP Process Permit.*$|Demo Declaration.*$|\bPart [59]( Design)?\b[: -]*', ' ', d, flags=re.I)
        # Contractors' and people's names, and the permit's conditions, never go on the map.
        d = re.split(r'\b(Demo(lition)?\s*(Contractor|Declaration|Declared|by)?\s*[:–-]|Contractor\s*:|(as per |by |per )?engineered demolition|submitted by|provided by|prepared by|Ok for field review|BRB Notes|Conditions?\s*:|Note\s*:|\s1[.)]\s)', d, maxsplit=1, flags=re.I)[0]
        d = re.sub(r'\s+', ' ', d).strip(' .:-*;,')
        if re.search(r'one-family|single[- ]detached|single[- ]family|two-family|duplex|infill', d, re.I): continue
        if not d: d = 'New building' if kind == 'building' else 'Demolition'
        m = UNITS.search(desc)
        a = re.sub(r',\s*Vancouver.*$', '', r.get('address') or '', flags=re.I)
        a = re.sub(r'\b(AVENUE|AV)\b', 'AVE', a.upper()); a = re.sub(r'\bSTREET\b', 'ST', a); a = re.sub(r'\bDRIVE\b', 'DR', a); a = re.sub(r'\bBOULEVARD\b', 'BLVD', a)
        a = re.sub(r'\b(\d+)(St|Nd|Rd|Th)\b', lambda x: x.group(1) + x.group(2).lower(), title_case(a))
        units = int(m.group(1)) if m and kind == 'building' and 1 < int(m.group(1)) < 3000 else None
        items.append({'k': kind, 's': 'approved', 'date': (r.get('issuedate') or '')[:10], 'dl': 'issued', 'a': a, 'd': short(d),
                      'n': r.get('permitnumber'), 'at': [round(float(r['lon']), 6), round(float(r['lat']), 6)], 'units': units})

# ---------- New York: DOB NOW job filings (new buildings, full demolitions) ----------
p = os.path.join(RAW, 'dobnow.json')
if os.path.exists(p):
    # One job is filed once and then amended (job_filing_number "M00123456-I1", "-S1", "-P2"...): the latest status per
    # job. Stages from the filing status; a job held, withdrawn or denied is left out. Houses (new one- and two-family
    # buildings, and demolitions of them) are the small jobs Toronto leaves out too.
    S = B.get('dobnow', {})
    STAGE = {'Approved': 'approved', 'PAA Approved': 'approved', 'Permit Entire': 'building', 'Permit Issued': 'building',
             'LOC Issued': 'finished', 'CO Issued': 'finished', 'Full Demolition Signed-off': 'finished'}
    REVIEW = re.compile(r'Review|Pending|Objections|Incomplete|Assignment|QA', re.I)
    HOUSE = re.compile(r'\b(one|two|1|2)[- ]?(family|fam\.?)\b|single[- ]family|\bduplex\b|\b1 ?& ?2 family|\b[12]-?fam', re.I)
    ACC = re.compile(r'\b(garages?|sheds?|carports?|cabanas?|pool houses?|bulkheads?|fences?|parking lot)\b', re.I)
    CORE = re.compile(r'\b(dwelling|residential|apartments?|mixed[- ]use|commercial|school|hotel|office|units?|store|retail|community facility|warehouse|church|hospital)\b', re.I)
    # Numbered streets as people write them: "5 Avenue" -> "5th Avenue", "East 158 Street" -> "East 158th Street".
    ORD = lambda a: re.sub(r'\b(\d+) (Street|Avenue|Road|Place|Drive|Terrace|Court|Lane|Walk)\b', lambda m: m.group(1) + ('th' if 10 <= int(m.group(1)) % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(int(m.group(1)) % 10, 'th')) + ' ' + m.group(2), a)
    jobs, first = {}, {}
    for r in json.load(open(p))['rows']:
        j, _, suf = (r.get('job_filing_number') or '').partition('-')
        if not j or not r.get('latitude'): continue
        if suf.startswith('I') and r.get('job_description'): first[j] = r['job_description']   # the initial filing says what the job is
        last = max(r.get(k) or '' for k in ('current_status_date', 'signoff_date', 'first_permit_date', 'approved_date', 'filing_date'))
        if j not in jobs or last > jobs[j][0]: jobs[j] = (last, r)
    num = lambda v: int(float(v)) if v not in (None, '') and re.match(r'^-?\d+(\.\d+)?$', str(v).strip()) else None
    for j, (last, r) in jobs.items():
        st = (r.get('filing_status') or '').strip()
        stage = STAGE.get(st) or ('proposed' if REVIEW.search(st) else None)
        if not stage: continue
        kind = 'demolition' if r['job_type'] == 'Full Demolition' else 'building'
        desc = re.sub(r'\s+', ' ', first.get(j) or r.get('job_description') or '').strip()
        new_u, old_u = num(r.get('proposed_dwelling_units')), num(r.get('existing_dwelling_units'))
        if kind == 'building' and ((new_u is not None and 0 < new_u <= 2) or (not new_u and HOUSE.search(desc))): continue
        if ACC.search(desc) and not CORE.search(desc): continue   # a garage or shed on its own
        if kind == 'demolition' and ((old_u is not None and 0 < old_u <= 2) or HOUSE.search(desc)): continue
        filed, perm, done = r.get('filing_date') or '', r.get('first_permit_date') or r.get('approved_date') or '', r.get('signoff_date') or r.get('current_status_date') or ''
        if stage == 'finished' and done < ago(WIN): continue
        if stage == 'building' and perm < ago(OPEN_Y): continue
        if stage == 'approved' and (r.get('approved_date') or filed) < ago(APPR_Y): continue
        if stage == 'proposed' and filed < ago(OPEN_Y): continue
        date, dl = (done, 'finished') if stage == 'finished' else (perm, 'issued') if stage == 'building' and perm else (filed, 'applied')
        if not desc: desc = 'New building' if kind == 'building' else 'Demolition'
        stories = num(r.get('proposed_no_of_stories'))
        if kind == 'building' and stories and stories > 1 and 'stor' not in desc.lower(): desc = '%d-story building. %s' % (stories, desc)
        items.append({'k': kind, 's': stage, 'date': date[:10], 'dl': dl, 'a': ORD(address(r.get('house_no'), r.get('street_name'))),
                      'd': short(sentence(desc) if sum(c.isupper() for c in desc) > 0.6 * sum(c.isalpha() for c in desc) else desc),   # mostly capitals 'n': (r.get('job_filing_number') or '').split('-')[0],
                      'at': [round(float(r['longitude']), 6), round(float(r['latitude']), 6)],
                      'units': new_u if kind == 'building' and new_u and new_u > 2 else None, 'status': st})

# ---------- New York: land-use applications that rezone (ZAP) ----------
p = os.path.join(RAW, 'zap.json')
if os.path.exists(p):
    # Active projects are proposals (filed, or in public review: certified, at the community board, borough
    # president, City Planning Commission or City Council); completed ones count as approved, dated by their
    # completion (ZAP keeps the decision date, unlike Toronto's open data). Withdrawn, terminated, on-hold and
    # closed records are left out. A project covering many lots (an area rezoning) sits at the middle of them.
    ZDONE = re.compile(r'^Complet', re.I)
    zs = collections.Counter()
    for r in json.load(open(p))['rows']:
        st, ps = r.get('project_status') or '', r.get('public_status') or ''
        zs[(st, ps)] += 1
        filed, done = (r.get('app_filed_date') or r.get('certified_referred') or '')[:10], (r.get('completed_date') or '')[:10]
        if st == 'Active':
            if filed and filed < ago(OPEN_Y): continue
            stage, date, dl = 'proposed', filed or (r.get('current_milestone_date') or '')[:10], 'applied'
        elif ZDONE.match(st) and done:
            if done < ago(APPR_Y): continue
            stage, date, dl = 'approved', done, 'decided'
        else: continue
        name = re.sub(r'\s+', ' ', r.get('project_name') or '').strip()
        brief = re.sub(r'\s+', ' ', r.get('project_brief') or '').strip()
        # Who applied stays out (as with building filings): drop "X LLC is requesting", "is being sought by X", "represented by X".
        m = re.search(r'\b(?:(?:is|are) (?:requesting|proposing|seeking|applying for)|seeks?|requests?|proposes?|requesting)\s+(?=an?\b|the\b|[a-z]*\s*(?:zoning|ZM|ZR|rezon|minor|special|actions?))', brief)
        if m and m.start() < 160: brief = brief[m.end():]
        brief = re.sub(r',?\s*(?:is|are) being (?:sought|requested|proposed) by .*?(?=,? (?:at|in|on|to|for) |\.|$)', '', brief)
        brief = re.sub(r'^This is an? (?:private |public )?application (?:by|from) .*?\b(?:for|requesting|seeking|to)\s+', '', brief, flags=re.I)
        brief = re.sub(r'^The (?:private )?applicant,? [^,]*?,? (?:seeks|requests|proposes|is seeking|is requesting)\s+', '', brief, flags=re.I)
        brief = re.sub(r',?\s*(?:by|from|on behalf of) (?:the )?[A-Z0-9][^,.;]*?\b(?:LLC|L\.L\.C|Inc|Corp|Corporation|L\.?P|Associates|Holdings|Partners|Realty|Development|Company|Co)\b\.?,?', '', brief)
        brief = re.sub(r',?\s*represented by [^,.;]*', '', brief)
        brief = re.sub(r',?\s*(?:a|the) (?:private|public) applicant,?', '', brief)
        brief = brief[:1].upper() + brief[1:]
        lots = r.get('lots') or 0
        a = title_case(r['addr']) if r.get('addr') and lots <= 3 else (name or 'Area rezoning')
        d = brief or name
        if lots > 3: d = ('%d lots. ' % lots) + d
        items.append({'k': 'rezoning', 's': stage, 'date': date, 'dl': dl, 'a': a, 'd': short(d), 'n': r['project_id'],
                      'u': 'https://zap.planning.nyc.gov/projects/' + r['project_id'], 'at': r['at'], 'status': ps or st})
    print('  ZAP status counts:', dict(zs.most_common(20)))

# ---------- San Francisco: Planning's Development Pipeline ----------
p = os.path.join(RAW, 'pipeline.json')
if os.path.exists(p):
    # The pipeline lists only projects still under way, each at its latest step: a Planning or building permit
    # application filed (proposed), Planning approval or a building permit approved or issued (approved), or
    # construction (building). The date is the date it reached that step. Projects below the config's size
    # (homes or non-residential square feet) are left out, as are any whose status the build doesn't know.
    S = B.get('pipeline', {})
    num = lambda v: float(v) if v not in (None, '') and re.match(r'^-?\d+(\.\d+)?$', str(v).strip()) else 0
    stat, unknown = collections.Counter(), collections.Counter()
    for r in json.load(open(p))['rows']:
        st = (r.get('current_status') or '').strip()
        if not r.get('latitude'): continue
        # New homes, net of any removed (proposed_units counts the whole building, so an ADU in a 28-unit block is 29).
        units = int(num(r.get('net_pipeline_units')) if r.get('net_pipeline_units') not in (None, '') else num(r.get('proposed_units')) - num(r.get('existing_units')))
        sqft = num(r.get('non_residential_total_gsf'))
        if units < S.get('minUnits', 3) and sqft < S.get('minSqft', 10000): continue
        date = (r.get('current_status_date') or '')[:10]
        if re.match(r'BP\b.*filed', st, re.I) and r.get('approved_date_planning'):   # Planning approved it; building permit under review
            stage, dl, date = 'approved', 'decided', r['approved_date_planning'][:10]
        elif re.search(r'filed', st, re.I): stage, dl = 'proposed', 'applied'
        elif re.match(r'PL\b.*approv', st, re.I): stage, dl = 'approved', 'decided'
        elif re.search(r'approv|issued|reinstat', st, re.I): stage, dl = 'approved', 'issued'
        elif re.search(r'construct', st, re.I): stage, dl = 'building', 'started'
        elif re.search(r'complet', st, re.I): stage, dl = 'finished', 'finished'
        else: unknown[st] += 1; continue
        if stage == 'proposed' and date < ago(OPEN_Y): continue
        if stage == 'approved' and date < ago(APPR_Y): continue
        if stage == 'finished' and date < ago(WIN): continue
        stat[st] += 1
        a = re.sub(r'\s+', ' ', r.get('nameaddr') or '').strip()
        if a.isupper(): a = re.sub(r'\b(\d+)(St|Nd|Rd|Th)\b', lambda m: m.group(1) + m.group(2).lower(), title_case(a))
        d = r.get('description_planning') or r.get('description_dbi') or ('New building' if units else 'Non-residential project')
        d = re.sub(r'\s*\*\*.*$', '', d).rstrip('…').strip() or ('New building' if units else 'Non-residential project')   # "** planner: note" staff notes
        items.append({'k': 'building', 's': stage, 'date': date, 'dl': dl, 'a': a, 'd': short(sentence(d) if d.isupper() else d),
                      'n': next((v for v in (r.get('case_no'), r.get('bpa_no')) if v and re.search(r'\d', v)), None), 'at': [round(float(r['longitude']), 6), round(float(r['latitude']), 6)],
                      'units': units if units >= 3 else None, 'status': st})
    print('  pipeline statuses kept:', dict(stat.most_common()), '· unknown, left out:', dict(unknown))

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
