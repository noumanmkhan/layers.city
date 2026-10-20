"""Build docs/chicago/data/voting.geojson: Chicago's election precincts and vote centers for the card's election box.

Inputs: raw/precincts.geojson (fetch_precincts.py: City Data Portal i8fv-xe4b, the precincts approved
December 9, 2025) and, when present, raw/vote_centers/centers.json (fetch_vote_centers.py: the Board of
Election Commissioners' early voting / vote center sites).
The Board publishes no precinct-to-polling-place list (its lookup needs a voter's name), but any Chicago voter
can vote at any of its vote centers: the 50 ward sites and two downtown sites during early voting, and the
50 ward sites and the downtown SuperSite on election day. So each precinct is an area of the county "chicago"
(k), and the box lists the nearest centers (engine: card.vote.counties) and names the precinct.
Features: c code (ward 2 digits + precinct 3), w ward, p precinct, k "chicago" (only with centers).
Top level: asof (the centers' fetch date; without centers, the precincts' approval date), election,
counts {chicago: {ed, ev}}, centers [x, y, name, room, address, county, kind] (kind 1 election day,
2 early voting, 3 both).
"""
import json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
TMP = os.path.join(HERE, 'tmp')
OUT = os.path.join(ROOT, 'docs', 'chicago', 'data', 'voting.geojson')
CENTERS = os.path.join(HERE, 'raw', 'vote_centers', 'centers.json')


def main():
    cfg = json.load(open(os.path.join(HERE, 'city.json')))
    src = json.load(open(os.path.join(HERE, 'raw', 'precincts.geojson')))
    cs = json.load(open(CENTERS)) if os.path.exists(CENTERS) else None
    feats = []
    for f in src['features']:
        p = f['properties']
        w, n = int(float(p['ward'])), int(float(p['precinct']))
        props = {'c': f'{w:02d}{n:03d}', 'w': w, 'p': n}
        if cs:
            props['k'] = 'chicago'
        feats.append({'type': 'Feature', 'properties': props, 'geometry': f['geometry']})
    os.makedirs(TMP, exist_ok=True)
    tmp = os.path.join(TMP, 'voting.geojson')
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(tmp, 'w'))
    subprocess.run(['npx', 'mapshaper', '-i', tmp, '-simplify', 'interval=5', 'keep-shapes',
                    '-o', tmp + '.out', 'precision=0.00001', 'format=geojson', '-quiet'], check=True, cwd=ROOT)
    fc = json.load(open(tmp + '.out'))
    out = {'type': 'FeatureCollection', 'asof': '2025-12-09', 'election': cfg['card'].get('vote', {}).get('date')}
    if cs:
        placed = [c for c in cs['centers'] if c.get('x') is not None]
        for c in cs['centers']:
            if c.get('x') is None:
                print('not placed, left out:', c['name'], c['address'])
        out['asof'] = cs['asof']
        out['centers'] = [[c['x'], c['y'], c['name'], c.get('room') or '', c['address'], 'chicago',
                           (1 if c['ed'] else 0) + (2 if c['ev'] else 0)] for c in placed]
        out['counts'] = {'chicago': {'ed': sum(1 for c in placed if c['ed']), 'ev': sum(1 for c in placed if c['ev'])}}
    out['features'] = fc['features']
    with open(OUT, 'w') as f:
        json.dump(out, f, separators=(',', ':'), ensure_ascii=False)
    print('precincts', len(feats), '· centers', len(out.get('centers', [])), out.get('counts'), '· wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    main()
