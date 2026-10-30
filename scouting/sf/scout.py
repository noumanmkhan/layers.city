"""Scouting (October 30, 2026): what San Francisco and the nine-county Bay Area actually publish, before building the city.
Desk scouting is in the project notes (sf-bay-data-scouting.md); this checks it from Actions, with counts, field
names and freshness, because none of these hosts can be reached from a Claude sandbox.

Decided with the user: shape A (the Toronto/GTA shape): San Francisco (city and county) is the full-detail city,
the nine-county Bay Area (101 cities) is the regional view with county focus. Units, hub and skyscraper cut-off
are still open; the counts here are what decides them.

Writes scouting/sf/out/:
  catalog.json          every dataset on data.sfgov.org: id, name, type, updated, category, licence
  datasets/<key>.json   for each dataset the map needs: candidates, the one picked, columns, row count,
                        last data update, licence and 3 sample rows (geometry trimmed)
  arcgis.json           MTC/ABAG regional layers (cities, counties), SFMTA ArcGIS, ArcGIS Online searches
  gtfs.json             Muni, BART, Caltrain and the 511 regional feed (if FIVE11_KEY is set): routes, stops, dates
  baywheels.json        GBFS station_information: count, fields, regions
  probes.json           Census ACS tracts, AFDC chargers, Wikipedia tallest, AB 604 (Prop 50) map, SF polling
                        places, Recology, SFUSD, HCAI hospitals
  summary.json          one line per check
  FINDINGS.md           the same, readable
Nothing here feeds the map."""
import csv, io, json, os, re, time, urllib.parse, urllib.request, zipfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'out')
os.makedirs(os.path.join(OUT, 'datasets'), exist_ok=True)
UA = {'User-Agent': 'city-layers-scouting (https://layers.city)'}
SOC = 'https://data.sfgov.org'
KEY511 = os.environ.get('FIVE11_KEY', '').strip()
summary, findings = {}, []


def note(line):
    print(line); findings.append(line)


def get(url, binary=False, tries=3, timeout=120, headers=None):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers or UA), timeout=timeout) as r:
                b = r.read()
                return b if binary else json.loads(b)
        except Exception as e:
            print('  retry', i + 1, url[:140], str(e)[:120]); time.sleep(5 * (i + 1))
    return None


def save(name, obj):
    with open(os.path.join(OUT, name), 'w') as f: json.dump(obj, f, indent=1, ensure_ascii=False)


# ---------------------------------------------------------------- 1. the whole DataSF catalogue
cat = []
# DataSF's own DCAT catalogue (the Socrata discovery API returned only a handful of SF datasets on the first run)
d = get(f'{SOC}/data.json', timeout=300) or {}
for r in d.get('dataset', []):
    m = re.search(r'/views/([a-z0-9]{4}-[a-z0-9]{4})', r.get('identifier', '') or '')
    if not m: continue
    cat.append({'id': m.group(1), 'name': r.get('title', ''), 'type': None, 'updated': (r.get('modified') or '')[:10],
                'category': (r.get('theme') or [None])[0], 'dept': (r.get('publisher') or {}).get('name'),
                'licence': r.get('license'), 'desc': (r.get('description') or '')[:200].replace('\n', ' ')})
if len(cat) < 50:      # fall back to the discovery API, paged
    off = 0
    while True:
        d = get(f'https://api.us.socrata.com/api/catalog/v1?domains=data.sfgov.org&search_context=data.sfgov.org&limit=100&offset={off}')
        if not d or not d.get('results'): break
        for r in d['results']:
            res = r['resource']
            if all(c['id'] != res['id'] for c in cat):
                cat.append({'id': res['id'], 'name': res['name'], 'type': res.get('type'), 'updated': (res.get('data_updated_at') or '')[:10],
                            'category': (r.get('classification') or {}).get('domain_category'), 'dept': None, 'licence': None, 'desc': ''})
        off += 100
cat.sort(key=lambda x: x['name'].lower()); save('catalog.json', cat)
note(f'Catalogue: {len(cat)} datasets on data.sfgov.org')
summary['catalog'] = {'datasets': len(cat), 'categories': Counter(c['category'] for c in cat).most_common(15),
                      'licences': Counter(c['licence'] for c in cat).most_common(8)}

# ---------------------------------------------------------------- 2. the datasets the map needs
# key -> ids known from desk scouting first (checked as-is), then title phrases (exact title first, then containment)
WANT = {
    'analysis_neighborhoods': (['p5b7-5n3h'], ['Analysis Neighborhoods']),
    'tracts_to_neighborhoods': (['sevw-6tgi'], ['Analysis Neighborhoods - 2020 census tracts assigned to neighborhoods']),
    'sffind_neighborhoods': (['pty2-tcw4'], ['SF Find Neighborhoods']),
    'realtor_neighborhoods': ([], ['Realtor Neighborhoods', 'Neighborhoods - Realtor']),
    'supervisor_districts': ([], ['Supervisor Districts (2022)', 'Current Supervisor Districts', 'Supervisor Districts']),
    'precincts': ([], ['Election Precincts', 'Precincts', 'San Francisco Election Precincts']),
    'polling_places': ([], ['Polling Places', 'Polling Place Locations', 'Election Day Polling Places']),
    'zip_codes': (['srq6-hmpi'], ['San Francisco ZIP Codes', 'ZIP Codes']),
    'city_boundary': ([], ['City and County of San Francisco', 'San Francisco Boundary', 'Bay Area Counties']),
    'shoreline': ([], ['Shoreline', 'San Francisco Shoreline']),
    'historic_districts': (['63x5-g3m4'], ['Historic Districts']),
    'article10_landmarks': (['97yj-54sx'], ['Landmarks Listed in Article 10 of the San Francisco Planning Code']),
    'cbds': ([], ['Community Benefit Districts', 'Community Benefit Districts (CBDs)', 'Business Improvement Districts']),
    'cultural_districts': ([], ['Cultural Districts']),
    'rec_park_properties': ([], ['Recreation and Parks Properties', 'Rec and Park Properties', 'Park Lands - Recreation and Parks Department']),
    'rec_park_facilities': ([], ['Recreation and Parks Facilities', 'Rec Park Facilities', 'Park Facilities']),
    'playgrounds': ([], ['Playgrounds', 'Rec Park Playgrounds']),
    'dog_play_areas': ([], ['Dog Play Areas', 'Dog Parks']),
    'pools': ([], ['Pools', 'Recreation and Parks Pools']),
    'public_restrooms': ([], ['Public Restrooms', 'Pit Stop Locations', 'Restrooms']),
    'popos': ([], ['Privately Owned Public Open Spaces', 'POPOS']),
    'libraries': ([], ['Library Branches', 'San Francisco Public Library Locations', 'SFPL Locations']),
    'city_facilities': ([], ['City Facilities', 'Facilities', 'City-owned and leased facilities']),
    'schools': ([], ['Schools', 'Map of Schools', 'SFUSD Schools', 'Public Schools']),
    'sfusd_attendance': ([], ['SFUSD Attendance Areas (2025-2026)', 'SFUSD Attendance Areas (2024-2025)', 'SFUSD Attendance Areas']),
    'hospitals': ([], ['Hospitals', 'Health Care Facilities', 'Licensed Health Facilities']),
    'street_centerline': ([], ['Streets – Active and Retired', 'Streets - Active and Retired', 'Street Centerlines', 'Streets']),
    'bike_network': ([], ['SFMTA Bikeway Network', 'Bikeway Network', 'MTA Bike Network Linear Features']),
    'bike_parking': ([], ['Bicycle Parking (Public)', 'Bicycle Parking']),
    'slow_streets': ([], ['Slow Streets']),
    'muni_stops': ([], ['Muni Stops']),
    'muni_routes': ([], ['Muni Simple Routes', 'Muni Routes']),
    'street_closures': (['8x25-yybr'], ['Temporary Street Closures']),
    'closure_intersections': ([], ['Temp Street Closure Intersections']),
    'closures_wzdx': (['4ftp-yz2f'], ['Temporary Street Closures in the Work Zone Data Exchange (WZDx) Format']),
    'street_use_permits': ([], ['Street-Use Permits']),
    'building_permits': ([], ['Building Permits']),
    'dev_pipeline': ([], ['SF Development Pipeline', 'Development Pipeline', 'Housing Pipeline']),
    'planning_projects': ([], ['Planning Department Records - Projects', 'Planning Records - Projects']),
    'offstreet_parking': (['vqzx-t7c4'], ['SFMTA Managed Off-street Parking']),
    'offstreet_parking_all': (['mizu-nf6z'], ['SFMTA - Off-Street Parking Locations (Lots and Parking Garages)']),
    'rpp_areas': ([], ['Residential Parking Permit Areas', 'RPP Areas', 'Map of Residential Parking Permit Areas']),
    'rpp_parcels': ([], ['Residential Parking Permit Eligibility Parcels']),
    'street_sweeping': (['yhqp-riqs'], ['Street Sweeping Schedule']),
    'parking_meters': ([], ['Parking Meters']),
    'ev_chargers': ([], ['Electric Vehicle Charging Stations', 'EV Charging Stations']),
    'beach_water': (['v3fv-x3ux'], ['Beach Water Quality Monitoring']),
    'tsunami': ([], ['Tsunami Hazard Zone', 'Tsunami Inundation', 'Tsunami Hazard Area']),
    'liquefaction': ([], ['Liquefaction Zones', 'Seismic Hazard Zones']),
    'soft_story': ([], ['Soft-Story Properties', 'Soft Story Properties']),
    'police_districts': ([], ['Current Police Districts', 'Police Districts']),
    'tree_inventory': ([], ['Street Tree List']),
    'zoning': ([], ['Zoning Map - Zoning Districts', 'Zoning Districts']),
    'height_districts': ([], ['Zoning Map - Height and Bulk Districts', 'Height and Bulk Districts']),
    'address_points': ([], ['Addresses - Enterprise Addressing System', 'Addresses with Units - Enterprise Addressing System']),
    'recology': ([], ['Recology', 'Refuse Collection', 'Garbage Collection']),
}
by_name = {}
for c in cat: by_name.setdefault(c['name'].strip().lower(), []).append(c)
by_id = {c['id']: c for c in cat}


def candidates(ids, phrases):
    out = [('id', by_id.get(i) or {'id': i, 'name': '(pinned id, not in catalogue)', 'type': None, 'updated': None}) for i in ids]
    for p in phrases:
        for c in by_name.get(p.lower(), []):
            if all(c['id'] != o[1]['id'] for o in out): out.append(('exact', c))
    for p in phrases:
        for c in cat:
            if p.lower() in c['name'].lower() and all(c['id'] != o[1]['id'] for o in out): out.append(('contains', c))
    return out[:8]


BIG = {'street_centerline', 'address_points', 'building_permits', 'street_sweeping', 'parking_meters', 'tree_inventory',
       'street_use_permits', 'rpp_parcels', 'zoning', 'planning_projects'}
summary['datasets'] = {}
for key, (ids, phrases) in WANT.items():
    cands = candidates(ids, phrases)
    rec = {'key': key, 'looked_for': phrases, 'candidates': [[k, c['id'], c['name'], c.get('type'), c.get('updated')] for k, c in cands]}
    if not cands:
        note(f'{key}: NOT FOUND in catalogue ({phrases[0]})'); summary['datasets'][key] = None
        save(f'datasets/{key}.json', rec); continue
    pick = cands[0][1]; i = pick['id']; print(f'{key}: {pick["name"]} ({i})')
    meta = get(f'{SOC}/api/views/{i}.json') or {}
    if not meta and len(cands) > 1:     # a pinned id that no longer answers: fall back to the next candidate
        pick = cands[1][1]; i = pick['id']; meta = get(f'{SOC}/api/views/{i}.json') or {}
    cols = [{'name': c.get('fieldName'), 'type': c.get('dataTypeName'), 'label': c.get('name')} for c in meta.get('columns', [])]
    ts = lambda t: time.strftime('%Y-%m-%d', time.gmtime(t)) if t else None
    cnt = None
    c = get(f'{SOC}/resource/{i}.json?$select=count(*)', tries=2)
    try: cnt = int(list(c[0].values())[0])
    except Exception: cnt = None
    samples = get(f'{SOC}/resource/{i}.json?$limit=3', tries=2) or []
    if isinstance(samples, list):
        for s in samples:
            for k, v in list(s.items()):
                if isinstance(v, dict) and 'type' in v and 'coordinates' in v: s[k] = {'geometry_type': v['type']}
                elif isinstance(v, str) and len(v) > 300: s[k] = v[:300] + '…'
    else:
        samples = []
    geo = None
    if cnt is None and key not in BIG:   # map-type views: count by reading the GeoJSON export
        g = get(f'{SOC}/api/geospatial/{i}?method=export&format=GeoJSON', binary=True, timeout=300, tries=2)
        if g:
            try:
                gj = json.loads(g); geo = {'bytes': len(g), 'features': len(gj.get('features', [])),
                                           'props': sorted(gj['features'][0]['properties'].keys()) if gj.get('features') else []}
                cnt = geo['features']
            except Exception as e:
                geo = {'bytes': len(g), 'error': str(e)[:100]}
    rec.update({'picked': {'id': i, 'name': meta.get('name') or pick['name'], 'type': pick.get('type'), 'viewType': meta.get('viewType'),
                           'attribution': meta.get('attribution'), 'category': meta.get('category'),
                           'licence': (meta.get('license') or {}).get('name') if isinstance(meta.get('license'), dict) else meta.get('licenseId'),
                           'rows_updated': ts(meta.get('rowsUpdatedAt')), 'view_modified': ts(meta.get('viewLastModified')),
                           'description': (meta.get('description') or '')[:800]},
                'count': cnt, 'geo': geo, 'columns': cols, 'samples': samples})
    save(f'datasets/{key}.json', rec)
    line = f'{key}: "{rec["picked"]["name"]}" {i} · {cnt if cnt is not None else "?"} rows · data {rec["picked"]["rows_updated"]} · {len(cols)} cols · {rec["picked"]["licence"]}'
    note(line); summary['datasets'][key] = [i, rec['picked']['name'], cnt, rec['picked']['rows_updated'], rec['picked']['licence']]
    time.sleep(0.3)

# value counts that decide card wording (RPP area letters, sweeping weekdays, closure types)
def groupby(i, field, limit=60):
    d = get(f'{SOC}/resource/{i}.json?' + urllib.parse.urlencode({'$select': f'{field},count(*)', '$group': field, '$order': 'count(*) DESC', '$limit': limit}), tries=1)
    return d if isinstance(d, list) else None
groups = {}
for key, fields in {'street_closures': ['type', 'status'], 'street_sweeping': ['weekday', 'fullname'],
                    'historic_districts': ['article', 'type', 'designation'], 'offstreet_parking': ['type', 'owner'],
                    'beach_water': ['source', 'station_name'], 'dev_pipeline': ['status', 'project_status'], 'schools': ['category', 'type']}.items():
    v = summary['datasets'].get(key)
    if not v: continue
    for f in fields:
        r = groupby(v[0], f)
        if r: groups[f'{key}.{f}'] = r; note(f'{key} by {f}: {[list(x.values()) for x in r[:12]]}')
save('groups.json', groups)

# ---------------------------------------------------------------- 3. ArcGIS services (MTC/ABAG regional layers, SFMTA)
arc = {}
def arc_layer(name, url, where='1=1'):
    m = get(url + '?f=pjson', tries=2) or {}
    c = get(url + '/query?where=' + urllib.parse.quote(where) + '&returnCountOnly=true&f=json', tries=2) or {}
    s = get(url + '/query?where=' + urllib.parse.quote(where) + '&outFields=*&resultRecordCount=3&returnGeometry=false&f=json', tries=2) or {}
    ed = (m.get('editingInfo') or {}).get('lastEditDate')
    arc[name] = {'url': url, 'name': m.get('name'), 'geometry': m.get('geometryType'), 'count': c.get('count'),
                 'last_edit': time.strftime('%Y-%m-%d', time.gmtime(ed / 1000)) if ed else None,
                 'fields': [(f['name'], f.get('type'), f.get('alias')) for f in m.get('fields', [])],
                 'samples': [f.get('attributes') for f in s.get('features', [])], 'copyright': m.get('copyrightText'),
                 'max_record_count': m.get('maxRecordCount')}
    note(f'ArcGIS {name}: {arc[name]["count"]} features · edited {arc[name]["last_edit"]} · {len(arc[name]["fields"])} fields')

MTC = 'https://services3.arcgis.com/i2dkYWmb4wHvYPda/ArcGIS/rest/services'
for name in ['region_incorporatedplace_clp', 'region_incorporatedplace', 'region_county_clp', 'region_county']:
    arc_layer(f'mtc_{name}', f'{MTC}/{name}/FeatureServer/0')
# the 101 cities by county (field names unknown until the run: group by whatever looks like a county field)
f = {x[0].upper(): x[0] for x in arc.get('mtc_region_incorporatedplace_clp', {}).get('fields', [])}
co = next((f[k] for k in f if 'COUNTY' in k or k in ('CO_NAME', 'CNTY')), None)
if co:
    d = get(f'{MTC}/region_incorporatedplace_clp/FeatureServer/0/query?where=1%3D1&groupByFieldsForStatistics={co}&outStatistics=' +
            urllib.parse.quote(json.dumps([{'statisticType': 'count', 'onStatisticField': 'OBJECTID', 'outStatisticFieldName': 'n'}])) + '&f=json') or {}
    arc['mtc_cities_by_county'] = [x['attributes'] for x in d.get('features', [])]; note(f'MTC cities by {co}: {arc["mtc_cities_by_county"]}')
# MTC/ABAG catalogue: what else the regional portal holds
d = get('https://services3.arcgis.com/i2dkYWmb4wHvYPda/ArcGIS/rest/services?f=pjson') or {}
arc['mtc_services'] = [s.get('name') for s in d.get('services', [])]; note(f'MTC services: {len(arc["mtc_services"])} ({arc["mtc_services"][:40]})')
# SFMTA's own ArcGIS (the DataSF master map service): layer list
d = get('https://services.sfmta.com/arcgis/rest/services/DataSF/master/MapServer?f=pjson') or {}
arc['sfmta_master_layers'] = [(l['id'], l['name']) for l in d.get('layers', [])]; note(f'SFMTA DataSF/master layers: {arc["sfmta_master_layers"][:80]}')
for q in ['Residential Parking Permit Areas San Francisco', 'San Francisco polling places 2026', 'Bay Area cities boundaries MTC',
          'California Protected Areas Database', 'Golden Gate National Recreation Area boundary', 'California tsunami hazard area',
          'SFUSD attendance area', 'Community Benefit Districts San Francisco', 'AB 604 congressional districts']:
    d = get('https://www.arcgis.com/sharing/rest/search?' + urllib.parse.urlencode({'q': q, 'f': 'json', 'num': 6}), tries=2) or {}
    arc[f'search: {q}'] = [(r.get('type'), r.get('title'), r.get('owner'), r.get('url'),
                           time.strftime('%Y-%m-%d', time.gmtime((r.get('modified') or 0) / 1000))) for r in d.get('results', [])]
    note(f'ArcGIS Online "{q}": {arc[f"search: {q}"][:3]}')
save('arcgis.json', arc); summary['arcgis'] = {k: (v.get('count') if isinstance(v, dict) else None) for k, v in arc.items()}

# ---------------------------------------------------------------- 4. GTFS: agency feeds without a key, then 511 regional
gt = {}
def read_gtfs(name, z):
    try:
        zf = zipfile.ZipFile(io.BytesIO(z))
        rd = lambda n: list(csv.DictReader(io.TextIOWrapper(zf.open(n), 'utf-8-sig'))) if n in zf.namelist() else []
        lines = lambda n: sum(1 for _ in csv.reader(io.TextIOWrapper(zf.open(n), 'utf-8-sig'))) - 1 if n in zf.namelist() else None
        routes = rd('routes.txt'); cal = rd('calendar.txt'); fi = rd('feed_info.txt'); ag = rd('agency.txt')
        gt[name] = {'mb': round(len(z) / 1e6, 1), 'files': zf.namelist(), 'feed_info': fi[:1],
                    'agencies': [[a.get('agency_id'), a.get('agency_name')] for a in ag],
                    'routes': len(routes), 'routes_by_type': Counter(r.get('route_type') for r in routes).most_common(),
                    'routes_by_agency': Counter(r.get('agency_id') for r in routes).most_common(40),
                    'stops': lines('stops.txt'), 'trips': lines('trips.txt'), 'shapes': 'shapes.txt' in zf.namelist(),
                    'calendar_span': [min((c['start_date'] for c in cal), default=None), max((c['end_date'] for c in cal), default=None)],
                    'routes_sample': [[r.get('agency_id'), r.get('route_short_name'), (r.get('route_long_name') or '')[:50], r.get('route_type'), r.get('route_color')] for r in routes[:60]]}
        note(f'GTFS {name}: {gt[name]["mb"]} MB · {len(ag)} agencies · {len(routes)} routes {gt[name]["routes_by_type"]} · {gt[name]["stops"]} stops · {gt[name]["trips"]} trips · {gt[name]["calendar_span"]}')
    except Exception as e:
        gt[name] = f'unreadable: {e}'; note(f'GTFS {name}: unreadable {e}')

for name, url in [('muni', 'https://gtfs.sfmta.com/transitdata/google_transit.zip'),
                  ('muni_alt', 'https://www.sfmta.com/reports/gtfs-transit-data'),
                  ('bart', 'https://www.bart.gov/dev/schedules/google_transit.zip'),
                  ('caltrain', 'https://data.trilliumtransit.com/gtfs/caltrain-ca-us/caltrain-ca-us.zip')]:
    z = get(url, binary=True, timeout=300, tries=2)
    if z and z[:2] != b'PK':   # a page, not a zip: list the zip links it carries
        gt[name] = {'page': url, 'zip_links': sorted(set(re.findall(r'https?://[^"\'\s>]+\.zip', z.decode('utf-8', 'ignore'))))[:10]}
        note(f'{name}: page with zip links {gt[name]["zip_links"]}'); continue
    if not z: gt[name] = f'download failed ({url})'; note(f'GTFS {name}: download failed'); continue
    read_gtfs(name, z)
if KEY511:
    ops = get(f'https://api.511.org/transit/gtfsoperators?api_key={KEY511}', binary=True, tries=2)
    try:
        ops = json.loads(ops.decode('utf-8-sig')); gt['511_operators'] = [[o.get('Id'), o.get('Name'), o.get('LastGenerated')] for o in ops]
        note(f'511 operators: {len(ops)} ({[o[0] for o in gt["511_operators"]]})')
    except Exception as e:
        gt['511_operators'] = f'unreadable: {e}'
    z = get(f'https://api.511.org/transit/datafeeds?api_key={KEY511}&operator_id=RG', binary=True, timeout=600, tries=2)
    if z and z[:2] == b'PK': read_gtfs('511_regional', z)
    else: gt['511_regional'] = 'download failed'; note('GTFS 511 regional: download failed')
else:
    gt['511_regional'] = 'skipped: no FIVE11_KEY secret (request a free key at 511.org/open-data/token)'
    note('GTFS 511 regional: skipped, no FIVE11_KEY secret')
# 511 terms page: keep the wording that matters for a later commercial fork
b = get('https://511.org/about/terms-use', binary=True, tries=1, timeout=60)
h = re.sub(r'<[^>]+>', ' ', b.decode('utf-8', 'ignore')) if b else ''
gt['511_terms_mentions'] = sorted(set(m.strip() for m in re.findall(r'[^.]{0,160}(?:commercial|attribution|credit|redistribut)[^.]{0,160}\.', h, re.I)))[:12]
note(f'511 terms page: {len(gt["511_terms_mentions"])} sentences on commercial use / attribution')
save('gtfs.json', gt); summary['gtfs'] = {k: (v if isinstance(v, (str, list)) else {kk: v.get(kk) for kk in ('mb', 'routes', 'stops', 'calendar_span')}) for k, v in gt.items() if k != '511_terms_mentions'}

# ---------------------------------------------------------------- 5. Bay Wheels GBFS
bw = {}
g = get('https://gbfs.baywheels.com/gbfs/gbfs.json') or get('https://gbfs.lyft.com/gbfs/2.3/bay/gbfs.json')
if g:
    data = g.get('data', {}); lang = data.get('en') or (data[list(data.keys())[0]] if data and isinstance(data[list(data.keys())[0]], dict) else data)
    feeds = {f['name']: f['url'] for f in (lang.get('feeds') if isinstance(lang, dict) else data.get('feeds', []))}
    si = get(feeds.get('station_information', '')) or {}
    st = si.get('data', {}).get('stations', [])
    regions = get(feeds.get('system_regions', '')) or {}
    rname = {r['region_id']: r['name'] for r in regions.get('data', {}).get('regions', [])}
    bw = {'feeds': feeds, 'stations': len(st), 'fields': sorted(st[0].keys()) if st else [],
          'regions': [[rname.get(k, k), n] for k, n in Counter(s.get('region_id') for s in st).most_common(10)],
          'charging': sum(1 for s in st if s.get('is_charging_station') or s.get('charging_station')),
          'capacity_total': sum(s.get('capacity', 0) for s in st), 'sample': st[:2],
          'system_information': (get(feeds.get('system_information', '')) or {}).get('data')}
    note(f'Bay Wheels: {bw["stations"]} stations · {bw["charging"]} charging · regions {bw["regions"]}')
else:
    note('Bay Wheels GBFS: not reachable')
save('baywheels.json', bw); summary['baywheels'] = {'stations': bw.get('stations'), 'regions': bw.get('regions')}

# ---------------------------------------------------------------- 6. probes
pr = {}
COUNTIES = {'001': 'Alameda', '013': 'Contra Costa', '041': 'Marin', '055': 'Napa', '075': 'San Francisco',
            '081': 'San Mateo', '085': 'Santa Clara', '095': 'Solano', '097': 'Sonoma'}
for year in (2024, 2023):
    acs = get(f'https://api.census.gov/data/{year}/acs/acs5?get=NAME,B25003_001E,B25003_003E,B25077_001E,B25064_001E,B08301_001E,B08301_002E,B25024_001E'
              f'&for=tract:*&in=state:06&in=county:{",".join(COUNTIES)}', tries=2)
    if acs:
        hdr = acs[0]; ci = hdr.index('county')
        pr['acs_tracts'] = {'year': year, 'rows': len(acs) - 1, 'header': hdr, 'sample': acs[1:3],
                            'by_county': {COUNTIES.get(k, k): n for k, n in Counter(r[ci] for r in acs[1:]).items()}}
        break
note(f'ACS tracts in the 9 counties: {(pr.get("acs_tracts") or {}).get("year")} {(pr.get("acs_tracts") or {}).get("by_county")}')
a = get('https://developer.nlr.gov/api/alt-fuel-stations/v1.json?api_key=DEMO_KEY&fuel_type=ELEC&state=CA&zip=94103&access=public&status=E&limit=1', tries=2) \
    or get('https://developer.nrel.gov/api/alt-fuel-stations/v1.json?api_key=DEMO_KEY&fuel_type=ELEC&state=CA&zip=94103&access=public&status=E&limit=1', tries=1)
pr['afdc_sample'] = (a or {}).get('total_results'); note(f'AFDC public open EV stations (ZIP 94103 probe): {pr["afdc_sample"]}')
w = get('https://en.wikipedia.org/w/api.php?action=parse&page=List_of_tallest_buildings_in_San_Francisco&prop=sections&format=json')
pr['wikipedia_sections'] = [s['line'] for s in (w or {}).get('parse', {}).get('sections', [])]; note(f'Wikipedia SF tallest sections: {pr["wikipedia_sections"][:12]}')
w = get('https://en.wikipedia.org/w/api.php?action=parse&page=List_of_cities_and_towns_in_the_San_Francisco_Bay_Area&prop=sections&format=json')
pr['wikipedia_bay_cities_sections'] = [s['line'] for s in (w or {}).get('parse', {}).get('sections', [])][:15]
# pages whose links tell us where the files are: Prop 50 / AB 604 map, SF elections, Recology, SFUSD, HCAI
for name, url, pat in [
        ('statewide_database', 'https://statewidedatabase.org/', r'href="([^"]+(?:\.zip|604|shp|congress)[^"]*)"'),
        ('rdh_ca_congress', 'https://redistrictingdatahub.org/state/california/', r'href="([^"]+(?:cong|ab604|604)[^"]*)"'),
        ('sf_vote_in_person', 'https://www.sf.gov/vote-in-person', r'href="([^"]+(?:polling|xlsx|csv|pdf|map)[^"]*)"'),
        ('sf_elections_myvotinglocation', 'https://sfelections.gov/myvotinglocation', r'href="([^"]+)"'),
        ('recology_sf', 'https://www.recology.com/recology-san-francisco/collection-calendar/', r'href="([^"]+(?:schedule|calendar|api)[^"]*)"'),
        ('sfusd_attendance', 'https://www.sfusd.edu/student-assignment-policy/tiebreakers/attendance-area', r'href="([^"]+(?:map|arcgis|attendance)[^"]*)"'),
        ('hcai_facilities', 'https://data.chhs.ca.gov/dataset/licensed-healthcare-facility-listing', r'href="([^"]+(?:\.csv|\.xlsx|download)[^"]*)"'),
        ('ca_kosher_halal', 'https://www.cdfa.ca.gov/', r'href="([^"]+(?:kosher|halal)[^"]*)"')]:
    b = get(url, binary=True, tries=1, timeout=60)
    h = b.decode('utf-8', 'ignore') if b else ''
    pr[name] = {'ok': bool(b), 'title': re.findall(r'<title>(.*?)</title>', h, re.S)[:1], 'links': sorted(set(re.findall(pat, h)))[:30]}
    note(f'{name}: ok={pr[name]["ok"]} · {len(pr[name]["links"])} links {pr[name]["links"][:4]}')
save('probes.json', pr)

# ---------------------------------------------------------------- 7. summary
save('summary.json', summary)
with open(os.path.join(OUT, 'FINDINGS.md'), 'w') as f:
    f.write('# San Francisco + Bay Area scouting run\n\nGenerated by scouting/sf/scout.py in GitHub Actions on ' + time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime()) +
            '. Read with the project note sf-bay-data-scouting.md. Details per dataset in out/datasets/.\n\n')
    for l in findings: f.write('- ' + l + '\n')
print('done')
