"""Polygon layers added for parity with Toronto (October 16, 2026), from raw/ (fetch_layers.py) -> tmp/ (simplified by
mapshaper in run.sh), plus the election-day voting places straight to docs/vancouver/data/voting.geojson.

  heritage    Historic area zoning districts and the First Shaughnessy heritage conservation area: the City's
              zoning (`zoning-districts-and-labels`) HA-1 and HA-1A (Chinatown, one district), HA-2 (Gastown),
              HA-3 (Yaletown) and FSD (First Shaughnessy). These are the City's heritage districts: zones whose
              rules protect the character of a whole area. Vancouver publishes no other heritage-area boundaries.
  bia         The 22 business improvement areas (`business-improvement-areas-bia`; Dunbar Village's three pieces
              are one BIA).
  provincial  BC provincial electoral districts (DataBC; the boundaries used in the October 24, 2026 election),
              cut to the City's land: a district that reaches into Burnaby shows only its Vancouver part.
  federal     Federal ridings, 2023 Representation Order (Open North's Represent), cut to the City's land the same
              way, so Marpole (in Richmond Centre—Marpole) is covered.
  voting      Vancouver votes at any voting place in the city: one area (the City) and every election-day voting
              place from the City's `voting-places-2026`, in Dallas's vote-centre shape. Advance-only places are left
              out (advance voting has ended); two places in one building are one entry."""
import json, os, re
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, polylabel

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, 'raw')
TMP = os.path.join(HERE, 'tmp'); os.makedirs(TMP, exist_ok=True)
OUT = os.path.join(HERE, '..', '..', 'docs', 'vancouver', 'data')
load = lambda *p: json.load(open(os.path.join(R, *p)))
CITY = next(shape(f['geometry']).buffer(0) for f in load('csds.geojson')['features'] if f['properties']['CSDUID'] == '5915022')


def label_pt(g):
    if g.geom_type == 'MultiPolygon': g = max(g.geoms, key=lambda p: p.area)
    try: p = polylabel(g, tolerance=0.0002)
    except Exception: p = g.representative_point()
    return [round(p.x, 5), round(p.y, 5)]


def polys(g):
    if g.geom_type in ('Polygon', 'MultiPolygon'): return g
    return unary_union([x for x in getattr(g, 'geoms', []) if x.geom_type in ('Polygon', 'MultiPolygon')])


def dump(name, feats):
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(TMP, name + '.geojson'), 'w'), separators=(',', ':'), ensure_ascii=False)
    print(name, len(feats), [f['properties'].get('name') for f in feats][:30])


feat = lambda g, p: {'type': 'Feature', 'properties': {**p, 'lp': label_pt(g)}, 'geometry': mapping(g)}

# ---------- Heritage districts ----------
ZONES = {'HA-1': 'Chinatown', 'HA-1A': 'Chinatown', 'HA-2': 'Gastown', 'HA-3': 'Yaletown', 'FSD': 'First Shaughnessy'}
KIND = {'Chinatown': 'Historic area (HA-1, HA-1A)', 'Gastown': 'Historic area (HA-2)', 'Yaletown': 'Historic area (HA-3)',
        'First Shaughnessy': 'Heritage conservation area (FSD)'}
by = {}
for f in load('ods', 'zoning-districts-and-labels.geojson')['features']:
    n = ZONES.get(f['properties']['zoning_district'])
    if n: by.setdefault(n, []).append(shape(f['geometry']).buffer(0))
missing = set(ZONES.values()) - set(by)
if missing: raise SystemExit('heritage zones missing from the zoning file: ' + ', '.join(sorted(missing)))
dump('heritage', [feat(polys(unary_union(gs).buffer(0.00002).buffer(-0.00002)), {'name': n, 'kind': KIND[n]}) for n, gs in sorted(by.items())])

# ---------- Business improvement areas ----------
by = {}
for f in load('ods', 'business-improvement-areas-bia.geojson')['features']:
    n = re.sub(r'\s*BIA$', '', f['properties']['name'].strip()).replace('Commercial Dr.', 'Commercial Drive').replace('Fraser St.', 'Fraser Street') \
        .replace('Kitsilano Fourth Ave.', 'Kitsilano 4th Avenue').replace('Robson St.', 'Robson Street').replace('Hastings - North', 'Hastings North')
    by.setdefault(n, []).append(shape(f['geometry']).buffer(0))
dump('bia', [feat(polys(unary_union(gs)), {'name': n}) for n, gs in sorted(by.items())])

# ---------- Provincial districts and federal ridings, cut to the City ----------
def cut(features, name_of, min_km2=0.05):
    out = []
    for f in features:
        g = polys(shape(f['geometry']).buffer(0).intersection(CITY))
        if g.is_empty or g.area * 72.6 * 111.2 < min_km2: continue
        out.append(feat(g, {'name': name_of(f['properties'])}))
    return sorted(out, key=lambda f: f['properties']['name'])


dump('provincial', cut(load('prov_districts.geojson')['features'], lambda p: p['ED_NAME']))
dump('federal', cut(load('fed2023.geojson')['features'], lambda p: p['name']))

# ---------- Where to vote (October 17, 2026) ----------
centers = []
for f in load('ods', 'voting-places-2026.geojson')['features']:
    p = f['properties']
    if (p.get('advance_only') or '').upper() == 'YES' or not f.get('geometry'): continue
    x, y = f['geometry']['coordinates']
    centers.append([round(x, 6), round(y, 6), p['facility_name'].strip(), (p.get('location') or '').strip(), p['facility_address'].strip(), 'vancouver', 1])
# One building can hold two voting places (Central Library has two rooms): one entry, both rooms.
merged = {}
for c in centers:
    k = (c[2], c[4])
    if k in merged:
        if c[3] and c[3] not in merged[k][3]: merged[k][3] = (merged[k][3] + '; ' + c[3]).strip('; ')
    else: merged[k] = c
centers = sorted(merged.values(), key=lambda c: c[2])
meta = load('ods', 'meta.json').get('voting-places-2026', {})
json.dump({'type': 'FeatureCollection', 'asof': (meta.get('modified') or '')[:10], 'election': '2026-10-17',
           'counts': {'vancouver': {'ed': len(centers), 'ev': 0}}, 'centers': centers,
           'features': [{'type': 'Feature', 'properties': {'k': 'vancouver'}, 'geometry': mapping(CITY.simplify(0.0002))}]},
          open(os.path.join(OUT, 'voting.geojson'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('voting places:', len(centers))
