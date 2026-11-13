"""Melbourne's Heritage buildings layer -> docs/melbourne/data/heritage_buildings.geojson (the shape Toronto's and
Chicago's use: n, a, id). Every place on the Victorian Heritage Register inside the City, from the Victorian Heritage
Database (Heritage Council of Victoria, CC BY 4.0; raw/more/heritage_places.json, fetch_more.py). The councils'
Heritage Overlay listings in the same database are left out: the Register is the state's list of places protected
one by one, as Toronto's designated and Chicago's landmark buildings are. Heritage Overlay precincts (the districts
Toronto shows) have no names in Vicmap's planning data, so they wait."""
import json, os, re
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'docs', 'melbourne', 'data')
CITY = prep(unary_union([shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(DATA, 'suburbs.geojson')))['features']]))
places = json.load(open(os.path.join(HERE, 'raw', 'more', 'heritage_places.json')))
SMALL = {'and', 'of', 'the', 'at', 'in', 'on', 'for', 'to', 'a'}


def title(s):
    """'ROYAL EXHIBITION BUILDING AND CARLTON GARDENS' -> 'Royal Exhibition Building and Carlton Gardens'."""
    w = s.strip().lower().split()
    out = ' '.join(x if (i and x in SMALL) else x[:1].upper() + x[1:] for i, x in enumerate(w))
    out = re.sub(r"\b(Mc|O')(\w)", lambda m: m.group(1) + m.group(2).upper(), out)
    return re.sub(r'\b(Ii|Iii|Iv|Vi)\b', lambda m: m.group(1).upper(), out)


feats, seen = [], set()
for p in places:
    if not p.get('vhr_number') or not p.get('latlon'): continue
    lat, lon = (float(v) for v in p['latlon'].split(','))
    if not CITY.contains(Point(lon, lat)) or p['vhr_number'] in seen: continue
    seen.add(p['vhr_number'])
    loc = re.sub(r',\s*MELBOURNE CITY$', '', p.get('location') or '')
    pr = {'n': title(p['name']), 'a': title(loc), 'b': p['vhr_number'], 'id': p['vhr_number']}
    if p.get('url'): pr['u'] = p['url'].replace('http://', 'https://')
    feats.append({'type': 'Feature', 'properties': pr, 'geometry': {'type': 'Point', 'coordinates': [round(lon, 5), round(lat, 5)]}})
json.dump({'type': 'FeatureCollection', 'asof': None, 'features': feats}, open(os.path.join(DATA, 'heritage_buildings.geojson'), 'w'),
          separators=(',', ':'), ensure_ascii=False)
print('heritage buildings:', len(feats), [f['properties']['n'] for f in feats[:6]])
