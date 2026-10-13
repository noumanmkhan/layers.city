"""Fetch Toronto's curbside collection areas and pickup calendar for the card's Collection day row.

- Areas: the City's GIS layer "Residential Waste Collection Schedule"
  (gis.toronto.ca, cot_geospatial21/MapServer/3), one polygon per collection calendar. AREA_NAME is
  the calendar's name, e.g. "Wednesday1". This is the live layer behind the City's own lookup; the
  CKAN shapefile of the same areas dates from 2019.
- Calendar: Toronto Open Data "Solid Waste Collection Schedule" (solid-waste-pickup-schedule,
  Open Government Licence – Toronto), one CSV per year. The newest year's resource is taken, so a
  new year's calendar is picked up on the next run after the City publishes it (usually by March).
  One row per calendar per pickup date (WeekStarting is the pickup day itself) with T/0 flags.

Writes cities/toronto/raw/collection/areas.geojson, schedule.csv and meta.json.
Runs in Actions (fetch-toronto-collection.yml): the sandbox can't reach either host.
"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'collection'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (city-layers-pipeline; github.com/noumanmkhan/city-layers)'}
LAYER = 'https://gis.toronto.ca/arcgis/rest/services/cot_geospatial21/MapServer/3'
CKAN = 'https://ckan0.cf.opendata.inter.prod-toronto.ca'


def get(url, raw=False):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                b = r.read()
                return b if raw else json.loads(b)
        except Exception as e:
            print('  retry', i + 1, url[:140], e); time.sleep(6 * (i + 1))
    raise SystemExit('could not fetch ' + url)


# 1. Areas, as GeoJSON in WGS84.
q = urllib.parse.urlencode({'where': '1=1', 'outFields': 'AREA_NAME,AREA_LONG_CODE,AREA_ID', 'returnGeometry': 'true',
                            'outSR': 4326, 'f': 'geojson'})
areas = get(f'{LAYER}/query?{q}')
names = sorted({f['properties']['AREA_NAME'] for f in areas['features']})
print('areas:', len(areas['features']), names)
if len(areas['features']) < 20: raise SystemExit('too few areas; keeping the last copy')
json.dump(areas, open(os.path.join(OUT, 'areas.geojson'), 'w'), separators=(',', ':'))
info = get(f'{LAYER}?f=json')
edit = (info.get('editingInfo') or {}).get('lastEditDate')

# 2. The newest year's calendar.
pkg = get(f'{CKAN}/api/3/action/package_show?id=solid-waste-pickup-schedule')['result']
cands = []
for r in pkg['resources']:
    m = re.fullmatch(r'pickup-schedule-(\d{4})', r.get('name', ''))
    if m and r.get('datastore_active'): cands.append((int(m.group(1)), r))
year, res = max(cands, key=lambda c: c[0])
csv = get(f"{CKAN}/datastore/dump/{res['id']}", raw=True).decode('utf-8-sig')
open(os.path.join(OUT, 'schedule.csv'), 'w').write(csv)
rows = csv.count('\n') - 1
print('calendar', year, res['id'], rows, 'rows')

json.dump({'fetched': datetime.now(timezone.utc).isoformat(timespec='minutes'), 'year': year, 'resource': res['id'],
           'resource_modified': res.get('last_modified'), 'areas': len(areas['features']), 'calendars': names,
           'areas_edited': datetime.fromtimestamp(edit / 1000, timezone.utc).date().isoformat() if edit else None},
          open(os.path.join(OUT, 'meta.json'), 'w'), indent=1)
