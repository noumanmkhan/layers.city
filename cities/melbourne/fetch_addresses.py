"""Melbourne's address points for the card's Address row -> cities/melbourne/raw/addresses.json, the shape San
Francisco's uses: {"fetched", "rows": [[street, number, lon, lat], ...]}. Runs in GitHub Actions (fetch-melbourne.yml);
the sandbox can't reach Vicmap.

Vicmap Address (CC BY 4.0), the WFS layer open-data-platform:address, every point in the City's box, paged. One row
per street number: units in one building share it, so only the first point of each (street, number) is kept."""
import json, os, sys, time, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_lib import RAW, CITY, get

WFS = 'https://opendata.maps.vic.gov.au/geoserver/wfs'
rows, seen, start, PAGE = [], set(), 0, 5000
while True:
    q = {'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature', 'typeNames': 'open-data-platform:address',
         'outputFormat': 'application/json', 'srsName': 'EPSG:4326', 'count': PAGE, 'startIndex': start, 'sortBy': 'pfi',
         'propertyName': 'road_name,road_type,road_suffix,house_number_1,locality_name,geom',
         'bbox': f'{CITY[1]},{CITY[0]},{CITY[3]},{CITY[2]},urn:ogc:def:crs:EPSG::4326'}
    d = json.loads(get(WFS + '?' + urllib.parse.urlencode(q), tries=4, timeout=300))
    fs = d.get('features', [])
    for f in fs:
        p = f['properties']; n = p.get('house_number_1'); g = f.get('geometry')
        if not n or not p.get('road_name') or not g: continue
        st = ' '.join(x for x in (p['road_name'], p.get('road_type'), p.get('road_suffix')) if x)
        if (st, n) in seen: continue
        seen.add((st, n))
        c = g['coordinates']
        while isinstance(c[0], list): c = c[0]
        rows.append([st, int(n), round(c[0], 6), round(c[1], 6)])
    print(f'  page from {start}: {len(fs)} points, {len(rows)} rows so far')
    if len(fs) < PAGE: break
    start += PAGE; time.sleep(1)
json.dump({'fetched': time.strftime('%Y-%m-%d'), 'rows': rows}, open(os.path.join(RAW, 'addresses.json'), 'w'), separators=(',', ':'))
print('wrote addresses.json', len(rows), 'rows', os.path.getsize(os.path.join(RAW, 'addresses.json')) // 1000, 'KB')
