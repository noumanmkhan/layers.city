"""Match the current officeholders to the map's districts. Output: docs/dallas/data/representatives.json

{"updated": date of the last change, "council": {"1": {"name", "url"}}, "house": {...}, "senate": {...}, "congress": {...},
 "race_congress"/"race_house"/"race_senate"/"race_statewide": the November 3, 2026 races (engine/ballot.py); members carry "runs"}
House, Senate and Congress entries also carry "party". A seat with no current holder is left out, and the page shows
it as vacant. "updated" only moves when a name, party or link changes.

- Council: the City of Dallas council district layer names each district's council member (COUNCILPER).
- Texas House and Senate: Open States' current Texas legislators (raw/representatives/tx.csv).
- U.S. House: the Clerk of the House member list. Members sit for the districts they were elected on (PLANC2193), so
  the card looks the seat up in us_house_2021.geojson until the new members take office on January 3, 2027.
"""
import csv, datetime, json, os, xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'raw', 'representatives')
DATA = os.path.join(HERE, '..', '..', 'docs', 'dallas', 'data')
OUT = os.path.join(DATA, 'representatives.json')
nums = lambda f: {str(x['properties']['num']) for x in json.load(open(os.path.join(DATA, f)))['features']}
PARTY = {'D': 'Democrat', 'R': 'Republican', 'Democratic': 'Democrat', 'Republican': 'Republican', 'I': 'Independent'}

council = {}
for f in json.load(open(os.path.join(HERE, 'raw', 'dallas_council.geojson')))['features']:
    n, who = str(int(f['properties']['COUNCIL'])), (f['properties'].get('COUNCILPER') or '').strip()
    if who: council[n] = {'name': who, 'url': f'https://dallascityhall.com/government/citycouncil/district{n}/Pages/default.aspx'}

house, senate = {}, {}
for r in csv.DictReader(open(os.path.join(SRC, 'tx.csv'), encoding='utf-8')):
    links = r['links'].split(';')
    if r['current_chamber'] == 'lower':
        url = next((l for l in links if 'member-page' in l), next((l for l in links if 'house.texas.gov' in l), ''))
    else:
        url = next((l for l in links if 'senate.texas.gov' in l), '')
    entry = {'name': r['name'], 'url': url, 'party': PARTY.get(r['current_party'], r['current_party'])}
    (house if r['current_chamber'] == 'lower' else senate)[str(int(r['current_district']))] = entry

congress = {}
for m in ET.parse(os.path.join(SRC, 'house.xml')).getroot().find('members'):
    sd, name = m.findtext('statedistrict') or '', m.findtext('member-info/official-name')
    if not sd.startswith('TX') or not name: continue
    congress[str(int(sd[2:]))] = {'name': name, 'url': 'https://clerk.house.gov/members/' + m.findtext('member-info/bioguideID'),
                                  'party': PARTY.get(m.findtext('member-info/party'), m.findtext('member-info/party'))}

out = {'council': {k: v for k, v in council.items() if k in nums('council.geojson')},
       'house': {k: v for k, v in house.items() if k in nums('tx_house.geojson')},
       'senate': {k: v for k, v in senate.items() if k in nums('tx_senate.geojson')},
       'congress': {k: v for k, v in congress.items() if k in nums('us_house_2021.geojson')}}

# The November 3, 2026 ballot (raw/ballot/candidates.json, from ballot.py): each district's race and, on each sitting
# member, where they're running (engine/ballot.py). The card shows the races until election day.
BAL = os.path.join(HERE, 'raw', 'ballot', 'candidates.json')
if os.path.exists(BAL):
    import sys; sys.path.insert(0, os.path.join(HERE, '..', '..', 'engine'))
    from ballot import ballot_tables
    out.update(ballot_tables(json.load(open(BAL)), {k: out[k] for k in ('congress', 'house', 'senate')}))
old = json.load(open(OUT)) if os.path.exists(OUT) else {}
same = {k: v for k, v in old.items() if k != 'updated'} == out
out = {'updated': old['updated'] if same and old.get('updated') else datetime.date.today().isoformat(), **out}
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=0)
print('representatives:', {k: len(v) for k, v in out.items() if k != 'updated'}, 'updated', out['updated'],
      '· missing council', sorted(nums('council.geojson') - set(out['council'])), 'house', sorted(nums('tx_house.geojson') - set(out['house'])),
      'senate', sorted(nums('tx_senate.geojson') - set(out['senate'])), 'congress', sorted(nums('us_house_2021.geojson') - set(out['congress'])))
