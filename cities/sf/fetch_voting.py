"""Where San Franciscans vote on November 3, 2026 -> cities/sf/raw/voting/. Runs in GitHub Actions (fetch-sf.yml);
the sandbox can't reach these hosts.

- polling_places.xlsx: the Department of Elections' polling place list for the election (linked from
  sf.gov/vote-in-person; the address below is the September 29 version, change it when the Department posts a newer one).
- precincts.geojson: Election Precincts - Current, Defined 2022 (DataSF d6x4-hefw, public domain), the precincts the
  list refers to.
- sites.json: each polling place address from the list, placed with the U.S. Census Bureau's geocoder (written by
  voting.py's helper below on the runner, since the geocoder isn't reachable from the sandbox)."""
import csv, io, json, os, subprocess, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, step, RAW, FAILED

V = os.path.join(RAW, 'voting'); os.makedirs(V, exist_ok=True)
LIST = 'https://api.sf.gov/documents/63956/Polling_Place_List_Nov_3_2026_as_of_09_29_2026.xlsx'
SOC = 'https://data.sfgov.org'


def xlsx():
    b = get(LIST, tries=3)
    open(os.path.join(V, 'polling_places.xlsx'), 'wb').write(b)
    print('  list', len(b) // 1000, 'KB')


def precincts():
    for url in [f'{SOC}/resource/d6x4-hefw.geojson?$limit=5000', f'{SOC}/api/v3/views/d6x4-hefw/query.geojson?accessType=DOWNLOAD']:
        try:
            d = json.loads(get(url, tries=2))
            if d.get('features') and d['features'][0].get('geometry'):
                json.dump(d, open(os.path.join(V, 'precincts.geojson'), 'w'), separators=(',', ':'))
                print('  precincts', len(d['features']), sorted(d['features'][0]['properties'])); return
        except Exception as e: print('  ', url, e)
    raise RuntimeError('no precincts')


def rows():
    try: import openpyxl
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'openpyxl']); import openpyxl
    wb = openpyxl.load_workbook(os.path.join(V, 'polling_places.xlsx'), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        for r in ws.iter_rows(values_only=True):
            out.append([('' if c is None else str(c)).strip() for c in r])
        print('  sheet', ws.title, 'rows', len(out))
    json.dump(out, open(os.path.join(V, 'rows.json'), 'w'), ensure_ascii=False)
    for r in out[:8]: print('   ', r)


def geocode():
    """Every distinct address-looking cell, through the Census batch geocoder (one request)."""
    out = json.load(open(os.path.join(V, 'rows.json')))
    head = next((i for i, r in enumerate(out) if any('address' in c.lower() for c in r)), None)
    if head is None: raise RuntimeError('no address column found')
    col = next(i for i, c in enumerate(out[head]) if 'address' in c.lower())
    addrs = sorted({r[col] for r in out[head + 1:] if len(r) > col and r[col]})
    buf = io.StringIO(); w = csv.writer(buf)
    for i, a in enumerate(addrs): w.writerow([i, a, 'San Francisco', 'CA', ''])
    import uuid
    bnd = uuid.uuid4().hex
    body = (f'--{bnd}\r\nContent-Disposition: form-data; name="benchmark"\r\n\r\nPublic_AR_Current\r\n'
            f'--{bnd}\r\nContent-Disposition: form-data; name="addressFile"; filename="a.csv"\r\nContent-Type: text/csv\r\n\r\n{buf.getvalue()}\r\n--{bnd}--\r\n').encode()
    import urllib.request
    req = urllib.request.Request('https://geocoding.geo.census.gov/geocoder/locations/addressbatch', data=body,
                                 headers={'Content-Type': f'multipart/form-data; boundary={bnd}', 'User-Agent': 'city-layers/1.0 (https://layers.city)'})
    res = urllib.request.urlopen(req, timeout=600).read().decode()
    sites = {}
    for r in csv.reader(io.StringIO(res)):
        if len(r) > 5 and r[2] == 'Match':
            x, y = r[5].split(',')
            sites[addrs[int(r[0])]] = [round(float(x), 6), round(float(y), 6)]
    json.dump({'fetched': time.strftime('%Y-%m-%d'), 'source': LIST, 'sites': sites, 'unmatched': [a for a in addrs if a not in sites]},
              open(os.path.join(V, 'sites.json'), 'w'), indent=0, ensure_ascii=False)
    print('  geocoded', len(sites), 'of', len(addrs), '· unmatched', [a for a in addrs if a not in sites][:20])


for label, fn in [('list', xlsx), ('precincts', precincts), ('rows', rows), ('geocode', geocode)]:
    print('==', label); step(label, fn)
print('FAILED:', FAILED or 'none')
