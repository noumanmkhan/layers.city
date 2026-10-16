"""Races on the November 3, 2026 ballot for the card's ballot rows, from Dallas County's official sample ballot
(raw/ballot/dallas_county_2026-11-03.pdf, fetched by fetch_ballot.py) -> raw/ballot/candidates.json.

  {"source", "asof", "races": {"statewide": {"ussenate": [[name, party], ...], "governor": [...]},
   "congress": {"30": [[name, party], ...]}, "house": {...}, "senate": {...}},
   "covered": {"senate": [...]}}

The PDF is a picture of the printed ballot (no text layer), so this reads it with OCR: each page is rendered at
300 dpi, cut into its three columns (the printed column rules are found on the page), cleaned of the grey
"SAMPLE" watermark and shading, and read with Tesseract. Races are a heading ("United States Representative,
District 30") followed by one line per candidate ending in a party code (Rep, Dem, Lib, Grn). Ballot order is kept.
Run by hand after a new ballot is fetched (needs pdftoppm, tesseract and Pillow); the JSON is committed so the
regular build needs none of them. Check the names against the PDF after each run: OCR can misread.

"covered" lists, for each kind, the districts that reach into Dallas County, whose races (if any) are on this
ballot: a covered district with no race is not on the ballot this year. Districts that touch the city only in
Collin, Denton, Kaufman or Rockwall counties aren't covered, so the card says nothing about their races."""
import json, os, re, subprocess, sys, tempfile
from PIL import Image
from shapely.geometry import shape

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'raw', 'ballot', 'dallas_county_2026-11-03.pdf')
OUT = os.path.join(HERE, 'raw', 'ballot', 'candidates.json')
DATA = os.path.join(HERE, '..', '..', 'docs', 'dallas', 'data')

tmp = tempfile.mkdtemp()
subprocess.run(['pdftoppm', '-r', '300', '-png', SRC, os.path.join(tmp, 'p')], check=True)
pages = sorted(f for f in os.listdir(tmp) if f.startswith('p-'))


def rules(im):
    """x positions of the printed column rules: dark vertical lines over most of the page height."""
    w, h = im.size; px = im.load(); xs = []
    for x in range(w):
        dark = sum(1 for y in range(int(h * .1), int(h * .9), 4) if px[x, y] < 100)
        if dark > (h * .8 / 4) * .6: xs.append(x)
    runs = []
    for x in xs:
        if runs and x - runs[-1][-1] <= 3: runs[-1].append(x)
        else: runs.append([x])
    return [r[0] for r in runs]


text = []
for p in pages:
    im = Image.open(os.path.join(tmp, p)).convert('L')
    edges = rules(im)
    for a, b in zip(edges, edges[1:]):
        col = im.crop((a + 6, 0, b - 6, im.size[1])).point(lambda v: 0 if v < 110 else 255)
        f = os.path.join(tmp, 'col.png'); col.save(f)
        text.append(subprocess.run(['tesseract', f, '-', '--psm', '4'], capture_output=True, text=True, check=True).stdout)
text = '\n'.join(text)

HEADS = [(r'^United States Senator$', 'statewide', 'ussenate'), (r'^Governor$', 'statewide', 'governor'),
         (r'^United States Representative, District (\d+)$', 'congress', None),
         (r'^State Senator, District (\d+)$', 'senate', None),
         (r'^State Representative, District (\d+)$', 'house', None)]
races = {'statewide': {}, 'congress': {}, 'house': {}, 'senate': {}}
cur = None
for line in text.splitlines():
    line = line.strip()
    if not line: continue
    for pat, kind, key in HEADS:
        m = re.match(pat, line)
        if m:
            cur = races[kind].setdefault(key or m.group(1), []); break
    else:
        c = re.match(r'^[©oO0®@.,:\s]*([A-Z][^©]*?)\s+(Rep|Dem|Lib|Grn|Ind)$', line)
        # OCR reads a generational suffix's I as l ("Haynes Ill"): put it back.
        if c and cur is not None: cur.append([re.sub(r'\s(I|l)(I|l)(I|l)?$', lambda m: ' ' + 'I' * len(m.group(0).strip()), c.group(1).strip()), c.group(2)])
        elif cur is not None and (line.startswith(('Write-in', 'Vote for')) or re.match(r'^[A-Z][a-z]+.*,\s*(District|Place)', line)
                                  or line in ('Governor', 'Lieutenant Governor')):
            if cur: cur = None   # the race's candidates have ended

# Districts reaching into Dallas County, from the map's own files.
dc = [shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(DATA, 'counties.geojson')))['features']
      if f['properties']['name'] == 'Dallas County'][0]
covered = {}
# Senate only: every Texas House and U.S. House seat is up every two years; Texas Senate terms are staggered.
for kind, file in (('senate', 'tx_senate'),):
    covered[kind] = sorted((str(f['properties']['num']) for f in json.load(open(os.path.join(DATA, file + '.geojson')))['features']
                            # a real share of the district, not a sliver where two boundary files disagree
                            if shape(f['geometry']).buffer(0).intersection(dc).area > .02 * shape(f['geometry']).buffer(0).area), key=int)

out = {'source': 'Dallas County Elections Department, Countywide Sample Ballot, General and Joint Election, November 3, 2026',
       'asof': '2026-10-16', 'races': races, 'covered': covered}
json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
for kind, rs in races.items():
    for k, cs in rs.items(): print(kind, k, cs)
bad = [(k, d) for k in ('congress', 'house', 'senate') for d, cs in races[k].items() if not cs] + \
      [('statewide', s) for s in ('ussenate', 'governor') if not races['statewide'].get(s)]
if bad: sys.exit('races with no candidates read: %s' % bad)
