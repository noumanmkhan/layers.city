"""Melbourne's address points for the card's Address row -> cities/melbourne/raw/addresses.json, the shape San
Francisco's uses: {"fetched", "rows": [[street, number, lon, lat], ...]}. Runs in GitHub Actions (fetch-melbourne.yml);
the sandbox can't reach Vicmap.

Vicmap Address (CC BY 4.0), the WFS layer open-data-platform:address, every point in the City's box, paged. One row
per street number: units in one building share it, so only the first point of each (street, number) is kept."""
import json, os, sys, time, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_lib import RAW, CITY, get, vicmap_box

WFS = 'https://opendata.maps.vic.gov.au/geoserver/wfs'
rows, seen = [], set()
for f in vicmap_box('open-data-platform:address', CITY, props=['road_name', 'road_type', 'road_suffix', 'house_number_1']):
    p = f['properties']; n = p.get('house_number_1'); g = f.get('geometry')
    if not n or not p.get('road_name') or not g: continue
    st = ' '.join(x for x in (p['road_name'], p.get('road_type'), p.get('road_suffix')) if x)
    if (st, n) in seen: continue
    seen.add((st, n))
    c = g['coordinates']
    while isinstance(c[0], list): c = c[0]
    rows.append([st, int(n), round(c[0], 6), round(c[1], 6)])
json.dump({'fetched': time.strftime('%Y-%m-%d'), 'rows': rows}, open(os.path.join(RAW, 'addresses.json'), 'w'), separators=(',', ':'))
print('wrote addresses.json', len(rows), 'rows', os.path.getsize(os.path.join(RAW, 'addresses.json')) // 1000, 'KB')
