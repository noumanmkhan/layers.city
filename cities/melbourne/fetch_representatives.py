"""Fetch Melbourne's electoral boundaries and current representatives into raw/representatives/. Runs in GitHub Actions
(fetch-melbourne.yml when this file changes; weekly by fetch-melbourne-representatives.yml); the sandbox can't reach these.

  districts.geojson  Victorian Legislative Assembly districts (Vicmap Admin - State Assembly Polygon 2022: the 2021
                     redivision, used at the 2022 and 2026 elections), from DataVic. CC BY 4.0.
  divisions.geojson  Federal electoral divisions (AEC; Victoria's 2024 redistribution, used since the 2025 election),
                     from data.gov.au. CC BY 4.0.
  aec_elected.csv    Members elected at the 2025 federal election (AEC tally room).
  handbook.json      Current members of the House of Representatives (Parliamentary Handbook API), for by-elections
                     since 2025 and each member's page.
Members of the Legislative Assembly come after the November 28, 2026 state election. Each step keeps last time's file
if it fails.
"""
import csv, io, json, os, re, subprocess, sys, tempfile, urllib.parse, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_lib import TMP, FAILED, get, download, step

OUT = os.path.join(HERE, 'raw', 'representatives'); os.makedirs(OUT, exist_ok=True)
BOX = (144.33, -38.51, 145.88, -37.17)   # Greater Melbourne


def ckan(api, query=None, pid=None):
    if pid:
        return json.loads(get(api + 'package_show?id=' + pid))['result']
    res = json.loads(get(api + 'package_search?' + urllib.parse.urlencode({'q': query, 'rows': 20})))['result']['results']
    for p in res: print('   ', p['name'], '|', p['title'])
    return res


def shp_zip_to_geojson(url, out, keep_fields):
    z = download(url, os.path.join(TMP, os.path.basename(out) + '.zip'))
    d = tempfile.mkdtemp(dir=TMP)
    zipfile.ZipFile(z).extractall(d)
    shps = [os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f.lower().endswith('.shp')]
    print('  shapefiles:', [os.path.relpath(s, d) for s in shps])
    shp = max(shps, key=os.path.getsize)
    info = subprocess.run(['ogrinfo', '-so', '-al', shp], capture_output=True, text=True).stdout
    print('  ' + '\n  '.join(l for l in info.splitlines() if ':' in l)[:1500])
    tmp = os.path.join(TMP, os.path.basename(out))
    subprocess.run(['ogr2ogr', '-f', 'GeoJSON', '-t_srs', 'EPSG:4326', '-lco', 'COORDINATE_PRECISION=6', '-spat', *map(str, BOX),
                    '-spat_srs', 'EPSG:4326', '-simplify', '0.00003', tmp, shp], check=True)
    fc = json.load(open(tmp))
    print('  fields:', sorted(fc['features'][0]['properties']) if fc['features'] else None, '·', len(fc['features']), 'features')
    json.dump(fc, open(os.path.join(OUT, out), 'w'), separators=(',', ':'))


def pick_zip(pkg, prefer=r'(?i)shp|shape|esri'):
    rs = pkg['resources']
    for r in rs: print('   resource:', r.get('name'), '|', r.get('format'), '|', r.get('url'))
    z = [r for r in rs if re.search(prefer, (r.get('format') or '') + ' ' + (r.get('name') or '') + ' ' + (r.get('url') or ''))
         and (r.get('url') or '').lower().split('?')[0].endswith('.zip')]
    z = z or [r for r in rs if (r.get('url') or '').lower().split('?')[0].endswith('.zip')]
    return z[0]['url'] if z else None


def districts():
    api = 'https://discover.data.vic.gov.au/api/3/action/'
    try:
        pkg = ckan(api, pid='vicmap-admin-state-assembly-polygon-2022')
    except Exception as e:
        print('  package_show failed', e)
        pkg = ckan(api, query='State Assembly Polygon 2022')[0]
    url = pick_zip(pkg)
    print('  districts from', url)
    shp_zip_to_geojson(url, 'districts.geojson', None)
step('state districts', districts)


def divisions():
    api = 'https://data.gov.au/data/api/3/action/'
    res = ckan(api, query='Federal Electoral Divisions AEC')
    cand = [p for p in res if re.search(r'(?i)federal electoral division', p['title'])]
    cand.sort(key=lambda p: ('2025' in p['title'], '2024' in p['title'], p.get('metadata_modified', '')), reverse=True)
    for p in cand:
        url = pick_zip(p)
        if url:
            print('  divisions from', p['title'], url)
            shp_zip_to_geojson(url, 'divisions.geojson', None); return
    raise RuntimeError('no federal divisions package with a zip')
step('federal divisions', divisions)


def elected():
    b = get('https://results.aec.gov.au/31496/Website/Downloads/HouseMembersElectedDownload-31496.csv')
    open(os.path.join(OUT, 'aec_elected.csv'), 'wb').write(b)
    print('  aec_elected.csv', len(b), 'bytes ·', b.decode('utf-8', 'replace').splitlines()[:3])
step('aec members elected', elected)


def handbook():
    d = json.loads(get('https://handbookapi.aph.gov.au/api/individuals'))
    rows = d.get('value', d) if isinstance(d, dict) else d
    print('  handbook individuals:', len(rows), '· fields', sorted(rows[0]) if rows else None)
    # Keep the current members of the House only (the full list runs back to 1901).
    cur = [r for r in rows if any('Representatives' in str(v) or 'MP' == str(v) for v in r.values())
           and not any(k.lower().startswith(('deathdate', 'dateofdeath')) and r.get(k) for k in r)]
    print('  rows mentioning the House:', len(cur), '· e.g.', json.dumps(cur[:2])[:1500])
    json.dump(rows if len(json.dumps(rows)) < 3_000_000 else cur, open(os.path.join(OUT, 'handbook.json'), 'w'), separators=(',', ':'))
step('parliamentary handbook', handbook)

print('done; failed:', FAILED or 'none')
