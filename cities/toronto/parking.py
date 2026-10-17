"""Parking: Green P car parks, EV chargers and permit parking areas, from raw/parking/ (fetch_parking.py).
Writes docs/toronto/data/parking.geojson (points), docs/toronto/data/permit_areas.geojson (polygons) and adds
each neighbourhood's permit-parking share to docs/toronto/data/nbhd_profiles.json ("permit", "permitBand").
Run after profiles.py (run.sh), or on its own (fetch-toronto-parking.yml): it only needs the published
neighbourhoods and profiles.

Green P (c "gp"): the City's open-data list is from 2019 and won't be refreshed; it is shown as that, with its
date. Rates and permits aren't carried over: they've changed since. Per lot: n address, t "g" garage or
"s" surface lot, cap spaces, h clearance in metres (garages that list one), ttc 1 for TTC commuter lots.
OpenStreetMap tags only part of Green P's lots, so it can't confirm or prune this list; the log says how many
it does match, as a rough check on how stale the list is.

EV chargers (c "ev"): public stations from the Alternative Fuels Data Center (Natural Resources Canada's
locator data), plus City-operated chargers it lacks (on-street and in Green P lots). Left out: private
stations, stations open only to a building's residents, guests or staff (restricted_access), and planned ones.
Stations with one name at one address on one network (a garage's units, listed one by one) become one point; names
used at three or more addresses are operators, so those points take the address as their name. Per point: n name, op operator,
a address, l2 Level 2 ports, dc DC fast ports, kw the fastest DC charger's power where given, net network,
h24 1 when open 24 hours daily, else hrs its hours as listed, fee pricing where given, tes 1 for Tesla-only, off 1 when listed as temporarily unavailable,
conf the date the listing was last confirmed, l1 Level 1 ports (a household outlet; rare) where any.

Permit areas: the City's on-street permit parking areas (name "12B", lp a label point). A permit area is where residents may
buy a permit for the signed streets in it; not every street inside has permit parking. The neighbourhood
share is the share of its land inside a permit area (planar, fine for a ratio at this latitude)."""
import json, math, os, re
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union, polylabel

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'parking')
DATA = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data')
CUTS = (25, 75)                    # permitBand: p0 none, p1 under 25%, p2 25–75%, p3 75% or more
K = math.cos(math.radians(43.7))
spots = lambda p: p.get('l1', 0) + p.get('l2', 0) + p.get('dc', 0)
metres = lambda a, b: math.hypot((a[0] - b[0]) * 111320 * K, (a[1] - b[1]) * 110950)
rnd = lambda v: round(float(v), 5)
load = lambda n: json.load(open(os.path.join(RAW, n))) if os.path.exists(os.path.join(RAW, n)) else None
feats = []
GP_ADDR = {}
# EV chargers are kept to the City (with a margin for ones on a boundary road), like the rest of the city layers.
CITY = [shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(DATA, 'base.geojson')))['features'] if f['properties'].get('kind') == 'city'][0].buffer(0.003)

# ---- Green P
NOTE = re.compile(r'reduced|closed|closure|construction|repairs|until|entrance via|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)\b', re.I)


def gp_name(addr):
    """The 2019 file's address, without its notices of the day ("- reduced parking - Sept. to Dec.")."""
    parts = [' '.join(x.split()).rstrip('.') for x in addr.split(' - ')]
    return ' - '.join(x for x in parts if x and not NOTE.search(x))


gp = load('greenp.json')
if gp:
    osm = (load('greenp_osm.json') or {}).get('elements', [])
    matched = 0
    for c in gp['carparks']:
        at = [rnd(c['lng']), rnd(c['lat'])]
        p = {'c': 'gp', 'n': gp_name(c['address']), 't': 'g' if c['carpark_type'] == 'garage' else 's'}
        if str(c.get('capacity') or '').isdigit(): p['cap'] = int(c['capacity'])
        try:
            h = float(c.get('max_height') or 0)
            if p['t'] == 'g' and 1.5 < h < 5: p['h'] = round(h, 2)
        except ValueError: pass
        if c.get('is_ttc'): p['ttc'] = 1
        p['id'] = c['id']
        if osm and min(metres(at, e['at']) for e in osm) <= 150: matched += 1
        feats.append({'type': 'Feature', 'properties': p, 'geometry': {'type': 'Point', 'coordinates': at}})
    GP_ADDR = {f['properties']['id']: f['properties']['n'] for f in feats}
    gp_asof = '2019-06-30'   # the file's date on the portal ("green-p-parking-2019", not refreshed since)
    print(f"Green P: {len(gp['carparks'])} lots ({sum(1 for f in feats if f['properties']['t'] == 'g')} garages), "
          f"{sum(f['properties'].get('cap', 0) for f in feats):,} spaces; {matched} have a Toronto Parking Authority car park "
          f"in OpenStreetMap within 150 m ({len(osm)} there)")

# ---- EV chargers
ev_af, ev_city = load('ev_afdc.json'), load('ev_city.geojson')
NETS = {'CHARGELAB': 'ChargeLab', 'SHELL_RECHARGE': 'Shell Recharge', 'EVGATEWAY': 'EVgateway', 'RED_E': 'RED E', 'JULE': 'Jule', 'IVY': 'Ivy'}


def tidy(name):
    """Station names as people would say them: Green P's unit codes ("GREENP CP26-002-FC") become "Green P car park 26";
    names in capitals get title case."""
    name = ' '.join(name.split())
    m = re.match(r'^GREEN ?P\W*CP\s*(\d+)', name, re.I)
    if m: return f'Green P car park {int(m.group(1))}'
    if name.isupper() and len(name) > 4: name = name.title()
    return name


groups = defaultdict(list)
skipped = Counter()
for s in (ev_af or {}).get('fuel_stations', []):
    if s.get('access_code') != 'public': skipped['private'] += 1; continue
    if s.get('restricted_access'): skipped['restricted'] += 1; continue
    if s.get('status_code') not in ('E', 'T'): skipped['planned'] += 1; continue
    at = (rnd(s['longitude']), rnd(s['latitude']))
    if not CITY.contains(Point(at)): skipped['outside the city'] += 1; continue
    # One point per place and network: the same tidy name at the same address (a garage's units, listed one by one), else
    # the same spot to about 10 m.
    addr = ' '.join((s.get('street_address') or '').lower().split())
    key = (tidy(s['station_name']).lower(), addr) if addr else (round(at[0], 4), round(at[1], 4))
    groups[key + (s.get('ev_network') or '',)].append(s)
# Names used at three or more addresses are operators (SWTCH Energy, ImPark), not places: those points are titled by
# their address and keep the operator's name on its own line.
seen = defaultdict(set)
for k, ss in groups.items(): seen[tidy(ss[0]['station_name']).lower()].add(' '.join((ss[0].get('street_address') or '').lower().split()))
OPERATORS = {n for n, a in seen.items() if len(a) >= 3 and not n.startswith('green p')}
ev = []
for key, ss in groups.items():
    net = key[-1]
    s0 = max(ss, key=lambda s: (s.get('ev_level2_evse_num') or 0) + (s.get('ev_dc_fast_num') or 0))
    p = {'c': 'ev', 'n': tidy(s0['station_name']), 'a': (s0.get('street_address') or '').strip()}
    m = re.match(r'Green P car park (\d+)$', p['n'])
    if m and m.group(1) in GP_ADDR: p['n'] = 'Green P, ' + GP_ADDR[m.group(1)]
    if p['n'].lower() in OPERATORS and p['a']: p['op'], p['n'] = p['n'], p['a']
    l1, l2, dc = (sum(s.get(k) or 0 for s in ss) for k in ('ev_level1_evse_num', 'ev_level2_evse_num', 'ev_dc_fast_num'))
    if not (l1 or l2 or dc): skipped['no ports'] += 1; continue
    if l2: p['l2'] = l2
    if l1: p['l1'] = l1
    if dc:
        p['dc'] = dc
        kw = [c.get('power_kw') for s in ss for u in (s.get('ev_charging_units') or []) if u.get('charging_level') == 'dc_fast'
              for c in (u.get('connectors') or {}).values() if c.get('port_count') and c.get('power_kw')]
        if kw: p['kw'] = int(max(kw))
    if net and net != 'Non-Networked': p['net'] = NETS.get(net, net.replace(' Network', ''))
    hrs = (s0.get('access_days_time') or '').strip().rstrip('.')
    if 'tesla' in hrs.lower() and 'only' in hrs.lower() or all(s.get('ev_connector_types') == ['TESLA'] for s in ss): p['tes'] = 1
    if hrs.lower() == '24 hours daily': p['h24'] = 1
    elif hrs: p['hrs'] = hrs
    fee = (s0.get('ev_pricing') or '').strip()
    if fee: p['fee'] = fee
    if all(s.get('status_code') == 'T' for s in ss): p['off'] = 1
    conf = max((s.get('date_last_confirmed') or '') for s in ss)
    if conf: p['conf'] = conf
    ev.append({'type': 'Feature', 'properties': p, 'geometry': {'type': 'Point', 'coordinates': [rnd(s0['longitude']), rnd(s0['latitude'])]}})
# Second pass: points of one place listed under different networks or spellings of the address ("51 Dockside Dr" and
# "51 Dockside Drive") join up when within 12 m, or within 150 m under the same name (a big garage's entrances).
def same(a, b):
    d = metres(a['geometry']['coordinates'], b['geometry']['coordinates'])
    return d < 12 or (d < 150 and a['properties']['n'].lower() == b['properties']['n'].lower())
merged = []
for f in sorted(ev, key=lambda f: -spots(f['properties'])):
    t = next((m for m in merged if same(m, f)), None)
    if not t: merged.append(f); continue
    P, q = t['properties'], f['properties']
    for k in ('l1', 'l2', 'dc'):
        if q.get(k): P[k] = P.get(k, 0) + q[k]
    if q.get('kw'): P['kw'] = max(P.get('kw', 0), q['kw'])
    nets = [x for x in (P.get('net', '').split(' · ') + [q.get('net', '')]) if x]
    if nets: P['net'] = ' · '.join(dict.fromkeys(nets))
    if not q.get('off'): P.pop('off', None)
    if q.get('conf', '') > P.get('conf', ''): P['conf'] = q['conf']
    if not q.get('tes'): P.pop('tes', None)
ev = merged
af_n = len(ev)
for f in (ev_city or {}).get('features', []):
    if not f.get('geometry'): continue
    g = shape(f['geometry']); at = [rnd(g.x), rnd(g.y)] if g.geom_type == 'Point' else [rnd(g.centroid.x), rnd(g.centroid.y)]
    q = f['properties']
    if any(metres(at, e['geometry']['coordinates']) < 40 for e in ev): continue
    l2, l3 = int(q.get('Level2_Charging_Ports') or 0), int(q.get('Level3_Charging_Ports') or 0)
    if not (l2 or l3): continue
    p = {'c': 'ev', 'n': (q.get('Location') or q.get('Address') or '').strip().rstrip('.'), 'a': (q.get('Address') or '').strip().rstrip('.'),
         'net': 'City of Toronto' + (' · Green P' if q.get('Type') == 'Green P' else '')}
    if p['n'] == p['a']: p['n'] = ('Green P' if q.get('Type') == 'Green P' else 'On-street') + ' charging, ' + p['a']
    if l2: p['l2'] = l2
    if l3: p['dc'] = l3
    p['city'] = 1
    ev.append({'type': 'Feature', 'properties': p, 'geometry': {'type': 'Point', 'coordinates': at}})
feats += ev
evs = [f['properties'] for f in ev]
print(f"EV: {len(ev)} public charging points ({af_n} from AFDC, {len(ev) - af_n} City-operated it lacks); "
      f"{sum(p.get('l2', 0) for p in evs):,} Level 2 ports, {sum(p.get('dc', 0) for p in evs):,} DC fast ports at "
      f"{sum(1 for p in evs if p.get('dc'))} sites; {sum(1 for p in evs if p.get('tes'))} Tesla-only; "
      f"{sum(1 for p in evs if p.get('off'))} temporarily unavailable; left out {dict(skipped)}")

counts = {'greenp': sum(1 for f in feats if f['properties']['c'] == 'gp'), 'ev': len(ev),
          'spaces': sum(f['properties'].get('cap', 0) for f in feats if f['properties']['c'] == 'gp'),
          'l2': sum(p.get('l2', 0) for p in evs), 'dc': sum(p.get('dc', 0) for p in evs)}
json.dump({'type': 'FeatureCollection', 'asof': {'gp': gp_asof if gp else None, 'ev': (ev_af or {}).get('fetched')},
           'count': counts, 'features': feats},
          open(os.path.join(DATA, 'parking.geojson'), 'w'), ensure_ascii=False, separators=(',', ':'))

# ---- Permit parking areas, and each neighbourhood's share
pa = load('permit_areas.geojson')
if pa:
    areas = []
    for f in pa['features']:
        g = shape(f['geometry']).buffer(0)
        if g.is_empty: continue
        areas.append((f['properties']['name'], g))
    out = []
    for name, g in sorted(areas, key=lambda a: a[0]):
        s = g.simplify(0.00003, preserve_topology=True)
        gj = json.loads(json.dumps(mapping(s)), parse_float=lambda v: round(float(v), 5))
        big = max(getattr(g, 'geoms', [g]), key=lambda x: x.area)
        lp = polylabel(big, tolerance=0.00005)   # label point: deep inside the area's largest part
        out.append({'type': 'Feature', 'properties': {'name': name, 'lp': [round(lp.x, 5), round(lp.y, 5)]}, 'geometry': gj})
    u = unary_union([g for _, g in areas])
    nb = json.load(open(os.path.join(DATA, 'neighbourhoods.geojson')))['features']
    profp = os.path.join(DATA, 'nbhd_profiles.json')
    prof = json.load(open(profp))
    band = lambda v: 'p0' if v == 0 else 'p' + str(1 + sum(v >= c for c in CUTS))
    for f in nb:
        g = shape(f['geometry']).buffer(0)
        pct = round(100 * g.intersection(u).area / g.area) if g.area else 0
        d = prof.get(str(f['properties']['code']))
        if d is not None: d['permit'], d['permitBand'] = pct, band(pct)
    json.dump(prof, open(profp, 'w'), separators=(',', ':'))
    json.dump({'type': 'FeatureCollection', 'asof': (pa.get('modified') or '')[:10], 'features': out},
              open(os.path.join(DATA, 'permit_areas.geojson'), 'w'), separators=(',', ':'))
    print(f"Permit areas: {len(out)}; neighbourhoods by share:",
          dict(sorted(Counter(d.get('permitBand') for d in prof.values()).items(), key=lambda kv: str(kv[0]))))
