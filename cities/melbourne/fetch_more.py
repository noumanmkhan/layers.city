"""Melbourne's places, schools, heritage, development and parking -> cities/melbourne/raw/more/. Runs in GitHub Actions
(fetch-melbourne.yml runs a fetch script when a push changes it); the sandbox can't reach these hosts.

- OpenStreetMap via Overpass (ODbL): in and around the City, libraries, community centres, places of worship, shops
  and restaurants tagged halal or kosher, and cycleways and bike lanes (osm_city.json); across Greater Melbourne,
  hospitals, universities and colleges (osm_region.json).
- DataVic (data.vic.gov.au, CKAN; CC BY 4.0 unless the package says otherwise): the Department of Education's school
  locations (latest year), the Victorian Heritage Register, Government School Zones (packages listed in
  datavic.json with their resources; the chosen files saved alongside).
- Vicmap WFS (CC BY 4.0): the planning scheme's Heritage Overlay in the City (heritage_overlay.geojson).
- City of Melbourne open data (CC BY 4.0 on most; catalogue in com_catalog.json): the Development Activity Monitor,
  off-street car parks (latest census year), landmarks and places of interest, bike routes, and the activities and
  planned works feed, when the catalogue has them.
Each step logs its own failure and the rest carry on."""
import csv, io, json, os, re, sys, urllib.parse, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_lib import RAW, CITY, REGION, FAILED, get, step, overpass

OUT = os.path.join(RAW, 'more'); os.makedirs(OUT, exist_ok=True)
def bb(b): return f'{b[1]},{b[0]},{b[3]},{b[2]}'
NEAR = (CITY[0] - 0.03, CITY[1] - 0.025, CITY[2] + 0.03, CITY[3] + 0.025)   # the City and a walk past its edge


def osm():
    B = bb(NEAR)
    overpass(f"""[out:json][timeout:400];(
  nwr["amenity"~"^(library|community_centre|place_of_worship)$"]({B});
  nwr["diet:halal"~"^(yes|only)$"]({B});
  nwr["diet:kosher"~"^(yes|only)$"]({B});
  nwr["shop"]["halal"~"^(yes|only)$"]({B});
);out tags center;""", 'more/osm_city.json')
    overpass(f"""[out:json][timeout:400];(
  way["highway"="cycleway"]({B});
  way["cycleway"~"^(lane|track|shared_lane|share_busway|separate)$"]({B});
  way["cycleway:left"~"^(lane|track|shared_lane|share_busway)$"]({B});
  way["cycleway:right"~"^(lane|track|shared_lane|share_busway)$"]({B});
  way["cycleway:both"~"^(lane|track|shared_lane|share_busway)$"]({B});
  way["highway"="path"]["bicycle"="designated"]({B});
);out tags geom;""", 'more/osm_bikes.json')
    R = bb(REGION)
    overpass(f"""[out:json][timeout:400];(
  nwr["amenity"="hospital"]({R});
  nwr["amenity"~"^(university|college)$"]({R});
);out tags center;""", 'more/osm_region.json')


DV = 'https://discover.data.vic.gov.au/api/3/action/'


def datavic():
    found = {}
    for q in ['school locations', 'school zones', 'victorian heritage register', 'hospital locations']:
        d = json.loads(get(DV + 'package_search?' + urllib.parse.urlencode({'q': q, 'rows': 12})))
        for p in d['result']['results']:
            found[p['name']] = {'title': p['title'], 'license': p.get('license_title'), 'modified': p.get('metadata_modified'),
                                'resources': [{'name': r.get('name'), 'format': r.get('format'), 'url': r.get('url'),
                                               'modified': r.get('last_modified') or r.get('created')} for r in p.get('resources', [])]}
    json.dump(found, open(os.path.join(OUT, 'datavic.json'), 'w'), indent=1, ensure_ascii=False, sort_keys=True)
    for k, v in sorted(found.items()):
        print(f'  {k} | {v["title"]} | {v["license"]}')
        for r in v['resources'][:8]: print(f'      {r["format"]} | {r["name"]} | {r["url"]}')
    # School locations: the newest CSV of the package whose title says "School Locations".
    pk = [v for v in found.values() if re.search(r'school locations', v['title'], re.I)]
    rs = [r for v in pk for r in v['resources'] if (r['format'] or '').upper() == 'CSV']
    rs.sort(key=lambda r: (re.findall(r'20\d\d', (r['name'] or '') + r['url']) or ['0'])[-1], reverse=True)
    if rs:
        b = get(rs[0]['url']); open(os.path.join(OUT, 'school_locations.csv'), 'wb').write(b)
        print('  saved school_locations.csv from', rs[0]['name'], len(b) // 1000, 'KB; header', b[:400])
    # Victorian Heritage Register: a GeoJSON, else a zipped shapefile, of the places.
    pk = [v for v in found.values() if re.search(r'heritage register', v['title'], re.I)]
    for v in pk:
        for r in v['resources']:
            f = (r['format'] or '').upper()
            if f in ('GEOJSON', 'JSON') or (f in ('ZIP', 'SHP') and 'shp' in (r['url'] + (r['name'] or '')).lower()):
                try:
                    b = get(r['url']); ext = 'geojson' if f in ('GEOJSON', 'JSON') else 'zip'
                    open(os.path.join(OUT, 'vhr.' + ext), 'wb').write(b); print('  saved vhr.' + ext, r['name'], len(b) // 1000, 'KB'); return
                except Exception as e: print('   ', r['url'], e)


WFS = 'https://opendata.maps.vic.gov.au/geoserver/wfs'


def heritage_overlay():
    cap = get(WFS + '?service=WFS&request=GetCapabilities&version=2.0.0').decode('utf-8', 'replace')
    names = re.findall(r'<(?:wfs:)?Name>([^<]+)</(?:wfs:)?Name>', cap)
    hits = [n for n in names if re.search(r'overlay|heritage', n, re.I)]
    print('  overlay/heritage layers:', hits)
    for n in hits:
        if not re.search(r'plan_overlay$|planning_overlay|heritage_overlay', n): continue
        q = {'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature', 'typeNames': n, 'outputFormat': 'application/json',
             'srsName': 'EPSG:4326', 'count': 5000,
             'CQL_FILTER': f"zone_code LIKE 'HO%' AND BBOX(geom,{CITY[1]},{CITY[0]},{CITY[3]},{CITY[2]},'EPSG:4326')"}
        for geomname in ('geom', 'the_geom', 'shape'):
            q['CQL_FILTER'] = re.sub(r'BBOX\(\w+', f'BBOX({geomname}', q['CQL_FILTER'])
            try:
                b = get(WFS + '?' + urllib.parse.urlencode(q), tries=2)
                d = json.loads(b)
                if d.get('features'):
                    open(os.path.join(OUT, 'heritage_overlay.geojson'), 'wb').write(b)
                    print('  saved heritage_overlay from', n, len(d['features']), 'features; e.g.', d['features'][0]['properties']); return
            except Exception as e: print('   ', n, geomname, str(e)[:200])


CoM = 'https://data.melbourne.vic.gov.au/api/explore/v2.1/'


def com():
    seen = {}
    for t in ['development', 'car park', 'bicycle', 'bike', 'landmarks', 'activities', 'planned works', 'event', 'library',
              'community', 'heritage', 'waste', 'garbage', 'building']:
        d = json.loads(get(CoM + 'catalog/datasets?' + urllib.parse.urlencode({'where': f'search("{t}")', 'limit': 100})))
        for r in d.get('results', []):
            m = r.get('metas', {}).get('default', {})
            seen[r['dataset_id']] = {'title': m.get('title'), 'records': m.get('records_count'), 'license': m.get('license'),
                                     'modified': m.get('modified'), 'fields': [f['name'] for f in r.get('fields', [])][:40]}
    json.dump(seen, open(os.path.join(OUT, 'com_catalog.json'), 'w'), indent=1, ensure_ascii=False, sort_keys=True)
    for k, v in sorted(seen.items()): print(f'  {k} | {v["title"]} | {v["records"]} | {v["modified"]}')
    want = [k for k, v in seen.items() if re.search(
        r'development activity monitor|landmarks and places|bike route|bicycle route|bicycle network|city activities|planned works|^off-street car parks', v['title'] or '', re.I)]
    for k in want:
        q = ''
        if 'off-street' in (seen[k]['title'] or '').lower():
            # One row per car park per census year since 2002: the latest year only.
            y = json.loads(get(CoM + f'catalog/datasets/{k}/records?' + urllib.parse.urlencode({'select': 'max(census_year) as y'})))
            q = '?' + urllib.parse.urlencode({'where': f'census_year={y["results"][0]["y"]}'})
        try:
            b = get(CoM + f'catalog/datasets/{k}/exports/geojson' + q, tries=2)
            d = json.loads(b); f = d.get('features', [])
            open(os.path.join(OUT, k[:60] + '.geojson'), 'wb').write(b)
            print(f'  saved {k}: {len(f)} features; e.g.', json.dumps(f[0]['properties'], ensure_ascii=False)[:500] if f else None)
        except Exception as e: print('  ', k, e)


step('osm', osm)
step('datavic', datavic)
step('heritage overlay', heritage_overlay)
step('city of melbourne', com)
if FAILED: print('FAILED steps:', FAILED)
