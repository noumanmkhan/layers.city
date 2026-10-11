"""Fetch the 2021 Census Profile for the dissemination areas in the City of Vancouver into raw/census_da.json.
Runs in GitHub Actions (fetch-vancouver.yml) after fetch.py has written raw/das.geojson.

Source: Statistics Canada, 2021 Census of Population, Census Profile (Statistics Canada Open Licence), from
its Census Profile web data service (SDMX), dataflow DF_DA; the bulk download on www12.statcan.gc.ca
refuses GitHub's runners. First the characteristics code list (names and how they nest), then the data for
the City's DAs in batches, cut down to the profile sections the map uses.

Labels are written as the bulk CSV writes them, indented two spaces per level of nesting, so profiles.py
reads them the same way Toronto's reads the City's profile. Sections are matched by the start of their
"Total - ..." row, since some are 100% data (age, dwelling type, language) and others 25% sample data."""
import csv, io, json, os, re, time, urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
UA = {'User-Agent': 'city-layers/1.0 (https://maps.noumankhan.ca)'}
API = 'https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/'
SECTIONS = ['Total - Age groups of the population', 'Total - Private households by tenure',
            'Total - Occupied private dwellings by structural type of dwelling', 'Total - Occupied private dwellings by period of construction',
            'Total - Language spoken most often at home', 'Total - Immigrant status and period of immigration',
            'Total - Main mode of commuting', 'Total - Owner households in non-farm, non-reserve private dwellings',
            'Total - Tenant households in non-farm, non-reserve private dwellings']
SINGLE = ['Population, 2021', 'Median value of dwellings ($)', 'Median monthly shelter costs for rented dwellings ($)']


def get(url, accept='*/*', tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA, Accept=accept)), timeout=300) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, url[:160], e); time.sleep(10 * (i + 1))
    raise RuntimeError('failed: ' + url)


# 1. The characteristics: names and parents, from the dataflow's code lists.
x = get(API + 'dataflow/STC_CP/DF_DA?references=all', 'application/xml')
root = ET.fromstring(x)
ns = {'s': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure', 'c': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common'}
lists = {cl.get('id'): cl for cl in root.iter('{%s}Codelist' % ns['s'])}
print('code lists:', {k: len(v.findall('s:Code', ns)) for k, v in lists.items()})
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
print('characteristics:', len(names), '· examples:', [(k, names[k], depth(k)) for k in list(names)[:5]])
if parent:
    keep = {c for c in names if any(names[root_of(c)].startswith(p) for p in SECTIONS) or names[c] in SINGLE}
else:   # a flat code list: a section runs from its "Total - " row to the next one, in id order
    keep, on = set(), False
    for c in sorted(names, key=int):
        if names[c].startswith('Total - '): on = any(names[c].startswith(p) for p in SECTIONS)
        if on or names[c] in SINGLE: keep.add(c)
print('nesting from parents:', bool(parent))
print('kept:', len(keep), '· section rows:', [names[c] for c in sorted(keep, key=int) if names[c].startswith('Total - ')])

# 2. The data, a batch of DAs at a time (all characteristics, total gender, counts).
das = {f['properties']['DGUID']: f['properties']['DAUID'] for f in json.load(open(os.path.join(RAW, 'das.geojson')))['features']}
dg = sorted(das)
out, cols = defaultdict(dict), None
for i in range(0, len(dg), 40):
    batch = dg[i:i + 40]
    t = get(API + 'data/STC_CP,DF_DA/A5.' + '+'.join(batch) + '.1..1?format=csv', 'text/csv').decode('utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(t)))
    if cols is None:
        cols = list(rows[0].keys()) if rows else []
        print('csv columns:', cols, '· first row:', rows[0] if rows else None)
    gk = next(k for k in cols if 'GEO' in k.upper() or 'REF_AREA' in k.upper())
    ck = next(k for k in cols if 'CHARACTERISTIC' in k.upper())
    vk = next(k for k in cols if k.upper() in ('OBS_VALUE', 'VALUE'))
    for r in rows:
        c = r[ck].split(':')[0].strip()
        if c not in keep: continue
        v = (r[vk] or '').strip()
        out[das.get(r[gk].split(':')[0].strip(), r[gk])][c] = float(v) if re.fullmatch(r'-?[\d.]+(E-?\d+)?', v) else None
    print('  batch', i // 40 + 1, len(rows), 'rows')
    time.sleep(1)
print('DAs with data:', len(out), 'of', len(das))
labels = {c: '  ' * depth(c) + names[c] for c in sorted(keep, key=int)}
json.dump({'source': 'Statistics Canada, 2021 Census of Population, Census Profile web data service (STC_CP, DF_DA)',
           'labels': labels, 'das': {g: d for g, d in out.items()}},
          open(os.path.join(RAW, 'census_da.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('wrote census_da.json', os.path.getsize(os.path.join(RAW, 'census_da.json')) // 1000, 'KB')
