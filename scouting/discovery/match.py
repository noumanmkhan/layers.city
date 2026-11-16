"""Match the OSM candidates (out/<kind>.csv, written by scout.py) to the places the City of Toronto has already written
about, so a matched business "has a story" with a description we can quote with credit (OGL-Toronto).
Run at the end of scout.py, or alone: python3 match.py (needs out/*.csv). Downloads the City's CSVs from Toronto Open Data.

City sources (all Open Government Licence - Toronto):
  strollto  - StrollTO POI Details (1,800+ places with a paragraph each)
  hotspot   - Cultural Hotspot: Cultural Loop Tour Points (inner suburbs; "Did you know?" entries)
  music     - Music Locations (record and instrument stores only)
  publicart - Public Art (459 works), used for the art kinds only

Writes:
  out/matches.csv  - one row per OSM candidate with a City match: kind, names, distance, score, founding year
                     found in the text, the City's description and link (to quote with credit)
  out/art_gaps.csv - OSM murals / sculptures / monuments / installations with no City art record nearby
  out/match.json   - counts"""
import csv, difflib, io, json, math, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}
CKAN = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/'
CITY = {
    'strollto':  CKAN + 'f87fbe88-f9d1-432d-a482-b7044b32d587/resource/b30cc1eb-6385-4bf4-8231-20d3e9ec4021/download/strollto-poi-details-4326.csv',
    'hotspot':   CKAN + 'c7be2ee7-d317-4a28-8cbe-bff1ce116b46/resource/70eb3e9e-47c1-4254-9f78-ebcad6df29e9/download/cultural-loop-tour-points-4326.csv',
    'music':     CKAN + 'c52cdef8-7b21-40f9-9404-a8c1b20f4a7e/resource/989fb6a9-3b22-4ecb-8fdb-04f4d9b268fd/download/music-locations-4326.csv',
    'publicart': CKAN + 'bfdc6aa8-7ea6-4225-a3f7-e13d1d2b4018/resource/2cb2c65a-1565-4382-8fe3-3a235aec7655/download/public-art-4326.csv',
}
CREDIT = {'strollto': 'City of Toronto, StrollTO', 'hotspot': 'City of Toronto, Cultural Hotspot',
          'music': 'City of Toronto, Music Locations', 'publicart': 'City of Toronto, Public Art'}
BIZ = ['cafes', 'bakeries', 'restaurants', 'markets', 'books', 'records', 'vintage', 'comics_games_toys',
       'specialty_food', 'makers_oddities', 'viewpoints']
ART = ['murals', 'sculptures', 'monuments', 'installations']
NEAR = 80        # metres: a business and the City's point for it
ART_NEAR = 40    # metres: an OSM artwork already in the City's lists
STOP = {'the', 'and', 'of', 'cafe', 'café', 'coffee', 'bakery', 'restaurant', 'shop', 'store', 'inc', 'ltd', 'co', 'toronto',
        'records', 'books', 'bookstore', 'bar', 'kitchen', 'market', 'park', 'mural', 'a', 'on', 'at', 'de', 'la'}
YEAR = re.compile(r'(?i)\b(?:since|established in|est\.?|founded in|opened in|opened its doors in|in business since|dating (?:back )?to)\s+((?:18|19|20)\d\d)')


def fetch(name):
    """The City's CSV, from a local copy if CITY_DIR has one (for testing), else Toronto Open Data."""
    local = os.environ.get('CITY_DIR')
    if local and os.path.exists(os.path.join(local, name + '.csv')):
        return list(csv.DictReader(open(os.path.join(local, name + '.csv'), encoding='utf-8-sig')))
    with urllib.request.urlopen(urllib.request.Request(CITY[name], headers=UA), timeout=120) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode('utf-8-sig'))))


def point(row):
    if row.get('LATITUDE') not in (None, '', 'None'):
        return float(row['LATITUDE']), float(row['LONGITUDE'])
    c = json.loads(row['geometry'])['coordinates']
    while isinstance(c[0], list): c = c[0]
    return c[1], c[0]


def metres(a, b):
    return math.hypot((a[0] - b[0]) * 111_000, (a[1] - b[1]) * 111_000 * math.cos(math.radians(a[0])))


def words(s):
    return [w for w in re.findall(r"[a-z0-9']+", (s or '').lower().replace('’', "'")) if w not in STOP]


def score(a, b):
    """0..1: how alike two names are, ignoring generic words. A shared distinctive word counts for a lot."""
    wa, wb = words(a), words(b)
    if not wa or not wb: return 0
    ratio = difflib.SequenceMatcher(None, ' '.join(wa), ' '.join(wb)).ratio()
    shared = set(wa) & set(wb)
    overlap = len(shared) / min(len(set(wa)), len(set(wb)))
    return max(ratio, overlap if any(len(w) > 3 for w in shared) else 0)


class Grid:
    """Points bucketed by ~110 m cells, for near-neighbour lookups."""
    def __init__(self, items):
        self.g = {}
        for it in items: self.g.setdefault(self.key(it['pt']), []).append(it)

    key = staticmethod(lambda p: (int(p[0] * 1000), int(p[1] * 1000)))

    def near(self, p, r):
        k = self.key(p); out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for it in self.g.get((k[0] + dx, k[1] + dy), []):
                    d = metres(p, it['pt'])
                    if d <= r: out.append((d, it))
        return sorted(out, key=lambda x: x[0])


VENUE = re.compile(r"(?i)\b(mural|murals|park|garden|gardens|theatre|plaza|mall|college|university|museum|hollow|lookout|square)\b")


SHOPWORD = re.compile(r"(?i)\b(cafe|café|coffee|book ?store|books?|food court|pastry|shop|store|restaurant|bar|kitchen|bakery)\b")


def relation(osm_name, city_name):
    """same: the City wrote about this business. mural: the City's entry is a mural on or next to it.
    inside: the business sits in (or is named after) a place the City wrote about: lore for the setting, not the shop."""
    if re.search(r'(?i)\bmurals?\b', city_name) and not re.search(r'(?i)\bmurals?\b', osm_name): return 'mural'
    city_name = re.sub(r'\s*\([^)]*\)', '', city_name)          # "Kops Records (Queen)" -> "Kops Records"
    if VENUE.search(city_name) and SHOPWORD.search(osm_name): return 'inside'
    a, b = set(words(osm_name)), set(words(city_name))
    if difflib.SequenceMatcher(None, ' '.join(sorted(a)), ' '.join(sorted(b))).ratio() >= 0.85 or not (b - a) or not (a - b):
        if not (VENUE.search(city_name) and not VENUE.search(osm_name)): return 'same'
    return 'inside'


def city_places():
    places = []
    for x in fetch('strollto'):
        places.append({'src': 'strollto', 'name': x['Title'].strip(), 'pt': point(x), 'text': x['Description'],
                       'link': (x['Link_URL'] or '').strip(), 'nbhd': x['Neighbourhood']})
    for x in fetch('hotspot'):
        places.append({'src': 'hotspot', 'name': x['SiteName'].strip(), 'pt': point(x), 'text': x['Description'],
                       'link': x['ExternalLink'] if x['ExternalLink'] != 'None' else '', 'nbhd': x['Neighbourhood'],
                       'entry': x['EntryType'].strip()})
    for x in fetch('music'):
        if x['CATEGORY'] in ('Record Stores', 'Instrument Stores'):
            places.append({'src': 'music', 'name': x['NAME'].strip(), 'pt': point(x), 'text': '',
                           'link': x['WEBSITE'] if x['WEBSITE'] != 'None' else '', 'nbhd': '', 'cat': x['CATEGORY']})
    art = [{'src': 'publicart', 'name': x['TITLE'], 'pt': point(x)} for x in fetch('publicart')]
    art += [p for p in places if p['src'] in ('strollto', 'hotspot') and re.search(r'(?i)mural|sculpture|statue|monument|memorial|art', p['name'] + ' ' + p['text'][:200])]
    return places, art


def read(kind):
    p = os.path.join(OUT, kind + '.csv')
    return list(csv.DictReader(open(p, encoding='utf-8'))) if os.path.exists(p) else []


def main():
    places, art = city_places()
    grid, artgrid = Grid(places), Grid(art)
    print('city places', len(places), '· city art points', len(art), flush=True)

    rows, counts = [], {}
    for kind in BIZ:
        cand = read(kind); n = 0
        for c in cand:
            if not c['name']: continue
            p = (float(c['lat']), float(c['lon']))
            best = None
            for d, pl in grid.near(p, NEAR):
                s = score(c['name'], pl['name'])
                if s >= 0.75 and (best is None or s > best[1]): best = (d, s, pl)
            if not best: continue
            d, s, pl = best; n += 1
            rel = relation(c['name'], pl['name'])
            y = YEAR.search(pl['text']) or YEAR.search(c.get('start_date') or '')
            rows.append({'kind': kind, 'osm': c['osm'], 'osm_name': c['name'], 'neighbourhood': c['neighbourhood'],
                         'lat': c['lat'], 'lon': c['lon'], 'city_source': pl['src'], 'city_name': pl['name'],
                         'relation': rel, 'metres': round(d), 'score': round(s, 2), 'year': y.group(1) if y else (c.get('start_date') or ''),
                         'credit': CREDIT[pl['src']], 'city_link': pl['link'], 'website': c.get('website', ''),
                         'description': re.sub(r'\s+', ' ', pl['text']).strip()})
        counts[kind] = {'candidates': len(cand), 'matched': n}

    gaps, gapcount = [], {}
    for kind in ART:
        cand = read(kind); g = 0
        for c in cand:
            p = (float(c['lat']), float(c['lon']))
            if artgrid.near(p, ART_NEAR): continue
            g += 1
            gaps.append({'kind': kind, 'osm': c['osm'], 'name': c['name'], 'neighbourhood': c['neighbourhood'],
                         'lat': c['lat'], 'lon': c['lon'], 'artist_name': c.get('artist_name', ''),
                         'start_date': c.get('start_date', ''), 'wikidata': c.get('wikidata', '')})
        gapcount[kind] = {'osm': len(cand), 'not_in_city_lists': g}

    rows.sort(key=lambda r: (r['kind'], r['neighbourhood'], r['osm_name']))
    with open(os.path.join(OUT, 'matches.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ['kind']); w.writeheader(); w.writerows(rows)
    with open(os.path.join(OUT, 'art_gaps.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(gaps[0].keys()) if gaps else ['kind']); w.writeheader(); w.writerows(gaps)
    summary = {'near_m': NEAR, 'art_near_m': ART_NEAR, 'businesses': counts, 'art': gapcount,
               'by_source': {s: sum(r['city_source'] == s for r in rows) for s in CITY},
               'by_relation': {k: sum(r['relation'] == k for r in rows) for k in ('same', 'inside', 'mural')},
               'with_year': sum(1 for r in rows if r['year'])}
    with open(os.path.join(OUT, 'match.json'), 'w') as f: json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
