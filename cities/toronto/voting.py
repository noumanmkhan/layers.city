"""Build docs/toronto/data/voting.geojson: each election-day voting subdivision with its voting place.

Inputs (cities/toronto/fetch_voting.py, run daily in October by fetch-voting.yml):
  raw/voting/subdivisions.geojson  polygons, AREA_LONG_CODE = ward (2 digits) + subdivision (3)
  raw/voting/places.geojson        one point per subdivision, POINT_LONG_CODE the same code
  raw/voting/list.xlsx             optional: building names, entrances, accessibility notes
The points are edited more often than the spreadsheet (it is dated in its sheet name), so the
point's address wins; the spreadsheet's name and entrances are used only where its address agrees.
Advance voting places (subdivisions 98 and 99) are left out: advance voting ended October 11.
Output feature properties: c code, w ward, n building name (may be missing), a address,
e preferred entrance, ae accessible entrance when different, vat true where a Voter Assist Terminal
is set up, x/y the voting place. Top level: asof (the City's last edit to either layer, raw/voting/meta.json), election (city.json card.vote.date).
"""
import json, os, re, subprocess, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'voting')
TMP = os.path.join(HERE, 'tmp')
OUT = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'voting.geojson')
ROOT = os.path.join(HERE, '..', '..')


def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def key(a):
    # "137 McCaul St" vs "137 Mc Caul Street", "1 York Rd" vs "1 York Road": number plus 4 letters of the street.
    a = re.sub(r'[^a-z0-9]', '', clean(a).lower())
    m = re.match(r'(\d+)([a-z]{0,4})', a)
    return m.group(0) if m else a


def spreadsheet():
    path = os.path.join(RAW, 'list.xlsx')
    if not os.path.exists(path):
        return {}
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    out = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or not r[0] or not r[1]:
            continue
        w = str(r[0]).strip().zfill(2)
        s = re.sub(r'\D', '', str(r[1]).split()[0]).zfill(3)
        out[w + s] = {'name': clean(r[2]), 'addr': clean(r[3]), 'entrance': clean(r[4]), 'access': clean(r[5]),
                      'notes': clean(r[6]) + ' ' + clean(r[7])}
    return out


def main():
    cfg = json.load(open(os.path.join(HERE, 'city.json')))
    vote = cfg['card'].get('vote', {})
    subs = json.load(open(os.path.join(RAW, 'subdivisions.geojson')))
    places = {f['properties']['POINT_LONG_CODE']: f for f in json.load(open(os.path.join(RAW, 'places.geojson')))['features']}
    sheet = spreadsheet()
    feats, unnamed, sheet_used, moved = [], 0, 0, []
    for f in subs['features']:
        c = f['properties']['AREA_LONG_CODE']
        if c[2:] in ('098', '099') or not f.get('geometry'):
            continue
        p = places.get(c)
        if not p:
            print('no voting place for', c)
            continue
        pp = p['properties']
        x, y = p['geometry']['coordinates'] if p.get('geometry') else (pp['LONGITUDE'], pp['LATITUDE'])
        props = {'c': c, 'w': int(c[:2]), 'a': clean(pp.get('ADDRESS_FULL')), 'x': round(x, 6), 'y': round(y, 6)}
        name = clean(pp.get('POINT_NAME'))
        s = sheet.get(c)
        if s and key(s['addr']) == key(props['a']):
            sheet_used += 1
            name = name or s['name']
            if s['entrance'] and s['entrance'].lower() not in ('main doors', 'main door'):
                props['e'] = s['entrance']
            if s['access'] and not s['access'].lower().startswith('same as'):
                props['ae'] = s['access']
            if 'voter assist terminal' in s['notes'].lower():
                props['vat'] = True
        elif s:
            moved.append((c, s['addr'], props['a']))
        if name and name.lower() != props['a'].lower():
            props['n'] = re.sub(r'\s+', ' ', name)
        else:
            unnamed += 1
        feats.append({'type': 'Feature', 'properties': props, 'geometry': f['geometry']})
    print(f'subdivisions {len(feats)}, names/entrances from the list {sheet_used}, no building name {unnamed}')
    for m in moved:
        print('  moved since the list was published:', m)

    os.makedirs(TMP, exist_ok=True)
    tmp = os.path.join(TMP, 'voting.geojson')
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(tmp, 'w'))
    subprocess.run(['npx', 'mapshaper', '-i', tmp, '-simplify', 'interval=5', 'keep-shapes',
                    '-o', tmp + '.out', 'precision=0.00001', 'format=geojson', '-quiet'], check=True, cwd=ROOT)
    fc = json.load(open(tmp + '.out'))
    meta_path = os.path.join(RAW, 'meta.json')
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    asof = max([v for v in meta.values() if v] or [datetime.date.today().isoformat()])[:10]
    out = {'type': 'FeatureCollection', 'asof': asof, 'election': vote.get('date'), 'features': fc['features']}
    with open(OUT, 'w') as f:
        json.dump(out, f, separators=(',', ':'), ensure_ascii=False)
    print('wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    main()
