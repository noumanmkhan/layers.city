"""The neighbourhood lens and the card's Living here beyond the City of Toronto, by 2021 census tract.
Inputs: raw/gta_tracts/ (fetch_gta_tracts.py: tract boundaries and Census Profile figures, Statistics Canada Open
Licence), docs/toronto/data/base.geojson (the GTA's municipalities) and nbhd_profiles.json (Toronto's neighbourhoods).
Outputs: docs/toronto/data/gta_tracts.geojson ({code, name}) and gta_tract_profiles.json ({code: profile}), drawn and
read by the engine through city.json lens.region.

Only tracts whose inside point is in one of the GTA's 24 municipalities beyond Toronto are kept (the Toronto, Oshawa
and Hamilton CMAs reach past the GTA; Brock and Scugog have no tracts). Each profile has the same fields as a
Toronto neighbourhood's, so the card reads them alike, plus region: 1. The tiers use Toronto's own lines, so a tract
reads the same way a neighbourhood would:
- Housing cost: the tract's median home value and rent are placed among Toronto's 158 neighbourhoods (percentile),
  weighted by its owners and renters as in profiles.py, then compared with the scores that split Toronto into thirds.
- Getting to work and Renters and owners: the same fixed lines as profiles.py.
Tracts with too few people for Statistics Canada to publish a figure (it suppresses small areas) get no tier for it.
Caveats as for Toronto: 2021 Census; commuting counted in May 2021, during the pandemic."""
import json, os
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'gta_tracts')
DATA = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data')
if not os.path.exists(os.path.join(RAW, 'profile.json')):
    raise SystemExit('tracts: no raw/gta_tracts/ yet (fetch-gta-card.yml); skipped')
P = json.load(open(os.path.join(RAW, 'profile.json')))
labels = P['labels']
ids = list(labels)                     # in characteristic order
name = {c: labels[c].strip() for c in ids}
indent = {c: len(labels[c]) - len(labels[c].lstrip(' ')) for c in ids}


def find(text, after=None, starts=False):
    i0 = ids.index(after) + 1 if after else 0
    for c in ids[i0:]:
        if (name[c].startswith(text) if starts else name[c] == text):
            return c
    raise KeyError(text)


def under(top, labels_):
    return [find(l, top) for l in labels_]


POP = find('Population, 2021')
VALUE = find('Median value of dwellings ($)')
RENT = find('Median monthly shelter costs for rented dwellings ($)')
HH = find('Total - Private households by tenure', starts=True)
RENTER = find('Renter', HH)
COM = find('Total - Main mode of commuting', starts=True)
CAR, TRANSIT, WALK, BIKE = (find(x, COM) for x in ('Car, truck or van', 'Public transit', 'Walked', 'Bicycle'))
TYPE_T = find('Total - Occupied private dwellings by structural type of dwelling', starts=True)
TYPE_R = under(TYPE_T, ['Single-detached house', 'Semi-detached house', 'Row house', 'Other single-attached house',
                        'Apartment or flat in a duplex', 'Apartment in a building that has fewer than five storeys',
                        'Apartment in a building that has five or more storeys'])
TYPE_GROUPS = [[0], [1, 2, 3], [4, 5], [6]]
BUILT_T = find('Total - Occupied private dwellings by period of construction', starts=True)
BUILT_R = under(BUILT_T, ['1960 or before', '1961 to 1980', '1981 to 1990', '1991 to 2000', '2001 to 2005', '2006 to 2010',
                          '2011 to 2015', '2016 to 2021'])
BUILT_GROUPS = [[0], [1], [2, 3], [4, 5, 6, 7]]
AGE_T = find('Total - Age groups of the population', starts=True)
AGE_R = under(AGE_T, ['0 to 14 years', '15 to 19 years', '20 to 24 years', '25 to 29 years', '30 to 34 years', '35 to 39 years',
                      '40 to 44 years', '45 to 49 years', '50 to 54 years', '55 to 59 years', '60 to 64 years', '65 years and over'])
AGE_GROUPS = [[0], [1, 2], [3, 4, 5, 6], [7, 8, 9, 10], [11]]
IMM_T = find('Total - Immigrant status and period of immigration', starts=True)
IMM_RECENT = find('2016 to 2021', IMM_T)
LANG_T = find('Total - Language spoken most often at home', starts=True)
LANG_SINGLE = find('Single responses', LANG_T)
LANG_MULTI = find('Multiple responses', LANG_T)
li = ids.index(LANG_SINGLE); lm = ids.index(LANG_MULTI)
LANG_LEAVES = [ids[k] for k in range(li + 1, lm) if indent[ids[k + 1]] <= indent[ids[k]]]
LANG_NAME = {'Punjabi (Panjabi)': 'Punjabi', 'Tagalog (Pilipino, Filipino)': 'Tagalog (Filipino)', 'Yue (Cantonese)': 'Cantonese', 'Iranian Persian': 'Persian (Farsi)'}

# Toronto's neighbourhoods: the reference for the cost tier.
tor = json.load(open(os.path.join(DATA, 'nbhd_profiles.json')))
tv = sorted(d['value'] for d in tor.values() if d.get('value'))
trn = sorted(d['rent'] for d in tor.values() if d.get('rent'))
pct = lambda vals, x: (sum(v < x for v in vals) + 0.5 * sum(v == x for v in vals)) / len(vals)
tscore = sorted((1 - d['renterPct'] / 100) * pct(tv, d['value']) + (d['renterPct'] / 100) * pct(trn, d['rent'])
                for d in tor.values() if d.get('value') and d.get('rent') and d.get('renterPct') is not None)
cut1, cut2 = tscore[len(tscore) // 3], tscore[2 * len(tscore) // 3]

base = json.load(open(os.path.join(DATA, 'base.geojson')))['features']
munis = [(f['properties']['name'], prep(shape(f['geometry']).buffer(0))) for f in base if f['properties']['kind'] == 'neighbour']
feats, profs = [], {}
for f in json.load(open(os.path.join(RAW, 'tracts.geojson')))['features']:
    ct = f['properties']['CTUID']
    g = shape(f['geometry']).buffer(0)
    pt = g.representative_point()
    muni = next((n for n, m in munis if m.contains(pt)), None)
    if not muni:
        continue
    d0 = P['cts'].get(ct) or {}
    v = lambda c: d0.get(c) or 0
    code = 'ct' + ct
    hh, com = v(HH), v(COM)
    d = {'name': 'Census tract %s, %s' % (ct, muni), 'region': 1, 'muni': muni,
         'value': d0.get(VALUE), 'rent': d0.get(RENT),
         'renterPct': round(100 * v(RENTER) / hh) if hh else None,
         'carPct': round(100 * v(CAR) / com) if com else None,
         'transitPct': round(100 * v(TRANSIT) / com) if com else None,
         'walkBikePct': round(100 * (v(WALK) + v(BIKE)) / com) if com else None}
    tot = v(TYPE_T)
    d['homes'] = [round(100 * sum(v(TYPE_R[j]) for j in grp) / tot) for grp in TYPE_GROUPS] if tot else None
    tot = v(BUILT_T)
    d['built'] = [round(100 * sum(v(BUILT_R[j]) for j in grp) / tot) for grp in BUILT_GROUPS] if tot else None
    tot = v(LANG_T)
    if tot:
        langs = sorted(((LANG_NAME.get(name[c], name[c]), v(c)) for c in LANG_LEAVES if v(c)), key=lambda x: -x[1])[:5]
        d['lang'] = [[n, round(100 * k / tot)] for n, k in langs]
        d['langMulti'] = round(100 * v(LANG_MULTI) / tot)
    tot = v(AGE_T)
    d['pop'], d['hh'] = (v(POP) or None), (hh or None)
    d['ages'] = [round(100 * sum(v(AGE_R[j]) for j in grp) / tot) for grp in AGE_GROUPS] if tot else None
    tot = v(IMM_T)
    d['recent'] = round(100 * v(IMM_RECENT) / tot) if tot else None
    if d['value'] and d['rent'] and d['renterPct'] is not None:
        s = (1 - d['renterPct'] / 100) * pct(tv, d['value']) + (d['renterPct'] / 100) * pct(trn, d['rent'])
        d['cost'] = 'lower' if s < cut1 else 'middle' if s < cut2 else 'higher'
    elif d['value'] and d['renterPct'] is not None and d['renterPct'] < 15:   # rent suppressed where few rent: value alone
        s = pct(tv, d['value'])
        d['cost'] = 'lower' if s < cut1 else 'middle' if s < cut2 else 'higher'
    if d['carPct'] is not None:
        d['commute'] = 'car' if d['carPct'] >= 68 else 'mixed' if d['carPct'] >= 50 else 'transit'
    if d['renterPct'] is not None:
        d['tenure'] = 'owners' if d['renterPct'] < 35 else 'mix' if d['renterPct'] <= 60 else 'renters'
    profs[code] = {k: x for k, x in d.items() if x is not None}
    feats.append({'type': 'Feature', 'properties': {'code': code, 'name': 'Census tract ' + ct},
                  'geometry': json.loads(json.dumps(mapping(g.simplify(0.00006, preserve_topology=True))), parse_float=lambda x: round(float(x), 5))})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(DATA, 'gta_tracts.geojson'), 'w'), separators=(',', ':'))
json.dump(profs, open(os.path.join(DATA, 'gta_tract_profiles.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
from collections import Counter
print('gta tracts:', len(feats), '· cost', dict(Counter(p.get('cost') for p in profs.values())), '· commute',
      dict(Counter(p.get('commute') for p in profs.values())), '· tenure', dict(Counter(p.get('tenure') for p in profs.values())))
