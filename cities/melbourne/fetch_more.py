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
Each step logs its own failure and the rest carry on. (Its log is raw/fetch_more.log.)"""
import csv, io, json, os, re, sys, urllib.parse, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_lib import RAW, CITY, REGION, FAILED, get, step, overpass, vicmap_box

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


def wfs_bbox(layer, out, where=None):
    feats = vicmap_box(layer, CITY, page=2000, where=where)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(OUT, out), 'w'), separators=(',', ':'))
    print(f'  saved {out} from {layer}: {len(feats)} features; e.g.', json.dumps(feats[0]['properties'])[:600] if feats else None)


VHD = 'https://api.heritagecouncil.vic.gov.au/v1/'


def vhd(path):
    import urllib.request
    req = urllib.request.Request(VHD + path, headers={'Accept': 'application/hal+json', 'User-Agent': 'city-layers/1.0 (https://layers.city)'})
    with urllib.request.urlopen(req, timeout=120) as r: return json.loads(r.read())


def heritage():
    """The Victorian Heritage Database (Heritage Council API, CC BY 4.0): every place in the City's box, with its
    Heritage Register number when it has one (heritage_places.json); the authorities list to tell the Register
    from the councils' Heritage Overlay listings (heritage_authorities.json)."""
    json.dump(vhd('heritage-authorities'), open(os.path.join(OUT, 'heritage_authorities.json'), 'w'), ensure_ascii=False)
    places, page = [], 1
    while True:
        d = vhd(f'places?geo=-37.808,144.946,6&rpp=1000&page={page}')   # 6 km round the City's middle; heritage.py keeps the City's own
        got = (d.get('_embedded') or {}).get('places') or []
        places += got
        print(f'  heritage page {page}: {len(got)} (total {d.get("total_items") or d.get("total")})')
        if len(got) < 1000: break
        page += 1
    json.dump(places, open(os.path.join(OUT, 'heritage_places.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
    print('  saved heritage_places.json', len(places), '; e.g.', json.dumps(places[0], ensure_ascii=False)[:900] if places else None)


def overlay():
    wfs_bbox('open-data-platform:plan_overlay', 'heritage_overlay.geojson', where="zone_code LIKE 'HO%'")


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
        r'development activity monitor|landmarks and places|bike route|bicycle route|city activities|planned works|^off-street car parks', v['title'] or '', re.I)]
    for k in want:
        q = ''
        try:
            if 'off-street' in (seen[k]['title'] or '').lower():
                # One row per car park per census year since 2002: the latest year only.
                y = json.loads(get(CoM + f'catalog/datasets/{k}/records?' + urllib.parse.urlencode({'select': 'max(census_year) as y'})))
                print('  off-street car parks, latest year:', y)
                q = '?' + urllib.parse.urlencode({'where': f'year(census_year)={y["results"][0]["y"][:4]}'})
            b = get(CoM + f'catalog/datasets/{k}/exports/geojson' + q, tries=2)
            d = json.loads(b); f = d.get('features', [])
            open(os.path.join(OUT, k[:60] + '.geojson'), 'wb').write(b)
            print(f'  saved {k}: {len(f)} features; e.g.', json.dumps(f[0]['properties'], ensure_ascii=False)[:500] if f else None)
        except Exception as e: print('  failed', k, repr(e)[:300])


def construction():
    """Rail under construction across Greater Melbourne (OSM): the Suburban Rail Loop East's tracks and stations
    (osm_construction.json), whatever OSM tags them with, by name or operator."""
    overpass(f"""[out:json][timeout:300];(
  nwr["name"~"Suburban Rail Loop|^SRL"]({bb(REGION)});
  nwr["operator"~"Suburban Rail Loop"]({bb(REGION)});
  way["railway"="construction"]({bb(REGION)});
);out tags geom;""", 'more/osm_construction.json')


ONLY = os.environ.get('ONLY', 'construction').split(',')   # set ONLY=osm,datavic,com for a full run; heritage always runs
if not ONLY or 'osm' in ONLY: step('osm', osm)
if not ONLY or 'datavic' in ONLY: step('datavic', datavic)
if not ONLY or 'heritage' in ONLY: step('heritage', heritage)
if not ONLY or 'com' in ONLY: step('city of melbourne', com)
if not ONLY or 'construction' in ONLY: step('construction', construction)
if FAILED: print('FAILED steps:', FAILED)
