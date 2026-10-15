"""Build docs/dallas/data/voting.geojson: where people vote on November 3, 2026, for the card's election box.

Input: raw/voting/centers.json and raw/voting/denton_precincts.geojson (fetch_voting.py), raw/counties.geojson.
Dallas, Tarrant and Collin counties run countywide vote centers, so each county is one area (k: county key) and
the box lists the vote centers nearest the spot in that county. Denton County assigns an election day polling
place by precinct: each precinct is an area (k: denton, c: precinct) carrying its place (n name, a address,
r room, x/y), as Toronto's voting subdivisions do.
Top level: asof (the fetch date), election, counts per county, and centers: [x, y, name, room, address, county, kind]
with kind 1 = election day, 2 = early voting, 3 = both.
"""
import json, os, re, subprocess
from shapely.geometry import shape, mapping

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
R = os.path.join(HERE, 'raw')
TMP = os.path.join(HERE, 'tmp')
OUT = os.path.join(ROOT, 'docs', 'dallas', 'data', 'voting.geojson')
CENTERS = ['Dallas', 'Tarrant', 'Collin']


def main():
    src = json.load(open(os.path.join(R, 'voting', 'centers.json')))
    counties = {f['properties']['NAME']: f['geometry'] for f in json.load(open(os.path.join(R, 'counties.geojson')))['features']}
    feats = [{'type': 'Feature', 'properties': {'k': c.lower()}, 'geometry': counties[c]} for c in CENTERS]
    cs = src['centers']
    for c in cs:   # "St Paul'S Church" in a source's title case
        for k in ('name', 'room', 'address'): c[k] = re.sub(r"(\w)'S\b", r"\1's", c[k] or '')
    for f in json.load(open(os.path.join(R, 'voting', 'denton_precincts.geojson')))['features']:
        pc = str(f['properties']['PRECINCT_N'])
        p = {'k': 'denton', 'c': pc}
        i = src['denton'].get(pc)
        if i is not None:
            c = cs[i]
            p.update({'n': c['name'], 'a': c['address'] + ', ' + c['city'], 'r': c['room'], 'x': c['x'], 'y': c['y']})
        feats.append({'type': 'Feature', 'properties': p, 'geometry': f['geometry']})
    os.makedirs(TMP, exist_ok=True)
    tmp = os.path.join(TMP, 'voting.geojson')
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(tmp, 'w'))
    subprocess.run(['npx', 'mapshaper', '-i', tmp, '-simplify', 'interval=8', 'keep-shapes',
                    '-o', tmp + '.out', 'precision=0.00001', 'format=geojson', '-quiet'], check=True, cwd=ROOT)
    out = json.load(open(tmp + '.out'))
    centers = [[c['x'], c['y'], c['name'], c['room'], c['address'] + (', ' + c['city'] if c['city'] else ''), c['k'], (1 if c['ed'] else 0) + (2 if c['ev'] else 0)]
               for c in cs if c['x'] is not None]
    counts = {k: {'ed': sum(1 for c in cs if c['k'] == k and c['ed']), 'ev': sum(1 for c in cs if c['k'] == k and c['ev'])} for k in src['counties']}
    res = {'type': 'FeatureCollection', 'asof': src['asof'], 'election': src['election'], 'counts': counts, 'centers': centers, 'features': out['features']}
    with open(OUT, 'w') as f:
        json.dump(res, f, separators=(',', ':'))
    print('areas', len(feats), '· centers', len(centers), counts, '· wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    main()
