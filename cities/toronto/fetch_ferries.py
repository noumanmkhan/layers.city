"""Fetch the ferry routes from the City's Toronto Centreline (TCL) into cities/toronto/raw/ferries/tcl_ferry_routes.json.

The TCL carries every ferry crossing as its own feature class ("Ferry Route"): the City's three Toronto Island routes
from Jack Layton Ferry Terminal (Ward's Island, Centre Island, Hanlan's Point) and the Island Airport ferry across
the Western Gap. Rows named "Routing Connector" are the walking links at the docks: kept in the raw file, ignored by
ferries.py. Source: open.toronto.ca "Toronto Centreline (TCL)", resource "Centreline - Version 2" (datastore),
Open Government Licence – Toronto. The routes almost never change: re-run by hand (python3 fetch_ferries.py), then
python3 ferries.py."""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'ferries'); os.makedirs(OUT, exist_ok=True)
API = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/'
PACKAGE = 'toronto-centreline-tcl'


def get(action, **q):
    url = API + action + '?' + urllib.parse.urlencode(q)
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'layers.city'}), timeout=60) as r:
                d = json.load(r)
            if d.get('success'): return d['result']
        except Exception as e:
            print('  retry', i + 1, e)
        time.sleep(5 * (i + 1))
    raise SystemExit('CKAN did not answer: ' + url)


# The datastore copy of the centreline (the GeoJSON resource with datastore_active), found by name so a new
# resource id doesn't break the fetch.
pkg = get('package_show', id=PACKAGE)
res = next(r for r in pkg['resources'] if r.get('datastore_active') and r['format'].lower() == 'geojson')
rows = get('datastore_search', resource_id=res['id'], filters=json.dumps({'FEATURE_CODE_DESC': 'Ferry Route'}), limit=1000)['records']
keep = ('CENTRELINE_ID', 'LINEAR_NAME_FULL', 'FROM_INTERSECTION_ID', 'TO_INTERSECTION_ID', 'FEATURE_CODE_DESC', 'geometry')
rows = [{k: r.get(k) for k in keep} for r in rows]
for r in rows:
    if isinstance(r['geometry'], str): r['geometry'] = json.loads(r['geometry'])
rows.sort(key=lambda r: (r['LINEAR_NAME_FULL'] or '', r['CENTRELINE_ID']))
json.dump({'source': 'City of Toronto, Toronto Centreline (TCL), FEATURE_CODE_DESC = Ferry Route', 'resource': res['id'],
           'fetched': time.strftime('%Y-%m-%d'), 'rows': rows}, open(os.path.join(OUT, 'tcl_ferry_routes.json'), 'w'), indent=1)
names = {}
for r in rows: names[r['LINEAR_NAME_FULL']] = names.get(r['LINEAR_NAME_FULL'], 0) + 1
print('ferry rows:', len(rows), names)
