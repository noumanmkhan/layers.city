"""Local-area lenses and Living here rows from the 2021 Census, built from dissemination areas.
Inputs: raw/census_da.json (fetch_census.py), raw/das.geojson, raw/csds.geojson and raw/local_areas.geojson (fetch.py)
Output: docs/vancouver/data/la_profiles.json  {local area code: {...figures and tiers...}}

The City of Vancouver hasn't published 2021 profiles for its 22 local areas (its portal stops at 2016), so
each of the City's dissemination areas (DAs) is placed in the local area containing it (by a point inside
the DA; a DA no local area covers, such as Stanley Park's, joins the nearest) and its counts are summed.
DA counts are randomly rounded by Statistics Canada, which mostly cancels out in the sums.

The two medians can't be summed. Median home value and median rent here are the averages of the DAs'
medians, weighted by each DA's owner or tenant households: close to the true median, not the same thing.
Small DAs whose medians Statistics Canada suppresses are left out of that average.

Tiers and card rows follow Toronto's map (also 2021 Census), so the two Canadian cities read alike:
Housing cost: median value and rent ranked across the 22, the two ranks averaged by the share of owners
  and renters, split into thirds. Getting to work: share of commuters who drive: 68%+ mostly car, 50-68%
  mixed, under 50% mostly transit / walk / bike. Renters and owners: share who rent: under 35%, 35-60%, over 60%.
Card only: home types (detached; semi & row; low-rise: duplex flats and under five storeys; towers: five
  storeys or more), period of construction, language spoken most often at home (single responses, with the
  share naming two or more kept as langMulti), ages, and recent immigrants (2016-2021) as a share of
  everyone in private households."""
import json, os
from collections import Counter, defaultdict
from shapely.geometry import shape

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
OUT = os.path.join(HERE, '..', '..', 'docs', 'vancouver', 'data', 'la_profiles.json')

C = json.load(open(os.path.join(RAW, 'census_da.json')))
order = sorted(int(k) for k in C['labels'])
raw = {int(k): v for k, v in C['labels'].items()}
lab = {k: v.strip() for k, v in raw.items()}
indent = lambda k: len(raw[k]) - len(raw[k].lstrip(' '))


def find(text, after=0, prefix=False):
    for k in order:
        if k >= after and (lab[k].startswith(text) if prefix else lab[k] == text): return k
    raise SystemExit('row not found: ' + text)


def section(title, labels):
    top = find(title, prefix=True)
    return top, [find(l, top) for l in labels]


HH = find('Total - Private households by tenure', prefix=True)
OWNER, RENTER = find('Owner', HH), find('Renter', HH)
OWN_T = find('Total - Owner households in non-farm, non-reserve private dwellings', prefix=True)
TEN_T = find('Total - Tenant households in non-farm, non-reserve private dwellings', prefix=True)
VALUE = find('Median value of dwellings ($)', OWN_T)
RENT = find('Median monthly shelter costs for rented dwellings ($)', TEN_T)
COM = find('Total - Main mode of commuting', prefix=True)
CAR, TRANSIT, WALK, BIKE = (find(t, COM) for t in ('Car, truck or van', 'Public transit', 'Walked', 'Bicycle'))
TYPE_T, TYPE_R = section('Total - Occupied private dwellings by structural type of dwelling',
    ['Single-detached house', 'Semi-detached house', 'Row house', 'Other single-attached house',
     'Apartment or flat in a duplex', 'Apartment in a building that has fewer than five storeys',
     'Apartment in a building that has five or more storeys'])
TYPE_GROUPS = [[0], [1, 2, 3], [4, 5], [6]]
BUILT_T, BUILT_R = section('Total - Occupied private dwellings by period of construction',
    ['1960 or before', '1961 to 1980', '1981 to 1990', '1991 to 2000', '2001 to 2005', '2006 to 2010', '2011 to 2015', '2016 to 2021'])
BUILT_GROUPS = [[0], [1], [2, 3], [4, 5, 6, 7]]
LANG_T = find('Total - Language spoken most often at home', prefix=True)
LANG_SINGLE, LANG_MULTI = find('Single responses', LANG_T), find('Multiple responses', LANG_T)
LANG_LEAVES = [k for i, k in enumerate(order) if LANG_SINGLE < k < LANG_MULTI and i + 1 < len(order) and indent(order[i + 1]) <= indent(k)]
AGE_T, AGE_R = section('Total - Age groups of the population',
    ['0 to 14 years', '15 to 19 years', '20 to 24 years', '25 to 29 years', '30 to 34 years', '35 to 39 years', '40 to 44 years',
     '45 to 49 years', '50 to 54 years', '55 to 59 years', '60 to 64 years', '65 years and over'])
AGE_GROUPS = [[0], [1, 2], [3, 4, 5, 6], [7, 8, 9, 10], [11]]
IMM_T = find('Total - Immigrant status and period of immigration', prefix=True)
IMM_RECENT = find('2016 to 2021', IMM_T)
LANG_NAME = {'Punjabi (Panjabi)': 'Punjabi', 'Tagalog (Pilipino, Filipino)': 'Tagalog (Filipino)', 'Yue (Cantonese)': 'Cantonese',
             'Iranian Persian': 'Persian (Farsi)', 'Min Nan (Chinese)': 'Min Nan (Hokkien)'}
SUMMED = [OWNER, RENTER, HH, OWN_T, TEN_T, COM, CAR, TRANSIT, WALK, BIKE, TYPE_T, BUILT_T, LANG_T, LANG_MULTI, AGE_T, IMM_T, IMM_RECENT] \
    + TYPE_R + BUILT_R + LANG_LEAVES + AGE_R

las = sorted((f['properties']['name'].strip(), shape(f['geometry']).buffer(0)) for f in json.load(open(os.path.join(RAW, 'local_areas.geojson')))['features'])
code = {n: i for i, (n, _) in enumerate(las, 1)}
sums, wv, wr, placed = defaultdict(Counter), defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]), Counter()
CSDS = json.load(open(os.path.join(RAW, 'csds.geojson')))['features']
CITY = next(shape(f['geometry']).buffer(0) for f in CSDS if f['properties']['CSDUID'] == '5915022')
# The University Endowment Lands (build.py's unit 24): its dissemination areas make a profile of their own, marked "apart":
# tiers place it against the 22 local areas without moving theirs, and the facts engine never ranks it.
from shapely.geometry import box
UEL_NAME, UEL_CODE = 'University Endowment Lands', 24
UEL = next(shape(f['geometry']).buffer(0) for f in CSDS if f['properties']['CSDTYPE'] == 'RDA' and f['properties']['CSDNAME'].endswith(' A')) \
    .intersection(box(-123.30, 49.20, -123.19, 49.30)).difference(CITY)
for f in json.load(open(os.path.join(RAW, 'das.geojson')))['features']:
    da = f['properties']['DAUID']; d = C['das'].get(da)
    if not d: continue
    g = shape(f['geometry']).buffer(0); pt = g.representative_point()
    if UEL.contains(pt): la = UEL_NAME
    elif not CITY.contains(pt): continue   # the fetch takes Metro Vancouver's DAs in the City's box: Burnaby's along Boundary Road too
    else: la = next((n for n, lg in las if lg.contains(pt)), None) or min(las, key=lambda a: a[1].distance(pt))[0]
    placed[la] += 1
    v = lambda k: d.get(str(k)) or 0
    for k in SUMMED: sums[la][k] += v(k)
    if d.get(str(VALUE)) and v(OWN_T): wv[la][0] += d[str(VALUE)] * v(OWN_T); wv[la][1] += v(OWN_T)
    if d.get(str(RENT)) and v(TEN_T): wr[la][0] += d[str(RENT)] * v(TEN_T); wr[la][1] += v(TEN_T)

data = {}
code[UEL_NAME] = UEL_CODE
for name in [n for n, _ in las] + [UEL_NAME]:
    s = sums[name]; v = lambda k: s[k]
    hh, com = v(OWNER) + v(RENTER), v(COM)
    d = data[str(code[name])] = {
        'name': name,
        'value': int(round(wv[name][0] / wv[name][1], -4)) if wv[name][1] else None,
        'rent': int(round(wr[name][0] / wr[name][1], -1)) if wr[name][1] else None,
        'renterPct': round(100 * v(RENTER) / hh) if hh else None,
        'carPct': round(100 * v(CAR) / com) if com else None,
        'transitPct': round(100 * v(TRANSIT) / com) if com else None,
        'walkBikePct': round(100 * (v(WALK) + v(BIKE)) / com) if com else None,
    }
    tot = v(TYPE_T)
    d['homes'] = [round(100 * sum(v(TYPE_R[j]) for j in grp) / tot) for grp in TYPE_GROUPS] if tot else None
    tot = v(BUILT_T)
    d['built'] = [round(100 * sum(v(BUILT_R[j]) for j in grp) / tot) for grp in BUILT_GROUPS] if tot else None
    tot = v(LANG_T)
    if tot:
        langs = sorted(((LANG_NAME.get(lab[k], lab[k]), v(k)) for k in LANG_LEAVES if v(k)), key=lambda x: -x[1])[:5]
        d['lang'] = [[n, round(100 * c / tot)] for n, c in langs]
        d['langMulti'] = round(100 * v(LANG_MULTI) / tot)
    tot = v(AGE_T)
    d['pop'], d['hh'] = int(round(tot)) or None, int(round(hh)) or None   # weights for citywide figures (Compare page); card never shows them
    d['ages'] = [round(100 * sum(v(AGE_R[j]) for j in grp) / tot) for grp in AGE_GROUPS] if tot else None
    tot = v(IMM_T)
    d['recent'] = round(100 * v(IMM_RECENT) / tot) if tot else None


data[str(UEL_CODE)]['apart'] = True
CORE = {k: d for k, d in data.items() if not d.get('apart')}


def pct_rank(key):
    vals = sorted(d[key] for d in CORE.values() if d[key] is not None)   # ranked among the 22; the UEL is placed against them
    return {k: (sum(x < d[key] for x in vals) + 0.5 * sum(x == d[key] for x in vals)) / len(vals) for k, d in data.items() if d[key] is not None}


rv, rr = pct_rank('value'), pct_rank('rent')
score = {k: (1 - d['renterPct'] / 100) * rv.get(k, .5) + (d['renterPct'] / 100) * rr.get(k, .5) for k, d in data.items()}
ranked = sorted(CORE, key=score.get)
cut1, cut2 = score[ranked[int(len(ranked) / 3 + .999) - 1]], score[ranked[int(2 * len(ranked) / 3 + .999) - 1]]
for i, k in enumerate(ranked):
    data[k]['cost'] = 'lower' if i < len(ranked) / 3 else 'middle' if i < 2 * len(ranked) / 3 else 'higher'
for k, d in data.items():
    if d.get('apart'): d['cost'] = 'lower' if score[k] <= cut1 else 'middle' if score[k] <= cut2 else 'higher'
for d in data.values():
    d['commute'] = 'car' if d['carPct'] >= 68 else 'mixed' if d['carPct'] >= 50 else 'transit'
    d['tenure'] = 'owners' if d['renterPct'] < 35 else 'mix' if d['renterPct'] <= 60 else 'renters'

TW = os.path.join(RAW, 'transit_waterfront.json')
if os.path.exists(TW):
    tw = json.load(open(TW))['areas']
    for k, d in data.items():
        m = (tw.get(k) or {}).get('minutes')
        d['waterfront'] = m
        d['waterfrontBand'] = None if m is None else 'under30' if m < 30 else '30to45' if m < 45 else '45to60' if m <= 60 else 'over60'

json.dump(data, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
print('households summed:', sum(s[OWNER] + s[RENTER] for s in sums.values()))
for k in ('6', '12', '17'):
    if k in data: print('example', k, data[k])
print('languages ever in a top 3:', sorted({l[0] for d in data.values() for l in d.get('lang', [])[:3]}))
print('UEL:', data[str(UEL_CODE)])
print('profiles:', len(data), 'local areas from', sum(placed.values()), 'DAs;', dict(Counter(d['cost'] for d in data.values())),
      dict(Counter(d['commute'] for d in data.values())), dict(Counter(d['tenure'] for d in data.values())))
