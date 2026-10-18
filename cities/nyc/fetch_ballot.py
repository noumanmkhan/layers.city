"""Fetch the NYC Board of Elections' candidate list for the November 3, 2026 general election into
cities/nyc/raw/ballot/ (PDF and its RTF twin), for ballot.py. Runs in GitHub Actions (fetch-nyc.yml): vote.nyc
can't be reached from most sandboxes. The list page names the files by the time they were made, so the newest
"General Contest List" links on vote.nyc/page/list-candidates are found first, with the September 11 files as a
fallback. Prints the first lines of the PDF's text so the parser can be checked against it."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, RAW

OUT = os.path.join(RAW, 'ballot'); os.makedirs(OUT, exist_ok=True)
BASE = 'https://www.vote.nyc'
FALLBACK = {'pdf': '/sites/default/files/pdf/candidates/2026/9_11_2026%2010_26_11%20AM_General%20Contest%20List%20Web%20Version.pdf',
            'rtf': '/sites/default/files/pdf/candidates/2026/9_11_2026%2010_36_13%20AM_General%20Contest%20List%20Web%20Version..rtf'}
page = get(BASE + '/page/list-candidates').decode('utf-8', 'replace')
links = {}
for href in re.findall(r'href="([^"]+)"', page):
    if 'General' in href and 'Contest' in href and '/2026/' in href:
        ext = 'pdf' if href.lower().endswith('.pdf') else 'rtf' if href.lower().endswith('.rtf') else None
        if ext: links.setdefault(ext, href)
for ext in ('pdf', 'rtf'):
    href = links.get(ext) or FALLBACK[ext]
    url = href if href.startswith('http') else BASE + href
    data = get(url)
    open(os.path.join(OUT, 'candidates.' + ext), 'wb').write(data)
    open(os.path.join(OUT, 'source_' + ext + '.txt'), 'w').write(url + '\n')
    print('got', url, len(data) // 1024, 'KB')
from pypdf import PdfReader
text = '\n'.join(p.extract_text() or '' for p in PdfReader(os.path.join(OUT, 'candidates.pdf')).pages)
open(os.path.join(OUT, 'candidates.txt'), 'w').write(text)
print(len(text.splitlines()), 'lines of text')
print('\n'.join(text.splitlines()[:250]))
