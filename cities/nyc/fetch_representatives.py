"""Fetch who currently holds each office the New York City map shows, into cities/nyc/raw/representatives/.
Runs in GitHub Actions (fetch-nyc.yml now; a weekly refresh once NYC is released).

- ny.csv: Open States' current New York legislators (data.openstates.org): Assembly and Senate, district and party
- house.xml: Clerk of the U.S. House member list (current members of Congress, with state and district)
- council.json: each City Council district page's title on council.nyc.gov ("District 1 - <member>"), and the page URL
representatives.py matches them to the map's districts. Borough presidents are hand-kept there (elected 2025).
"""
import json, os, re, sys, time, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, RAW

OUT = os.path.join(RAW, 'representatives')
os.makedirs(OUT, exist_ok=True)
failed = []
for name, url in [('ny.csv', 'https://data.openstates.org/people/current/ny.csv'), ('house.xml', 'https://clerk.house.gov/xml/lists/MemberData.xml')]:
    try:
        b = get(url, tries=3); open(os.path.join(OUT, name), 'wb').write(b); print('wrote', name, len(b))
    except Exception as e:
        print('failed', name, e); failed.append(name)
council = {}
for n in range(1, 52):
    url = f'https://council.nyc.gov/district-{n}/'
    try:
        h = get(url, tries=2).decode('utf-8', 'replace')
        t = html.unescape(re.search(r'<title>(.*?)</title>', h, re.S).group(1)).strip()
        h1 = [html.unescape(re.sub('<[^>]+>', '', x)).strip() for x in re.findall(r'<h1[^>]*>(.*?)</h1>', h, re.S)]
        council[str(n)] = {'title': t, 'h1': h1[:3], 'url': url}
        print(n, t, h1[:2])
    except Exception as e:
        print('failed district', n, e)
    time.sleep(1)
json.dump(council, open(os.path.join(OUT, 'council.json'), 'w'), indent=1, ensure_ascii=False)
print('council pages', len(council), '· failed:', failed or 'none')
