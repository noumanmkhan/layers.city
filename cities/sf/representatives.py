"""Match the current officeholders to the map's districts. Output: docs/sf/data/representatives.json and
docs/sf/data/us_house_2021.geojson (the card's lookup of the sitting U.S. representative).

{"updated": date of the last change, "sup": {"1": {"name", "url"}}, "assembly": {...}, "senate": {...},
 "congress": {...}, "mayor": {"city": {...}}}
Assembly, Senate and Congress entries also carry "party". A seat with no current holder is left out, and the page
shows it as vacant. "updated" only moves when a name, party or link changes.

- Supervisors and the mayor: hand-kept below (SUPERVISORS, MAYOR). The Board's own site gives scripts empty pages
  and DataSF's district file still names a supervisor recalled in 2025. Checked October 30, 2026 against the Board's
  pages on sf.gov and Wikipedia's list: Alan Wong (District 4) was appointed in December 2025 and won the June 2,
  2026 special election; Districts 2, 4, 6, 8 and 10 are on the November 3, 2026 ballot (new terms start January 8,
  2027). Update the names after the results are certified.
- State Assembly and Senate: Open States' current California legislators (raw/representatives/ca.csv).
- U.S. House: the Clerk of the House member list. Members sit for the 2021 districts they were elected on, so the card
  looks the seat up in us_house_2021.geojson until the Proposition 50 members take office on January 3, 2027.
"""
import csv, datetime, json, os, xml.etree.ElementTree as ET
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'raw', 'representatives')
DATA = os.path.join(HERE, '..', '..', 'docs', 'sf', 'data')
OUT = os.path.join(DATA, 'representatives.json')
PARTY = {'D': 'Democrat', 'R': 'Republican', 'Democratic': 'Democrat', 'Republican': 'Republican', 'I': 'Independent'}

SUPERVISORS = {'1': 'Connie Chan', '2': 'Stephen Sherrill', '3': 'Danny Sauter', '4': 'Alan Wong', '5': 'Bilal Mahmood',
               '6': 'Matt Dorsey', '7': 'Myrna Melgar', '8': 'Rafael Mandelman', '9': 'Jackie Fielder',
               '10': 'Shamann Walton', '11': 'Chyanne Chen'}
MAYOR = {'name': 'Daniel Lurie', 'url': 'https://www.sf.gov/mayor'}

feats = lambda f: json.load(open(os.path.join(DATA, f)))['features']
nums = lambda f: {str(x['properties']['num']) for x in feats(f)}

# The 2021 congressional districts, cut to the city's land (the supervisor districts) so the card only finds the
# ones that cover it.
city = unary_union([shape(f['geometry']) for f in feats('supervisors.geojson')]).buffer(0)
rnd = lambda c: [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 5), round(c[1], 5)]
us = []
for f in json.load(open(os.path.join(SRC, 'us_house_2021.geojson')))['features']:
    g = shape(f['geometry']).intersection(city)
    if g.area < 1e-7: continue
    m = mapping(g)
    us.append({'type': 'Feature', 'properties': {'num': int(f['properties']['CD119FP'])},
               'geometry': {'type': m['type'], 'coordinates': rnd(m['coordinates'])}})
json.dump({'type': 'FeatureCollection', 'features': us}, open(os.path.join(DATA, 'us_house_2021.geojson'), 'w'), separators=(',', ':'))

sup = {n: {'name': who, 'url': f'https://www.sf.gov/department-district-{n}'} for n, who in SUPERVISORS.items()}

assembly, senate = {}, {}
for r in csv.DictReader(open(os.path.join(SRC, 'ca.csv'), encoding='utf-8')):
    if not r['current_district']: continue
    n, links = str(int(r['current_district'])), [l for l in r['links'].split(';') if l]
    if r['current_chamber'] == 'lower':
        url = next((l for l in links if f'a{n}.asmdc.org' in l or f'ad{n}.asmrc.org' in l), next((l for l in links if 'asmdc.org' in l or 'asmrc.org' in l), 'https://www.assembly.ca.gov/assemblymembers'))
    else:
        url = next((l for l in links if f'sd{n}.senate.ca.gov' in l), next((l for l in links if 'senate.ca.gov' in l), 'https://www.senate.ca.gov/senators'))
    (assembly if r['current_chamber'] == 'lower' else senate)[n] = {'name': r['name'], 'url': url.rstrip('/') + '/', 'party': PARTY.get(r['current_party'], r['current_party'])}

congress = {}
for m in ET.parse(os.path.join(SRC, 'house.xml')).getroot().find('members'):
    sd, name = m.findtext('statedistrict') or '', m.findtext('member-info/official-name')
    if not sd.startswith('CA') or not name: continue
    congress[str(int(sd[2:]))] = {'name': name, 'url': 'https://clerk.house.gov/members/' + m.findtext('member-info/bioguideID'),
                                  'party': PARTY.get(m.findtext('member-info/party'), m.findtext('member-info/party'))}

out = {'sup': {k: v for k, v in sup.items() if k in nums('supervisors.geojson')},
       'assembly': {k: v for k, v in assembly.items() if k in nums('assembly.geojson')},
       'senate': {k: v for k, v in senate.items() if k in nums('senate.geojson')},
       'congress': {k: v for k, v in congress.items() if k in {str(f['properties']['num']) for f in us}},
       'mayor': {'city': MAYOR}}
old = json.load(open(OUT)) if os.path.exists(OUT) else {}
same = {k: v for k, v in old.items() if k != 'updated'} == out
out = {'updated': old['updated'] if same and old.get('updated') else datetime.date.today().isoformat(), **out}
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=0)
print('representatives:', {k: len(v) for k, v in out.items() if k != 'updated'}, 'updated', out['updated'])
for k in ('assembly', 'senate', 'congress'): print(' ', k, {n: (v['name'], v['party'], v['url']) for n, v in out[k].items()})
