"""Helpers shared by the Dallas fetch scripts: polite HTTP with retries, Overpass with fallback servers,
logged steps (one failure doesn't stop the rest) and saving into raw/."""
import json, os, subprocess, tempfile, time, urllib.parse, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
os.makedirs(RAW, exist_ok=True)
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}
FRAME = (-98.7, 31.55, -95.3, 33.85)      # land shown around the region
REGION = (-98.07, 31.80, -95.84, 33.44)    # the nine counties of the Metroplex view
CITY = (-97.01, 32.60, -96.45, 33.04)      # the City of Dallas
CORE = ['Dallas', 'Tarrant', 'Collin', 'Denton', 'Rockwall', 'Ellis', 'Johnson', 'Kaufman', 'Parker']
TMP = tempfile.mkdtemp()
FAILED = []


def get(url, data=None, tries=4, timeout=300):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, url[:140], e); time.sleep(15 * (i + 1))
    raise RuntimeError('failed: ' + url)


def download(url, path, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=900) as r, open(path, 'wb') as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b)
            print('  downloaded', os.path.basename(path), os.path.getsize(path) // 1_000_000, 'MB')
            return path
        except Exception as e:
            print('  retry', i + 1, url[:140], e); time.sleep(30 * (i + 1))
    raise RuntimeError('failed: ' + url)


def step(label, fn):
    try:
        fn()
    except Exception as e:
        import traceback
        print('FAILED', label, repr(e)); traceback.print_exc()
        FAILED.append(label)


def save(name, obj):
    with open(os.path.join(RAW, name), 'w') as f:
        json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
    print('wrote', name, os.path.getsize(os.path.join(RAW, name)) // 1000, 'KB')


def shp_to_geojson(zip_path, where, out, select=None, spat=None):
    """Unzip a shapefile and write the matching features as WGS84 GeoJSON with ogr2ogr."""
    d = tempfile.mkdtemp(dir=TMP)
    zipfile.ZipFile(zip_path).extractall(d)
    shp = next(os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f.endswith('.shp'))
    cmd = ['ogr2ogr', '-f', 'GeoJSON', '-t_srs', 'EPSG:4326', '-lco', 'COORDINATE_PRECISION=6', '-where', where]
    if select: cmd += ['-select', select]
    if spat: cmd += ['-spat', *map(str, spat), '-spat_srs', 'EPSG:4326']
    subprocess.run(cmd + [os.path.join(RAW, out), shp], check=True)
    n = len(json.load(open(os.path.join(RAW, out)))['features'])
    print('wrote', out, n, 'features')


SERVERS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter',
           'https://maps.mail.ru/osm/tools/overpass/api/interpreter']


def overpass(q, name):
    for i in range(6):
        url = SERVERS[i % len(SERVERS)]
        try:
            d = json.loads(get(url, urllib.parse.urlencode({'data': q}).encode(), tries=1, timeout=400))
            if d.get('remark') and 'error' in d['remark'].lower(): raise RuntimeError(d['remark'])
            save(name, d); return d
        except Exception as e:
            print('  overpass retry', i + 1, url, e); time.sleep(20 * (i + 1))
    raise RuntimeError('overpass failed: ' + name)




def arcgis(layer_url, name, where='1=1', fields='*', page=1000):
    """Every feature of an ArcGIS REST layer as WGS84 GeoJSON, paged."""
    meta = json.loads(get(layer_url + '?f=json'))
    print(' ', meta.get('name'), '| fields:', [f['name'] for f in meta.get('fields', [])][:40])
    feats, off = [], 0
    while True:
        q = {'where': where, 'outFields': fields, 'outSR': 4326, 'f': 'geojson', 'resultOffset': off, 'resultRecordCount': page, 'geometryPrecision': 6}
        d = json.loads(get(layer_url + '/query?' + urllib.parse.urlencode(q)))
        got = d.get('features', [])
        feats += got
        if len(got) < page or not (d.get('exceededTransferLimit') or len(got) == page): break
        off += len(got); time.sleep(1)
    save(name, {'type': 'FeatureCollection', 'features': feats})
    if feats: print('  sample', feats[0]['properties'])
    return feats
