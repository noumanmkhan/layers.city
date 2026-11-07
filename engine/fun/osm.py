"""OpenStreetMap shops and amenities for a city's Fun maps (the `pair` maps' OSM sides), shared by the cities'
fetch_fun.py scripts: one Overpass query over a bounding box, written as osm_places.json, one row per place,
[lon, lat, amenity, shop, leisure, brand, name, cuisine, sport]. ODbL. Tennis and pickleball courts (leisure=pitch with
that sport) come too, for a city without a published sports layer. Toronto's fetch_fun.py has its own copy of this
query (it came first); the tags here are the same, plus supermarkets. The engine names no city.

Usage (from a city's fetch_fun.py): from fun.osm import places; places((s, w, n, e), out_path)"""
import json, time, urllib.parse, urllib.request

UA = {'User-Agent': 'layers.city pipeline (go@layers.city)'}
HOSTS = ('https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter')
COLS = ['lon', 'lat', 'amenity', 'shop', 'leisure', 'brand', 'name', 'cuisine', 'sport']


def places(bbox, out_path):
    s, w, n, e = bbox
    bb = f'{s},{w},{n},{e}'
    q = f"""[out:json][timeout:600];
(
  nwr["amenity"~"^(cafe|fast_food|restaurant|fuel|pharmacy|bar|pub|car_wash|ice_cream|library|bank)$"]({bb});
  nwr["shop"~"^(alcohol|cannabis|laundry|dry_cleaning|books|e-cigarette|bicycle|variety_store|convenience|bakery|tea|beverages|wine|car|supermarket)$"]({bb});
  nwr["leisure"="fitness_centre"]({bb});
  nwr["leisure"="pitch"]["sport"~"tennis|pickleball"]({bb});
);
out center tags;"""
    blob = None
    for host in HOSTS:
        for attempt in range(3):
            try:
                req = urllib.request.Request(host, data=urllib.parse.urlencode({'data': q}).encode(), headers=UA)
                with urllib.request.urlopen(req, timeout=900) as r:
                    blob = r.read()
                break
            except Exception as ex:
                print(f'  overpass {host} try {attempt + 1} failed: {ex}', flush=True)
                time.sleep(30)
        if blob:
            break
    if blob is None:
        raise RuntimeError('every Overpass host failed')
    rows = []
    for el in json.loads(blob)['elements']:
        t = el.get('tags', {})
        lat = el.get('lat') or el.get('center', {}).get('lat')
        lon = el.get('lon') or el.get('center', {}).get('lon')
        if lat is None:
            continue
        rows.append([round(lon, 5), round(lat, 5), *(t.get(k, '') for k in COLS[2:])])
    print(f'  {len(rows)} OSM places', flush=True)
    with open(out_path, 'w') as f:
        json.dump({'asof': time.strftime('%Y-%m-%d'), 'source': 'OpenStreetMap contributors (ODbL), via Overpass',
                   'cols': COLS, 'rows': rows}, f, separators=(',', ':'))
    return rows
