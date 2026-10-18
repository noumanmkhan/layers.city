"""Build docs/nyc/data/voting.geojson: where people vote in the November 3, 2026 general election, for the card's
election box. New York assigns every election district (ED) both an election day poll site and an early voting site.

Inputs (fetch_voting.py): raw/voting/election_districts.geojson (the EDs), raw/voting/pdf/ (the Board of Elections'
poll site lists, election day and early voting, one per borough: ED by ED, site name and address) and
raw/voting/nys_ed.json, nys_ev.json (the State GIS office's points for the same sites, to place them).
Sites are matched to the State's points by street address within the borough; raw/voting/places.json holds hand
positions for any the State's file lacks.

Each ED feature: c "AD-ED" (23-001), s the election day site and e the early voting site, as indexes into the top-level
sites list: [name (as the State writes it, else the Board's), address, x, y] (no x, y when unplaced). The page expands
them to n/a/x/y and en/ea/ex/ey when it loads the file. Top level: asof, election, sites."""
import glob, json, os, re, subprocess, datetime
from collections import Counter
import pypdf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
V = os.path.join(HERE, 'raw', 'voting')
TMP = os.path.join(HERE, 'tmp')
OUT = os.path.join(ROOT, 'docs', 'nyc', 'data', 'voting.geojson')
BORO = {'New_York': 'New York', 'Bronx': 'Bronx', 'Kings': 'Kings', 'Queens': 'Queens', 'Richmond': 'Richmond'}
COUNTY = {'Manhattan': 'New York', 'New York': 'New York', 'Bronx': 'Bronx', 'Brooklyn': 'Kings', 'Kings': 'Kings', 'Queens': 'Queens',
          'Staten Island': 'Richmond', 'Richmond': 'Richmond'}
ABBR = [('STREET', 'ST'), ('AVENUE', 'AVE'), ('AV', 'AVE'), ('BOULEVARD', 'BLVD'), ('ROAD', 'RD'), ('PLACE', 'PL'), ('PARKWAY', 'PKWY'),
        ('DRIVE', 'DR'), ('TERRACE', 'TER'), ('LANE', 'LN'), ('COURT', 'CT'), ('HIGHWAY', 'HWY'), ('TURNPIKE', 'TPKE'), ('EXPRESSWAY', 'EXPY'),
        ('EAST', 'E'), ('WEST', 'W'), ('NORTH', 'N'), ('SOUTH', 'S'), ('SAINT', 'ST'), ('CONCOURSE', 'CONC'), ('PLAZA', 'PLZ'), ('SQUARE', 'SQ')]


def key(addr):
    a = re.sub(r'[^A-Z0-9 -]', ' ', addr.upper())
    a = re.sub(r'(\d+)(ST|ND|RD|TH)\b', r'\1', a)
    w = [dict(ABBR).get(x, x) for x in a.split()]
    return ' '.join(w)


def lists(kind):
    out = {}
    for f in sorted(glob.glob(os.path.join(V, 'pdf', f'*{kind}*.pdf'))):
        boro = next(v for k, v in BORO.items() if '_' + k in f)
        ad = None
        for page in pypdf.PdfReader(f).pages:
            for line in page.extract_text().splitlines():
                m = re.match(r'\s*(\d{1,2})(st|nd|rd|th) Assembly District', line)
                if m: ad = int(m.group(1)); continue
                m = re.match(r'\s*(\d{3})\s+(.+?)\s*\.{2,}\s*(.+?)\s*$', line)
                if m and ad: out['%d%s' % (ad, m.group(1))] = (boro, m.group(2).strip(), m.group(3).strip())
    return out


def points(name):
    pts = {}
    for f in json.load(open(os.path.join(V, name)))['features']:
        p = f['properties']
        pts.setdefault((COUNTY.get(p['County'], p['County']), key(p['Poll_Site_Address'])), (p['Poll_Site_Name'].strip(), f['geometry']['coordinates']))
    return pts


import difflib
_by_num = {}
POINTS = {}


def fuzzy(boro, addr):
    """Same borough, same house number, the closest street name (the Board abbreviates: FT, QNS, LEX, BWAY...)."""
    if not _by_num:
        for kind in ('ed', 'ev'):
            for (b, k), v in POINTS[kind].items():
                num = k.split()[0] if k.split() else ''
                _by_num.setdefault((b, num), []).append((k, v))
    k = key(addr); num = k.split()[0] if k.split() else ''
    cands = _by_num.get((boro, num), [])
    if not cands: return None
    best = max(cands, key=lambda c: difflib.SequenceMatcher(None, k, c[0]).ratio())
    if difflib.SequenceMatcher(None, k, best[0]).ratio() <= 0.55: return None
    return best[1]


def same_site(name, other):
    """At least one word of three letters or more in common (PS 6 isn't Vollies Memorial Hall)."""
    w = lambda t: {x for x in re.sub(r'[^A-Z0-9 ]', ' ', t.upper()).split() if len(x) >= 3}
    return bool(w(name) & w(other))


def nice(s):
    """The Board's capitals in title case, keeping PS/IS/MS/HS, NYCHA and the like."""
    keep = {'PS', 'IS', 'MS', 'HS', 'JHS', 'NYCHA', 'YMCA', 'YWCA', 'CUNY', 'SUNY', 'NYPL', 'BPL', 'QPL', 'CC', 'II', 'III', 'IV', 'SCO', 'LGBT', 'NYC', 'BKLYN'}
    return ' '.join(w if w in keep or re.match(r'^\d', w) else w.capitalize() for w in s.split())


def main():
    # Hand positions for sites the State's points miss: {"<county>|<the Board's address>": {"xy": [lon, lat], "a": the
    # building's correct address, when the Board's list has it wrong}}, from the State's address geocoder.
    hand = json.load(open(os.path.join(V, 'places.json'))) if os.path.exists(os.path.join(V, 'places.json')) else {}
    ed, ev = lists('Election_Day'), lists('Early_Voting')
    P = {'ed': points('nys_ed.json'), 'ev': points('nys_ev.json')}
    POINTS.update(P)
    miss = Counter()

    def place(kind, row):
        boro, name, addr = row
        hit = P[kind].get((boro, key(addr))) or P['ed' if kind == 'ev' else 'ev'].get((boro, key(addr))) or (lambda h: h if h and same_site(name, h[0]) else None)(fuzzy(boro, addr))
        h = hand.get(boro + '|' + addr)
        if h: return nice(name) if not hit else hit[0], h.get('a') or nice(addr), h['xy']
        if not hit:
            miss[(kind, boro, name, addr)] += 1
            return nice(name), nice(addr), None
        return hit[0], nice(addr), hit[1]

    feats, sites, idx = [], [], {}

    def site(n, a, xy):
        k = (n, a, tuple(xy) if xy else None)
        if k not in idx:
            idx[k] = len(sites)
            sites.append([n, a] + ([round(xy[0], 6), round(xy[1], 6)] if xy else []))
        return idx[k]

    for f in json.load(open(os.path.join(V, 'election_districts.geojson')))['features']:
        c = str(f['properties']['elect_dist'])
        p = {'c': '%s-%s' % (c[:-3], c[-3:])}
        if c in ed: p['s'] = site(*place('ed', ed[c]))
        if c in ev: p['e'] = site(*place('ev', ev[c]))
        feats.append({'type': 'Feature', 'properties': p, 'geometry': f['geometry']})
    os.makedirs(TMP, exist_ok=True)
    tmp = os.path.join(TMP, 'voting.geojson')
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(tmp, 'w'))
    subprocess.run(['npx', 'mapshaper', '-i', tmp, '-simplify', 'interval=14', 'keep-shapes', '-o', tmp + '.out',
                    'precision=0.00001', 'format=geojson', '-quiet'], check=True, cwd=ROOT)
    out = json.load(open(tmp + '.out'))
    asof = datetime.date.fromtimestamp(max(os.path.getmtime(f) for f in glob.glob(os.path.join(V, 'pdf', '*.pdf')))).isoformat()
    meta = os.path.join(V, 'asof.txt')
    if os.path.exists(meta): asof = open(meta).read().strip()
    json.dump({'type': 'FeatureCollection', 'asof': asof, 'election': '2026-11-03', 'sites': sites, 'features': out['features']}, open(OUT, 'w'), separators=(',', ':'))
    placed = sum(1 for f in feats if len(sites[f['properties'].get('s', 0)]) > 2); eplaced = sum(1 for f in feats if 'e' in f['properties'] and len(sites[f['properties']['e']]) > 2)
    print('EDs', len(feats), '· election day site placed', placed, '· early site placed', eplaced, '· unplaced sites', len(miss))
    for (k, b, n, a), cnt in sorted(miss.items(), key=lambda x: -x[1])[:40]: print('  ', k, b, n, '|', a, '·', cnt, 'EDs')
    print('wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    main()
