"""Match the current officeholders in raw/representatives/ (fetch_representatives.py) to the map's districts.
Output: docs/nyc/data/representatives.json

{"updated", "council": {"1": {name, url}}, "assembly": {"65": {name, url, party}}, "senate": {...}, "congress": {...},
 "borough": {"Manhattan": {name, url, party}}, "mayor": {"city": {name, url}}}
Council members come from each district page's title on council.nyc.gov ("District 1 - Christopher Marte"; the
Speaker's district page is titled "Home - <name>"). The mayor and the five borough presidents (elected November 2025,
in office from January 2026) are hand-kept below; check them after each city election. A seat with no current holder
is left out and the page shows it as vacant. "updated" only moves when a name, party or link changes."""
import csv, datetime, json, os, xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'raw', 'representatives')
DATA = os.path.join(HERE, '..', '..', 'docs', 'nyc', 'data')
OUT = os.path.join(DATA, 'representatives.json')
nums = lambda f: {str(x['properties']['num']) for x in json.load(open(os.path.join(DATA, f)))['features']}
PARTY = {'D': 'Democrat', 'R': 'Republican', 'Democratic': 'Democrat', 'Republican': 'Republican', 'I': 'Independent'}

MAYOR = {'city': {'name': 'Zohran Mamdani', 'url': 'https://www.nyc.gov/mayors-office'}}
BOROUGH = {
    'Manhattan': {'name': 'Brad Hoylman-Sigal', 'party': 'Democrat', 'url': 'https://www.manhattanbp.nyc.gov/'},
    'Bronx': {'name': 'Vanessa L. Gibson', 'party': 'Democrat', 'url': 'https://bronxboropres.nyc.gov/'},
    'Brooklyn': {'name': 'Antonio Reynoso', 'party': 'Democrat', 'url': 'https://www.brooklynbp.nyc.gov/'},
    'Queens': {'name': 'Donovan Richards', 'party': 'Democrat', 'url': 'https://queensbp.org/'},
    'Staten Island': {'name': 'Vito Fossella', 'party': 'Republican', 'url': 'https://www.statenislandusa.com/'},
}

# Council members' parties (council.nyc.gov doesn't give them), hand-kept from the November 2025 results: five
# Republicans, the rest Democrats. Applied only while the district's member is the one named here, so a new member
# shows with no party until this list is checked.
COUNCIL_R = {'19': 'Paladino', '32': 'Ariola', '48': 'Vernikov', '50': 'Carr', '51': 'Morano'}
council = {}
for n, v in json.load(open(os.path.join(SRC, 'council.json'))).items():
    name = v['title'].split(' - ', 1)[-1].strip() if ' - ' in v['title'] else ''
    if name and 'Council' not in name: council[n] = {'name': name, 'url': v['url']}

KNOWN = json.load(open(os.path.join(HERE, 'council_members.json')))   # {district: name} as checked on October 19, 2026
for n, c in council.items():
    if KNOWN.get(n) == c['name']:
        c['party'] = 'Republican' if n in COUNCIL_R else 'Democrat'

assembly, senate = {}, {}
for r in csv.DictReader(open(os.path.join(SRC, 'ny.csv'), encoding='utf-8')):
    if not r['current_district'].isdigit(): continue
    lower = r['current_chamber'] == 'lower'
    links = [l for l in r['links'].split(';') if ('nyassembly.gov/mem/' in l if lower else 'nysenate.gov/senators/' in l)]
    entry = {'name': r['name'], 'url': links[0] if links else '', 'party': PARTY.get(r['current_party'], r['current_party'])}
    (assembly if lower else senate)[str(int(r['current_district']))] = entry

congress = {}
for m in ET.parse(os.path.join(SRC, 'house.xml')).getroot().find('members'):
    sd = m.findtext('statedistrict') or ''
    name = m.findtext('member-info/official-name')
    if not sd.startswith('NY') or not name: continue
    bio = m.findtext('member-info/bioguideID')
    congress[str(int(sd[2:]))] = {'name': name, 'url': 'https://clerk.house.gov/members/' + bio,
                                  'party': PARTY.get(m.findtext('member-info/party'), m.findtext('member-info/party'))}

out = {'council': {k: v for k, v in council.items() if k in nums('council.geojson')},
       'assembly': {k: v for k, v in assembly.items() if k in nums('assembly.geojson')},
       'senate': {k: v for k, v in senate.items() if k in nums('senate.geojson')},
       'congress': {k: v for k, v in congress.items() if k in nums('congress.geojson')},
       'borough': BOROUGH, 'mayor': MAYOR}
# The November 3, 2026 ballot (raw/ballot/candidates.json, from ballot.py): each district's race and, on each sitting
# member, where they're running (engine/ballot.py; the Assembly is its "house"). The card shows them until election day.
BAL = os.path.join(HERE, 'raw', 'ballot', 'candidates.json')
if os.path.exists(BAL):
    import sys; sys.path.insert(0, os.path.join(HERE, '..', '..', 'engine'))
    from ballot import ballot_tables, same
    cand = json.load(open(BAL))
    tables = ballot_tables(cand, {'congress': out['congress'], 'house': out['assembly'], 'senate': out['senate']})
    tables['race_assembly'] = tables.pop('race_house')
    tables['race_statewide']['proposals'].pop('parties', None)   # the Charter questions are yes or no
    # A council seat on this ballot (a special election): the race, and whether the sitting member is in it.
    tables['race_council'] = {d: {'candidates': [c[0] for c in cs], 'parties': [c[1] for c in cs]} for d, cs in cand['races']['council'].items()}
    for d in tables['race_council']:
        m = out['council'].get(d)
        if m: m['runs'] = {'office': 'council', 'district': d} if any(same(m['name'], c[0]) for c in cand['races']['council'][d]) else None
    out.update(tables)

# The tri-state region beyond the City (raw/region/, fetch_region.py): every lower-house, state Senate and congressional
# district that reaches the map's counties in New York, New Jersey and Connecticut, as card-only boundary files
# (docs/nyc/data/region_house.geojson, region_senate, region_congress: k = state and number, "NJ-14", st, num, lab, and
# on lower-house districts role) and tables keyed by k, for card.reps.outside. New Jersey elects two Assembly members per
# legislative district, so its region_house entries are lists.
RG = os.path.join(HERE, 'raw', 'region')
if os.path.exists(os.path.join(RG, 'lower.geojson')):
    import re
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union
    base = json.load(open(os.path.join(DATA, 'base.geojson')))['features']
    CITYG = unary_union([shape(f['geometry']).buffer(0) for f in base if f['properties']['kind'] == 'city' and f['geometry']]).buffer(0)
    REG = unary_union([shape(f['geometry']).buffer(0) for f in base if f['properties']['kind'] == 'neighbour' and f['geometry']]).buffer(0)
    REACH, CLIP = REG.difference(CITYG.buffer(0.002)).buffer(-0.002), REG.buffer(0.01)
    ST = {'36': 'NY', '34': 'NJ', '09': 'CT'}
    # Each member's official page, in order of preference: Connecticut's caucus pages are members' own pages; the
    # General Assembly's is a list of their bills.
    SITE = {'NJ': ('njleg.state.nj.us', 'pub.njleg.gov', 'njleg.gov'), 'CT': ('housedems.ct.gov', 'cthousegop.com', 'senatedems.ct.gov', 'ctsenaterepublicans.com', 'cga.ct.gov')}
    r5 = lambda v: round(float(v), 5)
    members = {'lower': {}, 'upper': {}, 'congress': {}}
    for k, v in assembly.items(): members['lower']['NY-' + k] = v
    for k, v in senate.items(): members['upper']['NY-' + k] = v
    for st in ('NJ', 'CT'):
        p = os.path.join(RG, st.lower() + '.csv')
        if not os.path.exists(p): continue
        for r in csv.DictReader(open(p, encoding='utf-8')):
            d = re.sub(r'\D', '', r['current_district'] or '')
            if not d: continue
            links = [l for l in r['links'].split(';') if l]
            url = next((l for s in SITE[st] for l in links if s in l), links[0] if links else '')
            e = {'name': r['name'], 'url': url, 'party': PARTY.get(r['current_party'], r['current_party'])}
            k = st + '-' + str(int(d))
            if st == 'NJ' and r['current_chamber'] == 'lower':
                members['lower'].setdefault(k, []).append(e)
            else:
                members[r['current_chamber']][k] = e
    for k, v in members['lower'].items():
        if isinstance(v, list): v.sort(key=lambda e: e['name'].split()[-1])
    for m in ET.parse(os.path.join(SRC, 'house.xml')).getroot().find('members'):
        sd, name = m.findtext('statedistrict') or '', m.findtext('member-info/official-name')
        if sd[:2] in ('NY', 'NJ', 'CT') and name:
            members['congress'][sd[:2] + '-' + str(int(sd[2:]))] = {'name': name, 'url': 'https://clerk.house.gov/members/' + m.findtext('member-info/bioguideID'),
                                                                   'party': PARTY.get(m.findtext('member-info/party'), m.findtext('member-info/party'))}
    LAB = {'lower': {'NY': 'NY Assembly District {}', 'NJ': 'NJ Legislative District {}', 'CT': 'CT House District {}'},
           'upper': {'NY': 'NY Senate District {}', 'NJ': 'NJ Legislative District {}', 'CT': 'CT Senate District {}'},
           'congress': {s: s + '-{}' for s in ('NY', 'NJ', 'CT')}}
    ROLE = {'NY': 'Assembly member', 'NJ': 'Assembly member', 'CT': 'State representative'}
    for src, table in (('lower', 'region_house'), ('upper', 'region_senate'), ('congress', 'region_congress')):
        feats, keys = [], set()
        for f in json.load(open(os.path.join(RG, src + '.geojson')))['features']:
            pr = f['properties']; g = shape(f['geometry']).buffer(0)
            if pr.get('STATE') not in ST or not re.search(r'\d', pr.get('BASENAME') or '') or not g.intersects(REACH): continue   # ZZ: water
            g = g.intersection(CLIP).simplify(0.0003, preserve_topology=True)
            if g.is_empty: continue
            st, num = ST[pr['STATE']], str(int(re.sub(r'\D', '', pr['BASENAME'])))
            k = st + '-' + num; keys.add(k)
            p = {'k': k, 'st': st, 'num': num, 'lab': LAB[src][st].format(num)}
            if src == 'lower': p['role'] = ROLE[st]
            feats.append({'type': 'Feature', 'properties': p, 'geometry': json.loads(json.dumps(mapping(g)), parse_float=r5)})
        json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(DATA, table + '.geojson'), 'w'), separators=(',', ':'))
        out[table] = {k: v for k, v in members[src].items() if k in keys}
        print(table, len(feats), 'districts ·', len(out[table]), 'with members · vacant/missing', sorted(keys - set(out[table])),
              '· NJ pairs', sum(1 for v in out[table].values() if isinstance(v, list) and len(v) == 2))

old = json.load(open(OUT)) if os.path.exists(OUT) else {}
same = {k: v for k, v in old.items() if k != 'updated'} == out
out = {'updated': old['updated'] if same and old.get('updated') else datetime.date.today().isoformat(), **out}
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=0)
for t, f in [('council', 'council.geojson'), ('assembly', 'assembly.geojson'), ('senate', 'senate.geojson'), ('congress', 'congress.geojson')]:
    print(t, len(out[t]), 'of', len(nums(f)), '· vacant or unmatched:', sorted(nums(f) - set(out[t]), key=int))
print('updated', out['updated'])
