"""Fetch the inputs for Toronto's Fun maps page into raw/fun/. Run from GitHub Actions (the sandbox can't reach
these hosts). Heavy files are boiled down here so only small summaries get committed.

  osm_places.json   OpenStreetMap shops and amenities in the City's bounding box (Overpass): one row per place,
                    [lon, lat, amenity, shop, leisure, brand, name, cuisine]. ODbL.
  sr311.json        311 Service Requests - Customer Initiated (Toronto Open Data, OGL-Toronto): the last complete
                    year's requests counted by ward and by request type. The file has no coordinates, only a
                    ward, a postal prefix and an intersection, so wards are the finest honest unit.
  tickets.json      Parking Tickets (Toronto Open Data): the last complete year's tickets, geocoded by matching
                    the ticket's address to the City's Address Points file, then counted per neighbourhood
                    (tickets, fines, top infraction, busiest address).
  suffixes.json     Toronto Centreline (Toronto Open Data): every named street, its suffix (Avenue, Crescent...)
                    and the neighbourhood its middle falls in; counted per neighbourhood by distinct street name.

Each part is independent: one failing is logged and the others still run."""
import csv, io, json, os, re, sys, time, traceback, urllib.parse, urllib.request, zipfile
from collections import Counter, defaultdict

from shapely.geometry import shape, Point
from shapely.strtree import STRtree

csv.field_size_limit(sys.maxsize)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'fun')
NBHD = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'neighbourhoods.geojson')
CKAN = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show?id='
UA = {'User-Agent': 'layers.city pipeline (go@layers.city)'}
BBOX = (43.575, -79.645, 43.860, -79.110)  # s, w, n, e
os.makedirs(OUT, exist_ok=True)


def fetch(url, tries=4, timeout=600, data=None):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA, data=data)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, url[:120], e, flush=True)
            time.sleep(10 * (i + 1))
    raise RuntimeError('failed: ' + url)


def save(name, obj):
    with open(os.path.join(OUT, name), 'w') as f:
        json.dump(obj, f, separators=(',', ':'))
    print('  wrote', name, os.path.getsize(os.path.join(OUT, name)), 'bytes', flush=True)


def package(pid):
    p = json.loads(fetch(CKAN + pid))['result']
    print(f'{pid}: {len(p["resources"])} resources', flush=True)
    for r in p['resources']:
        print('   ', r.get('name'), '|', r.get('format'), '|', r.get('last_modified') or r.get('created'), flush=True)
    return p['resources']


nb_feats = json.load(open(NBHD))['features']
nb_shapes = [shape(f['geometry']) for f in nb_feats]
nb_names = [f['properties']['name'] for f in nb_feats]
nb_tree = STRtree(nb_shapes)


def nbhd_of(lon, lat):
    p = Point(lon, lat)
    for i in nb_tree.query(p):
        if nb_shapes[i].covers(p):
            return nb_names[i]
    return None


def latest_year_resource(res, fmt_ok=('ZIP', 'CSV')):
    """The resource for the newest complete year (a name holding a year before the current one)."""
    this_year = time.gmtime().tm_year
    best = None
    for r in res:
        m = re.search(r'(20\d\d)', r.get('name', ''))
        if not m or (r.get('format') or '').upper() not in fmt_ok:
            continue
        y = int(m.group(1))
        if y >= this_year:
            continue
        if not best or y > best[0]:
            best = (y, r)
    return best


def decode(raw):
    """CSV bytes to text: UTF-8 (with or without a BOM), UTF-16, else Latin-1; leading blank lines dropped."""
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        text = raw.decode('utf-16')
    elif raw[:3] == b'\xef\xbb\xbf':
        text = raw[3:].decode('utf-8', errors='replace')
    else:
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
    text = text.replace('\x00', '')
    return text.lstrip('\r\n')


def csv_rows(blob):
    """Rows from a zip of CSVs or a bare CSV."""
    if blob[:2] == b'PK':
        z = zipfile.ZipFile(io.BytesIO(blob))
        for n in z.namelist():
            if not n.lower().endswith('.csv'):
                continue
            raw = z.read(n)
            print('    reading', n, len(raw), 'bytes, starts', repr(raw[:120]), flush=True)
            yield from csv.DictReader(io.StringIO(decode(raw)))
    else:
        yield from csv.DictReader(io.StringIO(decode(blob)))


def part_osm():
    s, w, n, e = BBOX
    bb = f'{s},{w},{n},{e}'
    q = f"""[out:json][timeout:600];
(
  nwr["amenity"~"^(cafe|fast_food|restaurant|fuel|pharmacy|bar|pub|car_wash|ice_cream|library|bank)$"]({bb});
  nwr["shop"~"^(alcohol|cannabis|laundry|dry_cleaning|books|e-cigarette|bicycle|variety_store|convenience|bakery|tea|beverages|wine|car)$"]({bb});
  nwr["leisure"="fitness_centre"]({bb});
);
out center tags;"""
    blob = None
    for host in ('https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'):
        try:
            blob = fetch(host, data=urllib.parse.urlencode({'data': q}).encode(), tries=3, timeout=900)
            break
        except Exception as ex:
            print('  overpass host failed', host, ex, flush=True)
    if blob is None:
        raise RuntimeError('every Overpass host failed')
    els = json.loads(blob)['elements']
    rows = []
    for el in els:
        t = el.get('tags', {})
        lat = el.get('lat') or el.get('center', {}).get('lat')
        lon = el.get('lon') or el.get('center', {}).get('lon')
        if lat is None:
            continue
        rows.append([round(lon, 5), round(lat, 5), t.get('amenity', ''), t.get('shop', ''), t.get('leisure', ''),
                     t.get('brand', ''), t.get('name', ''), t.get('cuisine', '')])
    print(f'  {len(rows)} OSM places', flush=True)
    save('osm_places.json', {'asof': time.strftime('%Y-%m-%d'), 'source': 'OpenStreetMap contributors (ODbL), via Overpass',
                             'cols': ['lon', 'lat', 'amenity', 'shop', 'leisure', 'brand', 'name', 'cuisine'],
                             'rows': rows})


def part_311():
    res = package('311-service-requests-customer-initiated')
    best = latest_year_resource(res)
    if not best:
        raise RuntimeError('no yearly 311 resource found')
    year, r = best
    print(f'  using {r["name"]} ({year})', flush=True)
    blob = fetch(r['url'])
    by_ward = defaultdict(Counter)
    by_fsa = defaultdict(Counter)
    total = 0
    cols = None
    for row in csv_rows(blob):
        if cols is None:
            cols = list(row.keys())
            print('  columns:', cols, flush=True)
        typ = (row.get('Service Request Type') or '').strip()
        if not typ:
            continue
        total += 1
        m = re.search(r'\((\d+)\)', row.get('Ward') or '')
        if m:
            by_ward[int(m.group(1))][typ] += 1
        fsa = (row.get('First 3 Chars of Postal Code') or '').strip().upper()
        if re.fullmatch(r'M\d[A-Z]', fsa):
            by_fsa[fsa][typ] += 1
    print(f'  {total} requests, {len(by_ward)} wards, {len(by_fsa)} postal prefixes', flush=True)
    save('sr311.json', {'year': year, 'source': r['name'], 'total': total,
                        'by_ward': {str(k): dict(v) for k, v in sorted(by_ward.items())},
                        'by_fsa': {k: dict(v) for k, v in sorted(by_fsa.items())}})


def norm_addr(s):
    s = re.sub(r'[^A-Z0-9 ]', ' ', (s or '').upper())
    return re.sub(r'\s+', ' ', s).strip()


def address_points():
    """{'4700 KEELE ST': (lon, lat)} from the City's Address Points file."""
    res = package('address-points-municipal-toronto-one-address-repository')
    def fmt_of(r):
        return (r.get('format') or '').upper()
    pick = (next((r for r in res if '4326' in (r.get('name') or '') and fmt_of(r) == 'CSV'), None)
            or next((r for r in res if '4326' in (r.get('name') or '') and fmt_of(r) in ('GEOJSON', 'JSON')), None)
            or next(r for r in res if fmt_of(r) in ('CSV', 'GEOJSON', 'JSON')))
    print('  address points from', pick['name'], pick.get('format'), flush=True)
    blob = fetch(pick['url'], timeout=1200)
    out = {}
    fmt = (pick.get('format') or '').upper()
    if fmt == 'CSV':
        for row in csv_rows(blob):
            full = row.get('ADDRESS_FULL') or f"{row.get('ADDRESS_NUMBER', '')} {row.get('LINEAR_NAME_FULL', '')}"
            g = row.get('geometry') or ''
            m = re.findall(r'-?\d+\.\d+', g)
            if len(m) >= 2:
                out.setdefault(norm_addr(full), (float(m[0]), float(m[1])))
    else:
        for f in json.loads(blob)['features']:
            p = f['properties']
            full = p.get('ADDRESS_FULL') or f"{p.get('ADDRESS_NUMBER', '')} {p.get('LINEAR_NAME_FULL', '')}"
            c = f['geometry']['coordinates']
            while isinstance(c[0], list):
                c = c[0]
            out.setdefault(norm_addr(full), (c[0], c[1]))
    print(f'  {len(out)} address points', flush=True)
    return out


ABBR = {'STREET': 'ST', 'AVENUE': 'AVE', 'ROAD': 'RD', 'DRIVE': 'DR', 'BOULEVARD': 'BLVD', 'CRESCENT': 'CRES',
        'COURT': 'CRT', 'PLACE': 'PL', 'SQUARE': 'SQ', 'TERRACE': 'TER', 'GARDENS': 'GDNS', 'PARKWAY': 'PKWY',
        'CIRCLE': 'CRCL', 'LANE': 'LANE', 'TRAIL': 'TRL', 'EAST': 'E', 'WEST': 'W', 'NORTH': 'N', 'SOUTH': 'S',
        'AV': 'AVE', 'STR': 'ST', 'CRS': 'CRES', 'CT': 'CRT'}


def ticket_addr(s):
    return ' '.join(ABBR.get(t, t) for t in norm_addr(s).split())


def part_tickets():
    res = package('parking-tickets')
    best = latest_year_resource(res)
    if not best:
        raise RuntimeError('no yearly parking ticket resource found')
    year, r = best
    print(f'  using {r["name"]} ({year})', flush=True)
    blob = fetch(r['url'], timeout=1200)
    by_addr = defaultdict(lambda: [0, 0.0, Counter()])
    n = 0
    cols = None
    for row in csv_rows(blob):
        row = {(k or '').strip().lower(): v for k, v in row.items()}
        if cols is None:
            cols = list(row.keys())
            print('  columns:', cols, flush=True)
        a = ticket_addr(row.get('location2'))
        if not a:
            continue
        n += 1
        rec = by_addr[a]
        rec[0] += 1
        try:
            rec[1] += float(row.get('set_fine_amount') or 0)
        except ValueError:
            pass
        rec[2][(row.get('infraction_description') or '').strip().upper()] += 1
    del blob
    print(f'  {n} tickets at {len(by_addr)} addresses', flush=True)
    pts = {ticket_addr(k): v for k, v in address_points().items()}
    nb = defaultdict(lambda: {'tickets': 0, 'fines': 0.0, 'inf': Counter(), 'top': None})
    matched = matched_t = 0
    for a, (cnt, fine, inf) in by_addr.items():
        p = pts.get(a)
        if not p:
            continue
        name = nbhd_of(*p)
        if not name:
            continue
        matched += 1
        matched_t += cnt
        d = nb[name]
        d['tickets'] += cnt
        d['fines'] += fine
        d['inf'].update(inf)
        if not d['top'] or cnt > d['top'][1]:
            d['top'] = [a.title(), cnt, round(fine), [round(p[0], 5), round(p[1], 5)]]
    print(f'  geocoded {matched} addresses holding {matched_t} of {n} tickets ({matched_t / max(n, 1):.0%})', flush=True)
    save('tickets.json', {'year': year, 'source': r['name'], 'tickets': n, 'geocoded': matched_t,
                          'by_nbhd': {k: {'tickets': v['tickets'], 'fines': round(v['fines']),
                                          'inf': v['inf'].most_common(3), 'top': v['top']}
                                      for k, v in sorted(nb.items())}})


SUFFIX = {'ST': 'Street', 'AVE': 'Avenue', 'RD': 'Road', 'DR': 'Drive', 'BLVD': 'Boulevard', 'CRES': 'Crescent',
          'CRT': 'Court', 'PL': 'Place', 'SQ': 'Square', 'TER': 'Terrace', 'GDNS': 'Gardens', 'PKWY': 'Parkway',
          'CIR': 'Circle', 'CRCL': 'Circle', 'LANE': 'Lane', 'LN': 'Lane', 'TRL': 'Trail', 'WAY': 'Way',
          'GATE': 'Gate', 'GRV': 'Grove', 'GROVE': 'Grove', 'HTS': 'Heights', 'PK': 'Park', 'PARK': 'Park',
          'MEWS': 'Mews', 'CLOSE': 'Close', 'GRN': 'Green', 'WALK': 'Walk', 'HILL': 'Hill', 'RDGE': 'Ridge',
          'LAWN': 'Lawn', 'WOOD': 'Wood', 'VIEW': 'View', 'CRCT': 'Circuit', 'SQUARE': 'Square', 'PATH': 'Path',
          'ROW': 'Row', 'LINE': 'Line', 'HWY': 'Highway', 'EXPY': 'Expressway', 'QUAY': 'Quay', 'MALL': 'Mall',
          'TOWNLINE': 'Townline', 'GLN': 'Glen', 'GLEN': 'Glen', 'CRS': 'Crescent', 'RISE': 'Rise', 'END': 'End',
          'VALE': 'Vale', 'WYND': 'Wynd', 'CRSNT': 'Crescent', 'ESPLANADE': 'Esplanade', 'GT': 'Gate',
          'PROM': 'Promenade', 'CMN': 'Common', 'COMMON': 'Common', 'VLY': 'Valley', 'DOWNS': 'Downs',
          'BAY': 'Bay', 'TERR': 'Terrace', 'SQ.': 'Square', 'AV': 'Avenue', 'CT': 'Court'}
DIRS = {'E', 'W', 'N', 'S', 'EAST', 'WEST', 'NORTH', 'SOUTH'}
SKIP_CLASS = re.compile(r'trail|walkway|rail|river|creek|hydro|ferry|geostatistical|shoreline|busway|'
                        r'ramp|expressway|laneway|access road|other|pending|airfield|major shoreline|'
                        r'minor shoreline|land|hydro line|island|cul-de-sac', re.I)


def suffix_of(name):
    toks = norm_addr(name).split()
    while toks and toks[-1] in DIRS:
        toks.pop()
    if len(toks) < 2:
        return None
    return SUFFIX.get(toks[-1], 'Other')


def part_suffixes():
    res = package('toronto-centreline-tcl')
    pick = None
    for r in res:
        nm = (r.get('name') or '').lower()
        if '4326' in nm and (r.get('format') or '').upper() == 'GEOJSON' and 'version 2' in nm:
            pick = r
    if not pick:
        pick = next((r for r in res if '4326' in (r.get('name') or '') and (r.get('format') or '').upper() == 'GEOJSON'), None)
    if not pick:
        pick = next(r for r in res if (r.get('format') or '').upper() == 'GEOJSON')
    print('  centreline from', pick['name'], flush=True)
    feats = json.loads(fetch(pick['url'], timeout=1200))['features']
    print(f'  {len(feats)} segments; properties: {list(feats[0]["properties"].keys())}', flush=True)
    classes = Counter()
    names = defaultdict(lambda: defaultdict(set))   # nbhd -> suffix -> {street names}
    city = defaultdict(set)
    for f in feats:
        p = f['properties']
        cls = p.get('FEATURE_CODE_DESC') or ''
        classes[cls] += 1
        if SKIP_CLASS.search(cls):
            continue
        nm = p.get('LINEAR_NAME_FULL') or p.get('LINEAR_NAME_FULL_LEGAL') or ''
        suf = suffix_of(nm)
        if not suf or not f.get('geometry'):
            continue
        try:
            mid = shape(f['geometry']).interpolate(0.5, normalized=True)
        except Exception:
            continue
        nb = nbhd_of(mid.x, mid.y)
        if not nb:
            continue
        key = norm_addr(nm)
        names[nb][suf].add(key)
        city[suf].add(key)
    print('  road classes:', dict(classes), flush=True)
    print('  city-wide distinct names by suffix:', {k: len(v) for k, v in sorted(city.items(), key=lambda kv: -len(kv[1]))}, flush=True)
    save('suffixes.json', {'asof': time.strftime('%Y-%m-%d'), 'source': pick['name'],
                           'city': {k: len(v) for k, v in city.items()},
                           'by_nbhd': {nb: {k: len(v) for k, v in d.items()} for nb, d in sorted(names.items())},
                           'examples': {nb: {k: sorted(v)[:3] for k, v in d.items()} for nb, d in sorted(names.items())}})


parts = sys.argv[1:] or ['osm', '311', 'suffixes', 'tickets']
failed = []
for name in parts:
    print(f'== {name}', flush=True)
    try:
        globals()['part_' + name]()
    except Exception:
        traceback.print_exc()
        failed.append(name)
print('failed parts:', failed or 'none')
