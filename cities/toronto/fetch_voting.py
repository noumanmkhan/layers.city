"""Fetch the City's voting subdivisions and voting places for the next municipal election.

Runs in GitHub Actions (fetch-voting.yml); the sandbox can't reach these hosts.
Sources (linked from toronto.ca/city-government/elections/city-elections/voting-places/):
  - Voting subdivisions (polygons): COTGEO_VOTING_SUBDIVISION on the City's ArcGIS Online.
  - Voting places (points): COTGEO_VOTING_LOCATION, same host. POINT_LONG_CODE = ward (2) + subdivision (3),
    the same code as the subdivision's AREA_LONG_CODE.
  - The List of Voting Places (All Wards) spreadsheet from the same page: building names, entrances and
    accessibility notes, keyed by ward and subdivision. Optional; the points carry names and addresses too.
Writes raw/voting/subdivisions.geojson, places.geojson, list.xlsx (when found) and prints a summary.
The data can change up to election day, so the workflow runs daily until then.
"""
import json, os, re, sys, time, urllib.request, urllib.parse
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'voting')
BASE = 'https://services3.arcgis.com/b9WvedVPoizGfvfD/ArcGIS/rest/services/{}/FeatureServer/0/query'
PAGE = 'https://www.toronto.ca/city-government/elections/city-elections/voting-places/'
UA = {'User-Agent': 'layers.city map (github.com/noumanmkhan/city-layers)'}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception as e:
            print('  retry', i + 1, url[:100], e)
            time.sleep(5 * (i + 1))
    raise SystemExit('failed: ' + url)


def layer(service):
    feats, off = [], 0
    while True:
        q = urllib.parse.urlencode({'where': '1=1', 'outFields': '*', 'outSR': 4326, 'f': 'geojson',
                                    'resultOffset': off, 'resultRecordCount': 1000, 'orderByFields': 'OBJECTID'})
        page = json.loads(get(BASE.format(service) + '?' + q))
        fs = page.get('features', [])
        feats += fs
        print(f'  {service}: {len(feats)}')
        if not fs or not (page.get('exceededTransferLimit') or page.get('properties', {}).get('exceededTransferLimit')) and len(fs) < 1000:
            break
        off += len(fs)
    return {'type': 'FeatureCollection', 'features': feats}


def main():
    os.makedirs(OUT, exist_ok=True)
    subs = layer('COTGEO_VOTING_SUBDIVISION')
    places = layer('COTGEO_VOTING_LOCATION')
    for name, fc in (('subdivisions', subs), ('places', places)):
        with open(os.path.join(OUT, name + '.geojson'), 'w') as f:
            json.dump(fc, f, separators=(',', ':'))

    # The spreadsheet: its file name changes with each update ("…All-Wards-List-as-of-Sept-30…").
    try:
        html = get(PAGE).decode('utf-8', 'replace')
        m = re.search(r'href="([^"]+All-Wards[^"]*\.xlsx)"', html)
        if m:
            with open(os.path.join(OUT, 'list.xlsx'), 'wb') as f:
                f.write(get(m.group(1)))
            with open(os.path.join(OUT, 'list_url.txt'), 'w') as f:
                f.write(m.group(1) + '\n')
            print('list:', m.group(1))
        else:
            print('list: no All Wards link found on the page')
    except SystemExit as e:
        print('list: skipped,', e)

    # Summary for the log.
    sp = [f['properties'] for f in subs['features']]
    pp = [f['properties'] for f in places['features']]
    print('subdivisions', len(sp), Counter(p.get('AREA_TYPE') for p in sp))
    print('places', len(pp), Counter(p.get('FEATURE_CODE_DESC') for p in pp), Counter(p.get('POINT_TYPE') for p in pp))
    sc = Counter(p['AREA_LONG_CODE'] for p in sp)
    pc = Counter(p['POINT_LONG_CODE'] for p in pp)
    print('subdivision codes repeated:', sum(1 for v in sc.values() if v > 1), 'place codes repeated:', sum(1 for v in pc.values() if v > 1))
    print('subdivisions without a place of the same code:', len(set(sc) - set(pc)), sorted(set(sc) - set(pc))[:30])
    print('places without a subdivision of the same code:', len(set(pc) - set(sc)), sorted(set(pc) - set(sc))[:30])
    print('places with no name:', sum(1 for p in pp if not p.get('POINT_NAME')))
    addr = Counter(p.get('ADDRESS_FULL') for p in pp)
    print('addresses serving 2+ codes:', sum(1 for v in addr.values() if v > 1))
    for p in pp[:12]:
        print('  sample', {k: p.get(k) for k in ('POINT_LONG_CODE', 'FEATURE_CODE_DESC', 'POINT_NAME', 'ADDRESS_FULL', 'VOTER_COUNT')})
    for p in [p for p in pp if p.get('FEATURE_CODE_DESC') == 'Secondary'][:12]:
        print('  secondary', {k: p.get(k) for k in ('POINT_LONG_CODE', 'POINT_NAME', 'ADDRESS_FULL', 'POINT_DESC', 'REF_FEATURE_ID_TAB', 'VOTER_COUNT')})
    for p in sp[:3]:
        print('  sub', {k: p.get(k) for k in ('AREA_LONG_CODE', 'AREA_NAME', 'AREA_DESC', 'PARENT_AREA_ID', 'VOTER_COUNT')})


if __name__ == '__main__':
    main()
