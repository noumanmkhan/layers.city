"""Scout the data for a parking layer: Green P lots, permit parking areas and EV chargers.
Run from GitHub Actions (Scout Toronto data, script=scout_parking.py); the sandbox can't reach these hosts.
Writes cities/toronto/raw/scouting/parking/: a summary (FINDINGS.txt) plus the raw files worth keeping.

- City of Toronto open data (CKAN): every package matching parking / permit / electric vehicle words,
  with resources, formats and licence; then the Green P carpark file and any permit-area geometry in full.
- EV chargers: the U.S. NREL Alternative Fuel Stations API (it also carries Canada's NRCan locator data),
  with DEMO_KEY, Ontario only, kept to a Toronto box; and OpenStreetMap charging stations in the same box
  to compare coverage and tags."""
import collections, json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'scouting', 'parking')
os.makedirs(OUT, exist_ok=True)
CKAN = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/'
BOX = (43.57, -79.65, 43.87, -79.10)   # south, west, north, east: the City plus a margin
UA = {'User-Agent': 'city-layers-pipeline (layers.city)'}
lines = []


def say(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    lines.append(s)


def get(url, data=None, raw=False, timeout=120):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                return b if raw else json.loads(b)
        except Exception as e:
            say('  retry', attempt + 1, url[:120], e)
            time.sleep(5 * (attempt + 1))
    return None


def inbox(lon, lat):
    return BOX[0] <= lat <= BOX[2] and BOX[1] <= lon <= BOX[3]


def keysummary(rows, top=8):
    """Field -> how often set, and its most common values."""
    c = collections.defaultdict(collections.Counter)
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (dict, list)): v = json.dumps(v)[:60]
            c[k][str(v)[:60]] += 1
    for k, vals in c.items():
        say(f'    {k}: {sum(vals.values())} set; {len(vals)} distinct; top {vals.most_common(top)}')


# ---- 1. CKAN packages
say('## CKAN packages')
seen = {}
for q in ('green p', 'parking', 'permit parking', 'electric vehicle', 'charging'):
    res = get(CKAN + 'package_search?' + urllib.parse.urlencode({'q': q, 'rows': 40}))
    for p in (res or {}).get('result', {}).get('results', []):
        seen[p['name']] = p
for name, p in sorted(seen.items()):
    say(f"- {name}: {p.get('title')} | licence {p.get('license_title')} | refreshed {p.get('refresh_rate')} | modified {p.get('last_refreshed') or p.get('metadata_modified')}")
    for r in p.get('resources', []):
        say(f"    res {r.get('name')} [{r.get('format')}] datastore={r.get('datastore_active')} {r.get('url')}")
json.dump(seen, open(os.path.join(OUT, 'ckan_packages.json'), 'w'), indent=1)

# ---- 2. Green P carparks
say('\n## Green P')
gp = seen.get('green-p-parking')
for r in (gp or {}).get('resources', []):
    if (r.get('format') or '').upper() != 'JSON': continue
    b = get(r['url'], raw=True)
    if not b: continue
    open(os.path.join(OUT, 'greenp_' + r['name'].replace(' ', '_') + '.json'), 'wb').write(b)
    d = json.loads(b)
    rows = d.get('carparks') if isinstance(d, dict) else d
    say(f"  {r['name']}: {len(rows or [])} rows; top-level keys {list(d)[:10] if isinstance(d, dict) else 'list'}")
    if rows:
        say('  first row:', json.dumps(rows[0])[:1500])
        keysummary(rows)

# ---- 3. Permit parking geometry: any GeoJSON / shapefile resource in a permit package
say('\n## Permit parking')
for name, p in sorted(seen.items()):
    if 'permit' not in name and 'permit' not in (p.get('title') or '').lower(): continue
    for r in p.get('resources', []):
        fmt = (r.get('format') or '').upper()
        if fmt not in ('GEOJSON', 'JSON', 'CSV'): continue
        b = get(r['url'], raw=True, timeout=300)
        if not b: continue
        fn = f"{name}__{r['name']}.{fmt.lower()}".replace(' ', '_').replace('/', '-')
        say(f"  {name} / {r['name']} [{fmt}] {len(b)} bytes")
        if len(b) < 40_000_000: open(os.path.join(OUT, fn), 'wb').write(b)
        if fmt in ('GEOJSON', 'JSON'):
            try:
                d = json.loads(b)
            except Exception as e:
                say('   not JSON', e); continue
            fs = d.get('features') if isinstance(d, dict) else None
            if fs:
                say('   features', len(fs), 'geometry types', collections.Counter(f['geometry']['type'] for f in fs if f.get('geometry')))
                keysummary([f['properties'] for f in fs])
        else:
            say('   head:', b[:800].decode('utf-8', 'replace'))

# ---- 4. EV chargers: NREL (NRCan data for Canada)
say('\n## EV chargers: NREL / NRCan')
ev = get('https://developer.nrel.gov/api/alt-fuel-stations/v1.json?' + urllib.parse.urlencode(
    {'api_key': 'DEMO_KEY', 'fuel_type': 'ELEC', 'country': 'CA', 'state': 'ON', 'status': 'all', 'access': 'all', 'limit': 'all'}), timeout=300)
if ev:
    st = [s for s in ev.get('fuel_stations', []) if s.get('longitude') and inbox(s['longitude'], s['latitude'])]
    say('  Ontario', ev.get('total_results'), '→ Toronto box', len(st))
    json.dump({'source': 'NREL Alternative Fuel Stations API (NRCan data for Canada)', 'box': BOX, 'fuel_stations': st},
              open(os.path.join(OUT, 'ev_nrel.json'), 'w'))
    if st:
        say('  first:', json.dumps(st[0])[:2500])
        keysummary(st, 6)
else:
    say('  NREL: no response')

# ---- 5. EV chargers: OpenStreetMap
say('\n## EV chargers: OpenStreetMap')
q = f'[out:json][timeout:180];nwr["amenity"="charging_station"]({BOX[0]},{BOX[1]},{BOX[2]},{BOX[3]});out tags center;'
osm = None
for url in ('https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'):
    osm = get(url, data=urllib.parse.urlencode({'data': q}).encode(), timeout=300)
    if osm: break
if osm:
    els = osm.get('elements', [])
    say('  elements', len(els))
    json.dump(els, open(os.path.join(OUT, 'ev_osm.json'), 'w'))
    keysummary([e.get('tags', {}) for e in els], 5)

open(os.path.join(OUT, 'FINDINGS.txt'), 'w').write('\n'.join(lines) + '\n')
