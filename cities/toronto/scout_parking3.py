"""Third scouting pass for the parking layer: where Green P's own map gets its car park list (parking.js, read
only, for the record), and OpenStreetMap car parks run by Green P / the Toronto Parking Authority, to check
the City's 2019 Green P file against today. Writes cities/toronto/raw/scouting/parking/ (FINDINGS3.txt, greenp_osm.json)."""
import collections, json, os, re, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'scouting', 'parking')
BOX = (43.57, -79.65, 43.87, -79.10)
lines = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); lines.append(s)
def get(url, data=None, ua='city-layers-pipeline (layers.city)'):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers={'User-Agent': ua}), timeout=300) as r: return r.read()
    except Exception as e:
        say('  fail', url[:100], e); return None

say('## parking.js')
b = get('https://parking.greenp.com/app/themes/greenp2022/_/js/parking.js', ua='Mozilla/5.0')
if b:
    t = b.decode('utf-8', 'replace'); say('  bytes', len(t))
    for m in re.finditer(r'(url|ajax|json|fetch|action|carpark)', t, re.I):
        s = m.start(); say('   ', t[max(0, s - 80):s + 140].replace('\n', ' '))
        if len(lines) > 80: break

say('\n## OSM Green P car parks')
bb = f'({BOX[0]},{BOX[1]},{BOX[2]},{BOX[3]})'
q = (f'[out:json][timeout:180];(nwr["amenity"="parking"]["operator"~"Green P|Toronto Parking Authority",i]{bb};'
     f'nwr["amenity"="parking"]["brand"~"Green P",i]{bb};nwr["amenity"="parking"]["name"~"Green P",i]{bb};);out tags center;')
for url in ('https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'):
    o = get(url, data=urllib.parse.urlencode({'data': q}).encode())
    if not o: continue
    els = json.loads(o).get('elements', [])
    say('  elements', len(els), 'from', url)
    json.dump(els, open(os.path.join(OUT, 'greenp_osm.json'), 'w'))
    c = collections.defaultdict(collections.Counter)
    for e in els:
        for k, v in e.get('tags', {}).items(): c[k][v[:40]] += 1
    for k, v in sorted(c.items(), key=lambda kv: -sum(kv[1].values()))[:30]: say(f'   {k}: {sum(v.values())}; {v.most_common(5)}')
    break
open(os.path.join(OUT, 'FINDINGS3.txt'), 'w').write('\n'.join(lines) + '\n')
