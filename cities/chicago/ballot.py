"""Races on the November 3, 2026 ballot for the card's ballot rows, from the Chicago Board of Elections'
candidate list (raw/school_board/cboe_candidate_list.pdf, fetched by fetch_school_board.py; it lists every office
whose district includes any of Chicago) -> raw/ballot/candidates.json.

  {"source", "asof", "races": {"statewide": {"ussenate": [[name, party], ...], "governor": [...]},
   "congress": {"7": [[name, party], ...]}, "house": {...}, "senate": {...}},
   "covered": {"senate": [...]}}

Ballot order is the board's. Write-in lines are skipped. The list covers every district that includes part of
Chicago, so a covered Illinois Senate district with no race is not on the ballot this year (see below). Run by hand after a new list is fetched (needs pypdf)."""
import json, os, re, sys
from pypdf import PdfReader

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'raw', 'school_board', 'cboe_candidate_list.pdf')
OUT = os.path.join(HERE, 'raw', 'ballot', 'candidates.json')
DATA = os.path.join(HERE, '..', '..', 'docs', 'chicago', 'data')
os.makedirs(os.path.dirname(OUT), exist_ok=True)

text = '\n'.join(p.extract_text() or '' for p in PdfReader(SRC).pages)
status = re.search(r'Status as of (\d+)/(\d+)/(\d{4})', text)
HEADS = [(r'^United States Senator$', 'statewide', 'ussenate'), (r'^Governor & Lieutenant Governor$', 'statewide', 'governor'),
         (r'^U\.S\. Representative, (\d+)\w\w District$', 'congress', None),
         (r'^State Senator, (\d+)\w\w District$', 'senate', None),
         (r'^State Representative, (\d+)\w\w District$', 'house', None)]
races = {'statewide': {}, 'congress': {}, 'house': {}, 'senate': {}}
cur = None
for line in text.splitlines():
    line = line.strip()
    for pat, kind, key in HEADS:
        m = re.match(pat, line)
        if m: cur = races[kind].setdefault(key or m.group(1), []); break
    else:
        c = re.match(r'^\(\d+\)\s+(.+?)\s+\(([^()]+)\)\s+Candidate$', line)
        if c and cur is not None: cur.append([c.group(1), c.group(2)])
        elif cur is not None and not line.startswith(('Vote for', 'Write-in', 'Ballot No.', 'Page ')) and not c:
            if cur: cur = None   # the next office has started

# Only the Senate needs it: every Illinois House and U.S. House seat is elected every two years, so a House district
# missing from the list just grazes the city in the map's file; Senate terms are staggered, so a missing one isn't up.
# A Senate district counts when one of its House districts is on the list (so it really includes part of Chicago).
hs = {str(f['properties']['num']): str(f['properties']['senate']) for f in json.load(open(os.path.join(DATA, 'il_house.geojson')))['features']}
covered = {'senate': sorted({hs[h] for h in races['house'] if h in hs}, key=int)}
out = {'source': 'Chicago Board of Elections, Candidate List for the November 3, 2026 General Election',
       'asof': '%s-%02d-%02d' % (status.group(3), int(status.group(1)), int(status.group(2))) if status else None,
       'races': races, 'covered': covered}
json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
for kind, rs in races.items():
    for k, cs in rs.items(): print(kind, k, cs)
print('senate seats not up:', [d for d in covered['senate'] if d not in races['senate']])
bad = [(k, d) for k in ('congress', 'house', 'senate') for d, cs in races[k].items() if not cs] + \
      [('statewide', s) for s in ('ussenate', 'governor') if not races['statewide'].get(s)]
if bad: sys.exit('races with no candidates read: %s' % bad)
