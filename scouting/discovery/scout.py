"""Scout OpenStreetMap for the discovery points of interest (cafés, bakeries, character shops, public art, viewpoints)
inside the City of Toronto. Run by scout.yml; writes to scouting/discovery/out/.

Source: BBBike's Toronto extract (the same file fetch_transit_union.py uses), falling back to Geofabrik's Ontario
extract. Public Overpass servers are avoided (they time out, and refuse the sandbox). OSM data is ODbL: the CSVs in
out/ are OpenStreetMap contributors' data and keep that licence.

For each kind in the project's discovery brief (claude/discovery-pois-brief.md) it counts every place, then splits
them three ways:
  branded      - has a brand or brand:wikidata tag
  likely chain - no brand tag, but the same name appears at 4 or more places in the city
  independent  - everything else: the candidates for the "character test", written to out/<kind>.csv
It also counts the tags that hint at a story (start_date, wikidata, wikipedia, heritage, website, description).

Set OSM_FILE to a local .osm/.pbf to test without downloading."""
import collections, csv, json, os, re, sys, tempfile, time, urllib.request
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
CHAIN_MIN = 4     # unbranded name seen this many times in the city = likely a chain

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
    ('makers_oddities',   'Character shops', lambda t: A(t, 'shop', 'art', 'collector', 'craft', 'frame', 'musical_instrument') or 'craft' in t and 'name' in t and 'shop' not in t and 'amenity' not in t),
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
    return re.sub(r'[^a-z0-9]+', ' ', (name or '').lower()).strip()


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

    # Name counts across the whole city (all kinds), to spot unbranded chains.
    namecount = collections.Counter(norm(it['t'].get('name')) for it in inside if it['t'].get('name'))
    for it in inside:
        t = it['t']
        if t.get('brand') or t.get('brand:wikidata'): it['class'] = 'branded'
        elif t.get('name') and namecount[norm(t['name'])] >= CHAIN_MIN: it['class'] = 'likely chain'
        else: it['class'] = 'independent'

    report = {'source': os.path.basename(src), 'chain_min': CHAIN_MIN, 'kinds': {}}
    for k, fam, _ in KINDS:
        rows = [it for it in inside if it['kind'] == k]
        ind = [it for it in rows if it['class'] == 'independent']
        named = [it for it in ind if it['t'].get('name')]
        report['kinds'][k] = {
            'family': fam, 'total': len(rows),
            'branded': sum(it['class'] == 'branded' for it in rows),
            'likely_chain': sum(it['class'] == 'likely chain' for it in rows),
            'independent': len(ind), 'independent_named': len(named),
            'story_tags_on_independent': {s: sum(1 for it in ind if it['t'].get(s)) for s in STORY},
            'top_neighbourhoods': collections.Counter(it['nbhd'] for it in ind).most_common(10),
            'top_chains': collections.Counter(it['t'].get('brand') or it['t'].get('name') for it in rows
                                              if it['class'] != 'independent').most_common(15),
        }
        if k in ('murals', 'sculptures', 'installations'):
            report['kinds'][k]['artwork_types'] = collections.Counter(it['t'].get('artwork_type', '(none)') for it in rows).most_common()
        if k == 'restaurants':
            report['kinds'][k]['cuisines_independent'] = collections.Counter(
                c.strip() for it in ind for c in (it['t'].get('cuisine') or '(none)').split(';')).most_common(25)
        with open(os.path.join(OUT, k + '.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['osm', 'neighbourhood', 'lat', 'lon'] + KEEP)
            for it in sorted(ind, key=lambda x: (x['nbhd'], x['t'].get('name', ''))):
                w.writerow([it['osm'], it['nbhd'], it['lat'], it['lon']] + [it['t'].get(c, '') for c in KEEP])

    with open(os.path.join(OUT, 'report.json'), 'w') as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    print('\n%-18s %6s %8s %7s %6s %6s' % ('kind', 'total', 'branded', 'chain?', 'indep', 'named'))
    for k, r in report['kinds'].items():
        print('%-18s %6d %8d %7d %6d %6d' % (k, r['total'], r['branded'], r['likely_chain'], r['independent'], r['independent_named']))
    print('\nwrote report.json and one CSV per kind (independent candidates). Data: (c) OpenStreetMap contributors, ODbL.')
