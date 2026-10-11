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

Writes raw/changes/<source>.json: {fetched, source, rows: [...]}. Prints counts by type and status (and
how many permits were placed) so the build's filters can be checked against the data.

Usage: python3 engine/fetch_changes.py <city>
"""
import collections, csv, datetime as dt, io, json, os, sys, time, urllib.parse, urllib.request

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


FN = {'ckan_devapps': ckan_devapps, 'ckan_permits': ckan_permits, 'socrata_permits': socrata_permits}
for name, spec in CFG['sources'].items():
    print('==', name, spec['type'])
    try:
        rows = FN[spec['type']](spec)
    except Exception as e:
        print('  FAILED:', e); continue
    json.dump({'fetched': TODAY.isoformat(), 'source': spec, 'rows': rows}, open(os.path.join(OUT, name + '.json'), 'w'), separators=(',', ':'))
    print('  wrote', name, len(rows), 'rows,', os.path.getsize(os.path.join(OUT, name + '.json')) // 1024, 'KB')
