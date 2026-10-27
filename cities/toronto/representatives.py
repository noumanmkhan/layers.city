"""Who represents each part of Toronto, with a link to their official page.
Inputs: raw/representatives/ (fetched by fetch_representatives.py), and the map's ward and
federal riding files for the names to match against.
Output: docs/toronto/data/representatives.json
  {"updated": date, "wards": {"11": {name, url}}, "prov": {"University—Rosedale": {name, party, url}},
   "fed": {"University—Rosedale": {name, party, url}},
   "trustees": {"tdsb": {"7": {candidates: [...], winner?, acclaimed?}}, "tcdsb": ..., "viamonde": ..., "monavenir": ...},
   "council": {"19": {candidates: [...], incumbentRunning: bool, incumbentElsewhere?: {office, ward?}, winner?, acclaimed?}},
   "mayor": {"city": {name, url}}, "mayorRace": {"city": {candidates: [...], incumbentRunning: bool, winner?}}}

Provincial ridings in Toronto share the wards' lines, so a ward's 'prov' name is the riding.
Councillors have no party: Toronto's municipal elections are non-partisan."""
import html, json, os, re, sys, unicodedata, datetime as dt
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'representatives')
DOCS = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data')


def key(s):
    """Riding names differ in dashes, accents and apostrophes between sources; compare loosely."""
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


wards = json.load(open(os.path.join(DOCS, 'wards.geojson')))['features']
feds = [f['properties']['name'] for f in json.load(open(os.path.join(DOCS, 'federal.geojson')))['features']]
provs = sorted({f['properties']['prov'] for f in wards})
problems = []

# City councillors: "Councillor Dianne Saxe – City of Toronto"
tor = json.load(open(os.path.join(RAW, 'toronto.json')))
out_w = {}
for n, v in tor.items():
    m = re.match(r'Councillor\s+(.+?)\s+[–\-|]', html.unescape(v['title']))
    if m: out_w[n] = {'name': m.group(1).strip(), 'url': v['url']}
    else: out_w[n] = {'name': None, 'url': v['url']}; problems.append('ward %s: no name in %r' % (n, v['title']))

# The mayor: "Olivia Chow, 66th Mayor of Toronto – City of Toronto" (or "Mayor Olivia Chow – ..."). The citywide
# seat is keyed "city" so the card can look it up like any other office.
out_m = None
try:
    mv = json.load(open(os.path.join(RAW, 'mayor.json')))
except FileNotFoundError:
    mv = None
if mv:
    t = html.unescape(mv['title'])
    m = re.match(r'(.+?),\s*\d+\w*\s+Mayor', t) or re.match(r'Mayor\s+(.+?)\s+[–\-|]', t)
    out_m = {'city': {'name': m.group(1).strip() if m else None, 'url': mv['url']}}
    if not m: problems.append('mayor: no name in %r' % t)
else:
    problems.append('no mayor page fetched yet (raw/representatives/mayor.json)')

# MPPs: cards with a link, a name, a party and a riding.
page = open(os.path.join(RAW, 'ola.html'), encoding='utf-8').read()
ola = {}
clean = lambda t: re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', '', t))).strip()
for card in page.split('class="mpp-card-link"')[1:]:
    name = re.search(r'<h3[^>]*>(.*?)</h3>', card, re.S)
    party = re.search(r'current-members-party">(.*?)</p>', card, re.S)
    riding = re.search(r'current-members-riding">(.*?)</p>', card, re.S)
    if not (name and party and riding): continue
    ola.setdefault(key(clean(riding.group(1))), {'name': clean(name.group(1)), 'party': clean(party.group(1)), 'href': None})
# The link sits just before each card's class attribute, so pair them up separately.
for href, card in re.findall(r'<a href="(/en/members/all/[^"]+)" class="mpp-card-link">(.{0,3000}?)</a>', page, re.S):
    riding = re.search(r'current-members-riding">(.*?)</p>', card, re.S)
    if riding and key(clean(riding.group(1))) in ola:
        ola[key(clean(riding.group(1)))]['url'] = 'https://www.ola.org' + href
for v in ola.values(): v.pop('href', None)
out_p = {}
for r in provs:
    if key(r) in ola: out_p[r] = ola[key(r)]
    else: out_p[r] = None; problems.append('MPP not found: ' + r)

# MPs: the House of Commons' list of current members.
root = ET.parse(os.path.join(RAW, 'ourcommons.xml')).getroot()
com = {}
for m in root.iter('MemberOfParliament'):
    g = lambda t: (m.findtext(t) or '').strip()
    if g('ConstituencyProvinceTerritoryName') != 'Ontario': continue
    name = g('PersonOfficialFirstName') + ' ' + g('PersonOfficialLastName')
    com[key(g('ConstituencyName'))] = {'name': name, 'party': g('CaucusShortName'),
                                       'url': 'https://www.ourcommons.ca/Members/en/%s(%s)' % (slug(name), g('PersonId'))}
out_f = {}
for r in feds:
    if key(r) in com: out_f[r] = com[key(r)]
    else: out_f[r] = None; problems.append('MP not found (seat may be vacant): ' + r)

# School board trustees, from the City's election results file. Each board's wards carry their
# candidates; once every poll in a ward has reported, the one with the most votes is the winner
# (unofficial until the Clerk certifies). A ward with a single candidate was won by acclamation.
# The card decides from the dates in city.json whether to show the race, the result or the trustee.
BOARDS = {'Toronto District School Board': 'tdsb', 'Toronto Catholic District School Board': 'tcdsb',
          'Conseil scolaire Viamonde': 'viamonde', 'Conseil scolaire catholique MonAvenir': 'monavenir'}
out_t = out_c = out_mr = None
try:
    res = json.load(open(os.path.join(RAW, 'results.json')))
except FileNotFoundError:
    res = None
def num(v):
    """The results file gives counts as text; on election night they may carry thousands separators."""
    return int(re.sub(r'[^0-9]', '', str(v or '')) or 0)


def race(w, what):
    cands = [(c['name'], num(c['votesReceived'])) for c in w['candidate']]
    row = {'candidates': [n for n, _ in cands]}
    if len(cands) == 1:
        row.update(winner=cands[0][0], acclaimed=True)
    elif num(w['polls']) and num(w['pollsReceived']) >= num(w['polls']):
        top = sorted(cands, key=lambda c: -c[1])
        if top[0][1] > top[1][1]: row['winner'] = top[0][0]
        else: problems.append('tie: %s ward %s' % (what, w['num']))
    return row


if res:
    out_t = {}
    for office in res['office']:
        board = BOARDS.get(office['name'])
        if not board: continue
        out_t[board] = {str(w['num']): race(w, board) for w in office['ward']}
    # City council races, for the election view of the ward layer and the councillor row. Whether the sitting
    # councillor is on the ballot is matched by name (loosely), since the results file doesn't say.
    for office in res['office']:
        if office['name'] != 'Councillor': continue
        out_c = {}
        for w in office['ward']:
            row = race(w, 'council')
            inc = (out_w.get(str(w['num'])) or {}).get('name')
            if inc: row['incumbentRunning'] = key(inc) in {key(n) for n in row['candidates']}
            out_c[str(w['num'])] = row
    if out_c is None: problems.append('no council races in the results file')
    for office in res['office']:
        if office['name'] == 'Mayor' and office['ward']:
            out_mr = {'city': race(office['ward'][0], 'mayor')}
            inc = ((out_m or {}).get('city') or {}).get('name')
            if inc: out_mr['city']['incumbentRunning'] = key(inc) in {key(n) for n in out_mr['city']['candidates']}
    # A sitting councillor not on their own ward's ballot may be running for mayor or in another ward: say where.
    if out_c:
        for num, row in out_c.items():
            inc = (out_w.get(num) or {}).get('name')
            if not inc or row.get('incumbentRunning'): continue
            if out_mr and key(inc) in {key(n) for n in out_mr['city']['candidates']}:
                row['incumbentElsewhere'] = {'office': 'mayor'}
            else:
                other = [n for n, r in out_c.items() if n != num and key(inc) in {key(c) for c in r['candidates']}]
                if other: row['incumbentElsewhere'] = {'office': 'council', 'ward': other[0]}
    for b in BOARDS.values():
        if b not in out_t: problems.append('no trustee races for ' + b)

# 'updated' is the date the list last changed, so a weekly run with no news leaves the file untouched.
OUT = os.path.join(DOCS, 'representatives.json')
new = {'wards': out_w, 'prov': out_p, 'fed': out_f}
if out_t is not None: new['trustees'] = out_t
if out_c is not None: new['council'] = out_c
if out_m is not None: new['mayor'] = out_m
if out_mr is not None: new['mayorRace'] = out_mr
try:
    old = json.load(open(OUT))
except Exception:
    old = {}
updated = old.get('updated') if {k: v for k, v in old.items() if k != 'updated'} == new else dt.date.today().isoformat()
json.dump(dict(updated=updated, **new), open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
print('representatives:', sum(1 for v in out_w.values() if v['name']), 'councillors,',
      sum(1 for v in out_p.values() if v), 'MPPs,', sum(1 for v in out_f.values() if v), 'MPs,',
      'trustee races:', {b: len(v) for b, v in (out_t or {}).items()},
      'decided:', sum(1 for v in (out_t or {}).values() for r in v.values() if r.get('winner')),
      'council races:', len(out_c or {}), 'incumbents not running here:', {k: v.get('incumbentElsewhere', 'not running') for k, v in (out_c or {}).items() if v.get('incumbentRunning') is False},
      'mayor:', ((out_m or {}).get('city') or {}).get('name'), 'mayoral candidates:', len(((out_mr or {}).get('city') or {}).get('candidates', [])))
for p in problems: print('  !', p)
# A partial list is still useful (a vacant seat is real), but an empty source means the page changed.
if not ola or not com or not any(v['name'] for v in out_w.values()):
    sys.exit('a source came back empty; the page format may have changed')
