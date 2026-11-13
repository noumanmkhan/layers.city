"""Melbourne's public car parks -> docs/melbourne/data/parking.geojson (the shape Toronto's Green P layer reads: c "gp").
The City of Melbourne's Census of Land Use and Employment counts every off-street car park; its "Commercial" ones
are the car parks open to the public for a fee (residential and private staff car parks are left out). One point
per car park, from the latest census year (raw/more/off-street-car-parks-with-capacity-and-type.geojson, fetch_more.py;
CC BY 4.0). The census doesn't say which are garages and which open-air lots, so every one shows as a garage."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'docs', 'melbourne', 'data')
src = json.load(open(os.path.join(HERE, 'raw', 'more', 'off-street-car-parks-with-capacity-and-type.geojson')))['features']
feats, year, spaces = [], None, 0
for f in src:
    p = f['properties']
    if p.get('parking_type') != 'Commercial' or not p.get('parking_spaces') or p.get('longitude') is None: continue
    year = p['census_year']
    a = re.sub(r'\s+[A-Z][A-Z ]+\s+VIC\s+\d{4}$', '', p.get('building_address') or '').strip()
    feats.append({'type': 'Feature', 'properties': {'c': 'gp', 'n': a, 't': 'g', 'cap': int(p['parking_spaces']), 'id': p['property_id']},
                  'geometry': {'type': 'Point', 'coordinates': [round(float(p['longitude']), 5), round(float(p['latitude']), 5)]}})
    spaces += int(p['parking_spaces'])
json.dump({'type': 'FeatureCollection', 'asof': {'gp': f'{year}-12-31' if year else None}, 'count': {'greenp': len(feats), 'spaces': spaces},
           'features': feats}, open(os.path.join(DATA, 'parking.geojson'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('parking:', len(feats), 'car parks,', spaces, 'spaces, census', year)
