"""Save the Wikipedia pages the Hyderabad representatives list is checked against (wikitext, via the API), into
cities/hyderabad/raw/reps/. The list itself is hand-kept in cities/hyderabad/representatives.json: members change only
at elections and by-elections, and party labels need a human eye (members who changed party after being elected)."""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'reps'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}
PAGES = ['Telangana Legislative Assembly', '2023 Telangana Legislative Assembly election',
         '2024 Indian general election in Telangana', 'List of members of the 18th Lok Sabha',
         '2025 Jubilee Hills Assembly by-election', '2024 Secunderabad Cantonment Assembly by-election']
for p in PAGES:
    url = 'https://en.wikipedia.org/w/api.php?' + urllib.parse.urlencode({'action': 'parse', 'page': p, 'prop': 'wikitext', 'format': 'json', 'redirects': 1})
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        if 'error' in d: print('  missing', p, d['error'].get('info')); continue
        t = d['parse']['wikitext']['*']
        fn = p.replace(' ', '_').replace('/', '-') + '.wiki'
        open(os.path.join(OUT, fn), 'w').write(t)
        print('  saved', fn, len(t))
    except Exception as e:
        print('  failed', p, e)
    time.sleep(1)
