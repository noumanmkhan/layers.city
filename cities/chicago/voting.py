"""Build docs/chicago/data/voting.geojson: Chicago's election precincts for the card's election box.

Input: raw/precincts.geojson (fetch_precincts.py: City Data Portal i8fv-xe4b, the precincts approved
December 9, 2025). The Board of Election Commissioners publishes no precinct-to-polling-place list, so
features carry no voting place: c code (ward 2 digits + precinct 3), w ward, p precinct. The engine then
names the precinct and links to the Board's lookup (city.json card.vote).
Top level: asof (the layout's approval date), election (card.vote.date).
"""
import json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
TMP = os.path.join(HERE, 'tmp')
OUT = os.path.join(ROOT, 'docs', 'chicago', 'data', 'voting.geojson')


def main():
    cfg = json.load(open(os.path.join(HERE, 'city.json')))
    src = json.load(open(os.path.join(HERE, 'raw', 'precincts.geojson')))
    feats = []
    for f in src['features']:
        p = f['properties']
        w, n = int(float(p['ward'])), int(float(p['precinct']))
        feats.append({'type': 'Feature', 'properties': {'c': f'{w:02d}{n:03d}', 'w': w, 'p': n}, 'geometry': f['geometry']})
    os.makedirs(TMP, exist_ok=True)
    tmp = os.path.join(TMP, 'voting.geojson')
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(tmp, 'w'))
    subprocess.run(['npx', 'mapshaper', '-i', tmp, '-simplify', 'interval=5', 'keep-shapes',
                    '-o', tmp + '.out', 'precision=0.00001', 'format=geojson', '-quiet'], check=True, cwd=ROOT)
    fc = json.load(open(tmp + '.out'))
    out = {'type': 'FeatureCollection', 'asof': '2025-12-09', 'election': cfg['card'].get('vote', {}).get('date'), 'features': fc['features']}
    with open(OUT, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print('precincts', len(feats), 'wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    main()
