"""Census tracts for the neighbourhood lens beyond the City of Toronto, into raw/gta_tracts/:

  tracts.geojson   2021 census tracts (cartographic boundaries) of the Toronto (535), Oshawa (532) and Hamilton (537, for
                   Burlington) CMAs, from Statistics Canada's ArcGIS service, with CTUID and DGUID.
  profile.json     {"labels": {characteristic id: indented name}, "cts": {CTUID: {characteristic id: value}}}: the 2021
                   Census Profile for those tracts, cut to the sections the lens uses, from the Census Profile web data
                   service (SDMX, dataflow DF_CT), labelled the way Vancouver's fetch_census.py labels DAs.

www12.statcan.gc.ca refuses GitHub's runners (403); these two services answer. Statistics Canada Open Licence.
Run from GitHub Actions (fetch-gta-card.yml)."""
import csv, io, json, os, re, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'gta_tracts')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}
GEO = 'https://geo.statcan.gc.ca/geo_wa/rest/services/2021/Cartographic_boundary_files/MapServer/'
API = 'https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/'
CMAS = ('535', '532', '537')
SECTIONS = ['Total - Age groups of the population', 'Total - Private households by tenure',
            'Total - Occupied private dwellings by structural type of dwelling', 'Total - Occupied private dwellings by period of construction',
            'Total - Language spoken most often at home', 'Total - Immigrant status and period of immigration',
            'Total - Main mode of commuting']
SINGLE = ['Population, 2021', 'Median value of dwellings ($)', 'Median monthly shelter costs for rented dwellings ($)']


def get(url, accept='*/*', tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA, Accept=accept)), timeout=300) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, url[:160], e, flush=True); time.sleep(10 * (i + 1))
    raise RuntimeError('failed: ' + url)


# ---------- boundaries ----------
layers = json.loads(get(GEO + '?f=json'))['layers']
print('layers:', [(l['id'], l['name']) for l in layers], flush=True)
ct_layer = next(l['id'] for l in layers if re.match(r'CT\b', l['name']))
feats, start = [], 0
where = ' OR '.join("CTUID LIKE '%s%%'" % c for c in CMAS)
while True:
    q = urllib.parse.urlencode({'where': where, 'outFields': '*', 'outSR': 4326, 'f': 'geojson',
                                'returnGeometry': 'true', 'orderByFields': 'OBJECTID', 'maxAllowableOffset': 0.00003,
                                'resultOffset': start, 'resultRecordCount': 500})
    d = json.loads(get(GEO + str(ct_layer) + '/query?' + q))
    if 'error' in d: raise RuntimeError(d['error'])
    feats += d.get('features', [])
    if not d.get('exceededTransferLimit') and len(d.get('features', [])) < 500: break
    start += 500; time.sleep(1)
json.dump({'type': 'FeatureCollection', 'source': 'Statistics Canada, 2021 cartographic boundary files (census tracts), Open Licence',
           'features': feats}, open(os.path.join(OUT, 'tracts.geojson'), 'w'), separators=(',', ':'))
print('tracts:', len(feats), '· fields:', list(feats[0]['properties']) if feats else None, flush=True)

# ---------- census profile (SDMX) ----------
x = get(API + 'dataflow/STC_CP/DF_CT?references=all', 'application/xml')
root = ET.fromstring(x)
ns = {'s': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure', 'c': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common'}
lists = {cl.get('id'): cl for cl in root.iter('{%s}Codelist' % ns['s'])}
char_cl = max((cl for k, cl in lists.items() if 'CHAR' in k.upper()), key=lambda cl: len(cl.findall('s:Code', ns)))
names, parent = {}, {}
for code in char_cl.findall('s:Code', ns):
    cid = code.get('id')
    nm = next((n.text for n in code.findall('c:Name', ns) if n.get('{http://www.w3.org/XML/1998/namespace}lang') == 'en'), None)
    names[cid] = (nm or '').strip()
    p = code.find('s:Parent/Ref', ns)
    if p is not None: parent[cid] = p.get('id')
def depth(c):
    d = 0
    while c in parent: c = parent[c]; d += 1
    return d
def root_of(c):
    while c in parent: c = parent[c]
    return c
if parent:
    keep = {c for c in names if any(names[root_of(c)].startswith(p) for p in SECTIONS) or names[c] in SINGLE}
else:
    keep, on = set(), False
    for c in sorted(names, key=int):
        if names[c].startswith('Total - '): on = any(names[c].startswith(p) for p in SECTIONS)
        if on or names[c] in SINGLE: keep.add(c)
print('characteristics kept:', len(keep), flush=True)

dg = {f['properties']['DGUID']: f['properties']['CTUID'] for f in feats}
keys = sorted(dg)
out = defaultdict(dict)
for i in range(0, len(keys), 40):
    batch = keys[i:i + 40]
    t = get(API + 'data/STC_CP,DF_CT/A5.' + '+'.join(batch) + '.1..1?format=csv', 'text/csv').decode('utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(t)))
    if i == 0: print('csv columns:', list(rows[0].keys()) if rows else None, flush=True)
    if not rows: continue
    cols = list(rows[0].keys())
    gk = next(k for k in cols if 'GEO' in k.upper() or 'REF_AREA' in k.upper())
    ck = next(k for k in cols if 'CHARACTERISTIC' in k.upper())
    vk = next(k for k in cols if k.upper() in ('OBS_VALUE', 'VALUE'))
    for r in rows:
        c = r[ck].split(':')[0].strip()
        if c not in keep: continue
        v = (r[vk] or '').strip()
        out[dg.get(r[gk].split(':')[0].strip(), r[gk])][c] = float(v) if re.fullmatch(r'-?[\d.]+(E-?\d+)?', v) else None
    if i // 40 % 10 == 0: print('  batch', i // 40 + 1, 'of', (len(keys) + 39) // 40, flush=True)
    time.sleep(1)
labels = {c: '  ' * depth(c) + names[c] for c in sorted(keep, key=int)}
json.dump({'source': 'Statistics Canada, 2021 Census of Population, Census Profile web data service (STC_CP, DF_CT)',
           'labels': labels, 'cts': out}, open(os.path.join(OUT, 'profile.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('profiles:', len(out), 'of', len(keys), flush=True)
