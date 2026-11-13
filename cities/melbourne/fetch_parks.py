"""Melbourne's parks and what's in them -> cities/melbourne/raw/parks/. Runs in GitHub Actions (fetch-melbourne.yml,
which runs a fetch script when a push changes it); the sandbox can't reach these hosts.

- City of Melbourne open data (data.melbourne.vic.gov.au, Opendatasoft; CC BY 4.0 on most datasets, checked per
  dataset in catalog.json): the catalogue's park-related datasets listed in catalog.json, and each one whose title
  is about open space, playgrounds, dogs, toilets, drinking fountains or barbecues saved as <dataset_id>.geojson.
- OpenStreetMap via Overpass (ODbL), the City's frame: named parks, gardens and reserves with their outlines
  (osm_parks.json; the City publishes no park outlines) and what's in or beside them (osm_amenities.json):
  playgrounds, dog parks, toilets, water play, barbecues, and public pitches, pools and skate parks for Sports & rec.
Each step logs its own failure and the rest carry on."""
import json, os, re, sys, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_lib import RAW, CITY, FAILED, get, step, overpass

OUT = os.path.join(RAW, 'parks'); os.makedirs(OUT, exist_ok=True)
CoM = 'https://data.melbourne.vic.gov.au/api/explore/v2.1/'
TERMS = ['open space', 'park', 'playground', 'dog', 'toilet', 'drinking fountain', 'barbecue', 'bbq', 'garden', 'reserve']
WANT = re.compile(r'open space|playground|dog|toilet|drinking fountain|barbecue|bbq', re.I)


def catalog():
    seen = {}
    for t in TERMS:
        q = urllib.parse.urlencode({'where': f'search("{t}")', 'limit': 100})
        d = json.loads(get(CoM + 'catalog/datasets?' + q))
        for r in d.get('results', []):
            m = r.get('metas', {}).get('default', {})
            seen[r['dataset_id']] = {'title': m.get('title'), 'records': m.get('records_count'), 'license': m.get('license'),
                                     'modified': m.get('modified'), 'geo': 'geo' in str(r.get('features', []))}
    json.dump(seen, open(os.path.join(OUT, 'catalog.json'), 'w'), indent=1, ensure_ascii=False, sort_keys=True)
    for k, v in sorted(seen.items()): print(f'  {k} | {v["title"]} | {v["records"]} | {v["license"]} | {v["modified"]} | geo {v["geo"]}')
    return seen


def datasets(seen):
    for k, v in sorted(seen.items()):
        if not v['title'] or not WANT.search(v['title']) or not v['geo'] or v['title'].startswith('Street furniture'): continue   # 27 MB of bollards and bins
        try:
            b = get(CoM + f'catalog/datasets/{k}/exports/geojson', tries=2)
            d = json.loads(b)
            open(os.path.join(OUT, k + '.geojson'), 'wb').write(b)
            f = d.get('features', [])
            print(f'  saved {k}: {len(f)} features; fields {sorted(f[0]["properties"]) if f else None}')
            if f: print('    e.g.', json.dumps(f[0]['properties'], ensure_ascii=False)[:400])
        except Exception as e: print('  ', k, e)


def bb(b): return f'{b[1]},{b[0]},{b[3]},{b[2]}'


def osm():
    """Parks and gardens with outlines, and what's in them: playgrounds, dog parks, toilets, water play, barbecues,
    drinking water, and public sports (pitches by sport, pools, skate parks). Private ones are left out."""
    B, PRIV = bb(CITY), '["access"!~"private|no|customers"]'
    overpass(f"""[out:json][timeout:300];(
  way["leisure"~"^(park|garden|nature_reserve)$"]["name"]({B});
  relation["leisure"~"^(park|garden|nature_reserve)$"]["name"]({B});
);out body geom;""", 'parks/osm_parks.json')
    overpass(f"""[out:json][timeout:300];(
  nwr["leisure"~"^(playground|dog_park|pitch|swimming_pool|water_park)$"]{PRIV}({B});
  nwr["leisure"="sports_centre"]["sport"~"swimming"]{PRIV}({B});
  nwr["sport"="skateboard"]{PRIV}({B});
  nwr["playground"~"splash_pad|water"]({B});
  nwr["amenity"~"^(toilets|bbq|drinking_water)$"]({B});
);out tags center;""", 'parks/osm_amenities.json')


box = {}
step('catalogue', lambda: box.update(seen=catalog()))
step('datasets', lambda: datasets(box.get('seen', {})))
step('osm', osm)
if FAILED: print('FAILED steps:', FAILED)
