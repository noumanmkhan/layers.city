"""Heritage buildings: build docs/<city>/data/heritage_buildings.geojson from cities/<city>/raw/heritage_buildings.json
(engine/fetch_heritage_buildings.py) for the "heritage" points layer, the card's Heritage building row and search.

One point per protected property, with:
  n  name (Chicago: the landmark's name; Toronto: the name its register description starts with, e.g.
     "John Scadding Cabin", or nothing when the description starts with council wording)
  a  address, y year built, ar architect, d year designated, b designation by-law (Toronto),
  t  building type (Toronto), hcd the Heritage Conservation District it is also in (Toronto), id.
Toronto's register can hold several address points for one property: one is kept (the primary address).

Usage: python3 engine/heritage_buildings.py <city>
"""
import json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
city = sys.argv[1]
RAW = os.path.join(ROOT, 'cities', city, 'raw', 'heritage_buildings.json')
OUT = os.path.join(ROOT, 'docs', city, 'data', 'heritage_buildings.geojson')
if not os.path.exists(RAW): sys.exit(f'{city}: no heritage buildings fetched yet (fetch-heritage-buildings.yml)')
R = json.load(open(RAW))
ABBR = {'ST': 'St', 'AVE': 'Ave', 'AV': 'Ave', 'RD': 'Rd', 'BLVD': 'Blvd', 'DR': 'Dr', 'CRES': 'Cres', 'CRT': 'Crt', 'PL': 'Pl', 'TER': 'Ter',
        'PKWY': 'Pkwy', 'LANE': 'Lane', 'GT': 'Gt', 'SQ': 'Sq', 'WAY': 'Way', 'CRCL': 'Crcl', 'PK': 'Park', 'GDNS': 'Gdns', 'TRL': 'Trl',
        'N': 'N', 'S': 'S', 'E': 'E', 'W': 'W'}


def tcase(s):
    out = []
    for w in re.sub(r'\s+', ' ', s or '').strip().split(' '):
        u = w.upper()
        if u in ABBR: out.append(ABBR[u])
        elif re.match(r'^\d+(ST|ND|RD|TH)$', u): out.append(u[:-2] + u[-2:].lower())
        elif re.match(r'^[\d-]+[A-Z]?$', u): out.append(u)
        else: out.append(u[:1] + u[1:].lower() if "'" not in u else "'".join(p[:1] + p[1:].lower() for p in u.split("'")))
    return ' '.join(out)


year = lambda v: (re.search(r'(1[6-9]\d\d|20\d\d)', str(v or '')) or [None])[0]
feats = []
if city == 'toronto':
    COUNCIL = re.compile(r'^(city council|council|part of|adopted|designat|included|listed|intention|the property|this property|by-?law|ola|oht|omb|olt)', re.I)
    def name_of(desc):
        d = (desc or '').strip()
        if not d or COUNCIL.match(d): return ''
        n = re.split(r'[,;(]|\s-\s?adopted|\s-adopted', d, maxsplit=1)[0].strip(' .-"\'“”')
        if re.match(r'^(see|refer|formerly|portion|rear|front|row|east|west|north|south|at|and|the|a|an|on|in|of)\b', n, re.I): return ''
        if re.search(r'identified through|convenience address|planning study|plan review|secondary plan|^exhibition pl$|^shop$|^pair of shops$|^city buildings$', n, re.I): return ''
        n = re.split(r'\.\s{2,}|\n', n, maxsplit=1)[0].strip(' .')
        if n.isupper(): n = re.sub(r"\b(And|Of|The|For|At)\b", lambda m: m.group(1).lower(), n.title()).replace("'S ", "'s ")   # "Glen Road Houses.  Semi-detached house" -> "Glen Road Houses"
        # A building type alone isn't a name ("Semi-detached house", "Commercial building", "Houses").
        if re.match(r'^((semi-?detached|detached|row|terrace|double|single|pair of|two|three|four|brick|frame|stone|stucco|commercial|residential|'
                    r'industrial|office|apartment|mixed[- ]use)\s+)*(house|houses|home|homes|building|buildings|residence|dwelling|store|stores|'
                    r'block|church|school|warehouse|factory|structure|townhouses?|row ?houses?|semi-detached|cottage|garage|stable)s?$', n, re.I): return ''
        if not n or len(n) > 70 or re.match(r'^\d', n) or re.search(r'adopted|council|by-law|designat', n, re.I): return ''
        return n
    best = {}
    for r in R['rows']:
        if r.get('STATUS') != 'Part IV' or r.get('lat') is None or (r.get('BUILDING_T') == 'Demolished'): continue
        k = r.get('Property_R') or r['ADDRESS']
        if k in best and best[k].get('ADDRESS_TY') == 'Primary': continue
        best[k] = r
    for r in best.values():
        p = {'n': name_of(r.get('DESCRIPTIO')), 'a': tcase(r.get('ADDRESS')), 'y': year(r.get('CONSTRUCTI')),
             'ar': (r.get('ARCHITECT_') or '').strip(), 'd': year(r.get('DESIGNATED')), 'b': (r.get('BYLAW_NO') or '').strip(),
             't': r.get('BUILDING_T') if r.get('BUILDING_T') not in ('Unknown', 'Miscellaneous', '') else '', 'hcd': (r.get('HTG_CONSER') or '').strip()}
        # "Smith, Eden" → "Eden Smith"; firms ("Darling and Pearson") stay as they are.
        m = re.match(r'^([A-Z][\w\'.-]+), ([A-Z][\w. ]+?)(\s*\(.*\))?$', p['ar'])
        if m and ' and ' not in p['ar'] and '&' not in p['ar']: p['ar'] = m.group(2).strip() + ' ' + m.group(1) + (m.group(3) or '')
        feats.append({'type': 'Feature', 'properties': {k: v for k, v in p.items() if v}, 'geometry': {'type': 'Point', 'coordinates': [round(r['lon'], 6), round(r['lat'], 6)]}})
elif city == 'vancouver':
    # The Vancouver Heritage Register: kept when municipally designated (protected by by-law), like Toronto's Part IV.
    # The A/B/C evaluation group goes in t; a register entry with no building name has only its address.
    for r in R['rows']:
        if str(r.get('municipaldesignationm')) not in ('Yes', 'Y') or r.get('lat') is None or r.get('status') != 'Active': continue
        num, street = (r.get('streetnumber') or '').strip(), (r.get('streetname') or '').strip()
        a = tcase(' '.join(x for x in (num, street) if x and x != 'N/A'))
        n = re.sub(r'\s+', ' ', (r.get('buildingnamespecifics') or '').replace('\u2011', '-').strip())
        n = re.sub(r'([“"])\s+', r'\1', n)
        n = re.sub(r'\s*(-\s*(includes .*|\d[\d-]*)|,\s*\d[\d-]*\s+\w+|\(\d[\d-]*\s+\w+\))\s*$', '', n).rstrip(' )-,') if not re.search(r'\([^)]*\)$', n) or re.search(r'\(\d', n) else n
        n = re.sub(r',\s*\d[\d-]*\s+[NSEW]?\s*[A-Z]\w+.*$', '', n)            # ", 315-321 W Cordova", ", 131 Water - part of…"
        n = re.sub(r'\s*\([^)]*$', '', n).strip()                                # an unclosed "(1900" or "(33-39 E Pender and"
        n = re.sub(r'\bBldg\b', 'Building', n).replace('Libary', 'Library')
        n = re.sub(r'\s+', ' ', re.sub(r'\s+-\s*|\s*-\s+', ' – ', n)).replace('St. Andrew’s – Wesley', 'St. Andrew’s-Wesley')
        if n.startswith('Facade only'): n = ''
        if re.match(r'^former [A-Z0-9]', n) and not re.match(r'^former \d', n): n = 'F' + n[1:]
        if n in ('None', 'N/A') or n.lower() == a.lower() or not n[:1].isupper() or re.match(r'^\d[\d-]*\s', n): n = ''
        p = {'n': n, 'a': a, 't': ('Group ' + r['evaluationgroup']) if r.get('evaluationgroup') in ('A', 'B', 'C') else '', 'id': r.get('id')}
        feats.append({'type': 'Feature', 'properties': {k: v for k, v in p.items() if v}, 'geometry': {'type': 'Point', 'coordinates': [round(r['lon'], 6), round(r['lat'], 6)]}})
elif city == 'nyc':
    # Landmarks Preservation Commission individual landmark sites: interior and scenic landmarks are left out
    # (a building's interior is inside an individual landmark, scenic ones are parks). The parcels come in State
    # Plane feet, so each point is the record's own latitude and longitude.
    for r in R['rows']:
        if not (r.get('landmarkty') or '').startswith('Individual') or not r.get('latitude'): continue
        if (r.get('lpc_sitest') or 'Designated') not in ('Designated', 'Amended'): continue
        p = {'n': (r.get('lpc_name') or '').strip(), 'a': tcase(r.get('address') or ''), 'd': year(r.get('desdate')), 'id': r.get('lpc_lpnumb')}
        feats.append({'type': 'Feature', 'properties': {k: v for k, v in p.items() if v},
                      'geometry': {'type': 'Point', 'coordinates': [round(float(r['longitude']), 6), round(float(r['latitude']), 6)]}})
else:
    F = {k.lower(): k for k in R['fields']}
    g = lambda r, *names: next((r.get(F.get(n, n)) for n in names if r.get(F.get(n, n)) not in (None, '', 'None')), '')
    for r in R['rows']:
        if r.get('lat') is None: continue
        ar = g(r, 'architect')
        p = {'n': re.sub(r'\bBldg\b', 'Building', g(r, 'name', 'landmark_name')), 'a': re.sub(r'\bAv\b', 'Ave', g(r, 'address')), 'y': year(g(r, 'date_built')),
             'ar': '' if re.match(r'^(architect )?unknown$', ar, re.I) else ar, 'd': year(g(r, 'landmark', 'landmark_designation_date')), 'id': g(r, 'id')}
        feats.append({'type': 'Feature', 'properties': {k: v for k, v in p.items() if v}, 'geometry': {'type': 'Point', 'coordinates': [round(r['lon'], 6), round(r['lat'], 6)]}})
feats.sort(key=lambda f: f['properties'].get('n') or f['properties'].get('a', ''))
json.dump({'type': 'FeatureCollection', 'asof': R['fetched'], 'features': feats}, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
named = sum(1 for f in feats if f['properties'].get('n'))
print(f"{city}: {len(feats)} heritage buildings ({named} named, {sum(1 for f in feats if f['properties'].get('ar'))} with an architect) · {os.path.getsize(OUT) // 1024} KB")
for f in feats[:5] + feats[-3:]: print('  ', f['properties'])
