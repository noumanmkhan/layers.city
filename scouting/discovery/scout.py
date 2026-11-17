"""Scout OpenStreetMap for the discovery points of interest (cafés, bakeries, character shops, public art, viewpoints)
inside the City of Toronto. Run by scout.yml; writes to scouting/discovery/out/.

Source: BBBike's Toronto extract (the same file fetch_transit_union.py uses), falling back to Geofabrik's Ontario
extract. Public Overpass servers are avoided (they time out, and refuse the sandbox). OSM data is ODbL: the CSVs in
out/ are OpenStreetMap contributors' data and keep that licence.

For each kind in the project's discovery brief (claude/discovery-pois-brief.md) it counts every place, then splits
them two ways (the brief's character test, revised November 17, 2026: only megachains are left out):
  megachain - a national or multinational chain in MEGACHAINS, matched on the brand tag, a brand:wikidata id seen on
              one of them, or the normalised name
  local     - everything else, small local chains included even when they carry a brand tag: the candidates,
              written to out/<kind>.csv
The old "same name at 4+ places" test no longer decides anything; it's kept as an informational count (name_count in
the CSVs, name_4plus and branded_local in report.json) to help spot chains the list is missing.
It also counts the tags that hint at a story (start_date, wikidata, wikipedia, heritage, website, description).

Set OSM_FILE to a local .osm/.pbf to test without downloading."""
import collections, csv, json, os, re, sys, tempfile, time, unicodedata, urllib.request
import osmium
from shapely import wkb
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, 'out'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}
SOURCES = ['https://download.bbbike.org/osm/bbbike/Toronto/Toronto.osm.pbf',
           'https://download.geofabrik.de/north-america/canada/ontario-latest.osm.pbf']
CHAIN_MIN = 4     # informational only: a name seen this many times in the city is counted in name_4plus

# National and multinational chains: the only businesses left out. Each entry is a name, its other spellings, and
# optionally the kinds it applies to (for names a local place could share, like a restaurant called "Michael's").
# A place matches when its brand or name, normalised, equals one of these or starts with one followed by more words
# ("Starbucks Reserve", "The Keg Steakhouse"), unless the entry is marked exact. Regional franchises (Sunset Grill,
# Eggsmart, St. Louis Bar & Grill, Wild Wing, Mr. Greek, Shoeless Joe's...) are not on it: see FINDINGS.md.
MEGACHAINS = [
    # coffee, doughnuts, bubble tea
    ('Tim Hortons', ['Tim Horton']), ('Starbucks', []), ('Second Cup', []), ('Aroma Espresso Bar', []),
    ('Aroma', [], ('cafes',), 'exact'),
    ('Country Style', []), ('Coffee Time', []), ('McCafe', []), ("Timothy's", ["Timothy's World Coffee"]),
    ("Dunkin'", ['Dunkin Donuts']), ('Krispy Kreme', []), ('Blenz', []), ('Good Earth Coffeehouse', ['Good Earth'], ('cafes',)),
    ('Booster Juice', []), ('Jugo Juice', []), ('DavidsTea', ["David's Tea"]),
    ('CoCo', ['CoCo Fresh Tea & Juice', 'CoCo Fresh Tea'], None, 'exact'), ('Chatime', []), ('Gong Cha', []),
    ('Real Fruit Bubble Tea', []), ('Kung Fu Tea', []), ('Presotea', []), ('Sharetea', []), ('Tiger Sugar', []),
    ('The Alley', [], ('cafes', 'specialty_food'), 'exact'), ('Xing Fu Tang', []), ('Machi Machi', []), ('Yi Fang', []),
    ("Ten Ren's Tea", ['Ten Ren']), ('Heytea', []), ('Happy Lemon', []), ('Chicha San Chen', []), ('Nespresso', []),
    ('Cotti Coffee', []),
    # bakeries, sweets
    ('COBS Bread', ['COBS']), ('Paris Baguette', []), ('Tous les Jours', []), ('Brioche Dorée', []), ('Mrs. Fields', []),
    ('Insomnia Cookies', []), ('Nothing Bundt Cakes', []), ('Crumbl', []), ('Cinnabon', []), ('Kernels', []),
    ('Lindt', []), ('Godiva', ['Godiva Chocolatier']), ('Purdys Chocolatier', ['Purdys', "Purdy's"]),
    ('Laura Secord', []), ('Läderach', []), ('Rocky Mountain Chocolate Factory', []), ('vomFASS', []), ('Bulk Barn', []),
    # restaurants
    ('Swiss Chalet', []), ('Pizza Hut', []), ('Freshii', []), ('Boston Pizza', []), ('The Keg', []),
    ("Jack Astor's", []), ("McDonald's", []), ('Subway', [], ('restaurants', 'cafes')), ('A&W', []), ("Wendy's", []),
    ('Burger King', []), ('KFC', ['Kentucky Fried Chicken']), ('Popeyes', []), ('Pizza Pizza', []), ("Domino's", []),
    ("Papa John's", []), ('Little Caesars', []), ("Mary Brown's", []), ("Harvey's", []), ('Dairy Queen', []),
    ('Taco Bell', []), ('Chipotle', []), ('Five Guys', []), ('Mr. Sub', []), ('Quesada', []), ("Osmow's", []),
    ('Pita Pit', []), ('Panera Bread', []), ("Montana's", []), ("Kelsey's", []), ("East Side Mario's", []),
    ('Milestones', []), ('Earls', ['Earls Kitchen + Bar'], ('restaurants',), 'exact'), ('Cactus Club Cafe', []), ('JOEY', [], ('restaurants',), 'exact'),
    ("Moxie's", []), ('The Old Spaghetti Factory', []), ("Denny's", []), ('Cora', [], ('restaurants',), 'exact'),
    ('Chuck E. Cheese', []), ('Thai Express', []), ('Mucho Burrito', []), ('Sushi Shop', []), ('Manchu Wok', []),
    ("Nando's", []), ('Shake Shack', []), ('Baskin-Robbins', []), ('St-Hubert', []), ('Sbarro', []),
    ('Red Lobster', []), ('Hooters', []), ('bb.q Chicken', ['bbq Chicken']),
    # shops
    ('Indigo', ['Chapters'], ('books',)), ('Coles', [], ('books',)), ('Sunrise Records', []), ('HMV', []),
    ('Value Village', ['Savers'], ('vintage',)), ("Plato's Closet", []), ('Mastermind Toys', []), ('Toys R Us', ['Toys"R"Us']),
    ('Lego', ['The Lego Store'], ('comics_games_toys',)), ('EB Games', []), ('GameStop', []),
    ('Michaels', [], ('makers_oddities',)), ('Long & McQuade', []), ('DeSerres', []), ('Lumas', []), ('YellowKorner', []),
]

# Kinds from the discovery brief. Each test takes the tag dict and returns True when the place is that kind.
# Order matters: the first match wins, so each place has exactly one kind.
A = lambda t, k, *v: t.get(k) in v
KINDS = [
    ('murals',            'Public art',      lambda t: A(t, 'tourism', 'artwork') and A(t, 'artwork_type', 'mural', 'graffiti', 'painting')),
    ('sculptures',        'Public art',      lambda t: A(t, 'tourism', 'artwork') and A(t, 'artwork_type', 'sculpture', 'statue', 'bust', 'relief', 'stone')),
    ('monuments',         'Public art',      lambda t: A(t, 'historic', 'memorial', 'monument') and not A(t, 'memorial', 'plaque', 'blue_plaque', 'ghost_bike')),
    ('installations',     'Public art',      lambda t: A(t, 'tourism', 'artwork')),   # every other artwork_type, or none
    ('cafes',             'Food & drink',    lambda t: A(t, 'amenity', 'cafe') or A(t, 'shop', 'coffee')),
    ('bakeries',          'Food & drink',    lambda t: A(t, 'shop', 'bakery', 'pastry')),
    ('restaurants',       'Food & drink',    lambda t: A(t, 'amenity', 'restaurant')),
    ('markets',           'Food & drink',    lambda t: A(t, 'amenity', 'marketplace', 'food_court')),
    ('books',             'Character shops', lambda t: A(t, 'shop', 'books') and not A(t, 'books', 'comic', 'comics')),
    ('records',           'Character shops', lambda t: A(t, 'shop', 'music')),
    ('vintage',           'Character shops', lambda t: A(t, 'shop', 'antiques', 'second_hand') or (A(t, 'shop', 'clothes') and A(t, 'second_hand', 'only'))),
    ('comics_games_toys', 'Character shops', lambda t: A(t, 'shop', 'games', 'toys', 'comic', 'anime', 'hobby', 'model') or (A(t, 'shop', 'books') and A(t, 'books', 'comic', 'comics'))),
    ('specialty_food',    'Character shops', lambda t: A(t, 'shop', 'cheese', 'deli', 'spices', 'tea', 'chocolate', 'confectionery', 'butcher', 'seafood', 'pasta', 'nuts')),
    ('makers_oddities',   'Character shops', lambda t: A(t, 'shop', 'art', 'collector', 'craft', 'frame', 'musical_instrument')),
    ('viewpoints',        'Places',          lambda t: A(t, 'tourism', 'viewpoint')),
]
STORY = ['start_date', 'wikidata', 'wikipedia', 'heritage', 'description', 'website', 'opening_hours']
KEEP = ['name', 'brand', 'brand:wikidata', 'operator', 'amenity', 'shop', 'tourism', 'historic', 'artwork_type', 'artist_name',
        'cuisine', 'start_date', 'wikidata', 'wikipedia', 'heritage', 'description', 'website', 'addr:housenumber', 'addr:street']


def kind_of(t):
    for k, fam, test in KINDS:
        try:
            if test(t): return k, fam
        except Exception: pass
    return None, None


def download():
    if os.environ.get('OSM_FILE'): return os.environ['OSM_FILE']
    tmp = tempfile.mkdtemp()
    for url in SOURCES:
        p = os.path.join(tmp, os.path.basename(url))
        for i in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=1800) as r, open(p, 'wb') as f:
                    while True:
                        b = r.read(1 << 22)
                        if not b: break
                        f.write(b)
                print('downloaded', url, os.path.getsize(p) // 1_000_000, 'MB', flush=True)
                return p
            except Exception as e:
                print('  retry', i + 1, url, e, flush=True); time.sleep(30)
    raise RuntimeError('no extract')


def city():
    """Toronto's 158 neighbourhoods from the published map, for clipping and naming."""
    fc = json.load(open(os.path.join(ROOT, 'docs', 'toronto', 'data', 'neighbourhoods.geojson')))
    polys = [shape(f['geometry']).buffer(0) for f in fc['features']]
    names = [f['properties']['name'] for f in fc['features']]
    return STRtree(polys), polys, names


class Grab(osmium.SimpleHandler):
    """Every node, way or area whose tags match a kind. Ways are taken from the area callback when closed."""
    def __init__(self):
        super().__init__()
        self.fab = osmium.geom.WKBFactory()
        self.items = []

    def add(self, typ, oid, tags, pt):
        t = {k: v for k, v in tags}
        k, fam = kind_of(t)
        if not k: return
        self.items.append({'osm': '%s/%d' % (typ, oid), 'kind': k, 'family': fam, 'lon': round(pt.x, 6), 'lat': round(pt.y, 6), 't': t})

    def node(self, n):
        if n.location.valid() and len(n.tags): self.add('node', n.id, n.tags, Point(n.location.lon, n.location.lat))

    def way(self, w):
        # Open ways only (e.g. a mural mapped along a wall); closed ones arrive in area().
        if not len(w.tags) or w.is_closed(): return
        try: g = wkb.loads(self.fab.create_linestring(w), hex=True)
        except Exception: return
        self.add('way', w.id, w.tags, g.interpolate(0.5, normalized=True))

    def area(self, a):
        if not len(a.tags): return
        try: g = wkb.loads(self.fab.create_multipolygon(a), hex=True)
        except Exception: return
        self.add('way' if a.from_way() else 'relation', a.orig_id(), a.tags, g.representative_point())


def norm(name):
    """Lower case, accents and apostrophes dropped, & as 'and', everything else to single spaces."""
    s = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"['’`]", '', s.replace('&', ' and '))
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def megachain_rules():
    """(normalised name, kinds or None, exact) for every name and spelling in MEGACHAINS."""
    rules = []
    for e in MEGACHAINS:
        name, alts, kinds, mode = (tuple(e) + (None, None))[:4]
        for n in [name] + list(alts):
            rules.append((norm(n), set(kinds) if kinds else None, mode == 'exact'))
    return rules


def megachain_of(t, kind, rules):
    """The rule a place's brand or name matches, or None."""
    for v in (t.get('brand'), t.get('name')):
        n = norm(v)
        if not n: continue
        for r, kinds, exact in rules:
            if kinds and kind not in kinds: continue
            if n == r or (not exact and n.startswith(r + ' ')): return r
    return None


if __name__ == '__main__':
    src = download()
    tree, polys, names = city()
    h = Grab()
    h.apply_file(src, locations=True, idx='flex_mem')
    print('matched in extract', len(h.items), flush=True)

    inside = []
    for it in h.items:
        p = Point(it['lon'], it['lat'])
        for i in tree.query(p):
            if polys[i].contains(p):
                it['nbhd'] = names[i]; inside.append(it); break
    print('inside Toronto', len(inside), flush=True)

    # Megachains by brand or name, then by any brand:wikidata id seen on one of them (catches odd spellings).
    rules = megachain_rules()
    for it in inside:
        it['class'] = 'megachain' if megachain_of(it['t'], it['kind'], rules) else 'local'
    qids = {it['t']['brand:wikidata'] for it in inside if it['class'] == 'megachain' and it['t'].get('brand:wikidata')}
    for it in inside:
        if it['class'] == 'local' and it['t'].get('brand:wikidata') in qids: it['class'] = 'megachain'
    # Informational: how many places in the city (all kinds) share each name.
    namecount = collections.Counter(norm(it['t'].get('name')) for it in inside if it['t'].get('name'))
    for it in inside:
        it['name_count'] = namecount[norm(it['t'].get('name'))] if it['t'].get('name') else 0

    report = {'source': os.path.basename(src), 'chain_min': CHAIN_MIN, 'megachain_names': len(MEGACHAINS), 'kinds': {}}
    for k, fam, _ in KINDS:
        rows = [it for it in inside if it['kind'] == k]
        ind = [it for it in rows if it['class'] == 'local']
        named = [it for it in ind if it['t'].get('name')]
        report['kinds'][k] = {
            'family': fam, 'total': len(rows),
            'megachain': sum(it['class'] == 'megachain' for it in rows),
            'local': len(ind), 'local_named': len(named),
            'branded_local': sum(1 for it in ind if it['t'].get('brand') or it['t'].get('brand:wikidata')),
            'name_4plus': sum(1 for it in ind if it['name_count'] >= CHAIN_MIN),
            'story_tags_on_local': {s: sum(1 for it in ind if it['t'].get(s)) for s in STORY},
            'top_neighbourhoods': collections.Counter(it['nbhd'] for it in ind).most_common(10),
            'top_megachains': collections.Counter(it['t'].get('brand') or it['t'].get('name') for it in rows
                                                  if it['class'] == 'megachain').most_common(15),
            # Names among the candidates seen 2+ times or carrying a brand tag: where to look for a missing megachain.
            'top_local_repeats': collections.Counter(it['t'].get('brand') or it['t'].get('name') for it in ind
                                                     if it['name_count'] >= 2 or it['t'].get('brand')).most_common(20),
        }
        if k in ('murals', 'sculptures', 'installations'):
            report['kinds'][k]['artwork_types'] = collections.Counter(it['t'].get('artwork_type', '(none)') for it in rows).most_common()
        if k == 'restaurants':
            report['kinds'][k]['cuisines_independent'] = collections.Counter(
                c.strip() for it in ind for c in (it['t'].get('cuisine') or '(none)').split(';')).most_common(25)
        with open(os.path.join(OUT, k + '.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['osm', 'neighbourhood', 'lat', 'lon'] + KEEP + ['name_count'])
            for it in sorted(ind, key=lambda x: (x['nbhd'], x['t'].get('name', ''))):
                w.writerow([it['osm'], it['nbhd'], it['lat'], it['lon']] + [it['t'].get(c, '') for c in KEEP] + [it['name_count']])

    with open(os.path.join(OUT, 'report.json'), 'w') as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    print('\n%-18s %6s %6s %6s %6s %7s %6s' % ('kind', 'total', 'mega', 'local', 'named', 'brand+', 'name4+'))
    for k, r in report['kinds'].items():
        print('%-18s %6d %6d %6d %6d %7d %6d' % (k, r['total'], r['megachain'], r['local'], r['local_named'],
                                                r['branded_local'], r['name_4plus']))
    print('\nwrote report.json and one CSV per kind (local candidates). Data: (c) OpenStreetMap contributors, ODbL.')
    import match   # the City's described places, matched to these candidates (match.py)
    match.main()
