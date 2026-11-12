"""Suburb lenses and Living here rows from the 2021 Census, built from Statistical Areas Level 1 (SA1s).
Inputs: raw/census_sa1.json and raw/sa1.geojson (fetch.py), tmp/unit_codes.json and tmp/suburbs.geojson (build.py)
Output: docs/melbourne/data/suburb_profiles.json  {suburb code: {...figures and tiers...}}

Each SA1 whose inside point falls in the City joins the suburb containing it; its counts are summed. The ABS
perturbs small counts, which mostly cancels out in the sums. The two medians can't be summed: median weekly rent
and median monthly mortgage repayment here are the averages of the SA1s' medians, weighted by each SA1's renting
or mortgaged households. Close to the true median, not the same thing.

When the Census counted (August 10, 2021) Melbourne was in its sixth lockdown and Australia's border was shut, so the
City's population was unusually low (international students away) and travel to work meaningless: there is no
getting-to-work lens. The cards say so.

Tiers: Housing cost: rent and mortgage ranks averaged by the share of renting and mortgaged households, split
into thirds across the City's suburbs. Renters and owners: share of households (tenure stated) that rent: under
35%, 35-60%, over 60% (Toronto's lines). Card only: home types (houses; semi-detached, terrace and town houses;
flats in one- to three-storey blocks, or attached to a house or shop; flats in blocks of four storeys or more),
language used at home (English only, or the other language each person uses), ages, and arrivals 2016-2021 as a
share of everyone counted."""
import json, os, re
from collections import Counter, defaultdict
from shapely.geometry import shape
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
RAW, TMP = os.path.join(HERE, 'raw'), os.path.join(HERE, 'tmp')
OUT = os.path.join(HERE, '..', '..', 'docs', 'melbourne', 'data', 'suburb_profiles.json')
C = json.load(open(os.path.join(RAW, 'census_sa1.json')))
T = {t: {r[0]: dict(zip(v['cols'][1:], r[1:])) for r in v['rows']} for t, v in C.items() if not t.startswith('_')}
num = lambda x: float(x) if x not in (None, '', '..', '-') else 0.0
units = [(f['properties']['name'], f['properties']['code'], shape(f['geometry']).buffer(0)) for f in json.load(open(os.path.join(TMP, 'suburbs.geojson')))['features']]
CITY = unary_union([g for _, _, g in units]).buffer(0.0003)

LANG_SKIP = {'POL_CL_Tot_Tot', 'POL_IAL_Tot_Tot', 'POL_SAL_Tot_Tot', 'POL_Tot_Tot', 'POL_Oth_Tot', 'POL_CL_Oth_Tot', 'POL_IAL_Oth_Tot', 'POL_SAL_Oth_Tot'}
LANG_NAME = {'PSEO_Tot': 'English', 'CL_Canton': 'Cantonese', 'CL_Mandarin': 'Mandarin', 'IAL_Bengali': 'Bengali', 'IAL_Guj': 'Gujarati',
             'IAL_Hindi': 'Hindi', 'IAL_Nepali': 'Nepali', 'IAL_Punjabi': 'Punjabi', 'IAL_Sinhal': 'Sinhalese', 'IAL_Urdu': 'Urdu',
             'SAL_Filipin': 'Filipino', 'SAL_Indon': 'Indonesian', 'SAL_Tagalog': 'Tagalog', 'Japan': 'Japanese', 'Macedon': 'Macedonian',
             'Persian_ED': 'Persian', 'AIndLng': 'Aboriginal languages'}
lang_cols = [c for c in C['G13']['cols'][1:] if c != 'P_Tot_Tot' and c not in LANG_SKIP]
lang_name = lambda c: LANG_NAME.get(c) or LANG_NAME.get(re.sub(r'^POL_|_Tot$', '', c)) or re.sub(r'^POL_|_Tot$', '', c)
TYPES = [['OPDs_Separate_house_Dwellings'], ['OPDs_SD_r_t_h_th_Tot_Dwgs'],
         ['OPDs_F_ap_I_1or2_sty_blk_Ds', 'OPDs_F_ap_I_3_sty_blk_Dwgs', 'OPDs_Flt_apt_Att_house_Ds'],
         ['OPDs_F_ap_I_4to8_sty_blk_Ds', 'OPDs_F_ap_I_9_m_sty_blk_Ds']]
AGES = [['Age_0_4_yr_P', 'Age_5_14_yr_P'], ['Age_15_19_yr_P', 'Age_20_24_yr_P'], ['Age_25_34_yr_P', 'Age_35_44_yr_P'],
        ['Age_45_54_yr_P', 'Age_55_64_yr_P'], ['Age_65_74_yr_P', 'Age_75_84_yr_P', 'Age_85ov_P']]
RECENT = ['Tot_2016', 'Tot_2017', 'Tot_2018', 'Tot_2019', 'Tot_2020', 'Tot_2021']

sums, wr, wm, placed = defaultdict(Counter), defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]), Counter()
for f in json.load(open(os.path.join(RAW, 'sa1.geojson')))['features']:
    sa1 = str(f['properties']['sa1_code_2021'])
    pt = shape(f['geometry']).buffer(0).representative_point()
    if not CITY.contains(pt) or sa1 not in T['G01']: continue
    u = next((n for n, _, g in units if g.contains(pt)), None) or min(units, key=lambda x: x[2].distance(pt))[0]
    placed[u] += 1
    s = sums[u]
    for t in ('G01', 'G36', 'G37', 'G10C', 'G13'):
        for k, v in T[t].get(sa1, {}).items(): s[k] += num(v)
    g2, g37 = T['G02'].get(sa1, {}), T['G37'].get(sa1, {})
    if num(g2.get('Median_rent_weekly')) and num(g37.get('R_Tot_Total')):
        wr[u][0] += num(g2['Median_rent_weekly']) * num(g37['R_Tot_Total']); wr[u][1] += num(g37['R_Tot_Total'])
    if num(g2.get('Median_mortgage_repay_monthly')) and num(g37.get('O_MTG_Total')):
        wm[u][0] += num(g2['Median_mortgage_repay_monthly']) * num(g37['O_MTG_Total']); wm[u][1] += num(g37['O_MTG_Total'])

data = {}
for name, code, _ in units:
    s = sums[name]
    own, mtg, rent = s['O_OR_Total'], s['O_MTG_Total'], s['R_Tot_Total']
    stated = own + mtg + rent + s['Oth_ten_type_Total']
    d = data[str(code)] = {'name': name,
        'rent': int(round(wr[name][0] / wr[name][1], -1)) if wr[name][1] else None,
        'mortgage': int(round(wm[name][0] / wm[name][1], -1)) if wm[name][1] else None,
        'renterPct': round(100 * rent / stated) if stated else None,
        'publicPct': round(100 * (s['R_ST_h_auth_Total'] + s['R_Com_Hp_Total']) / stated) if stated else None}
    tot = sum(s[k] for grp in TYPES for k in grp)
    d['homes'] = [round(100 * sum(s[k] for k in grp) / tot) for grp in TYPES] if tot else None
    tot = s['P_Tot_Tot'] - s.get('P_LUatH_NS_Tot', 0)
    if tot:
        langs = sorted(((lang_name(c), s[c]) for c in lang_cols if s[c]), key=lambda x: -x[1])[:5]
        d['lang'] = [[n, round(100 * c / tot)] for n, c in langs]
    tot = s['Tot_P_P']
    d['pop'], d['hh'] = int(tot) or None, int(s['Total_Total']) or None
    d['ages'] = [round(100 * sum(s[k] for k in grp) / tot) for grp in AGES] if tot else None
    d['recent'] = round(100 * sum(s[k] for k in RECENT) / tot) if tot else None
    if not tot or tot < 300:   # Port Melbourne's piece (the employment precinct), South Wharf, Carlton North's sliver
        d['few'] = True

core = {k: d for k, d in data.items() if not d.get('few') and d['rent'] and d['renterPct'] is not None}


def pct_rank(key):
    vals = sorted(d[key] for d in core.values() if d[key] is not None)
    return {k: (sum(x < d[key] for x in vals) + 0.5 * sum(x == d[key] for x in vals)) / len(vals) for k, d in data.items() if d.get(key) is not None}


rr, rm = pct_rank('rent'), pct_rank('mortgage')
def score(k):
    s = sums[data[k]['name']]
    r, m = s['R_Tot_Total'], s['O_MTG_Total']
    return (r * rr.get(k, .5) + m * rm.get(k, .5)) / (r + m) if r + m else .5
ranked = sorted(core, key=score)
for i, k in enumerate(ranked):
    data[k]['cost'] = 'lower' if i < len(ranked) / 3 else 'middle' if i < 2 * len(ranked) / 3 else 'higher'
for d in core.values():
    d['tenure'] = 'owners' if d['renterPct'] < 35 else 'mix' if d['renterPct'] <= 60 else 'renters'
# Too few people for figures to mean anything (the ABS perturbs small counts): no profile, so no Living here or tier.
few = sorted(d['name'] for d in data.values() if d.get('few'))
data = {k: d for k, d in data.items() if not d.get('few')}
print('no profile (under 300 people):', few)

json.dump(data, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
for d in sorted(data.values(), key=lambda d: d['name']):
    print('%-16s pop %6s hh %5s rent %4s mtg %5s rent%% %3s %-7s %-8s homes %s lang %s recent %s' % (d['name'], d['pop'], d['hh'], d.get('rent'), d.get('mortgage'),
          d['renterPct'], d.get('cost'), d.get('tenure'), d['homes'], (d.get('lang') or [])[:3], d['recent']))
print('profiles', len(data), 'from', sum(placed.values()), 'SA1s', dict(placed))
