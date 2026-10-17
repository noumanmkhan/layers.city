"""Libraries and community centres as map points: the same places the card's Nearby section names, from the
groups each city's nearby.py builds -> docs/<city>/data/community.geojson

  Point features, properties: name, cat ("library" or "centre"). Top level: count {library, centre}.

Called at the end of cities/<city>/nearby.py; run by hand as `python3 engine/community.py <city>` to rebuild it
from the published nearby.json."""
import json, os, sys

CATS = ('library', 'centre')


def write(data_dir, groups):
    feats = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': p[:2]}, 'properties': {'name': p[2], 'cat': cat}}
             for cat in CATS for p in sorted(groups.get(cat, []), key=lambda p: p[2]) if len(p) > 2]
    out = {'type': 'FeatureCollection', 'count': {c: sum(1 for f in feats if f['properties']['cat'] == c) for c in CATS}, 'features': feats}
    json.dump(out, open(os.path.join(data_dir, 'community.geojson'), 'w'), ensure_ascii=False, separators=(',', ':'))
    print('community:', out['count'])


if __name__ == '__main__':
    data = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', sys.argv[1], 'data')
    write(data, json.load(open(os.path.join(data, 'nearby.json')))['groups'])
