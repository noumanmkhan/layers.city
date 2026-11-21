"""Cameras: red light cameras and the former speed camera (ASE) sites -> docs/toronto/data/cameras/.

Reads what fetch_cameras.py wrote to raw/cameras/ (stdlib only, so run.sh needs nothing new):
  rlc_locations.geojson, rlc_charges.json   red light cameras and their charges by year
  ase_locations.json, ase_charges.json      ASE location snapshots (2022, March 2025, final) and charges by month
  centreline.json                           Toronto Centreline segments of the streets the camera texts name
  sources.json                              each package's refresh date, resources and licence
Writes:
  rlc.json   one point per red light camera (current and retired), tickets by year
  ase.json   one point per former ASE site, its periods and tickets
  meta.json  years, sources, licence, the fine amounts used and their dates

Words: the source counts charges (tickets), not drivers, and not dollars. The fine figures in meta.json are
set amounts from toronto.ca, for estimates only. Retired cameras and the ASE sites that have no point in any
published location file are placed from their text (intersection, side, house number) and marked approximate."""
import csv, json, math, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'cameras')
OUT = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'cameras')

# ---------- street names ----------
ABBR = {'street': 'st', 'avenue': 'ave', 'road': 'rd', 'drive': 'dr', 'boulevard': 'blvd', 'crescent': 'cres', 'court': 'crt',
        'circle': 'crcl', 'circuit': 'crct', 'gate': 'gt', 'place': 'pl', 'square': 'sq', 'parkway': 'pkwy', 'terrace': 'ter',
        'trail': 'trl', 'lane': 'lane', 'line': 'line', 'way': 'way', 'grove': 'grv', 'heights': 'hts', 'gardens': 'gdns',
        'circ': 'crcl', 'cir': 'crcl', 'crt': 'crt', 'ct': 'crt', 'trl': 'trl', 'hwy': 'highway', 'pk': 'park',
        'east': 'e', 'west': 'w', 'north': 'n', 'south': 's', 'mount': 'mount', 'saint': 'st'}
DIRS = {'e', 'w', 'n', 's'}
# Spellings in the ASE charges file that the centreline spells otherwise.
TYPO = {'tonybee': 'toynbee', 'bevridge': 'beveridge'}


def snorm(s):
    """'Queen St. W.' -> 'queen st w'; "O'Connor Dr." -> 'o connor dr'; "St. Olave's Rd." -> 'st olaves rd'."""
    s = (s or '').lower().replace('’', "'")
    s = re.sub(r"'s\b", 's', s).replace("'", ' ').replace('.', ' ').replace('-', ' ')
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    s = re.sub(r'\bmc ', 'mc', s)   # the centreline writes "Mc Alpine St"
    return ' '.join(TYPO.get(w, ABBR.get(w, w)) for w in s.split())


def base(n):
    """Drop a trailing direction: 'queen st w' -> 'queen st'."""
    w = n.split()
    return ' '.join(w[:-1]) if len(w) > 1 and w[-1] in DIRS else n


def bare(n):
    """Name only, no type or direction: 'queen st w' -> 'queen'."""
    w = base(n).split()
    return ' '.join(w[:-1]) if len(w) > 1 else n


REL = re.compile(r'^(.*?)\s+(north|south|east|west|near)\s+(?:of\s+)?(.*)$', re.I)


def parse_site(text):
    """An ASE site's text -> (main street, relation, cross street or None, house number or None)."""
    t = re.sub(r'\s+', ' ', text).strip().rstrip('*').strip()
    m = REL.match(t)
    if not m:
        return t, None, None, None
    main, rel, rest = m.group(1), m.group(2).lower(), m.group(3)
    num = re.match(r'^#?(\d+)\s+(.*)$', rest)
    if num:   # "Near 295 Alton Towers Circle": a house number on the main street
        return main, 'addr', num.group(2), int(num.group(1))
    return main, rel, rest, None


def parse_pair(text):
    """A red light camera's text ('Albion Rd. and Finch Ave.*', 'Dundas St. 275 M N of Royal York Rd.') -> (main, cross)."""
    t = re.sub(r'\s+', ' ', text).strip().rstrip('*').strip()
    m = re.match(r'^(.*?)\s+\d+\s*m\s+[nsew]\s+of\s+(.*)$', t, re.I)
    if m:
        return m.group(1), m.group(2)
    a, _, b = t.partition(' and ')
    return a, b.split(' / ')[0]


def wanted_streets(ase_texts, rlc_texts):
    """Every street name the texts mention, normalised to its bare name (for fetch_cameras.py to keep)."""
    out = set()
    for t in ase_texts:
        main, rel, cross, _ = parse_site(t)
        out.add(bare(snorm(main)))
        if cross:
            out.add(bare(snorm(cross)))
    for t in rlc_texts:
        a, b = parse_pair(t)
        out.update({bare(snorm(a)), bare(snorm(b))})
    out.discard('')
    return out


# ---------- geometry ----------
def metres(a, b):
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * 111320 * k, (a[1] - b[1]) * 111320)


def along(coords, d):
    """The point d metres along a line from its first vertex (its last if the line is shorter)."""
    for a, b in zip(coords, coords[1:]):
        s = metres(a, b)
        if s >= d and s > 0:
            f = d / s
            return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]
        d -= s
    return list(coords[-1])


class Centreline:
    def __init__(self, segs):
        # seg: [id, name, from_int, to_int, lo_l, hi_l, lo_r, hi_r, coords]
        self.segs = segs
        self.by_name, self.by_base, self.by_bare = defaultdict(list), defaultdict(list), defaultdict(list)
        for s in segs:
            n = snorm(s[1])
            self.by_name[n].append(s); self.by_base[base(n)].append(s); self.by_bare[bare(n)].append(s)

    def street(self, text):
        n = snorm(text)
        return self.by_name.get(n) or self.by_base.get(base(n)) or self.by_bare.get(bare(n)) or []

    @staticmethod
    def ends(s):
        return [(s[2], s[8][0]), (s[3], s[8][-1])]

    def crossing(self, main, cross):
        """Where two streets meet: a shared centreline intersection, else their closest vertices (within 60 m)."""
        M, C = self.street(main), self.street(cross)
        if not M or not C:
            return None, M
        cn = {i: p for s in C for i, p in self.ends(s)}
        hits = [(i, p) for s in M for i, p in self.ends(s) if i in cn]
        if hits:
            return (hits[0][0], hits[0][1]), M
        best = None
        for s in M:
            for p in s[8]:
                for t in C:
                    for q in t[8]:
                        d = metres(p, q)
                        if best is None or d < best[0]:
                            best = (d, p)
        if best and best[0] < 60:
            return (None, best[1]), M
        return None, M

    def offset(self, M, node, pt, rel, dist=80):
        """From where the streets meet, dist metres along the main street toward the named side."""
        want = {'north': (0, 1), 'south': (0, -1), 'east': (1, 0), 'west': (-1, 0)}[rel]
        cands = []
        for s in M:
            c = s[8]
            if (node is not None and s[2] == node) or metres(c[0], pt) < 5:
                cands.append(c)
            elif (node is not None and s[3] == node) or metres(c[-1], pt) < 5:
                cands.append(c[::-1])
        best = None
        for c in cands:
            q = along(c, dist)
            k = math.cos(math.radians(pt[1]))
            dx, dy = (q[0] - pt[0]) * k, q[1] - pt[1]
            L = math.hypot(dx, dy) or 1
            dot = (dx * want[0] + dy * want[1]) / L
            if best is None or dot > best[0]:
                best = (dot, q)
        return best[1] if best and best[0] > 0.3 else pt

    def address(self, main, num):
        """A house number on a street, from the segments' address ranges (interpolated)."""
        best = None
        for s in self.street(main):
            for lo, hi in ((s[4], s[5]), (s[6], s[7])):
                if lo is None or hi is None:
                    continue
                a, b = min(lo, hi), max(lo, hi)
                if a <= num <= b:
                    f = 0.5 if b == a else (num - lo) / (hi - lo)
                    total = sum(metres(p, q) for p, q in zip(s[8], s[8][1:]))
                    return along(s[8], total * max(0, min(1, f)))
                gap = min(abs(num - a), abs(num - b))
                if best is None or gap < best[0]:
                    best = (gap, s)
        if best and best[0] <= 40:
            c = best[1][8]
            return c[len(c) // 2]
        return None


def place_site(cl, text):
    """Place an ASE site from its text: (lon, lat) or None."""
    main, rel, cross, num = parse_site(text)
    if rel == 'addr':
        return cl.address(main, num)
    if not cross:
        return None
    hit, M = cl.crossing(main, cross)
    if not hit:
        return None
    node, pt = hit
    return cl.offset(M, node, pt, rel) if rel in ('north', 'south', 'east', 'west') else list(pt)


def place_pair(cl, text):
    main, cross = parse_pair(text)
    hit, _ = cl.crossing(main, cross)
    return list(hit[1]) if hit else None


# ---------- build ----------
def num(v):
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        m = re.match(r'^\s*(\d+)\s*\*?\s*$', v)
        if m:
            return int(m.group(1))
    return None


def day(v):
    return v[:10] if isinstance(v, str) and re.match(r'^\d{4}-\d\d-\d\d', v) else None


def r5(p):
    return [round(p[0], 5), round(p[1], 5)]


def build():
    src = json.load(open(os.path.join(RAW, 'sources.json')))
    cl = Centreline(json.load(open(os.path.join(RAW, 'centreline.json'))))
    log = []

    # Red light cameras. The charges file's "Location Codes" are the locations file's RLC numbers less 3500.
    loc = {}
    for f in json.load(open(os.path.join(RAW, 'rlc_locations.geojson')))['features']:
        p = f['properties']; c = f['geometry']['coordinates']
        loc[int(p['RLC'])] = (p, c[0] if f['geometry']['type'] == 'MultiPoint' else c)
    ch = json.load(open(os.path.join(RAW, 'rlc_charges.json')))
    hdr = ch['header']
    ycols = [(i, int(h)) for i, h in enumerate(hdr) if isinstance(h, (int, float)) or (isinstance(h, str) and re.match(r'^\d{4}$', h))]
    years = [y for _, y in ycols]
    partial = ch.get('partial')   # e.g. {"year": 2026, "to": "2026-06-30"} from the file's footnote
    feats, unplaced = [], []
    for row in ch['rows']:
        if not isinstance(row[0], (int, float)):
            continue
        code = int(row[0]); rlc = code + 3500; name = re.sub(r'\s+', ' ', str(row[2])).strip()
        built = name.endswith('**')   # the file's footnote: built, the intersection is under third-party construction
        retired = (name.endswith('*') and not built) or bool(day(row[4]))
        counts = [num(row[i]) for i, _ in ycols]
        p = {'id': rlc, 'n': name.rstrip('*').strip(), 'w': row[1], 't': counts}
        if day(row[3]): p['since'] = day(row[3])
        if day(row[4]): p['end'] = day(row[4])
        if retired: p['r'] = 1
        if built:
            p['built'] = 1   # built, not yet enforcing (third-party construction at the intersection)
        if rlc in loc:
            lp, c = loc[rlc]
            p['n'] = lp.get('NAME') or p['n']
            ai = lp.get('ADDITIONAL_INFO')
            if ai and ai != 'None': p['ap'] = ai.title()
            pt = c
        else:
            pt = place_pair(cl, name)
            if not pt:
                unplaced.append(name); continue
            p['ax'] = 1   # placed from its text: approximate
        feats.append({'type': 'Feature', 'properties': p, 'geometry': {'type': 'Point', 'coordinates': r5(pt)}})
    feats.sort(key=lambda f: -max([x or 0 for x in f['properties']['t']] or [0]))
    rlc_out = {'type': 'FeatureCollection', 'years': years, 'features': feats}
    if partial: rlc_out['partial'] = partial
    log.append(f"rlc: {len(feats)} cameras ({sum(1 for f in feats if f['properties'].get('r'))} retired, "
               f"{sum(1 for f in feats if f['properties'].get('ax'))} placed from their text); unplaced: {unplaced or 'none'}")

    # ASE sites: one point per site text (the same site may have several rows, with a code reused for a later site).
    snaps = json.load(open(os.path.join(RAW, 'ase_locations.json')))   # oldest first
    official = {}
    for s in snaps:   # later snapshots win
        for code, name, status, lon, lat in s['points']:
            official[snorm(name)] = [lon, lat]
    ac = json.load(open(os.path.join(RAW, 'ase_charges.json')))
    mcols = [(i, h[:7]) for i, h in enumerate(ac['header']) if isinstance(h, str) and re.match(r'^\d{4}-\d\d', h)]
    months = [m for _, m in mcols]
    sites = {}
    for row in ac['rows']:
        if not (isinstance(row[0], str) and re.match(r'^[A-Z]\d+', row[0])):
            continue
        text = re.sub(r'\s+', ' ', str(row[1])).strip()
        k = snorm(text)
        s = sites.setdefault(k, {'n': text, 'w': row[2], 'p': [], 'm': [0] * len(months), 'codes': []})
        s['codes'].append(row[0])
        if day(row[3]):
            s['p'].append([day(row[3]), day(row[4]) or ''])
        for j, (i, _) in enumerate(mcols):
            v = num(row[i])
            if v is not None:
                s['m'][j] += v
    afeats, how, unplaced = [], defaultdict(int), []
    far = []
    for k, s in sites.items():
        pt, ax = official.get(k), None
        guess = place_site(cl, s['n'])
        if pt and guess and metres(pt, guess) > 400:
            far.append(f"{s['n']} ({round(metres(pt, guess))} m from its text)")
        if not pt:
            pt, ax = guess, 1
        if not pt:
            unplaced.append(s['n']); continue
        how['text' if ax else 'official'] += 1
        mm = s['m']
        on = [j for j, v in enumerate(mm) if v]
        p = {'n': s['n'], 'w': s['w'], 'tot': sum(mm), 'mo': len(on), 'p': sorted(s['p'])}
        if on:
            p['first'], p['last'] = months[on[0]], months[on[-1]]
            p['peak'] = max(mm)
        if ax: p['ax'] = 1
        afeats.append({'type': 'Feature', 'properties': p, 'geometry': {'type': 'Point', 'coordinates': r5(pt)}})
    afeats.sort(key=lambda f: -f['properties']['tot'])
    ase_out = {'type': 'FeatureCollection', 'months': [months[0], months[-1]], 'features': afeats}
    log.append(f"ase: {len(afeats)} sites ({how['official']} from the published points, {how['text']} placed from their text); "
               f"unplaced {len(unplaced)}: {unplaced}")
    if far:
        log.append('ase: published point far from its text: ' + '; '.join(far))

    meta = {
        'rlc': {'years': [years[0], years[-1]], 'latestFull': max(y for y in years if not partial or y != partial.get('year')),
                'partial': partial, 'cameras': len(feats), 'source': src.get('rlc')},
        'ase': {'months': [months[0], months[-1]], 'sites': len(afeats), 'charges': sum(f['properties']['tot'] for f in afeats),
                'ended': '2025-11-14', 'lastDay': max((p[1] for f in afeats for p in f['properties']['p'] if p[1]), default=None),
                'source': src.get('ase')},
        'licence': 'Contains information licensed under the Open Government Licence – Toronto.',
        # Set amounts on toronto.ca's Red Light Cameras page (modified July 14, 2026). Estimates only: the data counts
        # charges, and some are cancelled, varied or unpaid.
        'fines': {'rlc': {'total': 328.25, 'setFine': 260, 'victimFund': 60, 'plateFee': 8.25, 'since': '2025-01-20',
                          'system': 'Administrative Penalty System (O. Reg. 355/22)',
                          'before': 'Before January 20, 2025 red light camera tickets went through the Provincial Offences courts and the amount differed ($325 from January 2010, $180 before).',
                          'url': 'https://www.toronto.ca/services-payments/streets-parking-transportation/traffic-management/pavement-markings/red-light-cameras/'}},
        # City-wide amounts the City says it collected (not per camera).
        'collected': {'year': 2024, 'rlc': 25.3e6, 'ase': 37.3e6,
                      'source': "City Manager's letter to the City Clerk, October 7, 2025 (administrative inquiry on ASE)",
                      'url': 'https://www.toronto.ca/legdocs/mmis/2025/ia/bgrd/backgroundfile-259226.pdf'},
        'fetched': src.get('fetched'),
    }
    os.makedirs(OUT, exist_ok=True)
    for name, obj in (('rlc.json', rlc_out), ('ase.json', ase_out), ('meta.json', meta)):
        with open(os.path.join(OUT, name), 'w') as fh:
            json.dump(obj, fh, separators=(',', ':'), ensure_ascii=False)
    for line in log:
        print(line)


if __name__ == '__main__':
    os.chdir(HERE)
    build()
