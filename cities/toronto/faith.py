"""Places of worship and halal/kosher food shops for the Faith & Community layers.
Inputs: raw/faith/worship_osm.json and raw/faith/geocode.json (fetch_faith.py), faith_overrides.csv,
faith_shops.csv. Output: docs/toronto/data/faith.geojson, one point per place, with "cat" for its toggle.

The rules (decided October 14, 2026; see the Faith & Community spec):
- Map facilities, never people: no layer, label or shading says who lives anywhere.
- Places of worship come from OpenStreetMap, named ones only, one point per place (a node and the
  building drawn round it, or two pins for one congregation, collapse to one). OSM misses storefront
  congregations and new buildings, so faith_overrides.csv adds them ("add"), corrects them ("fix": any
  field it fills wins) or takes them out ("drop"). Denomination is shown only where OSM or the overrides
  give one; it is never guessed.
- Food shops come from the certifiers' own lists (HMA for halal, COR for kosher), curated in
  faith_shops.csv: independent grocers, butchers and bakeries selling food to take home, one point per
  shop with all its roles; chains with a halal or kosher aisle, wholesalers and restaurants are left out.
  Restaurants belong to a future commercial layer."""
import csv, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'faith')
OUT = os.path.join(HERE, '..', '..', 'docs', 'toronto', 'data', 'faith.geojson')
CAT = {'muslim': 'mosque', 'sikh': 'gurdwara', 'jewish': 'synagogue', 'hindu': 'hindu', 'buddhist': 'buddhist',
       'christian': 'church'}   # anything else (Jain, Bahá'í, Zoroastrian, Unitarian…) is "otherfaith"
NOUN = {'mosque': 'Mosque', 'gurdwara': 'Gurdwara', 'synagogue': 'Synagogue', 'hindu': 'Hindu temple',
        'buddhist': 'Buddhist temple', 'church': 'Church'}
FAITH = {'jain': 'Jain', 'bahai': 'Bahá’í', 'zoroastrian': 'Zoroastrian', 'unitarian_universalist': 'Unitarian',
         'taoist': 'Taoist', 'shinto': 'Shinto', 'spiritualist': 'Spiritualist', 'multifaith': 'Multifaith'}


def metres(a, b):
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * 111320 * k, (a[1] - b[1]) * 110540)


def nice(s):
    return s.replace('_', ' ').strip().capitalize() if s else ''


osm = json.load(open(os.path.join(RAW, 'worship_osm.json')))['elements']
geo = json.load(open(os.path.join(RAW, 'geocode.json')))
rows = list(csv.DictReader(open(os.path.join(HERE, 'faith_overrides.csv'), encoding='utf-8')))
fix = {r['osm']: r for r in rows if r['action'] == 'fix'}
drop = {r['osm'] for r in rows if r['action'] == 'drop'}
known = {e['osm'] for e in osm}
stale = [o for o in list(fix) + list(drop) if o not in known]
if stale: print('  note: override rows for OSM ids no longer in the fetch:', ', '.join(stale))


def place(r):
    if r.get('lat') and r.get('lon'): return [round(float(r['lon']), 5), round(float(r['lat']), 5)]
    hit = geo.get(r['address'] + ', ' + r['locality'], {})
    return hit.get('at')


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
    feats.append({'type': 'Feature', 'properties': {'name': w['name'], 'cat': cat, 'sub': sub},
                  'geometry': {'type': 'Point', 'coordinates': w['at']}})

ROLE = (('grocer', 'grocer'), ('butcher', 'butcher'), ('bakery', 'bakery'))
for r in csv.DictReader(open(os.path.join(HERE, 'faith_shops.csv'), encoding='utf-8')):
    at = place(r)
    if not at: unplaced.append(r['name'] + (' (' + r['sub'] + ')' if r['sub'] else '')); continue
    roles = [label for key, label in ROLE if r[key]]
    what = ', '.join(roles[:-1]) + ' and ' + roles[-1] if len(roles) > 1 else roles[0]
    sub = ' · '.join(x for x in (r['sub'], r['diet'].capitalize() + ' ' + what, r['certifier'] + '-certified') if x)
    feats.append({'type': 'Feature', 'properties': {'name': r['name'], 'cat': r['diet'], 'sub': sub, 'roles': roles,
                                                    'cert': r['certifier']},
                  'geometry': {'type': 'Point', 'coordinates': at}})

feats.sort(key=lambda f: (f['properties']['cat'], f['properties']['name']))
json.dump({'type': 'FeatureCollection', 'features': feats}, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
count = {}
for f in feats: count[f['properties']['cat']] = count.get(f['properties']['cat'], 0) + 1
print('faith and community:', count, '| merged duplicates:', len(worship) - len(kept))
if unplaced: print('  NOT PLACED (add lat/lon to the CSV, or fix the address):', '; '.join(unplaced))
