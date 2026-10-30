"""Build docs/sf/data/tech_hq.geojson for the Tech headquarters layer from cities/sf/tech_hq.json (the hand-kept list and
its rule) and raw/tech_geocoded.json (fetch_tech.py). One point per company: name, category, ticker (or "Private"),
address and city, year founded. Companies at one address (Reddit and DoorDash at 303 2nd Street) are nudged apart a
little so both pins can be tapped. Nothing about size, revenue or value is published."""
import json, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(HERE, 'tech_hq.json')))
geo = json.load(open(os.path.join(HERE, 'raw', 'tech_geocoded.json')))['places']
CAT = {'chips': 'Chips', 'hardware': 'Hardware', 'software': 'Software', 'internet': 'Internet and platforms', 'ai': 'AI'}
feats, seen = [], Counter()
for name, tick, cat, addr, city, year in cfg['companies']:
    g = geo.get(name)
    if not g: print('  not placed:', name); continue
    x, y = g['at']; k = (round(x, 4), round(y, 4)); n = seen[k]; seen[k] += 1
    p = {'name': name, 'cat': cat, 'sub': CAT[cat] + ' · ' + (tick or 'Private') + ' · ' + city, 'a': addr + ', ' + city}
    if year: p['y'] = str(year)
    feats.append({'type': 'Feature', 'properties': p, 'geometry': {'type': 'Point', 'coordinates': [round(x + n * 0.00012, 5), round(y, 5)]}})
json.dump({'type': 'FeatureCollection', 'asof': cfg['asof'], 'count': dict(Counter(f['properties']['cat'] for f in feats)), 'features': feats},
          open(os.path.join(HERE, '..', '..', 'docs', 'sf', 'data', 'tech_hq.geojson'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('tech HQs:', len(feats), dict(Counter(f['properties']['cat'] for f in feats)))
