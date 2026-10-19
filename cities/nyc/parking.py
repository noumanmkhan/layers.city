"""Parking & Charging for New York: NYC DOT's municipal garages and fields, and public EV chargers, from raw/parking/
(fetch_parking.py) -> docs/nyc/data/parking.geojson, in the same shape as Toronto's (the spots layers read it).

City car parks (c "gp", the city-run car park category): NYC DOT's municipal garages and fields from its list, kept by
hand in cities/nyc/parking.json. Per lot: n name, t "g" garage or "s" field (surface lot), cap spaces, hrs hours,
a address where the City gives a block rather than a number, note anything the City says is changing.

EV chargers (c "ev"): public stations from the Alternative Fuels Data Center inside the city (with a margin for ones on a
boundary road). Left out: private stations, stations only for a building's residents, guests or staff
(restricted_access), and planned ones. Same rules as Toronto's (cities/toronto/parking.py): one point per place and
network; names used at three or more addresses are operators, so those points take the address as their name; points
of one place listed twice join up. Per point: n, op, a, l1, l2, dc, kw, net, h24 or hrs, fee, tes, off, conf."""
import json, math, os, re
from collections import Counter, defaultdict
from shapely.geometry import shape, Point

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'parking')
DATA = os.path.join(HERE, '..', '..', 'docs', 'nyc', 'data')
K = math.cos(math.radians(40.7))
spots = lambda p: p.get('l1', 0) + p.get('l2', 0) + p.get('dc', 0)
metres = lambda a, b: math.hypot((a[0] - b[0]) * 111320 * K, (a[1] - b[1]) * 110950)
rnd = lambda v: round(float(v), 5)
load = lambda n: json.load(open(os.path.join(RAW, n))) if os.path.exists(os.path.join(RAW, n)) else None
CITY = [shape(f['geometry']).buffer(0) for f in json.load(open(os.path.join(DATA, 'base.geojson')))['features']
        if f['properties'].get('kind') == 'city'][0].buffer(0.002)
feats = []

# ---- NYC DOT municipal garages and fields
mu = load('municipal.json')
if mu:
    for f in mu['facilities']:
        p = {'c': 'gp', 'n': f['name'].replace('#', 'No. '), 't': f['t'], 'cap': f['cap']}
        if f.get('hrs') == '24 hours, 7 days': p['h24'] = 1
        elif f.get('hrs'): p['hrs'] = f['hrs']
        if f.get('a'): p['a'] = f['a']
        if f.get('note'): p['note'] = f['note']
        feats.append({'type': 'Feature', 'properties': p, 'geometry': {'type': 'Point', 'coordinates': f['xy']}})
    print(f"Municipal: {len(feats)} ({sum(1 for f in feats if f['properties']['t'] == 'g')} garages), "
          f"{sum(f['properties']['cap'] for f in feats):,} spaces; not placed: {mu.get('missing') or 'none'}")

# ---- EV chargers
ev_af = load('ev_afdc.json')
NETS = {'ChargePoint Network': 'ChargePoint', 'Blink Network': 'Blink', 'EVCONNECT': 'EV Connect', 'EVGATEWAY': 'EVgateway',
        'SHELL_RECHARGE': 'Shell Recharge', 'Electrify America': 'Electrify America', 'eVgo Network': 'EVgo', 'Tesla': 'Tesla',
        'Tesla Destination': 'Tesla Destination', 'FLO': 'FLO', 'Revel': 'Revel', 'CHARGELAB': 'ChargeLab', 'IONNA': 'IONNA'}


def tidy(name):
    name = ' '.join(name.split())
    if name.isupper() and len(name) > 4: name = name.title()
    return name


groups, skipped = defaultdict(list), Counter()
for s in (ev_af or {}).get('fuel_stations', []):
    if s.get('access_code') != 'public': skipped['private'] += 1; continue
    if s.get('restricted_access'): skipped['restricted'] += 1; continue
    if s.get('status_code') not in ('E', 'T'): skipped['planned'] += 1; continue
    at = (rnd(s['longitude']), rnd(s['latitude']))
    if not CITY.contains(Point(at)): skipped['outside the city'] += 1; continue
    addr = ' '.join((s.get('street_address') or '').lower().split())
    key = (tidy(s['station_name']).lower(), addr) if addr else (round(at[0], 4), round(at[1], 4))
    groups[key + (s.get('ev_network') or '',)].append(s)
seen = defaultdict(set)
for k, ss in groups.items(): seen[tidy(ss[0]['station_name']).lower()].add(' '.join((ss[0].get('street_address') or '').lower().split()))
OPERATORS = {n for n, a in seen.items() if len(a) >= 3}
ev = []
for key, ss in groups.items():
    net = key[-1]
    s0 = max(ss, key=lambda s: (s.get('ev_level2_evse_num') or 0) + (s.get('ev_dc_fast_num') or 0))
    p = {'c': 'ev', 'n': tidy(s0['station_name']), 'a': (s0.get('street_address') or '').strip()}
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
feats += ev
evs = [f['properties'] for f in ev]
print(f"EV: {len(ev)} public charging points; {sum(p.get('l2', 0) for p in evs):,} Level 2 ports, "
      f"{sum(p.get('dc', 0) for p in evs):,} DC fast ports at {sum(1 for p in evs if p.get('dc'))} sites; "
      f"{sum(1 for p in evs if p.get('tes'))} Tesla-only; {sum(1 for p in evs if p.get('off'))} temporarily unavailable; left out {dict(skipped)}")

lots = [f['properties'] for f in feats if f['properties']['c'] == 'gp']
counts = {'greenp': len(lots), 'ev': len(ev), 'spaces': sum(p.get('cap', 0) for p in lots),
          'l2': sum(p.get('l2', 0) for p in evs), 'dc': sum(p.get('dc', 0) for p in evs)}
json.dump({'type': 'FeatureCollection', 'asof': {'gp': (mu or {}).get('asof'), 'ev': (ev_af or {}).get('fetched')},
           'count': counts, 'features': feats},
          open(os.path.join(DATA, 'parking.geojson'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('parking.geojson:', counts)
