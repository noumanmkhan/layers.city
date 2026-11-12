"""Where Victorians vote in the state election of November 28, 2026 -> cities/melbourne/raw/voting/. Runs in GitHub
Actions (fetch-melbourne-voting.yml); the sandbox can't reach the VEC.

- venues.xlsx: the VEC's venues spreadsheet ("location details and voting estimates" for early, election day, mobile,
  low-sensory and interstate centres), linked from vec.vic.gov.au/voting/2026-state-election/voting-locations.
  CC BY 4.0, "© Victorian Electoral Commission". The link is read from that page each run, since the VEC replaces
  the file when venues change; the address below is the one it had on November 13.
- venues.json: every sheet of it as rows (header row first), so the build and a reader of the diff needn't open Excel.
- sites.json: each early and election day venue's address placed with Vicmap Address (the state's address points,
  CC BY 4.0, via the Vicmap open data WFS): {"<address|suburb|postcode>": [lng, lat, how]}, how being "address"
  (the number on the street), "street" (the street in that suburb, when the number isn't listed) or null (not found).
  Kept between runs, so a run only looks up addresses it hasn't seen."""
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


def place(layer, props, line, suburb, pc):
    keys = {k.lower(): k for k in props}
    ezi, loc = keys.get('ezi_address'), keys.get('locality_name') or keys.get('locality')
    street = keys.get('road_name') or keys.get('street_name')
    m = re.match(r'(?:(?:shop|unit|level|suite)\s*\S+[,/ ]+)?(\d+)[a-z]?(?:-\d+[a-z]?)?\s+(.+)$', line.strip(), re.I)
    sub = suburb.strip().upper()
    if ezi:
        full = f'{line.strip()} {sub} {pc}'.upper()
        f = wfs(layer, f"{ezi} = '{esc(full)}'")
        if f: return pt(f[0]) + ['address']
        if m:
            f = wfs(layer, f"{ezi} LIKE '{esc(m.group(1))} {esc(m.group(2).upper())} {esc(sub)}%'")
            if f: return pt(f[0]) + ['address']
    if m and street and loc:
        name = m.group(2).upper().split(' ')[0]
        f = wfs(layer, f"{street} = '{esc(name)}' AND {loc} = '{esc(sub)}'", 20)
        if f:
            ps = [pt(x) for x in f]
            return [round(sum(p[0] for p in ps) / len(ps), 6), round(sum(p[1] for p in ps) / len(ps), 6), 'street']
    return [None, None, None]


def geocode():
    sh = json.load(open(os.path.join(RAW, 'venues.json')))['sheets']
    path = os.path.join(RAW, 'sites.json')
    cache = json.load(open(path)) if os.path.exists(path) else {}
    want = []
    for s in ('EVCs', 'VCs'):
        h = sh[s][0]; i = {k: h.index(k) for k in ('Address Line 1', 'Suburb', 'Post Code')}
        for r in sh[s][1:]:
            k = '|'.join(str(r[i[c]] or '').strip() for c in ('Address Line 1', 'Suburb', 'Post Code'))
            if k not in cache and k not in want: want.append(k)
    print(f'  {len(cache)} placed before, {len(want)} to look up')
    if not want: return
    layer, props = address_layer()
    t0 = time.time()
    for n, k in enumerate(want):
        line, suburb, pc = k.split('|')
        try: cache[k] = place(layer, props, line, suburb, pc)
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
