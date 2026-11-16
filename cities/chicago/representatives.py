"""Match the current officeholders in raw/representatives/ (fetched by fetch_representatives.py) to the
map's wards and districts. Output: docs/chicago/data/representatives.json

{"updated": date of the last change, "wards": {"1": {"name", "url"}}, "house": {...}, "senate": {...}, "congress": {...},
 "race_congress"/"race_house"/"race_senate"/"race_statewide": the November 3, 2026 races (engine/ballot.py); members carry "runs"}
House, Senate and Congress entries also carry "party". A seat with no current holder is left out, and
the page shows it as vacant. "updated" only moves when a name, party or link actually changes.

"trustees": {"cps": {"1a": {candidates, leader?, winner?}, ..., "president": {...}}} is the Chicago Board
of Education race on November 3, 2026: candidates in ballot order from raw/school_board/candidates.json
(school_board_candidates.py); once the election board posts results (raw/school_board/results.json,
from fetch_school_board_results.py), "leader" names whoever leads the count, and "winner" is set once
the board has proclaimed the results official.
"""
import csv, datetime, html, json, os, re, xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'raw', 'representatives')
DATA = os.path.join(HERE, '..', '..', 'docs', 'chicago', 'data')
OUT = os.path.join(DATA, 'representatives.json')
nums = lambda f, key='num': {str(x['properties'][key]) for x in json.load(open(os.path.join(DATA, f)))['features']}
PARTY = {'D': 'Democrat', 'R': 'Republican', 'Democratic': 'Democrat', 'Republican': 'Republican', 'I': 'Independent'}

wards = {}
for o in json.load(open(os.path.join(SRC, 'ward_offices.json'))):
    n = str(int(o['ward']))
    last, _, first = (o.get('alderman') or '').partition(',')
    if not last.strip(): continue
    url = (o.get('website') or {}).get('url') or 'https://www.chicago.gov/city/en/about/wards/%02d.html' % int(n)
    wards[n] = {'name': (first.strip() + ' ' + last.strip()).strip(), 'url': url}

house, senate = {}, {}
for r in csv.DictReader(open(os.path.join(SRC, 'il.csv'), encoding='utf-8')):
    links = [l for l in r['links'].split(';') if 'ilga.gov' in l]
    url = next((l for l in links if '/Members/Details/' in l), links[-1] if links else '')
    entry = {'name': r['name'], 'url': url, 'party': PARTY.get(r['current_party'], r['current_party'])}
    (house if r['current_chamber'] == 'lower' else senate)[str(int(r['current_district']))] = entry

congress = {}
for m in ET.parse(os.path.join(SRC, 'house.xml')).getroot().find('members'):
    sd = m.findtext('statedistrict') or ''
    name = m.findtext('member-info/official-name')
    if not sd.startswith('IL') or not name:
        continue
    bio = m.findtext('member-info/bioguideID')
    congress[str(int(sd[2:]))] = {'name': name, 'url': 'https://clerk.house.gov/members/' + bio,
                                  'party': PARTY.get(m.findtext('member-info/party'), m.findtext('member-info/party'))}

# Only the seats the map shows.
house_n = nums('il_house.geojson')
out = {'wards': {k: v for k, v in wards.items() if k in nums('wards.geojson')},
       'house': {k: v for k, v in house.items() if k in house_n},
       'senate': {k: v for k, v in senate.items() if str(int(k) * 2) in house_n or str(int(k) * 2 - 1) in house_n},
       'congress': {k: v for k, v in congress.items() if k in nums('congress.geojson')}}

# Chicago Board of Education, 2026.
SB = os.path.join(HERE, 'raw', 'school_board')
if os.path.exists(os.path.join(SB, 'candidates.json')):
    cand = json.load(open(os.path.join(SB, 'candidates.json')))
    cps = {k: {'candidates': v} for k, v in cand['districts'].items()}
    cps['president'] = {'candidates': cand['president']}
    rp = os.path.join(SB, 'results.json')
    if os.path.exists(rp):
        res = json.load(open(rp))
        clean = lambda t: re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', '', t))).strip()
        for contest, frag in res['contests'].items():
            m = re.search(r'Subdistrict (\d+)([AB])', contest)
            key = m.group(1) + m.group(2).lower() if m else ('president' if contest.startswith('President') else None)
            t = re.search(r'<table.*?</table>', frag, re.S)   # the first table is the contest's totals
            if key not in cps or not t: continue
            heads = [clean(h) for h in re.findall(r'<th[^>]*>(.*?)</th>', t.group(0), re.S)]
            cells = [clean(c) for c in re.findall(r'<td[^>]*>(.*?)</td>', t.group(0), re.S)]
            votes = sorted(((int(cells[i].replace(',', '') or 0), h) for i, h in enumerate(heads)
                            if i and h not in ('%', 'Total Votes') and i < len(cells)), reverse=True)
            if not votes or votes[0][0] == 0: continue
            if len(votes) > 1 and votes[0][0] == votes[1][0]:
                print('  ! tie in', contest); continue
            cps[key]['leader'] = votes[0][1]
            if res.get('official'): cps[key]['winner'] = votes[0][1]
    out['trustees'] = {'cps': cps}

# The November 3, 2026 ballot (raw/ballot/candidates.json, from ballot.py): each district's race and, on each sitting
# member, where they're running (engine/ballot.py). The card shows the races until election day.
BAL = os.path.join(HERE, 'raw', 'ballot', 'candidates.json')
if os.path.exists(BAL):
    import sys; sys.path.insert(0, os.path.join(HERE, '..', '..', 'engine'))
    from ballot import ballot_tables
    out.update(ballot_tables(json.load(open(BAL)), {k: out[k] for k in ('congress', 'house', 'senate')}))

# Chicagoland beyond the City (raw/region/, fetch_region.py): every state House, state Senate and congressional
# district in the region, Illinois and Indiana, as card-only boundary files (docs/chicago/data/region_house.geojson,
# region_senate, region_congress: properties k = state abbreviation and number, "IL-82", and name) and tables keyed
# the same way, for card.reps.outside.
RG = os.path.join(HERE, 'raw', 'region')
if os.path.exists(os.path.join(RG, 'lower.geojson')):
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union
    base = json.load(open(os.path.join(DATA, 'base.geojson')))['features']
    CITYG = unary_union([shape(f['geometry']).buffer(0) for f in base if f['properties']['kind'] == 'city']).buffer(0)
    REG = unary_union([shape(f['geometry']).buffer(0) for f in base if f['properties']['kind'] == 'neighbour']).buffer(0)
    REACH, CLIP = REG.difference(CITYG.buffer(-0.002)).buffer(-0.001), REG.buffer(0.01)
    ST = {'17': 'IL', '18': 'IN'}
    r5 = lambda v: round(float(v), 5)
    for r in csv.DictReader(open(os.path.join(RG, 'in.csv'), encoding='utf-8')):
        links = [l for l in r['links'].split(';') if 'iga.in.gov' in l]
        e = {'name': r['name'], 'url': links[0] if links else '', 'party': PARTY.get(r['current_party'], r['current_party'])}
        out.setdefault('_in', {})[(r['current_chamber'], str(int(r['current_district'])))] = e
    members = {'lower': {}, 'upper': {}, 'congress': {}}
    for k, v in house.items(): members['lower']['IL-' + k] = v
    for k, v in senate.items(): members['upper']['IL-' + k] = v
    for (ch, n), v in out.pop('_in', {}).items(): members[ch]['IN-' + n] = v
    for m in ET.parse(os.path.join(SRC, 'house.xml')).getroot().find('members'):
        sd, name = m.findtext('statedistrict') or '', m.findtext('member-info/official-name')
        if sd[:2] in ('IL', 'IN') and name:
            members['congress'][sd[:2] + '-' + str(int(sd[2:]))] = {'name': name, 'url': 'https://clerk.house.gov/members/' + m.findtext('member-info/bioguideID'),
                                                                   'party': PARTY.get(m.findtext('member-info/party'), m.findtext('member-info/party'))}
    for src, table in (('lower', 'region_house'), ('upper', 'region_senate'), ('congress', 'region_congress')):
        feats, keys = [], set()
        for f in json.load(open(os.path.join(RG, src + '.geojson')))['features']:
            pr = f['properties']; g = shape(f['geometry']).buffer(0)
            if pr.get('STATE') not in ST or not re.search(r'\d', pr.get('BASENAME') or '') or not g.intersects(REACH): continue   # ZZ: Lake Michigan
            g = g.intersection(CLIP).simplify(0.0003, preserve_topology=True)
            if g.is_empty: continue
            k = ST[pr['STATE']] + '-' + str(int(re.sub(r'\D', '', pr['BASENAME'])))
            keys.add(k)
            feats.append({'type': 'Feature', 'properties': {'k': k, 'name': k.replace('-', ' '), 'st': ST[pr['STATE']], 'num': k.split('-')[1]}, 'geometry': json.loads(json.dumps(mapping(g)), parse_float=r5)})
        json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(DATA, table + '.geojson'), 'w'), separators=(',', ':'))
        out[table] = {k: v for k, v in members[src].items() if k in keys}
        print(table, len(feats), 'districts ·', len(out[table]), 'members · vacant/missing', sorted(keys - set(out[table])))

old = json.load(open(OUT)) if os.path.exists(OUT) else {}
same = {k: v for k, v in old.items() if k != 'updated'} == out
out = {'updated': old['updated'] if same and old.get('updated') else datetime.date.today().isoformat(), **out}
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=0)
print('representatives:', {k: len(v) for k, v in out.items() if k != 'updated'}, 'updated', out['updated'],
      '· missing wards', sorted(nums('wards.geojson') - set(out['wards'])), 'house', sorted(house_n - set(out['house'])))
