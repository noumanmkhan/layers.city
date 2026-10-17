"""Fetch Ontario's school list (Ministry of Education, "School information and student demographics", Ontario Data
Catalogue, Open Government Licence - Ontario) and keep Toronto's publicly funded schools -> raw/schools/ontario_schools.csv

Run from GitHub Actions (fetch-toronto-schools.yml); the sandbox can't reach data.ontario.ca.
- Picks the newest English school-year file from the catalogue's API.
- Keeps only descriptive columns (board, school, level, grades, language, address, coordinates). Test results and
  student demographics are dropped here and never reach the repo: the map describes schools, it never ranks them.
- Keeps rows inside a box around Toronto; schools.py cuts them to the city itself.
- Logs every column name it found, so a renamed column shows up in fetch.log rather than as silent gaps.
"""
import csv, io, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'schools')
API = 'https://data.ontario.ca/api/3/action/package_show?id=school-information-and-student-demographics'
BOX = (-79.66, 43.57, -79.10, 43.87)   # west, south, east, north
KEEP = re.compile(r'^(board (number|name|type)|school (number|name|type|level|language|special condition.*)|grade range|'
                  r'building suite|p\.?o\.? box|street|municipality|city|province|postal code|website|latitude|longitude)$', re.I)


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'layers.city school fetch (go@layers.city)'})
    return urllib.request.urlopen(req, timeout=120).read()


pkg = json.loads(get(API))['result']
res = [r for r in pkg['resources'] if (r.get('format') or '').lower() in ('xlsx', 'xls', 'csv')]
for r in res: print('resource:', r.get('name'), '|', r.get('data_range_start') or '', '|', r.get('language') or '', '|', r['url'])
eng = [r for r in res if not re.search(r'french|fran', (r.get('name') or '') + ' ' + json.dumps(r.get('language') or ''), re.I)]
pick = max(eng, key=lambda r: (str(r.get('data_range_start') or ''), r.get('name') or ''))
print('picked:', pick.get('name'), pick.get('data_range_start'), pick['url'])
raw = get(pick['url'])

if pick['url'].lower().endswith('.csv'):
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig', 'replace'))))
else:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = [['' if v is None else str(v).strip() for v in row] for row in ws.iter_rows(values_only=True)]
head_i = next(i for i, r in enumerate(rows[:20]) if any(re.match(r'school name', c or '', re.I) for c in r))
head = [re.sub(r'\s+', ' ', h or '').strip() for h in rows[head_i]]
print('columns:', head)
keep = [i for i, h in enumerate(head) if KEEP.match(h)]
print('kept:', [head[i] for i in keep])
lat_i = next(i for i, h in enumerate(head) if re.match(r'latitude', h, re.I))
lon_i = next(i for i, h in enumerate(head) if re.match(r'longitude', h, re.I))
out = []
for r in rows[head_i + 1:]:
    try: lat, lon = float(r[lat_i]), float(r[lon_i])
    except (ValueError, IndexError): continue
    if BOX[0] <= lon <= BOX[2] and BOX[1] <= lat <= BOX[3]: out.append([r[i] for i in keep])
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, 'ontario_schools.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow([head[i] for i in keep]); w.writerows(out)
json.dump({'resource': pick.get('name'), 'url': pick['url'], 'data_range_start': pick.get('data_range_start'),
           'data_range_end': pick.get('data_range_end'), 'rows': len(out)},
          open(os.path.join(OUT, 'ontario_schools.meta.json'), 'w'), indent=1)
print('rows in the Toronto box:', len(out))
if not out: sys.exit('no rows: check the columns above')
