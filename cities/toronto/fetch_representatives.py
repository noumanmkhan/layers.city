"""Fetch the current elected representatives for Toronto from each government's own website.
Run from GitHub Actions (weekly, and on demand); writes raw/representatives/.

  ourcommons.xml   House of Commons, current members (ourcommons.ca/Members/en/search/XML)
  ola.html         Legislative Assembly of Ontario, current members (ola.org/en/members/current)
  toronto.json     City of Toronto: the <title> of each ward councillor's page on toronto.ca
                   (councillor-ward-1 ... councillor-ward-25), which names the current councillor
  mayor.json       the <title> of the Mayor's "About the Mayor" page on toronto.ca
                   ("Olivia Chow, 66th Mayor of Toronto"), the same way
  results.json     City of Toronto election results file (mediaresults.toronto.ca). Lists every
                   2026 candidate by office and ward; on election night it fills in the votes.
                   Used for the school board trustee rows. Optional: a failed fetch keeps the last copy.

Open North's Represent API was considered and not used: its House of Commons list lagged a
by-election by months. Taking names from the same pages the site links to keeps them in step."""
import json, os, re, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'representatives'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)', 'Accept-Language': 'en'}
WARD = 'https://www.toronto.ca/city-government/council/members-of-council/councillor-ward-{}/'
RESULTS = 'https://mediaresults.toronto.ca/results/unofficialresult.json'
MAYOR = 'https://www.toronto.ca/city-government/council/office-of-the-mayor/about-mayor/'


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            print('  retry', i + 1, url, e)
            if e.code in (401, 403, 404): break   # a refusal, not a blip: retrying won't change it
            time.sleep(5 * (i + 1))
        except Exception as e:
            print('  retry', i + 1, url, e); time.sleep(5 * (i + 1))
    raise SystemExit('failed: ' + url)


def keep(name, url):
    """Fetch url into raw/representatives/<name>; if the site refuses or is down, keep the committed copy
    (MPs and MPPs change only at by-elections) so one blocked source can't stop the rest, such as
    the election-night results."""
    path = os.path.join(OUT, name)
    try:
        data = get(url)   # fetch before opening the file, which would empty the last copy
    except SystemExit as e:
        if not os.path.exists(path): raise
        print('  ! %s not refreshed; keeping the last copy:' % name, e)
        return
    open(path, 'wb').write(data)


keep('ourcommons.xml', 'https://www.ourcommons.ca/Members/en/search/XML')
keep('ola.html', 'https://www.ola.org/en/members/current')
wards = {}
for n in range(1, 26):
    html = get(WARD.format(n)).decode('utf-8', 'replace')
    m = re.search(r'<title>(.*?)</title>', html, re.S)
    wards[n] = {'url': WARD.format(n), 'title': re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''}
    print(n, wards[n]['title'])
    time.sleep(1.5)   # one page at a time; the City's servers dislike bursts
json.dump(wards, open(os.path.join(OUT, 'toronto.json'), 'w'), indent=1, ensure_ascii=False)
html = get(MAYOR).decode('utf-8', 'replace')
m = re.search(r'<title>(.*?)</title>', html, re.S)
mayor = {'url': MAYOR, 'title': re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''}
print('mayor', mayor['title'])
json.dump(mayor, open(os.path.join(OUT, 'mayor.json'), 'w'), indent=1, ensure_ascii=False)
try:
    res = json.loads(get(RESULTS, tries=3))
    json.dump(res, open(os.path.join(OUT, 'results.json'), 'w'), indent=1, ensure_ascii=False)
    print('results:', res.get('electionDesc'), [o['name'] for o in res['office']])
except (SystemExit, ValueError, KeyError) as e:
    print('  ! election results not fetched; keeping the last copy:', e)
print('done')
