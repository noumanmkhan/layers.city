"""Second pass (November 3, 2026), for the questions the first pass (scout.py) left open:
- Elections Canada: what the Voter Information Service shows for a Scarborough North postal code during the December 7
  by-election (are polling places on a page keyed by district or poll, or only per address?), and the 2026 by-elections page.
- Elections Ontario: the first pass got HTTP 406 (no Accept header); retry with one.
- BC Data Catalogue: what "Provincial Voting Places" holds and how current it is.
Sites that answered the first pass with a bot check (202/403) are left alone: they don't welcome automated readers.
Writes scouting/elections/out/pass2.json and pages in out/pages/p2-*.html.
"""
import html, json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out'); PAGES = os.path.join(OUT, 'pages'); os.makedirs(PAGES, exist_ok=True)
# Identifies itself as a scout (no browser disguise); the Accept header is the ordinary content negotiation the
# first pass lacked, which is what Elections Ontario's 406 asked for.
BROWSER = {'User-Agent': 'layers.city-scout/1.0 (one-off check of public election pages)',
           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-CA,en;q=0.9'}
res = {}


def get(url, data=None, headers=BROWSER, timeout=60):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers, data=data), timeout=timeout) as r:
            return {'url': r.geturl(), 'status': r.status, 'type': r.headers.get('Content-Type', ''), 'body': r.read()}
    except urllib.error.HTTPError as e:
        return {'url': url, 'status': e.code, 'type': '', 'body': e.read() if hasattr(e, 'read') else b''}
    except Exception as e:
        return {'url': url, 'status': None, 'type': '', 'body': b'', 'error': repr(e)}


def t(b): return b.decode('utf-8', 'replace')
def title(h):
    m = re.search(r'<title[^>]*>(.*?)</title>', h, re.S | re.I); return html.unescape(re.sub(r'\s+', ' ', m.group(1))).strip() if m else ''
def links(h, base):
    return [{'text': html.unescape(re.sub(r'<[^>]+>|\s+', ' ', m.group(2))).strip()[:120], 'href': urllib.parse.urljoin(base, html.unescape(m.group(1)))}
            for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', h, re.S | re.I)]
def plain(h, n=3000):
    h = re.sub(r'<(script|style)\b.*?</\1>', ' ', h, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h))).strip()[:n]
def save(name, r):
    if r['body']: open(os.path.join(PAGES, 'p2-' + name), 'wb').write(r['body'][:1_500_000])
def step(name, fn):
    print('\n==', name)
    try: res[name] = fn()
    except Exception as e: print('  FAILED', repr(e)); res[name] = {'error': repr(e)}
    json.dump(res, open(os.path.join(OUT, 'pass2.json'), 'w'), indent=1, ensure_ascii=False, default=str)


EC = 'https://www.elections.ca'
POLL = re.compile(r'advance poll\w*|polling station\w*|polling place\w*|voting place\w*|where (?:do i|to) vote|election day|accessib\w+|by-election', re.I)


def ec_vis():
    out = {}
    form = get(EC + '/Scripts/vis/FindED?L=e&QID=-1&PAGEID=20'); fh = t(form['body'])
    params = {m.group(1): html.unescape(m.group(2)) for m in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)', fh, re.I)}
    params['CommonSearchTxt'] = 'M1V 1V2'
    r = get(EC + '/Scripts/vis/FindED?L=e&QID=-1&PAGEID=20', data=urllib.parse.urlencode(params).encode())
    rh = t(r['body']); save('ec-vis-result.html', r)
    out['result'] = {'status': r['status'], 'url': r['url'], 'title': title(rh), 'text': plain(rh, 2500),
                     'links': [l for l in links(rh, r['url']) if '/vis/' in l['href'].lower() or POLL.search(l['text'])][:50]}
    seen, follow = set(), []
    for l in out['result']['links']:
        if '/vis/' in l['href'].lower() and l['href'] not in seen and len(follow) < 14:
            seen.add(l['href']); follow.append(l)
    out['followed'] = []
    for i, l in enumerate(follow):
        pr = get(l['href']); ph = t(pr['body']); save('ec-vis-%d.html' % i, pr)
        out['followed'].append({'text': l['text'], 'url': pr['url'], 'status': pr['status'], 'title': title(ph),
                                'mentions': sorted(set(m.lower() for m in POLL.findall(ph))),
                                'text_sample': plain(ph, 1500),
                                'links': [x for x in links(ph, pr['url']) if POLL.search(x['text']) or re.search(r'poll|place|station', x['href'], re.I)][:30]})
    return out


def ec_byelections():
    r = get(EC + '/content.aspx?section=ele&dir=2026&document=index&lang=e'); h = t(r['body']); save('ec-2026.html', r)
    m = re.search(r'<main\b.*?</main>', h, re.S | re.I); body = m.group(0) if m else h
    ls = links(body, r['url'])
    out = {'status': r['status'], 'text': plain(body, 2500), 'links': ls[:80], 'pages': {}}
    for l in [l for l in ls if 'elections.ca' in l['href'] and re.search(r'dir=2026|scarborough|35\d{3}', l['href'] + l['text'], re.I)][:8]:
        pr = get(l['href']); ph = t(pr['body'])
        out['pages'][l['href']] = {'status': pr['status'], 'title': title(ph), 'text': plain(ph, 1500),
                                   'links': [x for x in links(ph, pr['url']) if POLL.search(x['text']) or re.search(r'\.pdf|\.csv|\.xlsx', x['href'])][:30]}
    return out


def eo():
    out = {}
    for u in ['https://www.elections.on.ca/en.html', 'https://www.elections.on.ca/en/media-centre/news-releases.html',
              'https://www.elections.on.ca/en/voting-in-ontario/where-to-vote.html', 'https://www.elections.on.ca/en/data-and-maps.html',
              'https://www.elections.on.ca/en/resource-centre/elections-results.html']:
        r = get(u); h = t(r['body'])
        out[u] = {'status': r['status'], 'title': title(h), 'text': plain(h, 800),
                  'feeds': re.findall(r'<link[^>]+(?:rss|atom)\+xml[^>]*>', h, re.I),
                  'links': [l for l in links(h, r['url']) if re.search(r'by-?election|news|release|vote|voting|location|data|map|rss|feed', l['text'] + l['href'], re.I)][:40]}
        if u.endswith('en.html'): save('eo-home.html', r)
        time.sleep(2)
    time.sleep(10)
    ck = get('https://data.ontario.ca/api/3/action/package_search?q=elections%20ontario&rows=30', headers={'User-Agent': BROWSER['User-Agent']})
    try:
        out['ontario_open_data'] = [{'name': p['title'], 'org': (p.get('organization') or {}).get('title'), 'formats': sorted({x.get('format') for x in p.get('resources', [])})}
                                    for p in json.loads(ck['body'])['result']['results']]
    except Exception:
        out['ontario_open_data'] = {'status': ck['status']}
    return out


def bc_places():
    out = {}
    r = get('https://catalogue.data.gov.bc.ca/api/3/action/package_search?q=%22Provincial%20Voting%20Places%22&rows=5',
            headers={'User-Agent': BROWSER['User-Agent']})
    for p in json.loads(r['body'])['result']['results']:
        out[p['title']] = {'notes': (p.get('notes') or '')[:1500], 'modified': p.get('metadata_modified'), 'licence': p.get('license_title'),
                           'resources': [{'name': x.get('name'), 'format': x.get('format'), 'url': x.get('url'), 'modified': x.get('last_modified')} for x in p.get('resources', [])]}
    # A peek at the CSV, if there is one: columns and a few rows (which election, which districts).
    for p in out.values():
        for x in p['resources']:
            if (x['format'] or '').lower() == 'csv' and x['url']:
                c = get(x['url'], headers={'User-Agent': BROWSER['User-Agent']})
                lines = t(c['body']).splitlines()
                x['peek'] = {'status': c['status'], 'rows': len(lines), 'head': lines[:6]}
                break
    return out


step('ec_vis', ec_vis)
step('ec_byelections', ec_byelections)
step('elections_ontario', eo)
step('bc_voting_places', bc_places)
print('\ndone')
