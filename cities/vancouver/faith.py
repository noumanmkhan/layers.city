"""Places of worship for the Faith & Community layers.
Inputs: raw/faith/worship_osm.json (fetch_faith.py), faith_overrides.csv. Output: docs/vancouver/data/faith.geojson,
one point per place, with "cat" for its toggle.

The rules (Toronto's, decided October 14, 2026; Vancouver mirrors them, October 16):
- Map facilities, never people: no layer, label or shading says who lives anywhere.
- Places of worship come from OpenStreetMap, named ones only, one point per place (a node and the
  building drawn round it, or two pins for one congregation, collapse to one). Churches inside the City; other
  faiths across Metro Vancouver, as in Chicago (most gurdwaras and many mosques and mandirs are in Surrey, Burnaby
  and Richmond). faith_overrides.csv adds ("add", with its own lat/lon), corrects ("fix") or drops ("drop").
  Denomination is shown only where OSM or the overrides give one; it is never guessed.
- Church families are Toronto's (Canadian denominations: Anglican and United among them).
- No halal or kosher shops: no BC certifier publishes the shops it certifies (PARKED.md)."""
import csv, json, math, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'faith')
OUT = os.path.join(HERE, '..', '..', 'docs', 'vancouver', 'data', 'faith.geojson')
CAT = {'muslim': 'mosque', 'sikh': 'gurdwara', 'jewish': 'synagogue', 'hindu': 'hindu', 'buddhist': 'buddhist',
       'christian': 'church'}   # anything else (Jain, Bahá'í, Zoroastrian, Unitarian…) is "otherfaith"
NOUN = {'mosque': 'Mosque', 'gurdwara': 'Gurdwara', 'synagogue': 'Synagogue', 'hindu': 'Hindu temple',
        'buddhist': 'Buddhist temple', 'church': 'Church'}
FAITH = {'jain': 'Jain', 'bahai': 'Bahá’í', 'zoroastrian': 'Zoroastrian', 'unitarian_universalist': 'Unitarian',
         'taoist': 'Taoist', 'shinto': 'Shinto', 'spiritualist': 'Spiritualist', 'multifaith': 'Multifaith'}


# Church families for the Churches layer's chips: Toronto's (Anglican, United and the rest). From the OSM
# denomination first, then, where OSM gives none, from words in the name. A church with neither shows only under
# All. Order matters: the first match wins.
CHURCH = [
    ('orthodox', ('orthodox', 'armenian_apostolic', 'coptic')),
    ('catholic', ('catholic',)),
    ('anglican', ('anglican', 'episcopal')),
    ('baptist', ('baptist',)),
    ('united', ('united',)),
    ('presbyterian', ('presbyterian',)),
    ('evangelical', ('evangelical', 'pentecostal', 'gospel', 'apostolic', 'nazarene', 'alliance', 'assemblies_of_god',
                     'assembly_of_god', 'foursquare', 'charismatic', 'vineyard', 'church_of_god')),
]
NAMED = [
    ('orthodox', r'orthodox|coptic|armenian apostolic'),
    ('catholic', r'catholic|\br\.? ?c\.?\b|our lady|\bparish of\b'),
    ('anglican', r'anglican|episcopal'),
    ('baptist', r'baptist'),
    ('united', r'united church(?! of jesus)'),
    ('presbyterian', r'presbyterian'),
    ('evangelical', r'evangelical|pentecostal|full gospel|gospel (hall|church|assembly|tabernacle)|assembl(y|ies) of god|'
                    r'alliance church|apostolic|foursquare|nazarene|tabernacle|revival|church of god|united church of jesus'),
    ('other', r'lutheran|adventist|kingdom hall|jehovah|salvation army|mennonite|latter-day|methodist|reformed|'
              r'christadelphian|christian science|church of christ|brethren|moravian|quaker|friends meeting'),
]


def church_group(den, name):
    d = (den or '').lower()
    if d and d not in ('protestant', 'christian', 'nondenominational', 'non-denominational', 'biblical'):
        return next((g for g, keys in CHURCH if any(k in d for k in keys)), 'other')
    return next((g for g, rx in NAMED if re.search(rx, name, re.I)), 'other' if d else '')


def metres(a, b):
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * 111320 * k, (a[1] - b[1]) * 110540)


def nice(s):
    return s.replace('_', ' ').strip().capitalize() if s else ''


osm = json.load(open(os.path.join(RAW, 'worship_osm.json')))['elements']
rows = list(csv.DictReader(open(os.path.join(HERE, 'faith_overrides.csv'), encoding='utf-8')))
fix = {r['osm']: r for r in rows if r['action'] == 'fix'}
drop = {r['osm'] for r in rows if r['action'] == 'drop'}
known = {e['osm'] for e in osm}
stale = [o for o in list(fix) + list(drop) if o not in known]
if stale: print('  note: override rows for OSM ids no longer in the fetch:', ', '.join(stale))


def place(r):
    return [round(float(r['lon']), 5), round(float(r['lat']), 5)] if r.get('lat') and r.get('lon') else None


worship, unplaced = [], []
for e in osm:
    if e['osm'] in drop: continue
    f = fix.get(e['osm'], {})
    rel = f.get('faith') or e.get('religion') or (e.get('denomination') if e.get('denomination') in CAT else '')
    worship.append({'name': f.get('name') or e['name'], 'rel': rel, 'den': f.get('denomination') or e.get('denomination', ''),
                    'at': [round(float(f['lon']), 5), round(float(f['lat']), 5)] if f.get('lat') else e['at'], 'osm': e['osm']})
for r in rows:
    if r['action'] != 'add': continue
    at = place(r)
    if not at: unplaced.append(r['name']); continue
    worship.append({'name': r['name'], 'rel': r['faith'], 'den': r['denomination'], 'at': at, 'osm': ''})

# One point per place: the same name within 150 m is the same congregation (a node inside its building).
worship.sort(key=lambda w: (w['osm'][:1] != 'n', w['name']))   # keep the hand-placed node where there is one
kept = []
for w in worship:
    if any(k['name'].lower() == w['name'].lower() and metres(k['at'], w['at']) < 150 for k in kept): continue
    kept.append(w)

feats = []
for w in kept:
    cat = CAT.get(w['rel'], 'otherfaith')
    sub = ' · '.join(x for x in ((NOUN.get(cat) or FAITH.get(w['rel']) or nice(w['rel']) or 'Place of worship'), nice(w['den'])) if x)
    props = {'name': w['name'], 'cat': cat, 'sub': sub}
    if cat == 'church':
        props['grp'] = church_group(w['den'], w['name'])
        if not props['grp']: del props['grp']
    feats.append({'type': 'Feature', 'properties': props, 'geometry': {'type': 'Point', 'coordinates': w['at']}})

feats.sort(key=lambda f: (f['properties']['cat'], f['properties']['name']))
json.dump({'type': 'FeatureCollection', 'features': feats}, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
count = {}
for f in feats: count[f['properties']['cat']] = count.get(f['properties']['cat'], 0) + 1
print('faith and community:', count, '| merged duplicates:', len(worship) - len(kept))
ch = [f['properties'] for f in feats if f['properties']['cat'] == 'church']
grp = {}
for p in ch: grp[p.get('grp', '(none)')] = grp.get(p.get('grp', '(none)'), 0) + 1
print('  churches by family:', dict(sorted(grp.items(), key=lambda kv: -kv[1])))
if unplaced: print('  NOT PLACED (add lat/lon to the CSV, or fix the address):', '; '.join(unplaced))
