"""Toronto's publicly funded schools for the Schools toggle in Education.
Inputs: raw/schools/ontario_schools.csv (fetch_schools.py: the Ministry of Education's school list, Ontario Data
Catalogue, Open Government Licence - Ontario) and french_schools.csv (the curated immersion and French-language list).
Output: docs/toronto/data/schools.geojson, one point per school:
  name, cat ("elementary" or "secondary", the Ministry's school level), grp ("fr" French-language board,
  "imm" French immersion, else none), sub ("TDSB · JK–8" and the immersion program), g (grade range),
  b (board short name), a (street address), u (the school's website, when listed).

The rules (decided October 18, 2026):
- Schools of the four Toronto boards (TDSB, TCDSB, Viamonde, MonAvenir) inside the City; no private schools, and no
  hospital or provincial schools. Describe only: name, board, level, grades. Never test results or enrolment.
- No attendance areas: the nearest school is often not the one a home is zoned for, so the map shows where schools
  are and never says which one a home goes to.
- French-language schools are those the Ministry lists in French. Immersion comes from the curated list (the boards'
  own 2026-27 location lists), matched by board and street address, then by name.
"""
import csv, json, os, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'schools')
OUT = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'schools.geojson')
BOARD = {'Toronto DSB': 'TDSB', 'Toronto CDSB': 'TCDSB', 'CS Viamonde': 'Viamonde', 'CS catholique MonAvenir': 'MonAvenir'}
ABBR = {'avenue': 'ave', 'street': 'st', 'road': 'rd', 'drive': 'dr', 'boulevard': 'blvd', 'crescent': 'cres', 'court': 'crt',
        'place': 'pl', 'square': 'sq', 'parkway': 'pkwy', 'circle': 'crcl', 'gardens': 'gdns', 'terrace': 'terr', 'east': 'e',
        'west': 'w', 'north': 'n', 'south': 's', 'trail': 'trl', 'heights': 'hts', 'lane': 'lane', 'grove': 'grv', 'circuit': 'crct', 'circt': 'crct', 'crct': 'crct'}


def fold(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9 ]+', ' ', s)


def addr(s):
    return ' '.join(ABBR.get(w, w) for w in fold(s).split())


def name_key(s):
    drop = {'public', 'school', 'catholic', 'elementary', 'secondary', 'jr', 'sr', 'junior', 'senior', 'middle', 'collegiate',
            'institute', 'ps', 'ecole', 'the', 'st', 'saint', 'of', 'and', 'academy'}
    return ' '.join(w for w in fold(s).split() if w not in drop)


def tidy(n):
    """The Ministry's names are mostly in title case already; fix shouting and stray spaces."""
    n = re.sub(r'\s+', ' ', n).strip()
    return n.title() if n.isupper() else n


rows = [r for r in csv.DictReader(open(os.path.join(RAW, 'ontario_schools.csv'), encoding='utf-8'))
        if r['Municipality'] == 'Toronto, City of' and r['Board Name'] in BOARD]
meta = json.load(open(os.path.join(RAW, 'ontario_schools.meta.json')))

# French immersion, from the curated list.
imm = [r for r in csv.DictReader(open(os.path.join(HERE, 'french_schools.csv'), encoding='utf-8')) if r['cat'] == 'immersion']
by_addr = {}
for r in rows: by_addr.setdefault((BOARD[r['Board Name']], addr(r['Street'])), []).append(r)
prog = {}
unmatched = []
for c in imm:
    cands = by_addr.get((c['board'], addr(c['city_address'])), [])
    if len(cands) > 1: cands = [r for r in cands if r['School Level'].lower() == c['level']] or cands
    if len(cands) > 1:   # schools sharing a building: the one whose name matches
        first = (name_key(c['name']) or name_key(c['city_name'])).split()[:1]
        cands = [r for r in cands if name_key(r['School Name']).split()[:1] == first] or cands
    if not cands:
        keys = {name_key(c['city_name']), name_key(c['name'])} - {''}
        cands = [r for r in rows if BOARD[r['Board Name']] == c['board'] and name_key(r['School Name']) in keys]
    if len(cands) == 1: prog[cands[0]['School Number']] = c['program'] or 'Immersion'
    else: unmatched.append((c['name'], c['city_address'], len(cands)))

PROGRAM = {'Early': 'early immersion', 'Middle': 'middle immersion', 'Early & Middle': 'early and middle immersion',
           'Immersion from JK': 'immersion from JK', 'Immersion': 'French immersion'}
feats, seen = [], {}
for r in sorted(rows, key=lambda r: r['School Name']):
    b, lvl = BOARD[r['Board Name']], r['School Level'].lower()
    grades = r['Grade Range'].replace('-', '–')
    grp = 'fr' if r['School Language'] == 'French' else ('imm' if r['School Number'] in prog else None)
    # Secondary schools continue the elementary streams, so they read as one program (as french_schools.py had it).
    pname = ('secondary immersion' if lvl == 'secondary' else PROGRAM.get(prog[r['School Number']], 'French immersion')) if grp == 'imm' else ''
    sub = b + ' · ' + grades + (' · ' + pname if pname else '')
    special = r.get('School Special Condition Code', '')
    if special in ('Alternative', 'Adult', 'Vocational/Occupational'): sub += ' · ' + special.lower().replace('/', ' or ')
    x, y = round(float(r['Longitude']), 5), round(float(r['Latitude']), 5)
    n = seen.get((x, y), 0); seen[(x, y)] = n + 1
    if n: x = round(x + 0.00012 * n, 5)   # schools sharing a building: nudged apart so each shows
    p = {'name': tidy(r['School Name']), 'cat': lvl, 'sub': sub, 'g': grades, 'b': b, 'a': tidy(r['Street'])}
    if grp: p['grp'] = grp
    w = (r.get('School Website') or '').strip()
    if re.match(r'https?://', w): p['u'] = w
    feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [x, y]}, 'properties': p})

count = {k: sum(1 for f in feats if f['properties']['cat'] == k) for k in ('elementary', 'secondary')}
count.update({k: sum(1 for f in feats if f['properties'].get('grp') == k) for k in ('fr', 'imm')})
json.dump({'type': 'FeatureCollection', 'asof': meta.get('data_range_start', '')[:4] + '–' + meta.get('data_range_end', '')[2:4],
           'count': count, 'features': feats}, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
print('schools:', len(feats), count, {b: sum(1 for f in feats if f['properties']['b'] == b) for b in BOARD.values()})
print('immersion not matched:', unmatched)
