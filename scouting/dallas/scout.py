"""Scout what the City of Dallas and others publish, for building Dallas to Toronto's feature set.
Lists: the Dallas Open Data (Socrata) catalogue; the City's ArcGIS servers' services and layers; the City's
ArcGIS Online organisation's services; ArcGIS Online items for school districts, trustees and sanitation;
and probes a few known endpoints. Writes scouting/dallas/out/*.json and prints a readable log."""
import json, os, re, sys, time, urllib.parse, urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}


def get(url, tries=2, timeout=90):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            err = e; time.sleep(5)
    raise err


def js(url):
    return json.loads(get(url))


def save(name, obj):
    json.dump(obj, open(os.path.join(OUT, name), 'w'), indent=1)


# 1. Socrata catalogue
rows, off = [], 0
while True:
    try:
        d = js(f'https://api.us.socrata.com/api/catalog/v1?domains=www.dallasopendata.com&limit=100&offset={off}')
    except Exception as e:
        print('catalog failed', e); break
    for r in d.get('results', []):
        res = r['resource']
        rows.append({'id': res['id'], 'name': res['name'], 'type': res.get('type'), 'updated': res.get('data_updated_at') or res.get('updatedAt'),
                     'cols': len(res.get('columns_name') or []), 'category': (r.get('classification') or {}).get('domain_category'),
                     'desc': (res.get('description') or '')[:160].replace('\n', ' ')})
    if len(d.get('results', [])) < 100: break
    off += 100
save('socrata.json', rows)
print('SOCRATA datasets', len(rows))
for r in sorted(rows, key=lambda r: (r['category'] or '', r['name'])):
    print(f"  [{r['category']}] {r['name']} | {r['id']} | {r['type']} | {str(r['updated'])[:10]}")

# 2. ArcGIS servers: every service and its layers
def walk(root, folder='', depth=0, acc=None):
    acc = acc if acc is not None else []
    try:
        d = js(f"{root}/{folder}?f=json" if folder else f"{root}?f=json")
    except Exception as e:
        print('  server failed', root, folder, e); return acc
    for f in d.get('folders', []):
        if depth < 2: walk(root, f, depth + 1, acc)
    for s in d.get('services', []):
        url = f"{root}/{s['name']}/{s['type']}"
        try:
            m = js(url + '?f=json')
            layers = [(l['id'], l['name']) for l in m.get('layers', [])]
        except Exception as e:
            layers = [('ERR', str(e)[:60])]
        acc.append({'url': url, 'layers': layers})
        print('  ', url, '->', layers[:40])
    return acc

servers = {}
for root in ['https://egis.dallascityhall.com/arcgis/rest/services', 'https://gis.dallascityhall.com/arcgis/rest/services',
             'https://services2.arcgis.com/rwnOSbfKSwyTBcwN/ArcGIS/rest/services']:
    print('SERVER', root)
    servers[root] = walk(root)
save('arcgis_servers.json', servers)

# 3. ArcGIS Online searches
for q in ['Dallas ISD trustee districts', 'Dallas ISD attendance zones', 'Dallas ISD school attendance boundaries', 'Dallas sanitation collection day',
          'City of Dallas library', 'Dallas recreation centers', 'Dallas landmark districts historic', 'Dallas bike lanes', 'Dallas park',
          'Dallas County hospital emergency', 'Richardson ISD attendance', 'Dallas building permits']:
    try:
        d = js('https://www.arcgis.com/sharing/rest/search?' + urllib.parse.urlencode({'q': q, 'f': 'json', 'num': 12}))
        print('ARCGIS', q)
        for r in d.get('results', []):
            print('    ', r.get('type'), '|', r.get('title'), '|', r.get('owner'), '|', r.get('url') or '', '| modified', time.strftime('%Y-%m-%d', time.gmtime((r.get('modified') or 0) / 1000)))
    except Exception as e:
        print('  search failed', q, e)

# 4. Probes
for name, url in [('wikipedia tallest', 'https://en.wikipedia.org/w/api.php?action=parse&page=List_of_tallest_buildings_in_Dallas&prop=sections&format=json'),
                  ('dart gtfs', 'https://www.dart.org/transitdata/latest/google_transit.zip'),
                  ('openstates tx', 'https://data.openstates.org/people/current/tx.csv'),
                  ('house clerk', 'https://clerk.house.gov/xml/lists/MemberData.xml')]:
    try:
        b = get(url); print('PROBE', name, 'ok', len(b), 'bytes')
        if name == 'openstates tx': print(b.decode()[:600])
    except Exception as e:
        print('PROBE', name, 'failed', e)
