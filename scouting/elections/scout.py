"""Scouting (November 3, 2026) for an election watcher: for each election agency behind the cities on the site,
(1) is there a feed or a stable news page a weekly job could watch for new elections and by-elections, and
(2) are voting places published as data (or only as PDFs, or only behind an address lookup)?

Read-only. Writes scouting/elections/out/ (one JSON per agency, summary.json and a few saved pages in pages/);
nothing here feeds the map. Run in Actions (scout-elections.yml): the sandbox can't reach these hosts.
The one address used for lookups is a shopping mall in Scarborough North (Woodside Square, M1V 1V2).
"""
import html, json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out'); PAGES = os.path.join(OUT, 'pages')
os.makedirs(PAGES, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (layers.city scouting)', 'Accept-Language': 'en-CA,en;q=0.8'}
KEY = re.compile(r'by-?election|special election|election|vot|poll|where|locat|news|media|release|rss|feed|open data|data', re.I)
summary = {}


def get(url, tries=2, timeout=60, data=None):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA, data=data)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return {'url': r.geturl(), 'status': r.status, 'type': r.headers.get('Content-Type', ''),
                        'length': r.headers.get('Content-Length'), 'body': r.read()}
        except urllib.error.HTTPError as e:
            return {'url': url, 'status': e.code, 'type': '', 'length': None, 'body': b''}
        except Exception as e:
            print('  retry', i + 1, url[:140], e); time.sleep(3)
    return {'url': url, 'status': None, 'type': '', 'length': None, 'body': b'', 'error': 'unreachable'}


def text(b):
    return b.decode('utf-8', 'replace')


def title(h):
    m = re.search(r'<title[^>]*>(.*?)</title>', h, re.S | re.I)
    return html.unescape(re.sub(r'\s+', ' ', m.group(1))).strip() if m else ''


def links(h, base):
    out = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', h, re.S | re.I):
        t = html.unescape(re.sub(r'<[^>]+>|\s+', ' ', m.group(2))).strip()
        out.append({'text': t[:120], 'href': urllib.parse.urljoin(base, html.unescape(m.group(1)))})
    return out


def feeds(h, base):
    f = [urllib.parse.urljoin(base, html.unescape(m.group(1))) for m in
         re.finditer(r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)', h, re.I)]
    f += [urllib.parse.urljoin(base, html.unescape(m.group(1))) for m in
          re.finditer(r'<link[^>]+href=["\']([^"\']+)["\'][^>]*type=["\']application/(?:rss|atom)\+xml', h, re.I)]
    return sorted(set(f))


def save_page(name, r):
    if r['body']:
        open(os.path.join(PAGES, name), 'wb').write(r['body'][:1_500_000])


def is_feed(r):
    b = r['body'][:2000].lower()
    return r['status'] == 200 and (b'<rss' in b or b'<feed' in b)


def feed_items(r, n=8):
    h = text(r['body'])
    items = re.findall(r'<(?:item|entry)\b.*?</(?:item|entry)>', h, re.S)
    out = []
    for it in items[:n]:
        t = re.search(r'<title[^>]*>(.*?)</title>', it, re.S)
        d = re.search(r'<(?:pubDate|updated|published)>(.*?)</', it, re.S)
        out.append({'title': html.unescape(re.sub(r'<!\[CDATA\[|\]\]>', '', t.group(1))).strip() if t else '',
                    'date': d.group(1).strip() if d else ''})
    return {'items': len(items), 'latest': out}


def site(name, home, extra_feeds=(), extra_pages=(), follow=12):
    """Homepage: title, feeds it advertises, keyword links; try the usual feed paths; save a few pages."""
    res = {'home': home}
    r = get(home); res['status'] = r['status']; res['final'] = r['url']
    h = text(r['body']); save_page(name + '-home.html', r)
    res['title'] = title(h); res['advertised_feeds'] = feeds(h, r['url'])
    ls = links(h, r['url'])
    res['keyword_links'] = [l for l in ls if KEY.search(l['text'] + ' ' + l['href'])][:80]
    root = '{0.scheme}://{0.netloc}'.format(urllib.parse.urlparse(r['url'] or home))
    tried = {}
    for f in list(res['advertised_feeds']) + [root + p for p in ('/feed/', '/rss', '/rss.xml', '/feed.xml', '/news/feed/')] + list(extra_feeds):
        if f in tried: continue
        fr = get(f, tries=1, timeout=30)
        tried[f] = {'status': fr['status'], 'feed': is_feed(fr)}
        if is_feed(fr): tried[f].update(feed_items(fr))
    res['feeds_tried'] = tried
    pages = {}
    want = [l['href'] for l in res['keyword_links'] if re.search(r'by-?election|special|news|media|release|where|locat|poll', l['text'] + l['href'], re.I)]
    for i, u in enumerate(list(extra_pages) + want[:follow]):
        if u in pages or not u.startswith('http'): continue
        pr = get(u, tries=1, timeout=45); ph = text(pr['body'])
        pages[u] = {'status': pr['status'], 'type': pr['type'][:40], 'title': title(ph) if 'html' in pr['type'] else '',
                    'feeds': feeds(ph, pr['url']) if 'html' in pr['type'] else [],
                    'links': [l for l in links(ph, pr['url']) if re.search(r'by-?election|special election|poll|voting place|voting location|where to vote|vote cent|\.pdf|\.csv|\.xlsx|\.zip|geojson|FeatureServer|MapServer|rss|feed', l['text'] + ' ' + l['href'], re.I)][:60]}
        if i < 6 and 'html' in pr['type']: save_page('%s-%d.html' % (name, i), pr)
    res['pages'] = pages
    return res


def step(name, fn):
    print('\n==', name)
    try:
        summary[name] = fn()
    except Exception as e:
        print('  FAILED', repr(e)); summary[name] = {'error': repr(e)}
    json.dump(summary[name], open(os.path.join(OUT, name + '.json'), 'w'), indent=1, ensure_ascii=False, default=str)
    s = summary[name] if isinstance(summary[name], dict) else {}
    print('  status', s.get('status'), '| feeds', [k for k, v in (s.get('feeds_tried') or {}).items() if v.get('feed')])


# ---------- Elections Canada ----------
EC = 'https://www.elections.ca'


def elections_canada():
    res = site('ec', EC + '/home.aspx', extra_pages=[
        EC + '/content.aspx?section=ele&dir=cur&document=index&lang=e',           # current elections
        EC + '/content.aspx?section=med&dir=pre&document=index&lang=e',           # media releases
        EC + '/content2.aspx?section=vote&dir=locate&document=index&lang=e',      # voting locations
        EC + '/content.aspx?section=res&dir=rss&document=index&lang=e',
    ], extra_feeds=[EC + '/rss/rss_e.xml', EC + '/content.aspx?section=med&dir=rss&lang=e'])
    # Voter Information Service: what the postal-code lookup returns during a by-election, and the pages behind it.
    vis = {}
    f = get(EC + '/Scripts/vis/FindED?L=e&QID=-1&PAGEID=20'); fh = text(f['body']); save_page('ec-vis-form.html', f)
    forms = re.findall(r'<form\b[^>]*>.*?</form>', fh, re.S | re.I)
    vis['forms'] = [{'action': (re.search(r'action=["\']([^"\']*)', fm) or [None, None])[1],
                     'method': (re.search(r'method=["\']([^"\']*)', fm, re.I) or [None, 'get'])[1],
                     'inputs': re.findall(r'<input[^>]*name=["\']([^"\']+)', fm, re.I)} for fm in forms]
    tries = []
    for fm in vis['forms']:
        names = fm['inputs']
        pc = next((n for n in names if re.search(r'pc|postal|code', n, re.I)), None)
        if not pc or not fm['action']: continue
        params = {n: '' for n in names}
        for m in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)', fh, re.I):
            params[m.group(1)] = html.unescape(m.group(2))
        params[pc] = 'M1V1V2'
        url = urllib.parse.urljoin(f['url'], html.unescape(fm['action']))
        if (fm['method'] or 'get').lower() == 'post':
            r = get(url, data=urllib.parse.urlencode(params).encode())
        else:
            r = get(url + ('&' if '?' in url else '?') + urllib.parse.urlencode(params))
        rh = text(r['body']); save_page('ec-vis-result.html', r)
        ls = links(rh, r['url'])
        tries.append({'url': r['url'], 'status': r['status'], 'title': title(rh),
                      'mentions': sorted(set(m.lower() for m in re.findall(r'by-election|advance poll\w*|polling station\w*|polling place\w*|election day', rh, re.I))),
                      'links': [l for l in ls if '/vis/' in l['href'].lower() or re.search(r'poll|vot|station|map', l['text'], re.I)][:60]})
        # Follow the lookup's own pages once, to see whether polling places sit on a page keyed by district or poll.
        for i, l in enumerate([l for l in ls if '/vis/' in l['href'].lower()][:10]):
            pr = get(l['href'], tries=1); ph = text(pr['body'])
            tries[-1].setdefault('followed', []).append({'text': l['text'], 'url': pr['url'], 'status': pr['status'], 'title': title(ph),
                'mentions': sorted(set(m.lower() for m in re.findall(r'advance poll\w*|polling station\w*|polling place\w*|wheelchair|accessib\w+', ph, re.I)))})
            save_page('ec-vis-%d.html' % i, pr)
        break
    vis['lookups'] = tries
    res['vis'] = vis
    # Boundaries, for completeness: the 2025 polling divisions behind every by-election this Parliament.
    svc = get('https://maps-cartes.services.geo.ca/server_serveur/rest/services/ELECTIONS/FED_Elect2025_en/MapServer?f=pjson')
    try:
        j = json.loads(svc['body']); res['geo_service'] = [{'id': l['id'], 'name': l['name']} for l in j.get('layers', [])]
    except Exception:
        res['geo_service'] = {'status': svc['status']}
    for z in ('PollingDivisionBoundaries_2025_SHP.zip', 'AdvancePollingDistrictBoundaries_2025_SHP.zip'):
        h = get(EC + '/res/cir/mapsCorner/vector/' + z, tries=1, timeout=30)
        res.setdefault('boundary_files', {})[z] = {'status': h['status'], 'bytes': len(h['body']) or h['length']}
    nw = get('https://www.newswire.ca/news/elections-canada/'); save_page('ec-newswire.html', nw)
    nh = text(nw['body'])
    res['newswire'] = {'status': nw['status'], 'feeds': feeds(nh, nw['url']),
                       'headlines': [l['text'] for l in links(nh, nw['url']) if '/news-releases/' in l['href'] and len(l['text']) > 20][:12]}
    return res


# ---------- Provincial agencies ----------
def elections_ontario():
    res = site('eo', 'https://www.elections.on.ca/en.html', extra_pages=[
        'https://www.elections.on.ca/en/media-centre/news-releases.html',
        'https://www.elections.on.ca/en/voting-in-ontario/where-to-vote.html',
        'https://www.elections.on.ca/en/data-and-maps.html'])
    ck = get('https://data.ontario.ca/api/3/action/package_search?q=%22Elections%20Ontario%22&rows=40')
    try:
        res['ontario_open_data'] = [{'name': p['title'], 'formats': sorted({x.get('format') for x in p.get('resources', [])}),
                                     'modified': p.get('metadata_modified')} for p in json.loads(ck['body'])['result']['results']]
    except Exception:
        res['ontario_open_data'] = {'status': ck['status']}
    return res


def elections_bc():
    res = site('ebc', 'https://elections.bc.ca/', extra_pages=[
        'https://elections.bc.ca/news/', 'https://elections.bc.ca/provincial-elections/by-elections/',
        'https://elections.bc.ca/docs/by/ljf-vmp/vmp-final-voting-places.pdf'])
    ck = get('https://catalogue.data.gov.bc.ca/api/3/action/package_search?q=%22Elections%20BC%22&rows=40')
    try:
        res['bc_data_catalogue'] = [{'name': p['title'], 'formats': sorted({x.get('format') for x in p.get('resources', [])}),
                                     'modified': p.get('metadata_modified')} for p in json.loads(ck['body'])['result']['results']]
    except Exception:
        res['bc_data_catalogue'] = {'status': ck['status']}
    return res


# ---------- Municipal and county agencies (the voting-place fetchers already exist; this checks for feeds) ----------
LOCAL = {
    'toronto-clerk': 'https://www.toronto.ca/city-government/elections/',
    'vancouver-elections': 'https://vancouver.ca/your-government/elections.aspx',
    'nyc-boe': 'https://www.vote.nyc/',
    'chicago-boe': 'https://www.chicagoelections.gov/',
    'dallas-county': 'https://www.dallascountyvotes.org/',
    'tarrant-county': 'https://www.tarrantcountytx.gov/en/elections.html',
    'collin-county': 'https://www.collincountytx.gov/Elections',
    'denton-county': 'https://www.votedenton.gov/',
    'sf-elections': 'https://www.sf.gov/departments/department-elections',
}

step('elections-canada', elections_canada)
step('elections-ontario', elections_ontario)
step('elections-bc', elections_bc)
for k, u in LOCAL.items():
    step(k, lambda u=u, k=k: site(k, u, follow=6))

json.dump({k: {'status': v.get('status') if isinstance(v, dict) else None,
               'feeds': [f for f, x in (v.get('feeds_tried') or {}).items() if x.get('feed')] if isinstance(v, dict) else []}
           for k, v in summary.items()}, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1)
print('\ndone')
