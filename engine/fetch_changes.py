"""What's changing here: fetch a city's development applications and building permits into
cities/<city>/raw/changes/ for engine/changes.py. Runs in GitHub Actions (fetch-changes.yml, weekly);
the sandbox can't reach these servers. Sources are set in cities/<city>/changes.json.

Kinds of source:
  - "ckan_devapps" (Toronto): the City's Development Applications (Community Planning and Committee of
    Adjustment, 2008 on). Kept: every row submitted in the last `years` years or not in a closed status,
    without the planner's contact fields. X/Y are MTM zone 10; converted to lon/lat here.
  - "ckan_permits" (Toronto): Building Permits, active and cleared. Kept: rows whose PERMIT_TYPE or WORK is
    in the config's lists, active or cleared within `years` years. These have no coordinates: each is
    placed on the City's Address Points by GEO_ID (an address point id), or else by its street address.
    Builder names are left out.
  - "socrata_permits" (Chicago): Building Permits issued in the last `years` years whose permit_type is in
    the config's list. Owner and contractor names are left out.
  - "socrata_dobnow" (New York): DOB NOW Job Application Filings whose job_type is in the config's "types" (new
    buildings, full demolitions). All of them are fetched (the dates are text fields, so the window is applied in
    changes.py). Owner, applicant and filing representative names are never requested.
  - "socrata_zap" (New York): City Planning's land-use applications (ZAP Project Data) whose actions include a
    zoning map amendment (ZM: a rezoning), filed in the last `years` years or still active. The open data has no
    coordinates, so each project's tax lots (ZAP BBL, spec "bbl_url") are placed on PLUTO's lot positions (spec
    "pluto_url"), and the project at the middle of its lots. Applicant names are never requested.
  - "ods_permits" (Vancouver): Issued Building Permits (Opendatasoft "portal", "dataset") issued in the last
    `years` years whose typeofwork is in the config's "types". Applicant and contractor names and addresses are
    never requested.

  - "socrata_sfpipeline" (San Francisco): Planning's quarterly Development Pipeline, every project with a
    Planning or building permit application still in the pipeline (filed, approved, permitted or under
    construction), with its homes and non-residential floor area and a point. The planner's, sponsor's and
    contact's fields are never requested.

Writes raw/changes/<source>.json: {fetched, source, rows: [...]}. Prints counts by type and status (and
how many permits were placed) so the build's filters can be checked against the data.

Usage: python3 engine/fetch_changes.py <city>
"""
import collections, csv, datetime as dt, io, json, os, re, sys, time, urllib.parse, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
city = sys.argv[1]
CFG = json.load(open(os.path.join(ROOT, 'cities', city, 'changes.json')))
OUT = os.path.join(ROOT, 'cities', city, 'raw', 'changes'); os.makedirs(OUT, exist_ok=True)
WORK = os.path.join(ROOT, 'cities', city, 'tmp', 'changes'); os.makedirs(WORK, exist_ok=True)
UA = {'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)'}
TODAY = dt.date.today()


def get(url, tries=4, timeout=600):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, url[:160], e); time.sleep(15 * (i + 1))
    raise RuntimeError('failed: ' + url)


def download(url, path):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=900) as r, open(path, 'wb') as f:
                while True:
                    b = r.read(1 << 22)
                    if not b: break
                    f.write(b)
            print('  got', url[:120], os.path.getsize(path) // (1 << 20), 'MB'); return path
        except Exception as e:
            print('  retry', i + 1, url[:120], e); time.sleep(20 * (i + 1))
    raise RuntimeError('download failed: ' + url)


def ckan_rows(pkg_url, pick):
    """Rows of the first datastore CSV resource of a CKAN package that `pick(resource)` accepts."""
    pkg = json.loads(get(pkg_url))['result']
    res = [r for r in pkg['resources'] if r.get('datastore_active') and pick(r)]
    out = []
    for r in res:
        url = pkg_url.split('/api/')[0] + '/datastore/dump/' + r['id']
        path = os.path.join(WORK, r['id'] + '.csv'); download(url, path)
        with open(path, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                row['_resource'] = r['name']; out.append(row)
        print('  resource', r['name'], len(out), 'rows so far')
    return out


def since(years): return (TODAY - dt.timedelta(days=round(365.25 * years))).isoformat()


def ckan_devapps(spec):
    from pyproj import Transformer
    rows = ckan_rows(spec['ckan'], lambda r: (r.get('format') or '').upper() == 'CSV')
    cut = since(spec['years']); closed = set(spec.get('closed', []))
    print('  application types:', dict(collections.Counter(r['APPLICATION_TYPE'] for r in rows).most_common()))
    st = collections.Counter((r['APPLICATION_TYPE'], r['STATUS']) for r in rows if (r['DATE_SUBMITTED'] or '')[:10] >= cut)
    print('  type/status, submitted in the window:'); [print('   ', k, n) for k, n in sorted(st.items())]
    st2 = collections.Counter((r['APPLICATION_TYPE'], r['STATUS']) for r in rows if (r['DATE_SUBMITTED'] or '')[:10] < cut)
    print('  type/status, submitted before it:'); [print('   ', k, n) for k, n in sorted(st2.items()) if n >= 5]
    # Two candidate projections for X/Y; the log compares them against the ward the row names.
    tr = {epsg: Transformer.from_crs(f'EPSG:{epsg}', 'EPSG:4326', always_xy=True) for epsg in (2952, 2019)}
    keep = []
    for r in rows:
        if (r['DATE_SUBMITTED'] or '')[:10] < cut and r['STATUS'] in closed: continue
        try: x, y = float(r['X']), float(r['Y'])
        except (TypeError, ValueError): x = y = None
        ll = {e: [round(v, 6) for v in t.transform(x, y)] for e, t in tr.items()} if x else {}
        keep.append({k: (r.get(k) or '').strip() for k in ('APPLICATION_TYPE', 'APPLICATION#', 'STREET_NUM', 'STREET_NAME', 'STREET_TYPE', 'STREET_DIRECTION',
                     'DATE_SUBMITTED', 'STATUS', 'DESCRIPTION', 'APPLICATION_URL', 'PARENT_FOLDER_NUMBER', 'REFERENCE_FILE#', 'WARD_NUMBER')} | {'ll': ll})
    print('  kept', len(keep), 'of', len(rows))
    if keep and keep[0]['ll']: print('  first row both projections:', keep[0]['APPLICATION#'], keep[0]['ll'])
    return keep


def address_points(spec):
    pkg = json.loads(get(spec['ckan']))['result']
    url = next(r['url'] for r in pkg['resources'] if r['name'].lower().endswith('4326.csv'))
    path = os.path.join(WORK, 'address_points.csv'); download(url, path)
    by_id, by_addr = {}, {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            try: g = json.loads(r['geometry'])['coordinates']
            except Exception: continue
            g = g[0] if isinstance(g[0], list) else g
            ll = [round(g[0], 6), round(g[1], 6)]
            by_id[r['ADDRESS_POINT_ID']] = ll
            key = (r['ADDRESS_NUMBER'].strip().upper(), r['LINEAR_NAME'].strip().upper(), (r['LINEAR_NAME_TYPE'] or '').strip().upper().replace('NONE', ''),
                   (r['LINEAR_NAME_DIR'] or '').strip().upper().replace('NONE', ''))
            by_addr.setdefault(key, ll)
    print('  address points:', len(by_id))
    return by_id, by_addr


def ckan_permits(spec):
    types, works = set(spec['types']), set(spec.get('works', []))
    cut = since(spec['years'])
    rows = []
    for pkg in spec['ckan']:
        rows += ckan_rows(pkg, lambda r: 'since 2017' in r['name'].lower() or 'active' in r['name'].lower())
    allt = collections.Counter((r['PERMIT_TYPE'], r['WORK']) for r in rows)
    print('  permit type / work (top 60):'); [print('   ', k, n) for k, n in allt.most_common(60)]
    import re
    houses = re.compile(spec['skip_uses'], re.I) if spec.get('skip_uses') else None
    sel = [r for r in rows if r['PERMIT_TYPE'] in types and r['WORK'] in works and
           ('active' in r['_resource'].lower() or (r.get('COMPLETED_DATE') or '')[:10] >= cut) and
           not (houses and houses.search(r['STRUCTURE_TYPE'] + ' | ' + r['CURRENT_USE'] if r['WORK'] == 'Demolition' else r['STRUCTURE_TYPE']))]
    # One row per permit: its latest revision, with the original (revision 00) description, which says what the
    # project is ("Proposal to construct a 16-storey office building"); revisions describe only what changed.
    first = {r['PERMIT_NUM']: r['DESCRIPTION'] for r in sel if r['REVISION_NUM'] in ('00', '0', '')}
    last = {}
    for r in sel:
        if r['PERMIT_NUM'] not in last or r['REVISION_NUM'] > last[r['PERMIT_NUM']]['REVISION_NUM']: last[r['PERMIT_NUM']] = r
    for k, r in last.items(): r['DESCRIPTION'] = first.get(k) or r['DESCRIPTION']
    sel = list(last.values())
    print('  selected', len(sel), '· by status', dict(collections.Counter(r['STATUS'] for r in sel).most_common(25)))
    by_id, by_addr = address_points(spec['addresses'])
    keep, placed = [], collections.Counter()
    for r in sel:
        ll = by_id.get((r.get('GEO_ID') or '').strip())
        how = 'geo_id' if ll else None
        if not ll:
            num = (r['STREET_NUM'] or '').strip().upper().split('-')[0].split(' ')[0]
            ll = by_addr.get((num, (r['STREET_NAME'] or '').strip().upper(), (r['STREET_TYPE'] or '').strip().upper(), (r['STREET_DIRECTION'] or '').strip().upper()))
            how = 'address' if ll else 'none'
        placed[how] += 1
        if not ll: continue
        keep.append({k: (r.get(k) or '').strip() for k in ('PERMIT_NUM', 'REVISION_NUM', 'PERMIT_TYPE', 'STRUCTURE_TYPE', 'WORK', 'STREET_NUM', 'STREET_NAME',
                     'STREET_TYPE', 'STREET_DIRECTION', 'APPLICATION_DATE', 'ISSUED_DATE', 'COMPLETED_DATE', 'STATUS', 'DESCRIPTION', 'CURRENT_USE',
                     'PROPOSED_USE', 'DWELLING_UNITS_CREATED', 'DWELLING_UNITS_LOST', 'EST_CONST_COST', '_resource')} | {'ll': ll})
    print('  placed:', dict(placed))
    return keep


def socrata_permits(spec):
    base = spec['url']
    cut = since(spec['years'])
    where = f"issue_date >= '{cut}' AND permit_type in(" + ','.join("'" + t + "'" for t in spec['types']) + ')'
    cols = ['id', 'permit_', 'permit_status', 'permit_milestone', 'permit_type', 'review_type', 'application_start_date', 'issue_date',
            'street_number', 'street_direction', 'street_name', 'work_description', 'reported_cost', 'community_area', 'latitude', 'longitude']
    rows, off = [], 0
    while True:
        q = urllib.parse.urlencode({'$select': ','.join(cols), '$where': where, '$order': 'id', '$limit': 50000, '$offset': off})
        page = json.loads(get(base + '?' + q))
        rows += page; off += len(page)
        print('  rows so far', len(rows))
        if len(page) < 50000: break
    print('  by type/status:', dict(collections.Counter((r.get('permit_type'), r.get('permit_status')) for r in rows).most_common()))
    print('  by milestone:', dict(collections.Counter(r.get('permit_milestone') for r in rows).most_common()))
    print('  with coordinates:', sum(1 for r in rows if r.get('latitude')))
    return rows


def ods_permits(spec):
    base = spec['portal'].rstrip('/') + '/api/explore/v2.1/catalog/datasets/' + spec['dataset'] + '/exports/json'
    cut = since(spec['years'])
    where = f"issuedate >= date'{cut}' AND (" + ' OR '.join('typeofwork = "' + t + '"' for t in spec['types']) + ')'
    cols = ['permitnumber', 'permitnumbercreateddate', 'issuedate', 'projectvalue', 'typeofwork', 'address', 'projectdescription',
            'propertyuse', 'specificusecategory', 'geolocalarea', 'geo_point_2d']
    rows = json.loads(get(base + '?' + urllib.parse.urlencode({'select': ','.join(cols), 'where': where})))
    for r in rows:
        p = r.pop('geo_point_2d', None) or {}
        r['lon'], r['lat'] = p.get('lon'), p.get('lat')
    print('  by type of work:', dict(collections.Counter(r.get('typeofwork') for r in rows).most_common()))
    print('  by use:', dict(collections.Counter(str(r.get('specificusecategory')) for r in rows).most_common(40)))
    print('  with coordinates:', sum(1 for r in rows if r.get('lat')))
    return rows


def socrata_dobnow(spec):
    cols = ['job_filing_number', 'filing_status', 'house_no', 'street_name', 'borough', 'job_type', 'building_type', 'existing_dwelling_units',
            'proposed_dwelling_units', 'proposed_no_of_stories', 'existing_stories', 'filing_date', 'approved_date', 'first_permit_date',
            'signoff_date', 'current_status_date', 'latitude', 'longitude', 'job_description', 'bbl']
    where = 'job_type in(' + ','.join("'" + t + "'" for t in spec['types']) + ") AND building_type not in('1 Family','2 Family')"   # houses: left out
    rows, off = [], 0
    while True:
        q = urllib.parse.urlencode({'$select': ','.join(cols), '$where': where, '$order': 'job_filing_number', '$limit': 50000, '$offset': off})
        page = json.loads(get(spec['url'] + '?' + q))
        rows += page; off += len(page)
        print('  rows so far', len(rows))
        if len(page) < 50000: break
    # The dates are text ("MM/DD/YYYY" or ISO): keep filings with any date in the window, so the file stays small.
    def iso(v):
        v = (v or '').strip()
        m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})', v)
        return '%s-%02d-%02d' % (m.group(3), int(m.group(1)), int(m.group(2))) if m else v[:10]
    cut = since(spec['years'])
    for r in rows:
        for k in ('filing_date', 'approved_date', 'first_permit_date', 'signoff_date', 'current_status_date'):
            if r.get(k): r[k] = iso(r[k])
    # Kept: filings made in the window, or signed off in the last two years. (Every filing's current_status_date is
    # recent, so it doesn't count.) Withdrawn ones are dropped here, and the descriptions trimmed.
    two = since(2)
    rows = [r for r in rows if ((r.get('filing_date') or '') >= cut or (r.get('signoff_date') or '') >= two) and 'Withdrawn' not in (r.get('filing_status') or '')]
    # One row per job (job_filing_number "X08055450-S9" is job X08055450's ninth amendment): the latest status, with the
    # initial filing's description, which says what the job is.
    jobs, first = {}, {}
    for r in rows:
        j, _, suf = (r.get('job_filing_number') or '').partition('-')
        if suf.startswith('I') and r.get('job_description'): first[j] = r['job_description']
        last = max(r.get(k) or '' for k in ('current_status_date', 'signoff_date', 'first_permit_date', 'approved_date', 'filing_date'))
        if j not in jobs or last > jobs[j][0]: jobs[j] = (last, r)
    rows = []
    for j, (_, r) in jobs.items():
        r = {k: v for k, v in r.items() if v not in (None, '') and k not in ('bbl', 'building_type')}
        if first.get(j): r['job_description'] = first[j]
        if r.get('job_description'): r['job_description'] = r['job_description'][:300]
        rows.append(r)
    print('  jobs', len(rows))
    print('  in the window', len(rows))
    print('  by type/status:', dict(collections.Counter((r.get('job_type'), r.get('filing_status')) for r in rows).most_common(40)))
    print('  with coordinates:', sum(1 for r in rows if r.get('latitude')), '· date sample:', [r.get('filing_date') for r in rows[:3]], [r.get('signoff_date') for r in rows[:3]])
    print('  sample:', json.dumps(rows[-1])[:1200])
    return rows


def socrata_zap(spec):
    cols = ['project_id', 'project_name', 'project_brief', 'project_status', 'public_status', 'ulurp_non', 'actions', 'borough',
            'community_district', 'app_filed_date', 'certified_referred', 'completed_date', 'current_milestone', 'current_milestone_date', 'dcp_visibility']
    cut = since(spec['years'])
    where = "actions like '%ZM%' AND (app_filed_date >= '" + cut + "' OR completed_date >= '" + cut + "' OR project_status = 'Active')"
    rows, off = [], 0
    while True:
        q = urllib.parse.urlencode({'$select': ','.join(cols), '$where': where, '$order': 'project_id', '$limit': 50000, '$offset': off})
        page = json.loads(get(spec['url'] + '?' + q)); rows += page; off += len(page)
        if len(page) < 50000: break
    rows = [r for r in rows if (r.get('dcp_visibility') or 'General Public') == 'General Public']
    print('  projects with a zoning map amendment:', len(rows), dict(collections.Counter((r.get('project_status'), r.get('public_status')) for r in rows).most_common(20)))
    # Tax lots per project.
    ids = [r['project_id'] for r in rows]; lots = collections.defaultdict(set)
    for i in range(0, len(ids), 80):
        q = urllib.parse.urlencode({'$where': 'project_id in(' + ','.join("'" + x + "'" for x in ids[i:i + 80]) + ')', '$limit': 50000})
        for b in json.loads(get(spec['bbl_url'] + '?' + q)):
            v = re.sub(r'\D', '', str(b.get('bbl') or ''))[:10]
            if len(v) == 10: lots[b['project_id']].add(v)
    allb = sorted({b for v in lots.values() for b in v})
    print('  projects with lots:', len(lots), '· lots:', len(allb), '· bbl sample:', allb[:3])
    # Lot positions from PLUTO (bbl is a number there, "1000010010.00000000"): ask for the numbers.
    pos = {}
    for i in range(0, len(allb), 150):
        q = urllib.parse.urlencode({'$select': 'bbl,latitude,longitude,address', '$where': 'bbl in(' + ','.join(allb[i:i + 150]) + ')', '$limit': 50000})
        for l in json.loads(get(spec['pluto_url'] + '?' + q)):
            k = re.sub(r'\.0*$', '', str(l.get('bbl') or ''))[:10]
            if l.get('latitude') and l.get('longitude'): pos[k] = (float(l['longitude']), float(l['latitude']), (l.get('address') or '').strip())
    print('  lots placed:', len(pos), 'of', len(allb))
    out = []
    for r in rows:
        ps = [pos[b] for b in sorted(lots.get(r['project_id'], ())) if b in pos]
        if not ps: continue
        r = {k: v for k, v in r.items() if v not in (None, '') and k != 'dcp_visibility'}
        r['lots'] = len(lots[r['project_id']])
        r['at'] = [round(sum(p[0] for p in ps) / len(ps), 6), round(sum(p[1] for p in ps) / len(ps), 6)]
        if len(ps) <= 3 and ps[0][2]: r['addr'] = ps[0][2]
        if r.get('project_brief'): r['project_brief'] = r['project_brief'][:400]
        out.append(r)
    print('  placed projects:', len(out), '· sample:', json.dumps(out[-1])[:900])
    return out


def socrata_sfpipeline(spec):
    cols = ['blklot', 'nameaddr', 'current_status', 'current_status_date', 'approved_date_planning', 'existing_units', 'proposed_units',
            'demo_units', 'net_pipeline_units', 'pipeline_affordable_units', 'case_no', 'bpa_no', 'description_planning', 'description_dbi',
            'non_residential_total_gsf', 'non_residential_net_gsf', 'nhood41', 'latitude', 'longitude']
    rows = json.loads(get(spec['url'] + '?' + urllib.parse.urlencode({'$select': ','.join(cols), '$limit': 50000, '$order': 'blklot'})))
    print('  by status:', dict(collections.Counter(r.get('current_status') for r in rows).most_common()))
    print('  with coordinates:', sum(1 for r in rows if r.get('latitude')), '· homes 10+:', sum(1 for r in rows if float(r.get('proposed_units') or 0) >= 10))
    return rows


FN = {'socrata_sfpipeline': socrata_sfpipeline, 'socrata_zap': socrata_zap, 'ckan_devapps': ckan_devapps, 'ckan_permits': ckan_permits, 'socrata_permits': socrata_permits, 'ods_permits': ods_permits, 'socrata_dobnow': socrata_dobnow}
for name, spec in CFG['sources'].items():
    print('==', name, spec['type'])
    try:
        rows = FN[spec['type']](spec)
    except Exception as e:
        print('  FAILED:', e); continue
    json.dump({'fetched': TODAY.isoformat(), 'source': spec, 'rows': rows}, open(os.path.join(OUT, name + '.json'), 'w'), separators=(',', ':'))
    print('  wrote', name, len(rows), 'rows,', os.path.getsize(os.path.join(OUT, name + '.json')) // 1024, 'KB')
