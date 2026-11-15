"""Census tracts for the neighbourhood lens beyond the City of Toronto, into raw/gta_tracts/:

  tracts.geojson   2021 census tract boundaries (Statistics Canada cartographic boundary file, lct_000b21a_e) for the
                   Toronto (535), Oshawa (532) and Hamilton (537, for Burlington) CMAs, in WGS84, {ct: "5350401.00"}
  profile.json     {ct: {"<section>|<characteristic>": count or rate}} for the figures tracts.py needs, from the 2021
                   Census Profile for census tracts (98-401-X2021007). Each row is keyed by the "Total - ..." section
                   it sits under, so names that repeat across sections ("2016 to 2021") stay apart.

Statistics Canada Open Licence. Run from GitHub Actions (fetch-gta-card.yml); the sandbox can't reach statcan.gc.ca."""
import csv, io, json, os, re, sys, time, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'gta_tracts')
TMP = '/tmp/gta_tracts'
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
CMAS = ('535', '532', '537')
UA = {'User-Agent': 'layers.city-pipeline (go@layers.city)'}
csv.field_size_limit(sys.maxsize)


def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    for a in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=1800) as r, open(path, 'wb') as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b)
            print('downloaded', url, round(os.path.getsize(path) / 1e6), 'MB', flush=True)
            return path
        except Exception as e:
            print('  retry', a + 1, url, e, flush=True); time.sleep(20 * (a + 1))
    raise SystemExit('failed: ' + url)


# ---------- boundaries ----------
import shapefile
from pyproj import Transformer
bz = download('https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lct_000b21a_e.zip', TMP + '/lct.zip')
with zipfile.ZipFile(bz) as z:
    z.extractall(TMP + '/lct')
shp = [os.path.join(dp, f) for dp, _, fs in os.walk(TMP + '/lct') for f in fs if f.endswith('.shp')][0]
prj = open(shp[:-4] + '.prj').read()
tr = Transformer.from_crs(prj, 'EPSG:4326', always_xy=True)
sf = shapefile.Reader(shp)
fields = [f[0] for f in sf.fields[1:]]
print('boundary fields:', fields)
feats = []
for sr in sf.iterShapeRecords():
    rec = dict(zip(fields, sr.record))
    ct = str(rec.get('CTUID') or rec.get('CTUID_') or '')
    if ct[:3] not in CMAS:
        continue
    shape = sr.shape
    parts = list(shape.parts) + [len(shape.points)]
    # Shapefile rings: clockwise ones are outer rings (each starts a polygon), counter-clockwise ones are holes.
    polys = []
    for i in range(len(parts) - 1):
        pts = shape.points[parts[i]:parts[i + 1]]
        area = sum(pts[k][0] * pts[k + 1][1] - pts[k + 1][0] * pts[k][1] for k in range(len(pts) - 1))
        xs, ys = tr.transform([p[0] for p in pts], [p[1] for p in pts])
        ring = [[round(x, 5), round(y, 5)] for x, y in zip(xs, ys)]
        if area <= 0 or not polys: polys.append([ring])
        else: polys[-1].append(ring)
    feats.append({'type': 'Feature', 'properties': {'ct': ct}, 'geometry': {'type': 'MultiPolygon', 'coordinates': polys}})
json.dump({'type': 'FeatureCollection', 'source': 'Statistics Canada, 2021 Census cartographic boundary file (census tracts), Open Licence',
           'features': feats}, open(os.path.join(OUT, 'tracts.geojson'), 'w'), separators=(',', ':'))
print('tracts:', len(feats), flush=True)

# ---------- census profile ----------
# Sections (the "Total - ..." row a characteristic sits under) and the rows kept from each.
WANT = {
    'Population and dwellings': None,
    'Age groups of the population': {'0 to 14 years', '15 to 19 years', '20 to 24 years', '25 to 29 years', '30 to 34 years',
                                     '35 to 39 years', '40 to 44 years', '45 to 49 years', '50 to 54 years', '55 to 59 years',
                                     '60 to 64 years', '65 years and over'},
    'Occupied private dwellings by structural type of dwelling': None,
    'Private households by tenure': None,
    'Occupied private dwellings by period of construction': None,
    'Owner households in non-farm, non-reserve private dwellings': None,
    'Tenant households in non-farm, non-reserve private dwellings': None,
    'Main mode of commuting': None,
    'Immigrant status and period of immigration': None,
    'Language spoken most often at home': None,
}
SINGLE = {'Population, 2021', 'Median value of dwellings ($)', 'Median monthly shelter costs for rented dwellings ($)',
          'Median monthly shelter costs for owned dwellings ($)', 'Total private dwellings', 'Private dwellings occupied by usual residents'}
pz = download('https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm?Lang=E&FILETYPE=CSV&GEONO=007',
              TMP + '/profile.zip')
prof, sections_seen = {}, set()
with zipfile.ZipFile(pz) as z:
    names = z.namelist(); print('profile zip:', names, flush=True)
    data = [n for n in names if re.search(r'data.*\.csv$', n, re.I) and 'English' in n] or [n for n in names if n.lower().endswith('.csv')]
    for dn in data:
        with z.open(dn) as raw:
            rd = csv.DictReader(io.TextIOWrapper(raw, encoding='latin-1'))
            print('columns:', rd.fieldnames[:20], flush=True)
            section = None
            for r in rd:
                geo = (r.get('ALT_GEO_CODE') or r.get('GEO_CODE') or '').strip()
                name = (r.get('CHARACTERISTIC_NAME') or '').strip()
                if name.startswith('Total - '):
                    section = name[8:]
                if len(geo) < 10 or geo[:3] not in CMAS:
                    continue
                key = None
                if name in SINGLE:
                    key = name
                else:
                    for s, rows in WANT.items():
                        if section and section.startswith(s) and (rows is None or name in rows):
                            key = s + '|' + name; sections_seen.add(section); break
                if not key:
                    continue
                v = (r.get('C1_COUNT_TOTAL') or '').strip()
                try: v = float(v)
                except ValueError: continue
                d = prof.setdefault(geo, {})
                if key not in d: d[key] = v
json.dump(prof, open(os.path.join(OUT, 'profile.json'), 'w'), separators=(',', ':'))
print('profiles:', len(prof), 'tracts; sections:', sorted(sections_seen)[:40], flush=True)
