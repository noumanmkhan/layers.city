"""Fetch where people vote on November 3, 2026 in the four core counties, into cities/dallas/raw/voting/.
Runs in GitHub Actions (fetch-dallas.yml, daily through election day); the sandbox can't reach these hosts.

Dallas, Tarrant and Collin counties run countywide vote centers: a registered voter can vote at any vote center
in their county, during early voting and on election day. Denton County assigns each precinct an election day
polling place (any site during early voting).

- Dallas County Elections: the public Vote Center Finder layer (codes, names, voting rooms, addresses, positions;
  the same 444 election day and 84 early voting centers as its PDF lists)
- Tarrant County Elections: the election day and early voting lists (PDF), placed with the Census Bureau's
  batch geocoder
- Collin County Elections: the polling-locations API behind its public map (positions included)
- Denton County Elections: its polling-locations layer (each election day site with the precincts it serves)
  and its voter precincts

Writes raw/voting/centers.json:
  {asof, election, counties: {county: {source, ed: n, ev: n}}, centers: [{k, name, room, address, city, zip, x, y, ed, ev}],
   denton: {precinct: index into centers}}
and raw/voting/denton_precincts.geojson. Anything that fails keeps the last good copy.
"""
import csv, io, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import *

V = os.path.join(RAW, 'voting')
os.makedirs(V, exist_ok=True)
ELECTION = '2026-11-03'
OUT = os.path.join(V, 'centers.json')
old = json.load(open(OUT)) if os.path.exists(OUT) else {'counties': {}, 'centers': [], 'denton': {}}
counties, centers, denton = {}, [], {}
title = lambda s: re.sub(r"\b([A-Za-z])([A-Za-z']*)", lambda m: m.group(1).upper() + m.group(2).lower(), s or '').replace("'S ", "'s ").strip()


def add(k, name, room, address, city, zip_, x, y, ed, ev):
    key = (k, re.sub(r'\W', '', (address or '').lower())[:24])
    for c in centers:
        if (c['k'], re.sub(r'\W', '', c['address'].lower())[:24]) == key:
            c['ed'] |= ed; c['ev'] |= ev
            return centers.index(c)
    centers.append({'k': k, 'name': name.strip(), 'room': (room or '').strip(), 'address': address.strip(), 'city': city.strip(),
                    'zip': str(zip_ or '').strip(), 'x': round(x, 6) if x is not None else None, 'y': round(y, 6) if y is not None else None,
                    'ed': ed, 'ev': ev})
    return len(centers) - 1


def dallas():
    feats = arcgis('https://services3.arcgis.com/zqe2kwz79KUqUvxC/arcgis/rest/services/Vote_Center_Finder_view/FeatureServer/4',
                   os.path.join('voting', 'dallas_finder_4.geojson'),
                   fields='L_Crnt_Sta,L_Poll_VC,L_Poll_NM,L_Poll_Add,L_Poll_Typ,L_Poll_Vtg')
    n = {'ed': 0, 'ev': 0}
    for f in feats:
        p = f['properties']
        if p.get('L_Crnt_Sta') != 'Active' or not f.get('geometry'): continue
        t = (p.get('L_Poll_Typ') or '').upper()
        m = re.match(r'(.+?),\s*(.+?),\s*Texas\s+(\d{5})', p.get('L_Poll_Add') or '')
        addr, city, z = (m.group(1), m.group(2), m.group(3)) if m else (p.get('L_Poll_Add') or '', '', '')
        x, y = f['geometry']['coordinates'][:2]
        add('dallas', p['L_Poll_NM'], p.get('L_Poll_Vtg'), addr, city, z, x, y, t == 'ED', t == 'EV')
        n[t.lower()] = n.get(t.lower(), 0) + 1
    counties['dallas'] = {'source': 'Dallas County Elections Vote Center Finder', **n}


def geocode(rows):
    """Census Bureau batch geocoder: [(id, street, city, zip)] -> {id: (x, y)}."""
    buf = io.StringIO()
    csv.writer(buf).writerows([(i, s, c, 'TX', z) for i, s, c, z in rows])
    boundary = 'layerscity'
    body = ('--' + boundary + '\r\nContent-Disposition: form-data; name="benchmark"\r\n\r\nPublic_AR_Current\r\n'
            '--' + boundary + '\r\nContent-Disposition: form-data; name="addressFile"; filename="a.csv"\r\nContent-Type: text/csv\r\n\r\n'
            + buf.getvalue() + '\r\n--' + boundary + '--\r\n').encode()
    req = urllib.request.Request('https://geocoding.geo.census.gov/geocoder/locations/addressbatch', data=body,
                                 headers={**UA, 'Content-Type': 'multipart/form-data; boundary=' + boundary})
    with urllib.request.urlopen(req, timeout=600) as r:
        out = {}
        for row in csv.reader(io.StringIO(r.read().decode('utf-8', 'replace'))):
            if len(row) >= 6 and row[2] == 'Match' and row[5]:
                lon, lat = row[5].split(',')
                out[row[0]] = (float(lon), float(lat))
        return out


def tarrant():
    import voting_sources as vs
    base = 'https://www.tarrantcountytx.gov/content/dam/main/elections/2026/1126/locations/'
    download(base + '1126_Vote_Center_Locations.pdf', os.path.join(V, 'tarrant_ed.pdf'))
    download(base + '1126_EV_Sched.pdf', os.path.join(V, 'tarrant_ev.pdf'))
    ed, ev = vs.tarrant_ed(os.path.join(V, 'tarrant_ed.pdf')), vs.tarrant_ev(os.path.join(V, 'tarrant_ev.pdf'))
    print('  Tarrant lists: election day', len(ed), '· early voting', len(ev))
    rows = [(f'{i}', r['address'], r['city'], r['zip']) for i, r in enumerate(ed + ev)]
    # Reuse earlier positions for addresses already placed; geocode the rest.
    known = {(c['address'], c['zip']): (c['x'], c['y']) for c in old['centers'] if c['k'] == 'tarrant' and c['x'] is not None}
    todo = [r for r in rows if (r[1], r[3]) not in known]
    got = geocode(todo) if todo else {}
    print('  geocoded', len(got), 'of', len(todo), 'new addresses')
    # What the Census geocoder can't match (new streets, highway addresses) goes to OpenStreetMap's Nominatim,
    # one request a second as its usage policy asks, keeping only an answer inside Tarrant County's box.
    for i, st, city, z in todo:
        if i in got: continue
        try:
            q = urllib.parse.urlencode({'street': st, 'city': city, 'state': 'Texas', 'postalcode': z, 'country': 'us', 'format': 'json', 'limit': 1})
            r = json.loads(get('https://nominatim.openstreetmap.org/search?' + q, tries=2))
            if r and -97.6 < float(r[0]['lon']) < -96.9 and 32.5 < float(r[0]['lat']) < 33.05:
                got[i] = (float(r[0]['lon']), float(r[0]['lat']))
        except Exception as e:
            print('  nominatim failed', st, e)
        time.sleep(1.1)
    print('  placed after Nominatim', len(got), 'of', len(todo))
    miss = 0
    for i, r in enumerate(ed + ev):
        xy = known.get((r['address'], r['zip'])) or got.get(str(i))
        if not xy: miss += 1; print('  not placed:', r['name'], r['address'], r['city']); continue
        add('tarrant', r['name'], r['room'], r['address'], r['city'], r['zip'], xy[0], xy[1], i < len(ed), i >= len(ed))
    counties['tarrant'] = {'source': 'Tarrant County Elections lists (PDF), placed by the Census Bureau geocoder', 'ed': len(ed), 'ev': len(ev), 'unplaced': miss}


def collin():
    d = json.loads(get('https://api.collincountytx.gov/Elections2APIProxy/elections/public'))
    els = d if isinstance(d, list) else d.get('data', d)
    for e in els: print('  Collin election', e.get('electionId'), e.get('electionDescription'), len(e.get('pollingLocations') or []))
    e = next(e for e in els if '2026' in str(e.get('electionDescription')) and 'Nov' in str(e.get('electionDescription')))
    n = {'ed': 0, 'ev': 0}
    for it in e.get('pollingLocations') or []:
        p, s = it.get('pollingLocation') or {}, it.get('schedule')
        if p.get('lat') is None: print('  no position:', p.get('pollPlace')); continue
        is_ed, is_ev = s in ('ElectionDay', 'Both'), s in ('EarlyVoting', 'Both')
        add('collin', p.get('displayName') or p.get('pollPlace') or '', p.get('alternateName') if p.get('alternateName') != p.get('pollPlace') else '',
            p.get('streetAddress') or '', p.get('city') or '', p.get('zip'), float(p['long']), float(p['lat']), is_ed, is_ev)
        n['ed'] += is_ed; n['ev'] += is_ev
    counties['collin'] = {'source': 'Collin County Elections polling locations', 'election': e.get('electionDescription'), **n}


def denton_():
    feats = arcgis('https://services.arcgis.com/oTsZYNubyv7xK5yP/arcgis/rest/services/Polling_Locations_-_Election_3_/FeatureServer/3',
                   os.path.join('voting', 'denton_polls_3.geojson'))
    n = {'ed': 0, 'ev': 0}
    for f in feats:
        p = f['properties']
        if p.get('ELECTION3') != ELECTION or not f.get('geometry'): continue
        t = (p.get('ELECTION3_LOCATION_TYPE') or '').upper()
        is_ed, is_ev = t in ('ED', 'BOTH'), t in ('EV', 'BOTH')
        x, y = f['geometry']['coordinates'][:2]
        i = add('denton', title(p.get('ELECTION3_LOCATION_NAME') or p.get('POLLING_LOCATION_NAME')),
                title(p.get('ELECTION3_ROOM_ED') or p.get('ELECTION3_ROOM_EV') or ''), title(p.get('ADDRESS')), title(p.get('CITY')), p.get('ZIP'), x, y, is_ed, is_ev)
        for pc in re.findall(r'\d{4}', p.get('ELECTION3_VP_ED') or ''):
            denton[pc] = i
        n['ed'] += is_ed; n['ev'] += is_ev
    arcgis('https://services.arcgis.com/oTsZYNubyv7xK5yP/arcgis/rest/services/Voter_Precincts/FeatureServer/0',
           os.path.join('voting', 'denton_precincts.geojson'), fields='PRECINCT_N')
    counties['denton'] = {'source': 'Denton County Elections polling locations', 'precincts': len(denton), **n}


for label, fn in [('dallas', dallas), ('tarrant', tarrant), ('collin', collin), ('denton', denton_)]:
    print('==', label); step(label, fn)
    if label in FAILED and label in old['counties']:   # keep the last good copy of that county
        print('  keeping the last copy of', label)
        counties[label] = old['counties'][label]
        remap = {}
        for j, c in enumerate(old['centers']):
            if c['k'] == label: remap[j] = len(centers); centers.append(c)
        if label == 'denton':
            denton.update({pc: remap[i] for pc, i in old['denton'].items() if i in remap})
for k, c in counties.items(): print(k, c)
# The date moves only when something changed, so a quiet day commits nothing.
same = {k: old.get(k) for k in ('counties', 'centers', 'denton')} == {'counties': counties, 'centers': centers, 'denton': denton}
asof = old['asof'] if same and old.get('asof') else datetime.now(timezone.utc).strftime('%Y-%m-%d')
save(os.path.join('voting', 'centers.json'), {'asof': asof, 'election': ELECTION, 'counties': counties, 'centers': centers, 'denton': denton})
print('FAILED:', FAILED or 'none')
