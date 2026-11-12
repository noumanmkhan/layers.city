"""Representation in the City of Melbourne: the boundary layers and who holds each seat.
Inputs: raw/representatives/ (fetch_representatives.py), council.json (hand-kept), tmp/suburbs.geojson (build.py)
Output: tmp/state.geojson and tmp/federal.geojson (Assembly districts and federal divisions cut to the City; run.sh
simplifies them into docs), docs/melbourne/data/representatives.json
  {"updated", "mayor": {"city", "deputy"}, "fed": {division: {name, party, url}}}

Federal members: the Parliamentary Handbook's current members for Victoria (so a by-election since 2025 shows), checked
against the AEC's 2025 members elected. Members of the Legislative Assembly are added after the November 28, 2026
election; until then the card names the district only. "updated" changes only when a name, party or link does."""
import csv, datetime as dt, io, json, os, re
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, polylabel

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'representatives')
TMP = os.path.join(HERE, 'tmp')
OUT = os.path.join(HERE, '..', '..', 'docs', 'melbourne', 'data', 'representatives.json')
os.makedirs(TMP, exist_ok=True)
SUB = os.path.join(TMP, 'suburbs.geojson')   # the weekly job has no tmp/: the published suburbs then
SUB = SUB if os.path.exists(SUB) else os.path.join(HERE, '..', '..', 'docs', 'melbourne', 'data', 'suburbs.geojson')
CITY = unary_union([shape(f['geometry']).buffer(0) for f in json.load(open(SUB))['features']])
KM2 = 88.2 * 111.2


def label_pt(g):
    g = max(getattr(g, 'geoms', [g]), key=lambda p: p.area)
    try: p = polylabel(g, tolerance=0.0001)
    except Exception: p = g.representative_point()
    return [round(p.x, 5), round(p.y, 5)]


def cut(fname, name_of, out, extra=lambda p: {}):
    feats = []
    for f in json.load(open(os.path.join(RAW, fname)))['features']:
        g = shape(f['geometry']).buffer(0).intersection(CITY)
        g = unary_union([p for p in getattr(g, 'geoms', [g]) if p.geom_type in ('Polygon', 'MultiPolygon')])
        if g.is_empty or g.area * KM2 < 0.05: continue   # slivers where the lines differ by a street's width
        n = name_of(f['properties'])
        feats.append({'type': 'Feature', 'properties': dict({'name': n, 'lp': label_pt(g)}, **extra(f['properties'])), 'geometry': mapping(g)})
    feats.sort(key=lambda f: f['properties']['name'])
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(TMP, out), 'w'), separators=(',', ':'))
    print(out, [(f['properties']['name'], round(shape(f['geometry']).area * KM2, 1)) for f in feats])
    return [f['properties']['name'] for f in feats]


title = lambda s: re.sub(r"\b(Mc|Mac|O')([a-z])", lambda m: m.group(1) + m.group(2).upper(), s.title())
state = cut('districts.geojson', lambda p: title(p['district']).replace(' District', ''), 'state.geojson',
            lambda p: {'region': title(p.get('region') or '').replace(' Region', '')})
fed = cut('divisions.geojson', lambda p: p['Elect_div'], 'federal.geojson')

PARTY = {'ALP': 'Labor', 'LIB': 'Liberal', 'LP': 'Liberal', 'GRN': 'Greens', 'GVIC': 'Greens', 'NAT': 'Nationals', 'IND': 'Independent', 'LNP': 'Liberal National'}
hb = {r['Electorate']: r for r in json.load(open(os.path.join(RAW, 'handbook.json')))
      if r.get('StateAbbrev') == 'Vic' and 'Member' in str(r.get('MPorSenator')) and r.get('Electorate')}
txt = open(os.path.join(RAW, 'aec_elected.csv'), encoding='utf-8-sig').read().splitlines()
aec = {r['DivisionNm']: r for r in csv.DictReader(io.StringIO('\n'.join(txt[1:]))) if r['StateAb'] == 'VIC'}
members, problems = {}, []
for d in fed:
    h, a = hb.get(d), aec.get(d)
    if h:
        given = (h.get('PreferredName') or h['GivenName']).strip('() ')
        members[d] = {'name': given + ' ' + title(h['FamilyName']), 'party': PARTY.get(h['PartyAbbrev'], h['Party']),
                      'url': 'https://www.aph.gov.au/Senators_and_Members/Parliamentarian?MPID=' + h['PHID']}
        if a and title(a['Surname']) != title(h['FamilyName']): problems.append('%s: the Handbook has %s, the AEC elected %s %s (by-election?)' % (d, h['DisplayName'], a['GivenNm'], a['Surname']))
    elif a:
        members[d] = {'name': a['GivenNm'].title() + ' ' + title(a['Surname']), 'party': PARTY.get(a['PartyAb'], a['PartyNm']),
                      'url': 'https://results.aec.gov.au/31496/Website/HouseDivisionPage-31496-%s.htm' % a['DivisionID']}
        problems.append(d + ': not in the Handbook; AEC 2025 result used')
    else:
        members[d] = None; problems.append(d + ': no member found (vacant?)')

C = json.load(open(os.path.join(HERE, 'council.json')))
data = {'mayor': {'city': C['mayor'], 'deputy': C['deputy']}, 'fed': members}
old = json.load(open(OUT)) if os.path.exists(OUT) else {}
out = dict(updated=old.get('updated') if {k: old.get(k) for k in data} == data else dt.date.today().isoformat(), **data)
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
print('state districts', state, '· MPs', {k: (v or {}).get('name') for k, v in members.items()})
if problems: print('  ' + '\n  '.join(problems))
