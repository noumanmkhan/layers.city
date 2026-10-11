"""Scouting (October 11, 2026): what Vancouver's open data actually holds, before building the city.
Desk scouting is in the project notes (vancouver-data-scouting.md); this checks it from Actions,
because opendata.vancouver.ca, TransLink and DataBC can't be reached from a Claude sandbox.

Decided with the user: units are the City's 22 local areas; sides are East / West / Downtown;
skyscraper cut-off 100 m; representatives wired after the October 17 and 24 elections.

Writes scouting/vancouver/out/:
  catalog.json        every dataset on the City portal: id, title, modified, records, licence, themes
  datasets/<id>.json  for the datasets that matter: fields, facets and 3 sample records
  local-areas.geojson the local-area boundary file, to confirm 22 areas and their names
  translink.json      GTFS feed: dates, agencies, routes by type, stop count
  databc.json         feature counts for provincial ridings and Metro Vancouver municipalities
  old-streams.json    UBC Dataverse file list for Vancouver's Old Streams 1880-1920
  summary.json        one line per check
Nothing here feeds the map."""
import csv, io, json, os, re, time, urllib.parse, urllib.request, zipfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'out')
os.makedirs(os.path.join(OUT, 'datasets'), exist_ok=True)
UA = {'User-Agent': 'city-layers-scouting (github.com/noumanmkhan/city-layers)'}
ODS = 'https://opendata.vancouver.ca/api/explore/v2.1'
summary = {}

# Datasets worth a closer look: matched against dataset id or title.
WANT = re.compile(r'local-area|census|heritage|building-permit|rezoning|development|park|community-cent|'
                  r'librar|street-tree|school|road-ahead|closure|construction|bikeway|hospital|health|'
                  r'election|voting|zoning|address|block-outline|property|rapid-transit|skytrain|'
                  r'cultural|landmark|public-art|off-leash|dog|playground|tennis|pool|rink|'
                  r'shoreline|stream|neighbourhood|area-boundar|street', re.I)


def get(url, binary=False, tries=4, timeout=120):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                b = r.read()
                return b if binary else json.loads(b)
        except Exception as e:
            print('  retry', i + 1, url[:120], e); time.sleep(10 * (i + 1))
    return None


def save(name, obj):
    with open(os.path.join(OUT, name), 'w') as f: json.dump(obj, f, indent=1, ensure_ascii=False)


# 1. City catalogue
cat, off = [], 0
while True:
    d = get(f'{ODS}/catalog/datasets?limit=100&offset={off}')
    if not d: break
    for r in d.get('results', []):
        m = r.get('metas', {}).get('default', {})
        cat.append({'id': r['dataset_id'], 'title': m.get('title'), 'modified': m.get('modified'),
                    'records': m.get('records_count'), 'license': m.get('license'),
                    'themes': m.get('theme'), 'publisher': m.get('publisher'),
                    'fields': [f['name'] for f in r.get('fields', [])]})
    off += 100
    if off >= d.get('total_count', 0): break
cat.sort(key=lambda x: x['id']); save('catalog.json', cat)
print('catalogue:', len(cat), 'datasets'); summary['catalog'] = {'datasets': len(cat), 'licences': Counter(c['license'] for c in cat).most_common()}

# 2. Closer look at the ones that matter
picked = [c for c in cat if WANT.search(c['id']) or WANT.search(c['title'] or '')]
summary['picked'] = []
for c in picked:
    i = c['id']; print('dataset', i)
    meta = get(f'{ODS}/catalog/datasets/{i}') or {}
    facets = get(f'{ODS}/catalog/datasets/{i}/facets') or {}
    recs = get(f'{ODS}/catalog/datasets/{i}/records?limit=3') or {}
    for r in recs.get('results', []):          # keep samples small: drop long geometry
        for k, v in list(r.items()):
            if isinstance(v, dict) and 'geometry' in v: r[k] = {'geometry_type': v['geometry'].get('type')}
    out = {'id': i, 'title': c['title'], 'modified': c['modified'], 'records': c['records'], 'license': c['license'],
           'description': (meta.get('metas', {}).get('default', {}).get('description') or '')[:1500],
           'fields': [{k: f.get(k) for k in ('name', 'type', 'label')} for f in meta.get('fields', [])],
           'facets': [{'name': f['name'], 'top': [(v['name'], v['count']) for v in f.get('facets', [])[:25]]}
                      for f in facets.get('facets', [])],
           'samples': recs.get('results', [])}
    save(f'datasets/{i}.json', out)
    summary['picked'].append([i, c['title'], c['records'], c['modified']])
    time.sleep(0.5)

# 3. Local areas: the units
la = next((c['id'] for c in cat if 'local-area-boundary' in c['id']), None)
if la:
    g = get(f'{ODS}/catalog/datasets/{la}/exports/geojson')
    if g:
        save('local-areas.geojson', g)
        names = sorted(str(f['properties'].get('name') or f['properties']) for f in g['features'])
        summary['local_areas'] = {'dataset': la, 'count': len(g['features']), 'names': names}
        print('local areas:', len(g['features']))
else:
    summary['local_areas'] = 'no local-area-boundary dataset found'

# 4. TransLink GTFS
z = get('https://gtfs-static.translink.ca/gtfs/google_transit.zip', binary=True, timeout=300)
if z:
    zf = zipfile.ZipFile(io.BytesIO(z))
    rd = lambda n: list(csv.DictReader(io.TextIOWrapper(zf.open(n), 'utf-8-sig'))) if n in zf.namelist() else []
    routes = rd('routes.txt'); cal = rd('calendar.txt')
    t = {'bytes': len(z), 'files': zf.namelist(), 'feed_info': rd('feed_info.txt'),
         'agencies': [a.get('agency_name') for a in rd('agency.txt')],
         'routes_by_type': Counter(r.get('route_type') for r in routes).most_common(),
         'routes_sample': [[r.get('route_short_name'), r.get('route_long_name'), r.get('route_type')] for r in routes[:400]],
         'stops': sum(1 for _ in csv.reader(io.TextIOWrapper(zf.open('stops.txt'), 'utf-8-sig'))) - 1,
         'calendar_span': [min((c['start_date'] for c in cal), default=None), max((c['end_date'] for c in cal), default=None)],
         'frequencies_rows': len(rd('frequencies.txt'))}
    save('translink.json', t); summary['translink'] = {k: t[k] for k in ('bytes', 'agencies', 'routes_by_type', 'stops', 'calendar_span')}
    print('translink:', t['routes_by_type'])
else:
    summary['translink'] = 'download failed'

# 5. DataBC: provincial ridings (expect 93) and municipalities
WFS = 'https://openmaps.gov.bc.ca/geo/pub/wfs?service=WFS&version=2.0.0&request=GetFeature&outputFormat=json&count=200&typeName='
db = {}
for name, layer, flt in [
    ('provincial_districts', 'WHSE_ADMIN_BOUNDARIES.EBC_PROV_ELECTORAL_DIST_SVW', ''),
    ('municipalities', 'WHSE_LEGAL_ADMIN_BOUNDARIES.ABMS_MUNICIPALITIES_SP', ''),
]:
    d = get(WFS + layer + '&propertyName=' + ('ED_NAME,ED_ABBREVIATION' if 'EBC' in layer else 'ADMIN_AREA_NAME,ADMIN_AREA_ABBREVIATION') + flt)
    if d:
        props = [f['properties'] for f in d.get('features', [])]
        db[name] = {'count': len(props), 'sample': props[:120]}
    else:
        db[name] = 'failed'
save('databc.json', db); summary['databc'] = {k: (v['count'] if isinstance(v, dict) else v) for k, v in db.items()}

# 6. Old streams (UBC Dataverse, Borealis)
os_ = get('https://borealisdata.ca/api/datasets/:persistentId/?persistentId=doi:10.5683/SP2/UEJGTV')
if os_:
    v = os_.get('data', {}).get('latestVersion', {})
    files = [{'name': f['dataFile'].get('filename'), 'id': f['dataFile'].get('id'), 'bytes': f['dataFile'].get('filesize')}
             for f in v.get('files', [])]
    save('old-streams.json', {'license': v.get('license'), 'termsOfUse': (v.get('termsOfUse') or '')[:3000], 'files': files})
    summary['old_streams'] = {'files': len(files), 'license': v.get('license')}
else:
    summary['old_streams'] = 'failed'

save('summary.json', summary)
print(json.dumps({k: v for k, v in summary.items() if k != 'picked'}, indent=1)[:4000])
print('picked', len(summary['picked']))
