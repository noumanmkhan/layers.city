"""Fetch where New Yorkers vote on November 3, 2026, into cities/nyc/raw/voting/. Runs in GitHub Actions (fetch-nyc.yml).

- election_districts.geojson: NYC Open Data, Election Districts (wwxk-38u4, Department of City Planning from the Board
  of Elections' lines): each ED as AD + ED ("elect_dist" 23001 = Assembly District 23, ED 001)
- pdf/*.pdf: the Board of Elections' poll site lists for the general election (vote.nyc), one per borough, for election
  day and for early voting: ED by ED, the site's name and address ("SUBJECT TO CHANGE")
- nys_ed.json, nys_ev.json: the State's GIS office's NYC election day (1,206) and early voting (157) poll site points
  (NYS Elections Districts and Polling Locations, NYSGIS_GPO), to place each site
- pages.txt: the links found on vote.nyc's election pages, to find files named differently
voting.py joins them."""
import json, os, re, sys, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, save, step, arcgis, RAW, FAILED

V = os.path.join(RAW, 'voting'); os.makedirs(os.path.join(V, 'pdf'), exist_ok=True)
NYS = 'https://services6.arcgis.com/EbVsqZ18sv1kVJ3k/arcgis/rest/services/NYS_Elections_Districts_and_Polling_Locations/FeatureServer/'
BASE = 'https://www.vote.nyc/sites/default/files/pdf/poll_site_list/GE2026/'


def eds():
    d = json.loads(get('https://data.cityofnewyork.us/resource/wwxk-38u4.geojson?$limit=10000'))
    save(os.path.join('voting', 'election_districts.geojson'), d)
    print('  EDs', len(d['features']), sorted(d['features'][0]['properties']))


def nys():
    arcgis(NYS + '3', os.path.join('voting', 'nys_ed.json'))
    arcgis(NYS + '1', os.path.join('voting', 'nys_ev.json'))


def pdfs():
    links = set()
    for u in ['https://www.vote.nyc/', 'https://www.vote.nyc/elections', 'https://www.vote.nyc/page/poll-site-locations',
              'https://www.vote.nyc/page/early-voting', 'https://www.vote.nyc/page/upcoming-elections']:
        try:
            h = get(u, tries=1).decode('utf-8', 'replace')
            links |= {urllib.parse.urljoin(u, l) for l in re.findall(r'href="([^"]+)"', h)}
        except Exception as e:
            print('  page failed', u, e)
    open(os.path.join(V, 'pages.txt'), 'w').write('\n'.join(sorted(links)))
    found = {l for l in links if 'poll_site_list' in l.lower() and l.lower().endswith('.pdf') and '2026' in l}
    print('  linked poll site lists:', sorted(found))
    for kind in ('Election_Day', 'Early_Voting'):
        for boro in ('New_York', 'Bronx', 'The_Bronx', 'Kings', 'Brooklyn', 'Queens', 'Richmond', 'Staten_Island'):
            for rev in ('', '_r1', '_r2', '_r3'):
                found.add(f'{BASE}Poll_Site_List_Nov_General_2026_{kind}_{boro}{rev}.pdf')
    got = []
    for u in sorted(found):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'city-layers/1.0 (https://layers.city)'}), timeout=90) as r:
                b = r.read()
            if b[:4] != b'%PDF': continue
            name = u.rsplit('/', 1)[1]
            open(os.path.join(V, 'pdf', name), 'wb').write(b); got.append(name); print('  pdf', name, len(b))
        except Exception:
            pass
    print('  pdfs:', got)


for label, fn in [('eds', eds), ('nys', nys), ('pdfs', pdfs)]:
    print('==', label); step(label, fn)
print('FAILED:', FAILED or 'none')
