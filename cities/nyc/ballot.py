"""Races on the November 3, 2026 ballot for the card's ballot rows, from the NYC Board of Elections' contest list
(raw/ballot/candidates.rtf, fetched by fetch_ballot.py; "tentative, subject to change", printed September 11) ->
raw/ballot/candidates.json:

  {"source", "asof", "races": {"statewide": {"governor": [[name, parties], ...], "comptroller": [...],
   "attorneygeneral": [...], "proposals": [[title, ""], ...]}, "congress": {"10": [...]}, "house": {...} (Assembly),
   "senate": {...}, "council": {"3": [...]}}}

The RTF keeps the list's columns apart (each cell is a frame with its own x position: party, name, address), which
the PDF's text runs together. New York has fusion voting: a candidate can be on several party lines, so each name
appears once with its lines joined, short ("D, WF"), in the order the list gives them (the ballot's party order).
A district that spans counties is listed under each county: the lines are merged. Judicial races (Supreme Court,
Civil Court, Surrogate) are left out: the map has no judicial districts. Run by hand after fetch_ballot.py."""
import json, os, re
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'raw', 'ballot', 'candidates.rtf')
OUT = os.path.join(HERE, 'raw', 'ballot', 'candidates.json')
SHORT = {'Democratic': 'D', 'Republican': 'R', 'Conservative': 'C', 'Working Families': 'WF'}
X_PARTY, X_NAME, X_HEAD = 341, 3461, 191

t = open(SRC, 'rb').read().decode('latin-1')
frames = [(int(x), int(y), re.sub(r'\s+', ' ', s).replace('\\_', '-').replace("\\'", '').strip())
          for x, y, s in re.findall(r'\\posx(\d+)\\posy(\d+)[^{]*\{[^}]*?\\insrsid\d+ ?(.*?)\\par', t, re.S)]
# RTF escapes for accented letters (\'e9) -> the letter
frames = [(x, y, re.sub(r"\\'([0-9a-f]{2})", lambda m: bytes.fromhex(m.group(1)).decode('cp1252'), s)) for x, y, s in frames]
asof = re.search(r'(\d+)/(\d+)/(2026) \d', t)

HEADS = [(r'^Governor/Lieutenant Governor - Citywide', 'statewide', 'governor'), (r'^State Comptroller - Citywide', 'statewide', 'comptroller'),
         (r'^Attorney General - Citywide', 'statewide', 'attorneygeneral'),
         (r'^Representative in Congress - (\d+)\w\w Congressional District', 'congress', None),
         (r'^State Senator - (\d+)\w\w Senatorial District', 'senate', None),
         (r'^Member of the Assembly - (\d+)\w\w Assembly District', 'house', None),
         (r'^Member of the City Council - (\d+)\w\w Council District', 'council', None)]
races = {'statewide': {}, 'congress': {}, 'house': {}, 'senate': {}, 'council': {}}
proposals = OrderedDict()
cur, row = None, {}


def flush():
    global row
    if cur is not None and row.get('name') and row.get('party'):
        lines = cur.setdefault(row['name'], [])
        p = SHORT.get(row['party'], row['party'])
        if p not in lines: lines.append(p)
    row = {}


lasty = None
for x, y, s in frames:
    if y != lasty: flush(); lasty = y
    if x == X_HEAD or (x < X_PARTY and ' # to be elected' in s) or s.startswith('Proposal Number'):
        flush(); cur = None
        m = re.match(r'^Proposal Number (\d), a Question: (?:Proposed Charter Amendment: )?(.+)$', s)
        if m: proposals[int(m.group(1))] = re.sub(r'\s*-\s*Citywide, # to be elected.*$', '', m.group(2)).strip(); continue
        for pat, kind, key in HEADS:
            h = re.match(pat, s)
            if h:
                cur = races[kind].setdefault(key or str(int(h.group(1))), OrderedDict()); break
        continue
    if cur is None: continue
    if x == X_NAME: row['name'] = re.sub(r'(\w)- (\w)', r'\1-\2', s)   # "Brian- Christopher A. Cunningham"
    elif x == X_PARTY: row['party'] = s
flush()

# An independent line named after its own candidate ("Karen Ortiz" on the Karen Ortiz line) adds nothing: left out.
out = {k: {d: [[n, ', '.join(p for p in ps if p != n) or 'independent'] for n, ps in cs.items()] for d, cs in v.items()} for k, v in races.items()}
out['statewide']['proposals'] = [[proposals[k], ''] for k in sorted(proposals)]
json.dump({'source': open(os.path.join(HERE, 'raw', 'ballot', 'source_rtf.txt')).read().strip(),
           'asof': '%s-%02d-%02d' % (asof.group(3), int(asof.group(1)), int(asof.group(2))) if asof else '',
           'races': out}, open(OUT, 'w'), ensure_ascii=False, indent=1)
for k, v in out.items():
    print(k, len(v), 'races' if k != 'statewide' else list(v), '· unopposed:', sorted((d for d, cs in v.items() if len(cs) == 1), key=lambda d: int(d) if d.isdigit() else 0) if k != 'statewide' else '')
for k in ('governor', 'comptroller', 'attorneygeneral'): print(' ', k, out['statewide'][k])
print('  congress 10:', out['congress'].get('10'))
print('  proposals:', [p[0][:60] for p in out['statewide']['proposals']])
print('  every party line:', sorted({p for v in out.values() for cs in v.values() for c in cs for p in c[1].split(', ') if p}))
