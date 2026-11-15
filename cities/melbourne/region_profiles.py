"""The suburb lens and the card's Living here beyond the City of Melbourne, by suburb (ABS Suburbs and Localities).
Inputs: raw/census_sal.json (fetch_sal_census.py), raw/sal.geojson, docs/melbourne/data/base.geojson (Greater
Melbourne's suburbs) and tmp/lens_cuts.json (profiles.py: the City's rents, mortgages and tier lines).
Outputs: docs/melbourne/data/region_suburbs.geojson ({code, name}) and region_profiles.json ({code: profile}), drawn
and read by the engine through city.json lens.region.

Every suburb whose inside point is in Greater Melbourne but not the City is kept. Each profile has the same fields as a
City suburb's, plus region: 1. A suburb is one SAL, so its medians are the ABS's own (in the City they are averaged
from SA1s). Tiers use the City's own lines, so a suburb reads the way a City suburb would:
- Housing cost: the suburb's rent and mortgage are placed among the City's suburbs (percentile), weighted by its
  renting and mortgaged households as in profiles.py, then compared with the scores that split the City into thirds.
- Renters and owners: the same fixed lines (35%, 60%).
Suburbs with fewer than 300 people get no profile (the ABS perturbs small counts)."""
import json, os, re
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
RAW, TMP = os.path.join(HERE, 'raw'), os.path.join(HERE, 'tmp')
DATA = os.path.join(HERE, '..', '..', 'docs', 'melbourne', 'data')
if not os.path.exists(os.path.join(RAW, 'census_sal.json')):
    raise SystemExit('region_profiles: no raw/census_sal.json yet (fetch_sal_census.py); skipped')
C = json.load(open(os.path.join(RAW, 'census_sal.json')))
T = {t: {r[0]: dict(zip(v['cols'][1:], r[1:])) for r in v['rows']} for t, v in C.items() if not t.startswith('_')}
num = lambda x: float(x) if x not in (None, '', '..', '-') else 0.0
CUTS = json.load(open(os.path.join(TMP, 'lens_cuts.json')))
base = json.load(open(os.path.join(DATA, 'base.geojson')))['features']
CITY = prep(unary_union([shape(f['geometry']) for f in base if f['properties']['kind'] == 'city']).buffer(0))
REGION = prep(unary_union([shape(f['geometry']) for f in base if f['properties']['kind'] == 'neighbour']).buffer(0.002))

# The same groupings as profiles.py (copied: profiles.py runs on import).
LANG_SKIP = {'POL_CL_Tot_Tot', 'POL_IAL_Tot_Tot', 'POL_SAL_Tot_Tot', 'POL_Tot_Tot', 'POL_Oth_Tot', 'POL_CL_Oth_Tot', 'POL_IAL_Oth_Tot', 'POL_SAL_Oth_Tot'}
LANG_NAME = {'PSEO_Tot': 'English', 'CL_Canton': 'Cantonese', 'CL_Mandarin': 'Mandarin', 'IAL_Bengali': 'Bengali', 'IAL_Guj': 'Gujarati',
             'IAL_Hindi': 'Hindi', 'IAL_Nepali': 'Nepali', 'IAL_Punjabi': 'Punjabi', 'IAL_Sinhal': 'Sinhalese', 'IAL_Urdu': 'Urdu',
             'SAL_Filipin': 'Filipino', 'SAL_Indon': 'Indonesian', 'SAL_Tagalog': 'Tagalog', 'Japan': 'Japanese', 'Macedon': 'Macedonian',
             'Persian_ED': 'Persian', 'AIndLng': 'Aboriginal languages'}
lang_name = lambda c: LANG_NAME.get(c) or LANG_NAME.get(re.sub(r'^POL_|_Tot$', '', c)) or re.sub(r'^POL_|_Tot$', '', c)
TYPES = [['OPDs_Separate_house_Dwellings'], ['OPDs_SD_r_t_h_th_Tot_Dwgs'],
         ['OPDs_F_ap_I_1or2_sty_blk_Ds', 'OPDs_F_ap_I_3_sty_blk_Dwgs', 'OPDs_Flt_apt_Att_house_Ds'],
         ['OPDs_F_ap_I_4to8_sty_blk_Ds', 'OPDs_F_ap_I_9_m_sty_blk_Ds']]
AGES = [['Age_0_4_yr_P', 'Age_5_14_yr_P'], ['Age_15_19_yr_P', 'Age_20_24_yr_P'], ['Age_25_34_yr_P', 'Age_35_44_yr_P'],
        ['Age_45_54_yr_P', 'Age_55_64_yr_P'], ['Age_65_74_yr_P', 'Age_75_84_yr_P', 'Age_85ov_P']]
RECENT = ['Tot_2016', 'Tot_2017', 'Tot_2018', 'Tot_2019', 'Tot_2020', 'Tot_2021']
lang_cols = [c for c in C['G13']['cols'][1:] if c != 'P_Tot_Tot' and c not in LANG_SKIP]
pct = lambda v, vals: (sum(x < v for x in vals) + 0.5 * sum(x == v for x in vals)) / len(vals)
units, data = [], {}
for f in json.load(open(os.path.join(RAW, 'sal.geojson')))['features']:
    g = shape(f['geometry']).buffer(0)
    pt = g.representative_point()
    if CITY.contains(pt) or not REGION.contains(pt):
        continue
    sal = 'SAL' + str(f['properties']['sal_code_2021'])
    code = 'sal' + str(f['properties']['sal_code_2021'])
    nm = re.sub(r'\s*\(Vic\.\)$', '', f['properties']['sal_name_2021'])
    units.append({'type': 'Feature', 'properties': {'code': code, 'name': nm},
                  'geometry': mapping(g.simplify(0.0002, preserve_topology=True))})
    s = {}
    for t in ('G01', 'G36', 'G37', 'G10C', 'G13'):
        for k, v in T[t].get(sal, {}).items(): s[k] = s.get(k, 0) + num(v)
    tot = s.get('Tot_P_P', 0)
    if tot < 300:
        continue
    g2 = T['G02'].get(sal, {})
    own, mtg, rent = s['O_OR_Total'], s['O_MTG_Total'], s['R_Tot_Total']
    stated = own + mtg + rent + s['Oth_ten_type_Total']
    d = {'name': nm, 'region': 1,
         'rent': int(round(num(g2.get('Median_rent_weekly')), -1)) or None,
         'mortgage': int(round(num(g2.get('Median_mortgage_repay_monthly')), -1)) or None,
         'renterPct': round(100 * rent / stated) if stated else None,
         'publicPct': round(100 * (s['R_ST_h_auth_Total'] + s['R_Com_Hp_Total']) / stated) if stated else None}
    ht = sum(s.get(k, 0) for grp in TYPES for k in grp)
    d['homes'] = [round(100 * sum(s.get(k, 0) for k in grp) / ht) for grp in TYPES] if ht else None
    lt = s.get('P_Tot_Tot', 0) - s.get('P_LUatH_NS_Tot', 0)
    if lt:
        langs = sorted(((lang_name(c), s[c]) for c in lang_cols if s.get(c)), key=lambda x: -x[1])[:5]
        d['lang'] = [[n, round(100 * c / lt)] for n, c in langs]
    d['pop'], d['hh'] = int(tot), int(s.get('Total_Total', 0)) or None
    d['ages'] = [round(100 * sum(s.get(k, 0) for k in grp) / tot) for grp in AGES]
    d['recent'] = round(100 * sum(s.get(k, 0) for k in RECENT) / tot)
    if d['rent'] or d['mortgage']:
        w = rent * (pct(d['rent'], CUTS['rents']) if d['rent'] else .5) + mtg * (pct(d['mortgage'], CUTS['mortgages']) if d['mortgage'] else .5)
        sc = w / (rent + mtg) if rent + mtg else .5
        d['cost'] = 'lower' if sc < CUTS['cuts'][0] else 'middle' if sc < CUTS['cuts'][1] else 'higher'
    if d['renterPct'] is not None:
        d['tenure'] = 'owners' if d['renterPct'] < 35 else 'mix' if d['renterPct'] <= 60 else 'renters'
    data[code] = d
json.dump({'type': 'FeatureCollection', 'features': units}, open(os.path.join(DATA, 'region_suburbs.geojson'), 'w'), separators=(',', ':'))
json.dump(data, open(os.path.join(DATA, 'region_profiles.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
from collections import Counter
print('region suburbs', len(units), '· profiles', len(data), '· cost', Counter(d.get('cost') for d in data.values()),
      '· tenure', Counter(d.get('tenure') for d in data.values()))
