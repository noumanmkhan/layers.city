"""ZIP-code lenses from the American Community Survey (5-year estimates, ZIP Code Tabulation Areas).
Inputs: raw/acs_zcta.json (fetch_zips.py) and tmp/zips.geojson, tmp/zip_partial.json (build.py).
Output: docs/dallas/data/zip_profiles.json  {ZIP: {...figures and tiers...}}

Each unit is a ZIP clipped to the city, but its figures describe the whole ZIP, so a ZIP that is mostly another
town (Coppell's 75019, Highland Park's 75205...) carries no figures (build.py marks them). Medians of home values
(B25075) and cash rents (B25063) are read from the brackets by linear interpolation, as in Chicago.
Tiers:
Housing cost: median home value and median rent ranked against Dallas's other ZIPs, averaged by the share of
  owners and renters, split into thirds.
Getting to work: share of commuters who drive. Nearly everyone in Dallas drives, so the cuts are Dallas's own:
  over 80% / 65-80% / under 65%.
Renters and owners: share of households that rent: mostly owners under 35%, a mix 35-60%, mostly renters over 60%.
Card-only descriptions (homes by building size, when built, language at home, ages, recent immigrants) as Chicago's.
"""
import json, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
OUT = os.path.join(HERE, '..', '..', 'docs', 'dallas', 'data', 'zip_profiles.json')
acs = json.load(open(os.path.join(RAW, 'acs_zcta.json')))
units = [f['properties'] for f in json.load(open(os.path.join(HERE, 'tmp', 'zips.geojson')))['features']]
partial = json.load(open(os.path.join(HERE, 'tmp', 'zip_partial.json')))
sums = {u['code']: Counter({k: x for k, x in acs['zctas'].get(u['code'], {}).items() if x}) for u in units if u['code'] not in partial}
msums = sums
MORE = acs
# Bracket lower edges (dollars), in table order.
VALUE = [0, 10e3, 15e3, 20e3, 25e3, 30e3, 35e3, 40e3, 50e3, 60e3, 70e3, 80e3, 90e3, 100e3, 125e3, 150e3, 175e3,
         200e3, 250e3, 300e3, 400e3, 500e3, 750e3, 1e6, 1.5e6, 2e6]                      # B25075_E002..E027
RENT = [0, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 900, 1000, 1250, 1500,
        2000, 2500, 3000, 3500]                                                          # B25063_E003..E026


def median(counts, edges):
    total = sum(counts)
    if not total: return None
    half, run = total / 2, 0
    for i, c in enumerate(counts):
        if run + c >= half:
            if i == len(edges) - 1: return edges[i]          # open-ended top bracket
            return edges[i] + (half - run) / c * (edges[i + 1] - edges[i])
        run += c


LAB = {k: lab.split('!!') for k, lab in MORE['labels'].items()}
leaf = lambda k: LAB[k][-1].rstrip(':')


def vars_where(table, test):
    return [k for k in sorted(LAB) if k.startswith(table + '_') and test(LAB[k])]


UNITS = {'1, detached': 0, '1, attached': 1, '2': 2, '3 or 4': 2, '5 to 9': 2, '10 to 19': 2, '20 to 49': 3, '50 or more': 3}
UNIT_VARS = [(k, UNITS[leaf(k)]) for k in vars_where('B25032', lambda l: len(l) == 4 and l[-1] in UNITS)]
def band(year_label):
    y = int(year_label.split()[1]) if year_label.split()[1].isdigit() else 0   # "Built 1939 or earlier" -> 1939
    return 0 if y <= 1939 else 1 if y < 1980 else 2 if y < 2000 else 3
BUILT_VARS = [(k, band(leaf(k))) for k in vars_where('B25036', lambda l: len(l) == 4 and l[-1].startswith('Built '))]
LANG_VARS = vars_where('C16001', lambda l: len(l) == 3 and (l[-1].endswith(':') or l[-1] == 'Speak only English'))
LANG_NAME = {'Speak only English': 'English only', 'French, Haitian, or Cajun': 'French or Haitian Creole',
             'German or other West Germanic languages': 'German or other West Germanic',
             'Russian, Polish, or other Slavic languages': 'Polish, Russian or other Slavic',
             'Other Indo-European languages': 'Other Indo-European (e.g. Hindi, Urdu)',
             'Other Asian and Pacific Island languages': 'Other Asian or Pacific Island',
             'Chinese (incl. Mandarin, Cantonese)': 'Chinese', 'Tagalog (incl. Filipino)': 'Tagalog (Filipino)'}
# Ages: B01001's age brackets (men and women alike), by the first age in the label ("Under 5" is 0).
def age0(lab):
    w = lab.split()
    return 0 if w[0] == 'Under' else int(w[0])
AGE_BAND = lambda a: 0 if a < 15 else 1 if a < 25 else 2 if a < 45 else 3 if a < 65 else 4
AGE_VARS = [(k, AGE_BAND(age0(leaf(k)))) for k in vars_where('B01001', lambda l: len(l) == 4)]
# Recent immigrants: the foreign-born who entered the US in B05005's latest period ("Entered 2010 or later").
ENTRY = {k: LAB[k][2].rstrip(':') for k in vars_where('B05005', lambda l: len(l) == 4 and l[2].startswith('Entered') and l[3].startswith('Foreign-born'))}
first_year = lambda t: next((int(w) for w in t.split() if w.isdigit()), 0)   # 'Entered before 1990' -> 1990, earlier than 2010
RECENT_PERIOD = max(ENTRY.values(), key=first_year) if ENTRY else None
RECENT_VARS = [k for k, t in ENTRY.items() if t == RECENT_PERIOD]
assert len(AGE_VARS) == 46 and RECENT_VARS, (len(AGE_VARS), ENTRY)
assert len(UNIT_VARS) == 16 and len(BUILT_VARS) == 20 and len(LANG_VARS) >= 10, (len(UNIT_VARS), len(BUILT_VARS), len(LANG_VARS))


def shares(s, pairs, n):
    tot = sum(s[k] for k, _ in pairs)
    if not tot: return None
    out = [0] * n
    for k, i in pairs: out[i] += s[k]
    return [round(100 * x / tot) for x in out]


v = lambda s, tbl, n: s.get(f'{tbl}_E{n:03d}', 0)
data = {}
for n in sorted(sums):
    s, name = sums[n], n
    hh = v(s, 'B25003', 1)
    com = v(s, 'B08301', 1) - v(s, 'B08301', 21)
    value = median([v(s, 'B25075', i) for i in range(2, 28)], VALUE)
    rent = median([v(s, 'B25063', i) for i in range(3, 27)], RENT)
    data[n] = {
        'name': name,
        'value': int(round(value, -4)) if value else None, 'rent': int(round(rent, -1)) if rent else None,
        'renterPct': round(100 * v(s, 'B25003', 3) / hh) if hh else None,
        'carPct': round(100 * v(s, 'B08301', 2) / com) if com else None,
        'transitPct': round(100 * v(s, 'B08301', 10) / com) if com else None,
        'walkBikePct': round(100 * (v(s, 'B08301', 18) + v(s, 'B08301', 19)) / com) if com else None,
    }
    m, d = msums.get(n, Counter()), data[n]
    # Shares of all occupied homes (the denominator includes mobile homes and boats, as Toronto's includes movable dwellings).
    tot = v(m, 'B25032', 1)
    d['homes'] = [round(100 * x / tot) for x in [sum(m[k] for k, i in UNIT_VARS if i == j) for j in range(4)]] if tot else None
    d['built'] = shares(m, BUILT_VARS, 4)
    tot = v(m, 'C16001', 1)
    if tot:
        names = [(LANG_NAME.get(leaf(k), leaf(k)), m[k]) for k in LANG_VARS if m[k] and not leaf(k).startswith('Other and unspecified')]
        d['lang'] = [[nm, round(100 * x / tot)] for nm, x in sorted(names, key=lambda a: -a[1])[:5]]
    d['ages'] = shares(m, AGE_VARS, 5)
    tot = v(m, 'B01001', 1)   # everyone (B05005's own total is only people born outside the US)
    d['pop'], d['hh'] = tot or None, hh or None   # weights for citywide figures (Compare page); card never shows them
    d['recent'] = round(100 * sum(m[k] for k in RECENT_VARS) / tot) if tot else None
    d['recentSince'] = RECENT_PERIOD.replace('Entered ', '')   # "2010 or later"


def pct_rank(key):
    vals = sorted(d[key] for d in data.values() if d[key] is not None)
    return {k: (sum(x < d[key] for x in vals) + 0.5 * sum(x == d[key] for x in vals)) / len(vals)
            for k, d in data.items() if d[key] is not None}


rv, rr = pct_rank('value'), pct_rank('rent')
score = {k: (1 - d['renterPct'] / 100) * rv.get(k, rr.get(k, .5)) + (d['renterPct'] / 100) * rr.get(k, rv.get(k, .5)) for k, d in data.items()}
order = sorted(score, key=score.get)
for i, k in enumerate(order):
    data[k]['cost'] = 'lower' if i < len(order) / 3 else 'middle' if i < 2 * len(order) / 3 else 'higher'
for d in data.values():
    d['commute'] = 'car' if d['carPct'] >= 80 else 'mixed' if d['carPct'] >= 65 else 'transit'
    d['tenure'] = 'owners' if d['renterPct'] < 35 else 'mix' if d['renterPct'] <= 60 else 'renters'

# Transit to downtown (fetch_transit_downtown.py): the median weekday-morning trip over each ZIP's grid points. A ZIP where
# fewer than half the points reach downtown within the router's three-hour limit gets no minutes, only the "over an hour" band.
TD = os.path.join(RAW, 'transit_downtown.json')
if os.path.exists(TD):
    td = json.load(open(TD))['areas']
    for k, d in data.items():
        a = td.get(k) or {}
        m = a.get('minutes')
        if a.get('points') and a.get('reached', 0) < a['points'] / 2: m = None; band = 'over60'
        else: band = None if m is None else 'under30' if m < 30 else '30to45' if m < 45 else '45to60' if m <= 60 else 'over60'
        d['downtown'], d['downtownBand'] = m, band

json.dump(data, open(OUT, 'w'), separators=(',', ':'))
print('languages ever in a top 3:', sorted({l[0] for d in data.values() for l in d.get('lang', [])[:3]}))
print('profiles:', len(data), 'ZIPs, ACS', acs['year'], ';', dict(Counter(d['cost'] for d in data.values())),
      dict(Counter(d['commute'] for d in data.values())), dict(Counter(d['tenure'] for d in data.values())))
for k in ('75214', '75208', '75201'):
    print('example', k, {x: data[k].get(x) for x in ('value', 'rent', 'renterPct', 'carPct', 'homes', 'built', 'lang', 'ages', 'recent')})
