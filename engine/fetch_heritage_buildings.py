"""Heritage buildings: fetch a city's individually protected buildings into cities/<city>/raw/heritage_buildings.json
for engine/heritage_buildings.py. Runs in GitHub Actions (fetch-heritage-buildings.yml); the sandbox can't
reach these servers. The source is set in cities/<city>/heritage_buildings.json:

  - "socrata" (Chicago): the City's Individual Landmarks (tdab-kixi): name, address, year built, architect,
    designation date and a point.
  - "ckan_shp" (Toronto): the City's Heritage Register (address points shapefile in a zip). Every record is
    kept with all its attributes; the build keeps only individually designated properties (Part IV of the
    Ontario Heritage Act). The log lists the fields and the values of the status-like ones.

Writes {fetched, source, fields, rows: [{...attributes, lon, lat}]}.
Usage: python3 engine/fetch_heritage_buildings.py <city>
"""
import collections, datetime as dt, io, json, os, sys, time, urllib.parse, urllib.request, zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
city = sys.argv[1]
CFG = json.load(open(os.path.join(ROOT, 'cities', city, 'heritage_buildings.json')))
OUT = os.path.join(ROOT, 'cities', city, 'raw', 'heritage_buildings.json')
UA = {'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)'}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r: return r.read()
        except Exception as e:
            print('  retry', i + 1, url[:140], e); time.sleep(15 * (i + 1))
    raise RuntimeError('failed: ' + url)


S = CFG['source']
if S['type'] == 'socrata_geo':
    # Polygons (each landmark's parcel or footprint): one point per landmark at its shape's centre.
    from shapely.geometry import shape
    fc = json.loads(get(S['url'] + '?' + urllib.parse.urlencode({'$limit': 5000})))
    rows = []
    for f in fc['features']:
        r = {k: v for k, v in f['properties'].items() if not k.startswith(':@')}
        if f.get('geometry'):
            g = shape(f['geometry']); c = g.representative_point()
            r['lon'], r['lat'] = round(c.x, 6), round(c.y, 6)
        rows.append(r)
    fields = sorted({k for r in rows for k in r})
elif S['type'] == 'socrata':
    rows = json.loads(get(S['url'] + '?' + urllib.parse.urlencode({'$limit': 5000})))
    for r in rows:
        r['lon'], r['lat'] = (float(r['longitude']), float(r['latitude'])) if r.get('latitude') else (None, None)
        for k in [k for k in r if k.startswith(':@') or k == 'location']: r.pop(k)
    fields = sorted({k for r in rows for k in r})
else:
    import shapefile
    pkg = json.loads(get(S['ckan']))['result']
    res = [r for r in pkg['resources'] if (r.get('format') or '').upper() == 'SHP']
    res.sort(key=lambda r: r.get('last_modified') or r.get('created') or '', reverse=True)
    r0 = next((r for r in res if '2022' not in r['name']), res[0])
    print('resource:', r0['name'], r0['url'])
    z = zipfile.ZipFile(io.BytesIO(get(r0['url'])))
    print('files:', z.namelist())
    shp = next(n for n in z.namelist() if n.lower().endswith('.shp'))
    base = shp[:-4]
    pick = lambda ext: io.BytesIO(z.read(next(n for n in z.namelist() if n.lower() == (base + ext).lower())))
    sf = shapefile.Reader(shp=pick('.shp'), dbf=pick('.dbf'), shx=pick('.shx'))
    fields = [f[0] for f in sf.fields[1:]]
    rows = []
    for sr in sf.iterShapeRecords():
        rec = dict(zip(fields, sr.record))
        pts = sr.shape.points
        rec['lon'], rec['lat'] = (pts[0][0], pts[0][1]) if pts else (None, None)
        rows.append({k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in rec.items()})
    for n in [n for n in z.namelist() if n.lower().endswith('.txt')]:
        print('--', n); print(z.read(n).decode('utf8', 'replace')[:3000])
keep = S.get('keep')
if keep:   # e.g. {"STATUS": ["Part IV"]}: only rows whose field has one of these values are written
    rows = [r for r in rows if all(str(r.get(k)) in v for k, v in keep.items())]
    print('kept by', keep, ':', len(rows))
if S.get('fields'): rows = [{k: r.get(k) for k in S['fields'] + ['lon', 'lat']} for r in rows]
print('fields:', fields)
print('rows:', len(rows), '· with a point:', sum(1 for r in rows if r.get('lat')))
for f in (S.get('fields') or fields):
    vals = collections.Counter(str(r.get(f)) for r in rows)
    if len(vals) <= 40: print(' ', f, dict(vals.most_common(40)))
    else: print(' ', f, len(vals), 'values, e.g.', [v for v, _ in vals.most_common(5)])
json.dump({'fetched': dt.date.today().isoformat(), 'source': S, 'fields': fields, 'rows': rows}, open(OUT, 'w'), separators=(',', ':'), default=str)
print('wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')
