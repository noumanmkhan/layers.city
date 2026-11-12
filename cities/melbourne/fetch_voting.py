"""Where Victorians vote in the state election of November 28, 2026 -> cities/melbourne/raw/voting/. Runs in GitHub
Actions (fetch-melbourne-voting.yml); the sandbox can't reach the VEC.

- venues.xlsx: the VEC's venues spreadsheet ("location details and voting estimates" for early, election day, mobile,
  low-sensory and interstate centres), linked from vec.vic.gov.au/voting/2026-state-election/voting-locations.
  CC BY 4.0, "© Victorian Electoral Commission". The link is read from that page each run, since the VEC replaces
  the file when venues change; the address below is the one it had on November 13.
- venues.json: every sheet of it as rows (header row first), so the build and a reader of the diff needn't open Excel.
- sites.json: each early and election day venue's address placed with Vicmap Address (the state's address points,
  CC BY 4.0, via the Vicmap open data WFS): {"<address|suburb|postcode>": [lng, lat, how]}, how being "address"
  (the number on the street), "near" (the nearest listed number on it), "corner" (where the two roads of a
  "Corner A and B" meet), "street" (somewhere on the street, when no number near it is listed) or null (not found:
  a reserve or a building name with no street). Address line 2 is tried when line 1 gives nothing. Kept between
  runs, so a run only looks up what it hasn't placed well."""
import json, os, re, subprocess, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw', 'voting'); os.makedirs(RAW, exist_ok=True)
PAGE = 'https://www.vec.vic.gov.au/voting/2026-state-election/voting-locations'
KNOWN = 'https://www.vec.vic.gov.au/-/media/19326aa361284a49a69b08194421da96.xlsx'


def link():
    try:
        html = get(PAGE, tries=3).decode('utf-8', 'replace')
        hits = re.findall(r'href="([^"]+\.xlsx[^"]*)"', html)
        if hits:
            u = hits[0].replace('&amp;', '&')
            return u if u.startswith('http') else 'https://www.vec.vic.gov.au' + u
        print('  no .xlsx link on the page; using the known address')
    except Exception as e: print('  page:', e)
    return KNOWN


def main():
    url = link(); print('  venues', url)
    b = get(url, tries=3)
    open(os.path.join(RAW, 'venues.xlsx'), 'wb').write(b)
    try: import openpyxl
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'openpyxl']); import openpyxl
    wb = openpyxl.load_workbook(os.path.join(RAW, 'venues.xlsx'), read_only=True, data_only=True)
    out = {'source': url, 'sheets': {}}
    for ws in wb.worksheets:
        rows = [[(c.isoformat() if hasattr(c, 'isoformat') else c) for c in r] for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(v not in (None, '') for v in r)]
        out['sheets'][ws.title] = rows
        print(f'  sheet {ws.title!r}: {len(rows)} rows; header {rows[0] if rows else None}')
    json.dump(out, open(os.path.join(RAW, 'venues.json'), 'w'), ensure_ascii=False, indent=0, default=str)


WFS = 'https://opendata.maps.vic.gov.au/geoserver/wfs'


def wfs(layer, cql, n=1):
    q = {'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature', 'typeNames': layer, 'outputFormat': 'application/json',
         'count': n, 'srsName': 'EPSG:4326', 'CQL_FILTER': cql}
    return json.loads(get(WFS + '?' + urllib.parse.urlencode(q), tries=3, timeout=60)).get('features', [])


def address_layer():
    cap = get(WFS + '?service=WFS&request=GetCapabilities&version=2.0.0').decode('utf-8', 'replace')
    names = re.findall(r'<(?:wfs:)?Name>([^<]+)</(?:wfs:)?Name>', cap)
    hits = [n for n in names if re.search(r'address', n, re.I)]
    print('  address layers:', hits)
    for n in sorted(hits, key=lambda n: (not re.search(r'vmadd|address_point|^.*:address$', n), len(n))):
        try:
            f = wfs(n, 'INCLUDE')
            if f:
                print('  using', n, '; fields', {k: v for k, v in f[0]['properties'].items()})
                return n, f[0]['properties']
        except Exception as e: print('  ', n, e)
    raise RuntimeError('no Vicmap address layer')


def pt(f):
    g = f['geometry']; c = g['coordinates']
    while isinstance(c[0], list): c = c[0]
    return [round(c[0], 6), round(c[1], 6)]


def esc(v): return v.replace("'", "''")


TYPES = {'ROAD', 'STREET', 'AVENUE', 'DRIVE', 'COURT', 'CRESCENT', 'PLACE', 'LANE', 'HIGHWAY', 'PARADE', 'BOULEVARD',
         'WAY', 'GROVE', 'CLOSE', 'TERRACE', 'CIRCUIT', 'SQUARE', 'ESPLANADE', 'FREEWAY', 'PROMENADE', 'TRACK', 'RISE',
         'WALK', 'VIEW', 'PATHWAY', 'RIDGE', 'MEWS', 'GARDENS', 'STRAND', 'BOULEVARDE', 'ROW', 'GLADE', 'CHASE', 'LINK'}
SHORT = {'RD': 'ROAD', 'ST': 'STREET', 'AVE': 'AVENUE', 'AV': 'AVENUE', 'DR': 'DRIVE', 'CT': 'COURT', 'CRES': 'CRESCENT',
         'PL': 'PLACE', 'HWY': 'HIGHWAY', 'PDE': 'PARADE', 'BLVD': 'BOULEVARD', 'CL': 'CLOSE', 'TCE': 'TERRACE'}


def road(text):
    """'Mt Derrimut Road' -> ('MOUNT DERRIMUT', 'ROAD'); the type is the last word when it is one. (Vicmap keeps ST in
    names such as ST KILDA, so only MT is spelled out.)"""
    w = re.sub(r'[^A-Za-z\' ]', ' ', text).upper().split()
    w = ['MOUNT' if x == 'MT' else x for x in w]
    if len(w) > 1 and SHORT.get(w[-1], w[-1]) in TYPES: return ' '.join(w[:-1]), SHORT.get(w[-1], w[-1])
    return ' '.join(w), None


def on_road(layer, name, typ, sub, pc, extra='', n=300):
    t = f" AND road_type = '{esc(typ)}'" if typ else ''
    names = [name] + ([name.replace("'", ''), name.replace("'", ' ')] if "'" in name else [])
    for nm in names:
        for area in (f"locality_name = '{esc(sub)}'", f"postcode = '{esc(pc)}'"):
            f = wfs(layer, f"road_name = '{esc(nm)}'{t} AND {area}{extra}", n)
            if f: return f
    return []


def place(layer, line, suburb, pc):
    """[lng, lat, how] for one venue line: a numbered address, a corner, or nothing."""
    sub = suburb.strip().upper()
    line = re.sub(r'^(?:(?:unit|shop|suite|level|lot)\s*[\w.]+\s*[/,]?\s*)+', '', line.strip(), flags=re.I)
    line = re.sub(r'^(\d+[A-Za-z]?)/(?=\d)', '', line)   # 8/85 -> 85
    c = re.match(r'^corner (?:of )?(.+?) and (.+)$', line, re.I)
    if c:
        A = on_road(layer, *road(c.group(1)), sub, pc); B = on_road(layer, *road(c.group(2)), sub, pc)
        if A and B:
            best = min(((pt(a), pt(b)) for a in A for b in B), key=lambda q: (q[0][0] - q[1][0]) ** 2 + (q[0][1] - q[1][1]) ** 2)
            if abs(best[0][0] - best[1][0]) + abs(best[0][1] - best[1][1]) < 0.004:
                return [round((best[0][0] + best[1][0]) / 2, 6), round((best[0][1] + best[1][1]) / 2, 6), 'corner']
        return None
    m = re.match(r'^(\d+)[A-Za-z]?(?:\s*-\s*(\d+)[A-Za-z]?)?\s+(.+)$', line)
    if not m:
        # A street with no number ("Molesworth Street"): the middle of its listed addresses.
        name, typ = road(line)
        if not typ: return None
        f = on_road(layer, name, typ, sub, pc, '', 60)
        return (sorted(pt(x) for x in f)[len(f) // 2] + ['street']) if f else None
    num = int(m.group(1)); name, typ = road(m.group(3))
    f = on_road(layer, name, typ, sub, pc, f' AND house_number_1 BETWEEN {max(num - 40, 0)} AND {num + 40}', 100)
    if f:
        g = min(f, key=lambda x: (abs((x['properties'].get('house_number_1') or 0) - num), x['properties'].get('is_primary') != 'Y'))
        return pt(g) + ['address' if g['properties'].get('house_number_1') == num else 'near']
    f = on_road(layer, name, typ, sub, pc, '', 60)
    if f:
        ps = sorted(pt(x) for x in f); mid = ps[len(ps) // 2]
        return mid + ['street']
    return None


def geocode():
    sh = json.load(open(os.path.join(RAW, 'venues.json')))['sheets']
    path = os.path.join(RAW, 'sites.json')
    cache = json.load(open(path)) if os.path.exists(path) else {}
    want, line2 = [], {}
    for s in ('EVCs', 'VCs'):
        h = sh[s][0]; i = {k: h.index(k) for k in ('Address Line 1', 'Address Line 2', 'Suburb', 'Post Code')}
        for r in sh[s][1:]:
            k = '|'.join(str(r[i[c]] or '').strip() for c in ('Address Line 1', 'Suburb', 'Post Code'))
            line2[k] = re.sub(r'\(.*?\)', '', str(r[i['Address Line 2']] or '')).strip()
            # Look again at what the first passes only placed on the street or not at all.
            if (k not in cache or cache[k][2] in (None, 'street')) and k not in want: want.append(k)
    print(f'  {len(cache)} placed before, {len(want)} to look up')
    if not want: return
    layer, props = address_layer()
    t0 = time.time()
    for n, k in enumerate(want):
        line, suburb, pc = k.split('|')
        try: cache[k] = place(layer, line, suburb, pc) or (line2[k] and place(layer, line2[k], suburb, pc)) or cache.get(k) or [None, None, None]
        except Exception as e: print('  ', k, e); continue
        if n % 100 == 0:
            print(f'  {n}/{len(want)} {time.time() - t0:.0f}s', k, cache[k])
            json.dump(cache, open(path, 'w'), ensure_ascii=False, indent=0, sort_keys=True)
    json.dump(cache, open(path, 'w'), ensure_ascii=False, indent=0, sort_keys=True)
    from collections import Counter
    print('  placed:', Counter(v[2] for v in cache.values()))
    print('  not found:', [k for k, v in cache.items() if v[2] is None][:40])


if __name__ == '__main__':
    main()
    geocode()
