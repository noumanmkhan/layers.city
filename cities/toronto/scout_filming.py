"""Scout: is there public data on where films and TV shows shoot in Toronto?

1. The City's road restrictions feed (the Closures layer's source): count records by workEventType and
   permitType, and print any that look like filming.
2. Toronto Open Data: search the catalogue for film, filming, noise exemption and special event datasets.
Writes raw/scouting/filming.json."""
import json, os, re, urllib.parse, urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'layers.city scouting (go@layers.city)'}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return json.load(r)


out = {}
feed = get('https://secure.toronto.ca/opendata/cart/road_restrictions/v3?format=json')
recs = feed.get('Closure') or next((v for v in feed.values() if isinstance(v, list)), [])
print(len(recs), 'records; fields:', sorted(recs[0].keys()) if recs else None)
for k in ('workEventType', 'permitType', 'source', 'type', 'subType'):
    c = Counter(str(r.get(k)) for r in recs)
    print(k, c.most_common(30))
    out[k] = c.most_common(50)
film = [r for r in recs if re.search(r'film|movie|production|tv |television|commercial shoot|photo shoot',
                                      json.dumps(r), re.I)]
print(len(film), 'records that look like filming')
for r in film[:15]:
    print(' ', {k: r.get(k) for k in ('workEventType', 'permitType', 'contractor', 'name', 'road', 'district',
                                       'description', 'startTime', 'endTime')})
out['film'] = film[:200]

base = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_search?rows=50&q='
for q in ('film', 'filming', 'noise exemption', 'special event', 'street event', 'right of way permit'):
    res = get(base + urllib.parse.quote(q))['result']['results']
    print(f'catalogue "{q}":', [(p['name'], p.get('title')) for p in res][:15])
    out['ckan_' + q] = [(p['name'], p.get('title'), (p.get('notes') or '')[:300]) for p in res]

os.makedirs(os.path.join(HERE, 'raw', 'scouting'), exist_ok=True)
json.dump(out, open(os.path.join(HERE, 'raw', 'scouting', 'filming.json'), 'w'), indent=1, default=str)
