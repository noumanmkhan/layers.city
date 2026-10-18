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

old = json.load(open(OUT)) if os.path.exists(OUT) else {}
same = {k: v for k, v in old.items() if k != 'updated'} == out
out = {'updated': old['updated'] if same and old.get('updated') else datetime.date.today().isoformat(), **out}
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=0)
for t, f in [('council', 'council.geojson'), ('assembly', 'assembly.geojson'), ('senate', 'senate.geojson'), ('congress', 'congress.geojson')]:
    print(t, len(out[t]), 'of', len(nums(f)), '· vacant or unmatched:', sorted(nums(f) - set(out[t]), key=int))
print('updated', out['updated'])
