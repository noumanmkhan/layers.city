"""Fetch the City's TCS New York City Marathon closure notice (marathon.json) and read its table into
raw/closures/marathon_<year>.json for fetch_closures.py. Run from GitHub Actions (fetch-nyc.yml, and daily from
late October in fetch-closures.yml); the sandbox can't reach nyc.gov.

Writes, for the race year when the City has posted it (and for marathon.json's "test" year, to check the parser):
  marathon_<year>.txt   the notice's text, page by page, as pypdf reads it
  marathon_<year>.json  {year, source, fetched, rows: [{borough, street, from, to, restriction, time, kind}]}
"""
import io, json, os, re, time, urllib.request
from pypdf import PdfReader

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'marathon.json')))
OUT = os.path.join(HERE, 'raw', 'closures'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (city-layers-pipeline; layers.city; go@layers.city)'}


def fetch(year):
    for u in CFG['notice']:
        u = u.format(year=year)
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90) as r:
                b = r.read()
            if b[:4] == b'%PDF': return u, b
            print('  not a PDF:', u)
        except Exception as e:
            print('  no notice at', u, '-', e)
    return None, None


BORO = re.compile(r'^(MANHATTAN|BROOKLYN|QUEENS|BRONX|STATEN ISLAND)\b.*\b(STREET CLOSURES|PARKING RESTRICTIONS|CLOSURES)', re.I)
for year in [CFG['year'], CFG.get('test')]:
    if not year: continue
    url, pdf = fetch(year)
    if not pdf: print(year, ': no notice yet'); continue
    pages = [p.extract_text() or '' for p in PdfReader(io.BytesIO(pdf)).pages]
    open(os.path.join(OUT, f'marathon_{year}.txt'), 'w').write('\n\n=== page break ===\n\n'.join(pages))
    rows, boro, kind = [], None, None
    for line in '\n'.join(pages).splitlines():
        s = re.sub(r'\s+', ' ', line).strip()
        m = BORO.match(s)
        if m:
            boro = m.group(1).title(); kind = 'parking' if 'PARKING' in m.group(2).upper() else 'closed'; continue
        rows.append({'borough': boro, 'kind': kind, 'line': s})
    json.dump({'year': year, 'source': url, 'fetched': time.strftime('%Y-%m-%d'), 'rows': rows},
              open(os.path.join(OUT, f'marathon_{year}.json'), 'w'), indent=0)
    print(year, ':', len(pages), 'pages,', len(rows), 'lines, by borough/kind:',
          {k: sum(1 for r in rows if (r['borough'], r['kind']) == k) for k in {(r['borough'], r['kind']) for r in rows}})
