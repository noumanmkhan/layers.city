"""Fetch Melbourne's electoral boundaries and current representatives into raw/representatives/. Runs in GitHub Actions
(fetch-melbourne.yml when this file changes; weekly by fetch-melbourne-representatives.yml); the sandbox can't reach these.

  districts.geojson  Victorian Legislative Assembly districts (Vicmap Admin - State Assembly Polygon 2022: the 2021
                     redivision, used at the 2022 and 2026 elections), from the Vicmap open data WFS. CC BY 4.0.
  divisions.geojson  Federal electoral divisions (Victoria's 2024 redistribution, used since the 2025 election), from
                     the AEC's GIS download (ESRI shapefile).
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


WFS = 'https://opendata.maps.vic.gov.au/geoserver/wfs'


def wfs_layers():
    cap = get(WFS + '?service=WFS&request=GetCapabilities&version=2.0.0').decode('utf-8', 'replace')
    names = re.findall(r'<(?:wfs:)?Name>([^<]+)</(?:wfs:)?Name>', cap)
    hits = [n for n in names if re.search(r'(?i)assembly|electoral|federal|commonwealth|council|division', n)]
    print('  WFS layers (%d); electoral ones: %s' % (len(names), hits))
    return hits


def wfs_get(layer, out):
    q = {'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature', 'typeNames': layer, 'outputFormat': 'application/json',
         'srsName': 'EPSG:4326'}   # all of Victoria's 88 districts (a bbox in EPSG:4326 matched nothing on November 12)
    fc = json.loads(get(WFS + '?' + urllib.parse.urlencode(q)))
    print('  %s: %d features · fields %s' % (layer, len(fc['features']), sorted(fc['features'][0]['properties']) if fc['features'] else None))
    json.dump(fc, open(os.path.join(OUT, out), 'w'), separators=(',', ':'))


LAYERS = []
step('wfs layers', lambda: LAYERS.extend(wfs_layers()))
# Victorian Legislative Assembly districts, 2021 redivision (DataVic "Vicmap Admin - State Assembly Polygon 2022")
step('state districts', lambda: wfs_get('open-data-platform:state_assembly_2022', 'districts.geojson'))


def divisions():
    # The AEC's own file for Victoria's 2024 redistribution (aec.gov.au/Electorates/gis/gis_datadownload.htm, "Current").
    shp_zip_to_geojson('https://aec.gov.au/Electorates/gis/files/Vic-october-2024-esri.zip', 'divisions.geojson', None)
step('federal divisions', divisions)


def elected():
    b = get('https://results.aec.gov.au/31496/Website/Downloads/HouseMembersElectedDownload-31496.csv')
    open(os.path.join(OUT, 'aec_elected.csv'), 'wb').write(b)
    print('  aec_elected.csv', len(b), 'bytes ·', b.decode('utf-8', 'replace').splitlines()[:3])
step('aec members elected', elected)


def handbook():
    d = json.loads(get('https://handbookapi.aph.gov.au/api/individuals'))
    rows = d.get('value', d) if isinstance(d, dict) else d
    keep = ('PHID', 'DisplayName', 'GivenName', 'PreferredName', 'FamilyName', 'Party', 'PartyAbbrev', 'Electorate', 'State',
            'StateAbbrev', 'MPorSenator', 'InCurrentParliament')
    cur = [{k: r.get(k) for k in keep} for r in rows if r.get('InCurrentParliament') in (True, 'true', 'True', 1, 'Yes')]
    print('  handbook: %d people, %d in the current Parliament · MPorSenator values %s' % (len(rows), len(cur), sorted({str(r.get('MPorSenator')) for r in rows})))
    print('  e.g.', json.dumps([r for r in cur if r.get('Electorate')][:3]))
    json.dump(cur, open(os.path.join(OUT, 'handbook.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
step('parliamentary handbook', handbook)

print('done; failed:', FAILED or 'none')
