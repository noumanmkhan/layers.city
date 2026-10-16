"""Fetch the official sample ballot for the November 3, 2026 general election, for the card's ballot rows.
Runs in GitHub Actions (fetch-dallas.yml); writes raw/ballot/.

  dallas_county_2026-11-03.pdf   Dallas County Elections Department, "Countywide Sample Ballot" (every race on any
                                 ballot in Dallas County, with party labels), linked from
                                 dallascountyvotes.org/voters/election/november-3-2026-general-and-joint-election/

ballot.py reads it into raw/ballot/candidates.json, which is committed so the regular build needs no PDF reader.
The parts of the city in Collin, Denton, Kaufman and Rockwall counties are covered only where their districts
also reach into Dallas County (see ballot.py's report)."""
import os, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'ballot'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}
SOURCES = [
    ('dallas_county_2026-11-03.pdf',
     'https://www.dallascountyvotes.org/wp-content/uploads/2026/09/Full-Sample-Ballot-Watermark-8.5x14-Legal_110326.pdf'),
]
failed = []
for name, url in SOURCES:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                body = r.read()
            if not body.startswith(b'%PDF'): raise ValueError('not a PDF')
            open(os.path.join(OUT, name), 'wb').write(body)
            print('wrote', name, len(body)); break
        except Exception as e:
            print('retry', attempt + 1, name, e); time.sleep(10)
    else:
        failed.append(name)
if failed: raise SystemExit('failed: ' + ', '.join(failed))
