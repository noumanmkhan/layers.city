"""Scouting (October 18, 2026): what New York City's open data actually holds, before building the city.
Desk scouting is in the project notes (nyc-data-scouting.md); this checks it from Actions, with counts,
field names and freshness, because none of these hosts can be reached from a Claude sandbox.

Decided with the user: community districts (59) are the units, NTAs (262) a second boundary layer;
"To Midtown" hub is Penn Station first (Grand Central as a user choice later); skyscrapers from 650 ft;
regional view is the tri-state commuter belt, mainly to show how far the commuter trains reach.

Writes scouting/nyc/out/:
  catalog.json          every dataset on data.cityofnewyork.us: id, name, type, updated, category
  datasets/<key>.json   for each dataset the map needs: the catalogue candidates, the one picked, its
                        columns, row count, last data update and 3 sample rows (geometry trimmed)
  arcgis.json           DSNY frequencies, NYSDOT roadway inventory, NYS polling-site layer
  gtfs.json             MTA subway, the six bus feeds, LIRR, Metro-North: routes by type, stops, dates
  citibike.json         GBFS station_information: count, fields, e-bike charging stations
  boe/                  the Board of Elections poll-site PDFs for November 3, 2026, one per borough,
                        with the AD/ED -> site rows parsed out where pypdf can read them
  probes.json           Census ACS tracts, AFDC chargers, Wikipedia tallest, NYS kosher/halal pages
  summary.json          one line per check
  FINDINGS.md           the same, readable
Nothing here feeds the map."""
import csv, io, json, os, re, time, urllib.parse, urllib.request, zipfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'out')
os.makedirs(os.path.join(OUT, 'datasets'), exist_ok=True); os.makedirs(os.path.join(OUT, 'boe'), exist_ok=True)
UA = {'User-Agent': 'city-layers-scouting (https://layers.city)'}
SOC = 'https://data.cityofnewyork.us'
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


# ---------------------------------------------------------------- 1. the whole Socrata catalogue
cat, off = [], 0
while True:
    d = get(f'https://api.us.socrata.com/api/catalog/v1?domains=data.cityofnewyork.us&limit=100&offset={off}')
    if not d: break
    for r in d.get('results', []):
        res = r['resource']
        cat.append({'id': res['id'], 'name': res['name'], 'type': res.get('type'),
                    'updated': (res.get('data_updated_at') or res.get('updatedAt') or '')[:10],
                    'category': (r.get('classification') or {}).get('domain_category'),
                    'agency': next((m.get('value') for m in (r.get('classification') or {}).get('domain_metadata', []) if 'Agency' in (m.get('key') or '')), None),
                    'desc': (res.get('description') or '')[:200].replace('\n', ' ')})
    if len(d.get('results', [])) < 100: break
    off += 100
cat.sort(key=lambda x: x['name'].lower()); save('catalog.json', cat)
note(f'Catalogue: {len(cat)} datasets on data.cityofnewyork.us')
summary['catalog'] = {'datasets': len(cat), 'categories': Counter(c['category'] for c in cat).most_common(15)}

# ---------------------------------------------------------------- 2. the datasets the map needs
# key -> list of title phrases to look for (first exact title wins, then containment), newest first
WANT = {
    'boroughs': ['Borough Boundaries', 'Borough Boundaries (Water Areas Included)'],
    'community_districts': ['Community Districts'],
    'ntas_2020': ['2020 Neighborhood Tabulation Areas (NTAs)'],
    'census_tracts_2020': ['2020 Census Tracts'],
    'neighborhood_names': ['Neighborhood Names GIS'],
    'council_districts': ['City Council Districts'],
    'assembly_districts': ['State Assembly Districts'],
    'senate_districts': ['State Senate Districts'],
    'congressional_districts': ['Congressional Districts'],
    'election_districts': ['Election Districts'],
    'school_districts': ['School Districts'],
    'bids': ['Business Improvement Districts'],
    'lpc_districts': ['Historic Districts'],
    'lpc_landmarks': ['Individual Landmark Sites', 'Individual Landmarks'],
    'lpc_buildings': ['LPC Individual Landmark and Historic District Building Database'],
    'lpc_calendared': ['Designated and Calendared Buildings and Sites'],
    'parks_properties': ['Parks Properties'],
    'playgrounds': ['Directory of Playgrounds', 'Playgrounds'],
    'spray_showers': ['Directory of Spray Showers', 'Spray Showers'],
    'dog_runs': ['NYC Parks Dog Runs', 'Directory of Dog Runs and Off-Leash Areas', 'Dog Runs'],
    'comfort_stations': ['Directory of Toilets in Public Parks', 'Comfort Stations'],
    'athletic_facilities': ['Athletic Facilities', 'Directory of Athletic Facilities'],
    'pools': ['Directory of Pools', 'NYC Parks Pools'],
    'rinks': ['Directory of Ice Skating Rinks', 'Ice Skating Rinks'],
    'skate_parks': ['Directory of Skate Parks', 'Skate Parks'],
    'rec_centers': ['Directory of Recreation Centers', 'Recreation Centers'],
    'facdb': ['Facilities Database', 'NYC Facilities Database'],
    'schools_points': ['School Point Locations', 'School Locations'],
    'school_zones_es': ['School Zones 2025-2026 (Elementary School)', 'School Zones 2024-2025 (Elementary School)'],
    'school_zones_ms': ['School Zones 2025-2026 (Middle School)', 'School Zones 2024-2025 (Middle School)'],
    'school_zones_hs': ['School Zones 2025-2026 (High School)', 'School Zones 2024-2025 (High School)'],
    'colleges': ['Colleges and Universities', 'COLLEGE UNIVERSITY'],
    'hospitals': ['NYC Health + Hospitals Facilities', 'Hospitals', 'Health Facility General Information'],
    'libraries': ['Library', 'LIBRARY'],
    'street_centerline': ['NYC Street Centerline (CSCL)', 'Street Centerline'],
    'lion': ['LION', 'LION Single Line Street Base Map'],
    'truck_routes': ['Truck Routes', 'NYC Truck Routes'],
    'bike_routes': ['New York City Bike Routes', 'Bicycle Routes', 'NYC Bike Routes'],
    'bike_racks': ['Bicycle Parking', 'Bicycle Parking Shelters'],
    'street_closures_block': ['Street Closures due to construction activities by Block'],
    'street_closures_intersection': ['Street Closures due to construction activities by Intersection'],
    'permitted_events': ['NYC Permitted Event Information'],
    'dob_now_jobs': ['DOB NOW: Build – Job Application Filings', 'DOB NOW: Build - Job Application Filings'],
    'dob_permits': ['DOB Permit Issuance'],
    'dob_now_permits': ['DOB NOW: Build – Approved Permits', 'DOB NOW: Build - Approved Permits'],
    'housing_database': ['Housing Database', 'Housing Database by 2020 NTA'],
    'zap_projects': ['Zoning Application Portal (ZAP) - Project Data'],
    'zap_bbl': ['Zoning Application Portal (ZAP) - BBL', 'Zoning Application Portal (ZAP) - Project BBLs'],
    'poll_sites_2018': ['Voting/Poll Sites', 'Voting Poll Sites'],
    'evacuation_zones': ['Hurricane Evacuation Zones'],
    'evacuation_centers': ['Hurricane Evacuation Centers'],
    'parking_regulations': ['Parking Regulation Locations and Signs'],
    'municipal_parking': ['Municipal Parking Facilities', 'DOT Municipal Parking Facilities', 'Carshare Locations - Municipal Garages and Lots'],
    'ev_chargers': ['Electric Vehicle Charging Stations', 'EV Charging Stations'],
    'pops': ['Privately Owned Public Spaces (POPS)', 'Privately Owned Public Spaces'],
    'open_streets': ['Open Streets Locations', 'Open Streets'],
    'plazas': ['NYC DOT Pedestrian Plazas', 'Pedestrian Plazas'],
    'ferry_routes': ['NYC Ferry Routes', 'Ferry Routes'],
    'ferry_landings': ['NYC Ferry Landings', 'Ferry Landings'],
    'subway_stations': ['MTA Subway Stations', 'Subway Stations'],
    'shoreline': ['Shoreline', 'NYC Shoreline'],
    'hydrography': ['Hydrography'],
    'address_points': ['NYC Address Points', 'Address Points'],
    'dsny_frequencies_socrata': ['DSNY Frequencies'],
    'dsny_districts': ['DSNY Districts', 'DSNY Sections'],
    'police_precincts': ['Police Precincts'],
    'nycha': ['Map of NYCHA Developments', 'NYCHA Developments'],
    'beaches': ['Beaches', 'Directory of Beaches'],
    'tree_canopy': ['Tree Canopy Change', 'Land Cover Raster Data'],
    'senior_centers': ['DFTA Contracts', 'Senior Centers'],
    'community_centers': ['DYCD Cornerstone', 'Community Centers'],
}
by_name = {}
for c in cat: by_name.setdefault(c['name'].strip().lower(), []).append(c)


def candidates(phrases):
    out = []
    for p in phrases:
        for c in by_name.get(p.lower(), []): out.append(('exact', c))
    for p in phrases:
        for c in cat:
            if p.lower() in c['name'].lower() and all(c is not o[1] for o in out): out.append(('contains', c))
    return out[:8]


summary['datasets'] = {}
for key, phrases in WANT.items():
    cands = candidates(phrases)
    rec = {'key': key, 'looked_for': phrases, 'candidates': [[k, c['id'], c['name'], c['type'], c['updated']] for k, c in cands]}
    if not cands:
        note(f'{key}: NOT FOUND in catalogue ({phrases[0]})'); summary['datasets'][key] = None
        save(f'datasets/{key}.json', rec); continue
    pick = cands[0][1]; i = pick['id']; print(f'{key}: {pick["name"]} ({i})')
    meta = get(f'{SOC}/api/views/{i}.json') or {}
    cols = [{'name': c.get('fieldName'), 'type': c.get('dataTypeName'), 'label': c.get('name')} for c in meta.get('columns', [])]
    ts = lambda t: time.strftime('%Y-%m-%d', time.gmtime(t)) if t else None
    cnt = None
    if meta.get('viewType') != 'geo' and pick['type'] != 'map':
        c = get(f'{SOC}/resource/{i}.json?$select=count(*)')
        try: cnt = int(list(c[0].values())[0])
        except Exception: cnt = None
    samples = get(f'{SOC}/resource/{i}.json?$limit=3') or []
    if isinstance(samples, list):
        for s in samples:
            for k, v in list(s.items()):
                if isinstance(v, dict) and 'type' in v and 'coordinates' in v: s[k] = {'geometry_type': v['type']}
                elif isinstance(v, str) and len(v) > 300: s[k] = v[:300] + '…'
    else:
        samples = []
    geo = None
    BIG = {'street_centerline', 'lion', 'address_points', 'hydrography', 'parking_regulations', 'dob_permits', 'dob_now_jobs', 'housing_database', 'census_tracts_2020'}
    if (meta.get('viewType') == 'geo' or pick['type'] == 'map') and key not in BIG:   # geo datasets: count by reading the GeoJSON export
        g = get(f'{SOC}/api/geospatial/{i}?method=export&format=GeoJSON', binary=True, timeout=300)
        if g:
            try:
                gj = json.loads(g); geo = {'bytes': len(g), 'features': len(gj.get('features', [])),
                                           'props': sorted(gj['features'][0]['properties'].keys()) if gj.get('features') else []}
                cnt = geo['features']
            except Exception as e:
                geo = {'bytes': len(g), 'error': str(e)[:100]}
    rec.update({'picked': {'id': i, 'name': pick['name'], 'type': pick['type'], 'viewType': meta.get('viewType'),
                           'attribution': meta.get('attribution'), 'category': meta.get('category'),
                           'rows_updated': ts(meta.get('rowsUpdatedAt')), 'view_modified': ts(meta.get('viewLastModified')),
                           'update_frequency': (meta.get('metadata') or {}).get('custom_fields', {}).get('Update', {}).get('Update Frequency'),
                           'description': (meta.get('description') or '')[:800]},
                'count': cnt, 'geo': geo, 'columns': cols, 'samples': samples})
    save(f'datasets/{key}.json', rec)
    line = f'{key}: "{pick["name"]}" {i} · {cnt if cnt is not None else "?"} rows · data {rec["picked"]["rows_updated"]} · {len(cols)} cols'
    note(line); summary['datasets'][key] = [i, pick['name'], cnt, rec['picked']['rows_updated']]
    time.sleep(0.3)

# ---------------------------------------------------------------- 3. ArcGIS services
arc = {}
def arc_layer(name, url, where='1=1'):
    m = get(url + '?f=pjson') or {}
    c = get(url + '/query?where=' + urllib.parse.quote(where) + '&returnCountOnly=true&f=json') or {}
    s = get(url + '/query?where=' + urllib.parse.quote(where) + '&outFields=*&resultRecordCount=3&returnGeometry=false&f=json') or {}
    ed = (m.get('editingInfo') or {}).get('lastEditDate')
    arc[name] = {'url': url, 'name': m.get('name'), 'geometry': m.get('geometryType'), 'count': c.get('count'),
                 'last_edit': time.strftime('%Y-%m-%d', time.gmtime(ed / 1000)) if ed else None,
                 'fields': [(f['name'], f.get('type'), f.get('alias')) for f in m.get('fields', [])],
                 'samples': [f.get('attributes') for f in s.get('features', [])], 'copyright': m.get('copyrightText'),
                 'max_record_count': m.get('maxRecordCount')}
    note(f'ArcGIS {name}: {arc[name]["count"]} features · edited {arc[name]["last_edit"]} · {len(arc[name]["fields"])} fields')

arc_layer('dsny_frequencies', 'https://services.arcgis.com/uKN48PkxmWiqJM9q/ArcGIS/rest/services/DSNY_Frequencies_OFFICIAL/FeatureServer/0')
for host in ['https://gis.dot.ny.gov/hostingny/rest/services/Roadways/RoadwayData/FeatureServer',
             'https://gisdev.dot.ny.gov/hostingny/rest/services/Roadways/RoadwayData/FeatureServer']:
    m = get(host + '?f=pjson')
    if m:
        arc['nysdot_service'] = {'url': host, 'layers': [(l['id'], l['name']) for l in m.get('layers', [])], 'description': (m.get('serviceDescription') or '')[:600]}
        note(f'NYSDOT {host.split("//")[1].split("/")[0]}: layers {arc["nysdot_service"]["layers"]}')
        # the roadway inventory layer: fields, and a count inside NYC (county names in the state's data)
        inv = next((l['id'] for l in m.get('layers', []) if 'Inventory' in l['name'] and 'Viewer' not in l['name']), None)
        if inv is not None:
            arc_layer('nysdot_inventory', f'{host}/{inv}')
            f = {x[0].upper(): x[0] for x in arc['nysdot_inventory']['fields']}
            fc = next((f[k] for k in f if 'FUNC' in k), None); co = next((f[k] for k in f if k in ('COUNTY', 'COUNTY_NAME', 'CO_NAME')), None)
            arc['nysdot_inventory']['functional_class_field'] = fc; arc['nysdot_inventory']['county_field'] = co
            if fc and co:
                q = f"{co} IN ('NEW YORK','KINGS','QUEENS','BRONX','RICHMOND')"
                d = get(f"{host}/{inv}/query?where={urllib.parse.quote(q)}&groupByFieldsForStatistics={fc}&outStatistics=" +
                        urllib.parse.quote(json.dumps([{'statisticType': 'count', 'onStatisticField': 'OBJECTID', 'outStatisticFieldName': 'n'}])) + '&f=json') or {}
                arc['nysdot_inventory']['nyc_by_class'] = [x['attributes'] for x in d.get('features', [])]
                note(f'NYSDOT NYC segments by {fc}: {arc["nysdot_inventory"]["nyc_by_class"]}')
        break
# NYS GIS polling sites item (data.gis.ny.gov): find its service through ArcGIS Online search
d = get('https://www.arcgis.com/sharing/rest/search?' + urllib.parse.urlencode({'q': 'Election Day Polling Sites NYC', 'f': 'json', 'num': 10}))
arc['nys_polling_search'] = [(r.get('type'), r.get('title'), r.get('owner'), r.get('url'),
                              time.strftime('%Y-%m-%d', time.gmtime((r.get('modified') or 0) / 1000))) for r in (d or {}).get('results', [])]
note(f'ArcGIS Online "Election Day Polling Sites NYC": {arc["nys_polling_search"][:3]}')
for r in arc['nys_polling_search']:
    if r[3] and 'FeatureServer' in r[3]:
        m = get(r[3] + '?f=pjson') or {}
        for l in m.get('layers', [])[:4]: arc_layer(f'nys_polling_{l["id"]}', f'{r[3]}/{l["id"]}')
        break
for q in ['NYC DCP LION', 'NYC Digital City Map', 'NJ municipal boundaries NJGIN', 'Connecticut town boundaries', 'MTA Subway Stations']:
    d = get('https://www.arcgis.com/sharing/rest/search?' + urllib.parse.urlencode({'q': q, 'f': 'json', 'num': 6})) or {}
    arc[f'search: {q}'] = [(r.get('type'), r.get('title'), r.get('owner'), r.get('url')) for r in d.get('results', [])]
save('arcgis.json', arc); summary['arcgis'] = {k: (v.get('count') if isinstance(v, dict) else None) for k, v in arc.items()}

# ---------------------------------------------------------------- 4. MTA GTFS
gt = {}
for name, url in [('subway', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip'),
                  ('bus_bronx', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_bx.zip'), ('bus_brooklyn', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_b.zip'),
                  ('bus_manhattan', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_m.zip'), ('bus_queens', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_q.zip'),
                  ('bus_staten_island', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_si.zip'), ('bus_company', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_busco.zip'),
                  ('lirr', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfslirr.zip'), ('metro_north', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfsmnr.zip')]:
    z = get(url, binary=True, timeout=600, tries=2)
    if not z: gt[name] = 'download failed'; note(f'GTFS {name}: download failed'); continue
    try:
        zf = zipfile.ZipFile(io.BytesIO(z))
        rd = lambda n: list(csv.DictReader(io.TextIOWrapper(zf.open(n), 'utf-8-sig'))) if n in zf.namelist() else []
        routes = rd('routes.txt'); cal = rd('calendar.txt'); fi = rd('feed_info.txt')
        stops = sum(1 for _ in csv.reader(io.TextIOWrapper(zf.open('stops.txt'), 'utf-8-sig'))) - 1 if 'stops.txt' in zf.namelist() else None
        trips = sum(1 for _ in csv.reader(io.TextIOWrapper(zf.open('trips.txt'), 'utf-8-sig'))) - 1 if 'trips.txt' in zf.namelist() else None
        express = sum(1 for r in routes if (r.get('route_short_name') or '').startswith(('X', 'BM', 'QM', 'BxM', 'SIM')))
        sbs = sum(1 for r in routes if 'SBS' in (r.get('route_short_name') or '') or 'Select Bus' in (r.get('route_long_name') or ''))
        gt[name] = {'mb': round(len(z) / 1e6, 1), 'files': zf.namelist(), 'feed_info': fi[:1],
                    'agencies': [a.get('agency_name') for a in rd('agency.txt')],
                    'routes': len(routes), 'routes_by_type': Counter(r.get('route_type') for r in routes).most_common(),
                    'express_routes': express, 'sbs_routes': sbs, 'stops': stops, 'trips': trips,
                    'calendar_span': [min((c['start_date'] for c in cal), default=None), max((c['end_date'] for c in cal), default=None)],
                    'routes_sample': [[r.get('route_short_name'), (r.get('route_long_name') or '')[:50], r.get('route_type'), r.get('route_color')] for r in routes[:40]]}
        note(f'GTFS {name}: {gt[name]["mb"]} MB · {len(routes)} routes {gt[name]["routes_by_type"]} · {stops} stops · {trips} trips · {gt[name]["calendar_span"]}')
    except Exception as e:
        gt[name] = f'unreadable: {e}'; note(f'GTFS {name}: unreadable {e}')
for name, url in [('path', 'https://www.panynj.gov/path/en/schedules-maps.html'), ('nyc_ferry_gtfs', 'http://nycferry.connexionz.net/rtt/public/utility/gtfs.aspx'),
                  ('njtransit_dev', 'https://developer.njtransit.com/terms/')]:
    b = get(url, binary=True, tries=1, timeout=60)
    gt[name] = {'ok': bool(b), 'bytes': len(b) if b else 0, 'zip': bool(b and b[:2] == b'PK'),
                'gtfs_links': sorted(set(re.findall(r'https?://[^"\'\s>]+(?:gtfs|GTFS)[^"\'\s>]*', b.decode('utf-8', 'ignore'))))[:10] if b and b[:2] != b'PK' else []}
    note(f'probe {name}: {gt[name]}')
save('gtfs.json', gt); summary['gtfs'] = {k: (v if isinstance(v, str) else {kk: v.get(kk) for kk in ('mb', 'routes', 'stops', 'calendar_span')}) for k, v in gt.items()}

# ---------------------------------------------------------------- 5. Citi Bike GBFS
cb = {}
g = get('https://gbfs.citibikenyc.com/gbfs/2.3/gbfs.json')
if g:
    feeds = {f['name']: f['url'] for f in g['data'].get('en', g['data'].get(list(g['data'].keys())[0]))['feeds']}
    si = get(feeds.get('station_information', '')) or {}
    st = si.get('data', {}).get('stations', [])
    cb = {'feeds': feeds, 'stations': len(st), 'fields': sorted(st[0].keys()) if st else [],
          'regions': Counter(s.get('region_id') for s in st).most_common(10),
          'charging': sum(1 for s in st if s.get('is_charging_station') or s.get('charging_station')),
          'capacity_total': sum(s.get('capacity', 0) for s in st), 'sample': st[:2],
          'system_information': (get(feeds.get('system_information', '')) or {}).get('data')}
    note(f'Citi Bike: {cb["stations"]} stations · {cb["charging"]} charging · regions {cb["regions"]}')
save('citibike.json', cb); summary['citibike'] = {'stations': cb.get('stations'), 'charging': cb.get('charging')}

# ---------------------------------------------------------------- 6. Board of Elections poll-site PDFs
try:
    import pypdf
except Exception:
    pypdf = None
boe = {}
for boro, slug in [('manhattan', 'New_York_r1'), ('manhattan_r0', 'New_York'), ('bronx', 'Bronx'), ('brooklyn', 'Kings'), ('queens', 'Queens'), ('staten_island', 'Richmond')]:
    url = f'https://www.vote.nyc/sites/default/files/pdf/poll_site_list/GE2026/Poll_Site_List_Nov_General_2026_Election_Day_{slug}.pdf'
    b = get(url, binary=True, tries=1, timeout=90)
    if not b: boe[boro] = {'url': url, 'ok': False}; print('BOE', boro, 'not found'); continue
    with open(os.path.join(OUT, 'boe', f'{boro}.pdf'), 'wb') as f: f.write(b)
    rec = {'url': url, 'ok': True, 'bytes': len(b)}
    if pypdf:
        try:
            text = '\n'.join((p.extract_text() or '') for p in pypdf.PdfReader(io.BytesIO(b)).pages)
            rows = re.findall(r'^\s*(\d{3})\s+(.+?)\.{3,}\s*(.+?)\s*$', text, re.M)
            ads = re.findall(r'(\d{1,3})(?:ST|ND|RD|TH)\s+(?:ASSEMBLY\s+)?DISTRICT', text.upper())
            rec.update({'pages': text.count('\f') + 1, 'ed_rows': len(rows), 'distinct_sites': len({r[1] for r in rows}),
                        'assembly_districts': sorted({int(a) for a in ads}), 'sample_rows': rows[:5], 'text_head': text[:600]})
            with open(os.path.join(OUT, 'boe', f'{boro}.txt'), 'w') as f: f.write(text)
        except Exception as e:
            rec['parse_error'] = str(e)[:200]
    boe[boro] = rec; note(f'BOE {boro}: {rec.get("ed_rows")} ED rows · {rec.get("distinct_sites")} sites · ADs {rec.get("assembly_districts")}')
save('boe.json', boe); summary['boe'] = {k: [v.get('ed_rows'), v.get('distinct_sites')] for k, v in boe.items()}

# ---------------------------------------------------------------- 7. probes
pr = {}
# Census ACS 5-year 2023 tracts in the five counties: tenure, value, rent, commute, units in structure (the Chicago recipe)
acs = get('https://api.census.gov/data/2023/acs/acs5?get=NAME,B25003_001E,B25003_003E,B25077_001E,B25064_001E,B08301_001E,B08301_002E,B25024_001E&for=tract:*&in=state:36&in=county:005,047,061,081,085')
pr['acs_2023_tracts'] = {'rows': len(acs) - 1 if acs else None, 'header': acs[0] if acs else None, 'sample': acs[1:3] if acs else None}
note(f'ACS 2023 tracts in NYC: {pr["acs_2023_tracts"]["rows"]}')
# tract -> NTA / CD equivalency from DCP (2020 census tracts carry NTA and CDTA codes)
# AFDC chargers in NY (one call; DEMO_KEY)
a = get('https://developer.nrel.gov/api/alt-fuel-stations/v1.json?api_key=DEMO_KEY&fuel_type=ELEC&state=NY&access=public&status=E&limit=1')
pr['afdc_ny_public_open'] = (a or {}).get('total_results'); note(f'AFDC public open EV stations in NY: {pr["afdc_ny_public_open"]}')
# Wikipedia tallest list: sections
w = get('https://en.wikipedia.org/w/api.php?action=parse&page=List_of_tallest_buildings_in_New_York_City&prop=sections&format=json')
pr['wikipedia_sections'] = [s['line'] for s in (w or {}).get('parse', {}).get('sections', [])]; note(f'Wikipedia sections: {pr["wikipedia_sections"][:12]}')
# NYS kosher and halal registries: what the pages link to
for name, url in [('nys_kosher', 'https://agriculture.ny.gov/KO/KOHome.html'), ('nys_halal', 'https://agriculture.ny.gov/halal'),
                  ('nys_halal_overview', 'https://agriculture.ny.gov/food-safety/overview-halal-foods-protection-act')]:
    b = get(url, binary=True, tries=1, timeout=60)
    h = b.decode('utf-8', 'ignore') if b else ''
    pr[name] = {'ok': bool(b), 'links': sorted(set(re.findall(r'href="([^"]+(?:xls|xlsx|csv|pdf|KO/|halal|Halal|kosher|Kosher)[^"]*)"', h)))[:30], 'title': re.findall(r'<title>(.*?)</title>', h)[:1]}
    note(f'{name}: {pr[name]["title"]} · {len(pr[name]["links"])} links')
# DCP Bytes of the Big Apple: do the download pages resolve?
for name, url in [('dcp_lion_page', 'https://www.nyc.gov/content/planning/pages/resources/datasets/lion'),
                  ('dcp_districts_page', 'https://www.nyc.gov/content/planning/pages/resources/datasets/political-administrative-districts'),
                  ('dcp_election_districts', 'https://www.nyc.gov/content/planning/pages/resources/datasets/election-districts')]:
    b = get(url, binary=True, tries=1, timeout=60)
    h = b.decode('utf-8', 'ignore') if b else ''
    pr[name] = {'ok': bool(b), 'zips': sorted(set(re.findall(r'href="([^"]+\.zip)"', h)))[:20]}
    note(f'{name}: ok={pr[name]["ok"]} zips={pr[name]["zips"][:6]}')
save('probes.json', pr)

# ---------------------------------------------------------------- 8. summary
save('summary.json', summary)
with open(os.path.join(OUT, 'FINDINGS.md'), 'w') as f:
    f.write('# NYC scouting run\n\nGenerated by scouting/nyc/scout.py in GitHub Actions on ' + time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime()) +
            '. Read with the project note nyc-data-scouting.md. Details per dataset in out/datasets/.\n\n')
    for l in findings: f.write('- ' + l + '\n')
print('done')
