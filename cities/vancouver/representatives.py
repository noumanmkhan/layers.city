"""Who represents each part of Vancouver, with a link to their official page.
Inputs: raw/representatives/ourcommons.xml (fetch_representatives.py) and the map's federal riding file for the names.
Output: docs/vancouver/data/representatives.json  {"updated": date, "fed": {"Vancouver Centre": {name, party, url}}}

Only MPs for now. Vancouver's mayor and councillors (elected at large, October 17, 2026) and its MLAs (BC votes
October 24, 2026) are added once the results are in; until then the card shows the riding names without people.
"updated" changes only when a name, party or link does, so the weekly job commits nothing in a quiet week."""
import json, os, re, unicodedata
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'representatives')
DOCS = os.path.join(HERE, '..', '..', 'docs', 'vancouver', 'data')
OUT = os.path.join(DOCS, 'representatives.json')


def key(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


feds = [f['properties']['name'] for f in json.load(open(os.path.join(DOCS, 'federal.geojson')))['features']]
com = {}
for m in ET.parse(os.path.join(RAW, 'ourcommons.xml')).getroot().iter('MemberOfParliament'):
    g = lambda t: (m.findtext(t) or '').strip()
    if g('ConstituencyProvinceTerritoryName') != 'British Columbia': continue
    name = g('PersonOfficialFirstName') + ' ' + g('PersonOfficialLastName')
    com[key(g('ConstituencyName'))] = {'name': name, 'party': g('CaucusShortName'),
                                       'url': 'https://www.ourcommons.ca/Members/en/%s(%s)' % (slug(name), g('PersonId'))}
fed, problems = {}, []
for r in feds:
    fed[r] = com.get(key(r))
    if not fed[r]: problems.append('MP not found (seat may be vacant): ' + r)
old = json.load(open(OUT)) if os.path.exists(OUT) else {}
import datetime as dt
out = {'updated': old.get('updated') if old.get('fed') == fed else dt.date.today().isoformat(), 'fed': fed}
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
print('MPs:', {k: (v or {}).get('name') for k, v in fed.items()})
if problems: print('  ' + '\n  '.join(problems))
