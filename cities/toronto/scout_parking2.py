"""Second scouting pass for the parking layer (after scout_parking.py):
- EV chargers: the NREL / AFDC station API under each host name it may now use (the lab was renamed),
  and NRCan's charging services on maps-cartes.services.geo.ca (layer list, then any station layer in a Toronto box);
  plus the City's own small "City-operated EV charging" dataset.
- Green P: the open-data file stopped in 2019, so look for a current list: Green P's own site
  (parking.greenp.com) and OpenStreetMap car parks run by Green P / the Toronto Parking Authority.
Writes cities/toronto/raw/scouting/parking/ (FINDINGS2.txt and raw files)."""
import collections, json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'scouting', 'parking')
os.makedirs(OUT, exist_ok=True)
BOX = (43.57, -79.65, 43.87, -79.10)
UA = {'User-Agent': 'Mozilla/5.0 (compatible; city-layers-pipeline; layers.city)'}
lines = []


def say(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    lines.append(s)


def get(url, data=None, raw=False, timeout=120, tries=2):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                return b if raw else json.loads(b)
        except Exception as e:
            say('  fail', attempt + 1, url[:140], str(e)[:160])
            time.sleep(4)
    return None


def inbox(lon, lat):
    return BOX[0] <= lat <= BOX[2] and BOX[1] <= lon <= BOX[3]


def keysummary(rows, top=6):
    c = collections.defaultdict(collections.Counter)
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (dict, list)): v = json.dumps(v)[:60]
            c[k][str(v)[:60]] += 1
    for k, vals in c.items():
        say(f'    {k}: {sum(vals.values())} set; {len(vals)} distinct; top {vals.most_common(top)}')


# ---- 1. AFDC / NREL station API, Ontario
say('## AFDC station API')
q = urllib.parse.urlencode({'api_key': 'DEMO_KEY', 'fuel_type': 'ELEC', 'country': 'CA', 'state': 'ON', 'status': 'all', 'access': 'all', 'limit': 'all'})
for host in ('developer.nrel.gov', 'developer.nlr.gov', 'api.nrel.gov', 'developer.nlr.gov/api/nrel'):
    ev = get(f'https://{host}/api/alt-fuel-stations/v1.json?{q}' if '/' not in host else f'https://{host}/alt-fuel-stations/v1.json?{q}', timeout=300)
    if ev and 'fuel_stations' in ev:
        st = [s for s in ev['fuel_stations'] if s.get('longitude') and inbox(s['longitude'], s['latitude'])]
        say('  host', host, 'Ontario', ev.get('total_results'), '-> Toronto box', len(st))
        json.dump({'source': f'AFDC station API ({host})', 'box': BOX, 'fuel_stations': st}, open(os.path.join(OUT, 'ev_afdc.json'), 'w'))
        if st:
            say('  first:', json.dumps(st[0])[:2500])
            keysummary(st)
        break
    elif ev:
        say('  host', host, 'answered:', json.dumps(ev)[:300])

# ---- 2. NRCan map services
say('\n## NRCan map services')
root = 'https://maps-cartes.services.geo.ca/server_serveur/rest/services/NRCan'
cat = get(root + '?f=json')
names = [s['name'] for s in (cat or {}).get('services', [])]
say('  services matching charg/EV/fuel:', [n for n in names if re.search('charg|ev|fuel|zev|afdc', n, re.I)])
for n in [n for n in names if re.search('charg|zev|afdc|fuel', n, re.I)][:8]:
    svc = get(f'{root.rsplit("/NRCan", 1)[0]}/{n}/MapServer?f=json')
    if not svc: continue
    say(f'  {n}:', [(l['id'], l['name']) for l in svc.get('layers', [])])
    for l in svc.get('layers', []):
        if not re.search('station|charg|exist|borne|port', l['name'], re.I) or l.get('subLayerIds'): continue
        base = f'{root.rsplit("/NRCan", 1)[0]}/{n}/MapServer/{l["id"]}'
        meta = get(base + '?f=json') or {}
        say(f'    layer {l["id"]} {l["name"]}: fields', [f['name'] for f in meta.get('fields', [])][:60], 'maxRecordCount', meta.get('maxRecordCount'))
        res = get(base + '/query?' + urllib.parse.urlencode({'where': '1=1', 'geometry': f'{BOX[1]},{BOX[0]},{BOX[3]},{BOX[2]}',
              'geometryType': 'esriGeometryEnvelope', 'inSR': 4326, 'outSR': 4326, 'spatialRel': 'esriSpatialRelIntersects',
              'outFields': '*', 'f': 'json', 'resultRecordCount': 4000}), timeout=180)
        fs = (res or {}).get('features', [])
        say(f'    -> {len(fs)} in the Toronto box; exceeded={ (res or {}).get("exceededTransferLimit") }')
        if fs:
            json.dump(res, open(os.path.join(OUT, f'ev_nrcan_{n.replace("/", "_")}_{l["id"]}.json'), 'w'))
            keysummary([f['attributes'] for f in fs])

# ---- 3. City-operated EV chargers (CKAN)
say('\n## City-operated EV chargers')
pk = get('https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show?id=city-operated-electric-vehicle-charging-station-map')
for r in (pk or {}).get('result', {}).get('resources', []):
    if r.get('format', '').upper() == 'GEOJSON' and '4326' in r.get('name', ''):
        d = get(r['url'])
        if d:
            json.dump(d, open(os.path.join(OUT, 'ev_city.geojson'), 'w'))
            say('  features', len(d['features']))
            keysummary([f['properties'] for f in d['features']])

# ---- 4. Green P: its own site
say('\n## Green P site')
for url in ('https://parking.greenp.com/', 'https://parking.greenp.com/wp-json/', 'https://parking.greenp.com/wp-json/wp/v2/types',
            'https://parking.greenp.com/find-parking/', 'https://parking.greenp.com/terms-of-use/', 'https://parking.greenp.com/robots.txt'):
    b = get(url, raw=True, timeout=60)
    if not b: continue
    t = b.decode('utf-8', 'replace')
    say(f'  {url}: {len(t)} bytes')
    for m in sorted(set(re.findall(r'["\'](https?://[^"\']*(?:json|api|ajax|carpark)[^"\']*)["\']', t)))[:30]: say('    link', m)
    for m in sorted(set(re.findall(r'(?:wp-json/[a-z0-9_/-]+|admin-ajax\.php\?action=[a-z_]+)', t)))[:30]: say('    route', m)
    if 'robots' in url or 'terms' in url: say('   ', re.sub(r'<[^>]+>', ' ', t)[:1500].replace('\n', ' '))
    open(os.path.join(OUT, 'greenp_site_' + re.sub(r'\W+', '_', url[27:]).strip('_')[:40] + '.html'), 'wb').write(b[:2_000_000])
wpj = get('https://parking.greenp.com/wp-json/', timeout=60)
if wpj:
    say('  wp-json namespaces', wpj.get('namespaces'))
    say('  routes with carpark/park', [r for r in wpj.get('routes', {}) if re.search('carpark|park|lot', r)][:40])

# ---- 5. OpenStreetMap car parks run by Green P
say('\n## OSM Green P car parks')
oq = (f'[out:json][timeout:180];(nwr["amenity"="parking"]["operator"~"Green P|Toronto Parking Authority|TPA",i]({BOX[0]},{BOX[1]},{BOX[2]},{BOX[3]});'
      f'nwr["amenity"="parking"]["brand"~"Green P",i]({BOX[0]},{BOX[1]},{BOX[2]},{BOX[3]});nwr["amenity"="parking"]["name"~"Green P",i]({BOX[0]},{BOX[1]},{BOX[2]},{BOX[3]}););out tags center;')
for url in ('https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'):
    o = get(url, data=urllib.parse.urlencode({'data': oq}).encode(), timeout=300)
    if o:
        els = o.get('elements', [])
        say('  elements', len(els))
        json.dump(els, open(os.path.join(OUT, 'greenp_osm.json'), 'w'))
        keysummary([e.get('tags', {}) for e in els])
        break

open(os.path.join(OUT, 'FINDINGS2.txt'), 'w').write('\n'.join(lines) + '\n')
