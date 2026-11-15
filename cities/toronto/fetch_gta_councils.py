"""Municipal councils beyond the City of Toronto, from Open North's Represent, into raw/gta_card/councils.json:
for each of the GTA's 24 municipalities, the representative set(s) whose name mentions it (members with their office,
ward and official page, and the set's last_updated date) and the ward boundary set(s) (shapes). Run from GitHub Actions
(fetch-gta-card.yml). gta_card.py decides what reaches the card: only sets updated after the October 26, 2026 election."""
import json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'gta_card')
REP = 'https://represent.opennorth.ca'
UA = {'User-Agent': 'layers.city-pipeline (go@layers.city)'}
MUNIS = ['Ajax', 'Aurora', 'Brampton', 'Brock', 'Burlington', 'Caledon', 'Clarington', 'East Gwillimbury', 'Georgina',
         'Halton Hills', 'King', 'Markham', 'Milton', 'Mississauga', 'Newmarket', 'Oakville', 'Oshawa', 'Pickering',
         'Richmond Hill', 'Scugog', 'Uxbridge', 'Vaughan', 'Whitby', 'Whitchurch-Stouffville']


def get(path):
    for a in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(REP + path, headers=UA), timeout=120) as r:
                time.sleep(1.1)   # Represent allows 60 requests a minute
                return json.load(r)
        except Exception as e:
            print('  retry', a + 1, path, e, flush=True); time.sleep(10 * (a + 1))
    raise SystemExit('failed: ' + path)


def mentions(name, muni):
    return re.search(r'(^|[^a-z])' + re.escape(muni.lower()) + r'([^a-z]|$)', name.lower()) is not None


rsets = get('/representative-sets/?limit=1000')['objects']
bsets = get('/boundary-sets/?limit=2000')['objects']
out = {'fetched': time.strftime('%Y-%m-%d'), 'source': 'Open North Represent', 'munis': {}}
for m in MUNIS:
    rec = {'sets': [], 'wards': []}
    for s in rsets:
        if not mentions(s['name'], m) or re.search(r'(?i)region|county|school|board', s['name']):
            continue
        reps = get(s['related']['representatives_url'] + '?limit=200')['objects']
        rec['sets'].append({'name': s['name'], 'url': s['url'], 'last_updated': s.get('last_updated'),
                            'data_url': s.get('data_url'), 'boundary_set': (s.get('related') or {}).get('boundary_set_url'),
                            'reps': [{'name': r['name'], 'office': r.get('elected_office'), 'district': r.get('district_name'),
                                      'url': r.get('url') or r.get('source_url'), 'party': r.get('party_name')} for r in reps]})
        print(m, '|', s['name'], '|', s.get('last_updated'), '|', len(reps), 'members', flush=True)
    for b in bsets:
        if not mentions(b['name'], m) or not re.search(r'(?i)ward|district', b['name']) or re.search(r'(?i)school|region', b['name']):
            continue
        bl = get(b['url'].replace('/boundary-sets/', '/boundaries/') + 'simple_shape?limit=200')
        rec['wards'].append({'name': b['name'], 'url': b['url'], 'last_updated': b.get('last_updated'),
                             'authority': b.get('authority'), 'source_url': b.get('source_url'), 'licence_url': b.get('licence_url'),
                             'features': [{'name': o['name'], 'geometry': o['simple_shape']} for o in bl['objects']]})
        print(m, '| wards:', b['name'], '|', b.get('last_updated'), '|', len(bl['objects']), flush=True)
    out['munis'][m] = rec
json.dump(out, open(os.path.join(OUT, 'councils.json'), 'w'), separators=(',', ':'))
print('councils: sets for', sum(1 for v in out['munis'].values() if v['sets']), 'municipalities; wards for',
      sum(1 for v in out['munis'].values() if v['wards']))
