"""Fetch Hyderabad's non-OpenStreetMap inputs into cities/hyderabad/raw/ (GitHub Actions: fetch-hyderabad.yml;
OpenStreetMap is fetch_osm.py). The sandbox can't reach these hosts. Each step is logged on its own.
Shapes are simplified (about 10 m) before saving, so the raw files stay small enough to commit.

- OpenCity: the Department of Posts' 2025 PIN code boundaries (Hyderabad and Secunderabad, and all of India).
- DataMeet: assembly and Lok Sabha constituencies (2008 delimitation, still in force).
"""
import json, os, re, subprocess, sys, tempfile, time, traceback, urllib.parse, urllib.request, zipfile
from shapely.geometry import shape, mapping, box

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RAW = os.path.join(HERE, 'raw'); os.makedirs(RAW, exist_ok=True)
TMP = tempfile.mkdtemp()
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}
S, W, N, E = 16.6, 77.2, 18.45, 79.2          # the four districts with a margin
BOX = '%s,%s,%s,%s' % (S, W, N, E)
FAILED = []


def step(label, fn):
    print('\n==', label, flush=True)
    try: fn()
    except Exception as e:
        print('FAILED', label, repr(e)); traceback.print_exc(); FAILED.append(label)


def get(url, data=None, tries=4, timeout=600):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, url[:120], e); time.sleep(20 * (i + 1))
    raise RuntimeError('failed: ' + url)


def save(name, obj):
    with open(os.path.join(RAW, name), 'w') as f:
        json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
    print('  wrote', name, os.path.getsize(os.path.join(RAW, name)) // 1000, 'KB')


def r5(g):
    return json.loads(json.dumps(mapping(g)), parse_float=lambda v: round(float(v), 5))


def ckan_resource_urls(package):
    d = json.loads(get('https://data.opencity.in/api/3/action/package_show?id=' + package))['result']
    return [(r.get('name'), r.get('url'), r.get('last_modified') or r.get('created')) for r in d['resources']]


def pincodes():
    feats, meta = [], []
    for package, want in (('india-pincode-maps-2025', r'(?i)hyderabad|all india'),):
        # The Hyderabad file first: where both cover a PIN, build.py keeps the first source's shape.
        res = sorted(ckan_resource_urls(package), key=lambda r: 'hyderabad' not in (r[0] or '').lower())
        for name, url, mod in res:
            if not re.search(want, name or ''): continue
            print('  resource', name, mod, url)
            p = os.path.join(TMP, os.path.basename(urllib.parse.urlparse(url).path))
            open(p, 'wb').write(get(url))
            print('  size', os.path.getsize(p) // 1000, 'KB')
            src = p
            if p.lower().endswith('.kmz'):   # a zip holding a .kml (GDAL's KMZ reader rejects this one): unzip it
                d = tempfile.mkdtemp(dir=TMP); zipfile.ZipFile(p).extractall(d)
                src = next(os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f.lower().endswith('.kml'))
            out = os.path.join(TMP, 'pin_%d.geojson' % len(meta))
            subprocess.run(['ogr2ogr', '-f', 'GeoJSON', '-t_srs', 'EPSG:4326', '-spat', str(W), str(S), str(E), str(N), '-nlt', 'PROMOTE_TO_MULTI', out, src], check=True)
            fs = json.load(open(out))['features']
            print('  features', len(fs), '· fields', sorted(fs[0]['properties']) if fs else [])
            if fs: print('  sample', {k: v for k, v in fs[0]['properties'].items() if v not in (None, '')})
            for f in fs:
                if not f.get('geometry'): continue
                g = shape(f['geometry']).buffer(0).simplify(0.0001, preserve_topology=True)
                if g.is_empty: continue
                feats.append({'type': 'Feature', 'properties': dict({k: v for k, v in f['properties'].items() if v not in (None, '') and k.lower() != 'description'},
                              _src=name), 'geometry': r5(g)})
            meta.append({'name': name, 'modified': mod, 'url': url, 'features': len(fs)})
    save('pincodes.geojson', {'type': 'FeatureCollection', 'sources': meta, 'features': feats})


def constituencies():
    base = 'https://raw.githubusercontent.com/datameet/maps/master/'
    area = box(W, S, E, N)
    for path, out in (('website/docs/data/geojson/ac.geojson', 'assembly.geojson'),
                      ('parliamentary-constituencies/india_pc_2019_simplified.geojson', 'loksabha.geojson')):
        fs = json.loads(get(base + path))['features']
        keep = [{'type': 'Feature', 'properties': f['properties'], 'geometry': r5(shape(f['geometry']).buffer(0).simplify(0.0001, preserve_topology=True))}
                for f in fs if f.get('geometry') and shape(f['geometry']).intersects(area)]
        save(out, {'type': 'FeatureCollection', 'features': keep})


OC = 'https://data.opencity.in/dataset/'
OC_FILES = [  # OpenCity copies of official maps, to check constituency lines against (DataMeet's are rough in the city)
    ('oc_ac_hyd_rr.geojson', OC + 'ddf1cb4a-1433-4e8b-aeeb-afb2d5ba5021/resource/76aa80ff-1791-4c19-a773-8f96658825f7/download/3fbc4f52-cde9-48d1-a257-7b4b7470f1a4.kml'),
    ('oc_ac_telangana.geojson', OC + 'ddf1cb4a-1433-4e8b-aeeb-afb2d5ba5021/resource/ab8095a4-cc07-4a73-8da2-3458baab4600/download/8137a4f0-4d33-48d9-ae93-23b2bf558424.kml'),
    ('oc_pc_telangana.geojson', OC + 'ddf1cb4a-1433-4e8b-aeeb-afb2d5ba5021/resource/030ea574-826a-468d-935f-3092f4658f1d/download/f809164b-4773-4360-be76-6fc5f8bb39cf.kml'),
    ('oc_ghmc_wards_2022.geojson', OC + '15cb7d8d-eed1-4aad-8cd7-f281cbf4f94f/resource/14b033e3-3721-4149-8326-cc29420e062e/download/ghmc_wards.kml'),
]


def opencity_maps():
    for out, url in OC_FILES:
        p = os.path.join(TMP, os.path.basename(url))
        open(p, 'wb').write(get(url))
        g = os.path.join(TMP, out)
        subprocess.run(['ogr2ogr', '-f', 'GeoJSON', '-t_srs', 'EPSG:4326', '-nlt', 'PROMOTE_TO_MULTI', g, p], check=True)
        fs = json.load(open(g))['features']
        print('  %s: %d features · fields %s' % (out, len(fs), sorted(fs[0]['properties']) if fs else []))
        if fs: print('   sample', {k: v for k, v in fs[0]['properties'].items() if v not in (None, '') and k.lower() != 'description'},
                     '· description', str(fs[0]['properties'].get('description') or '')[:300])
        keep = [{'type': 'Feature', 'properties': {k: v for k, v in f['properties'].items() if v not in (None, '')},
                 'geometry': r5(shape(f['geometry']).buffer(0).simplify(0.00005, preserve_topology=True))} for f in fs if f.get('geometry')]
        save(out, {'type': 'FeatureCollection', 'features': keep})


if __name__ == '__main__':
    only = sys.argv[1:]
    for label, fn in (('pincodes', pincodes), ('constituencies', constituencies), ('opencity_maps', opencity_maps)):
        if not only or label in only: step(label, fn)
    print('\nfailed:', FAILED or 'none')
