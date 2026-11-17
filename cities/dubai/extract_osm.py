"""Cut Dubai's OpenStreetMap inputs out of Geofabrik's GCC extract into cities/dubai/raw/ (run by hand, see SOURCES.md).

Needs osmium-tool on the PATH and raw/osm/gcc-states-latest.osm.pbf
(https://download.geofabrik.de/asia/gcc-states-latest.osm.pbf; gitignored, 260 MB). Everything is clipped to the
Dubai-Sharjah-Ajman frame and simplified to about 5 m before saving, so the files here stay small enough to commit.

Writes: admin.geojson (emirates, OSM's community and area polygons), land.geojson (the coastline closed into land),
roads.geojson, rail.geojson (lines, stations, the Blue Line under construction), places.json (place nodes),
pois.geojson (hospitals, schools, campuses, libraries, worship, parks, beaches, sports, heritage, chargers...)."""
import json, os, subprocess, sys, tempfile
from shapely.geometry import shape, mapping, box, Point
from shapely.ops import unary_union, polygonize, linemerge

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
SRC = os.path.join(RAW, 'osm', 'gcc-states-latest.osm.pbf')
TMP = tempfile.mkdtemp()
W, S, E, N = 54.85, 24.70, 55.80, 25.55
FRAME = box(W, S, E, N)
SEA_SEEDS = [(55.10, 25.20), (55.30, 25.40), (54.95, 25.10), (55.60, 25.54)]   # points in the Gulf


def osm(*args):
    subprocess.run(['osmium', *args, '--overwrite'], check=True, capture_output=True)


def export(pbf, types='point,linestring,polygon'):
    out = os.path.join(TMP, os.path.basename(pbf) + '.seq')
    osm('export', pbf, '-f', 'geojsonseq', '--add-unique-id=type_id', '--geometry-types=' + types, '-o', out)
    for line in open(out, encoding='utf-8'):
        f = json.loads(line.lstrip('\x1e'))
        yield f


def r5(g):
    return json.loads(json.dumps(mapping(g)), parse_float=lambda v: round(float(v), 5))


def save(name, obj):
    with open(os.path.join(RAW, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
    print('wrote', name, os.path.getsize(os.path.join(RAW, name)) // 1000, 'KB', flush=True)


KEEP = ('name', 'name:en', 'name:ar', 'alt_name', 'alt_name:en', 'old_name', 'short_name', 'ref', 'official_name:en',
        'admin_level', 'boundary', 'place', 'highway', 'railway', 'construction', 'construction:railway', 'operator',
        'amenity', 'leisure', 'natural', 'tourism', 'historic', 'religion', 'denomination', 'emergency', 'healthcare',
        'building', 'building:levels', 'height', 'sport', 'wikidata', 'website', 'ISO3166-2', 'oneway', 'access',
        'line', 'colour', 'start_date', 'opening_date', 'layer', 'tunnel', 'bridge', 'isced:level', 'school', 'operator:type',
        'landuse', 'cycleway', 'bicycle', 'segregated', 'capacity', 'network', 'brand', 'socket:type2', 'fee', 'station',
        'subway', 'light_rail', 'monorail', 'public_transport', 'level')
slim = lambda p: {k: v for k, v in p.items() if k in KEEP or k == '@id'}

metro = os.path.join(RAW, 'osm', 'metro.osm.pbf')
osm('extract', '-b', '%s,%s,%s,%s' % (W, S, E, N), '--strategy', 'smart', SRC, '-o', metro)

# ---------- Emirates (from the whole extract: their relations reach far past the frame) ----------
osm('tags-filter', SRC, 'r/admin_level=4', '-o', os.path.join(TMP, 'al4.pbf'))
emirates = []
for f in export(os.path.join(TMP, 'al4.pbf'), 'polygon'):
    p = f['properties']
    if p.get('admin_level') == '4' and p.get('boundary') == 'administrative' and (p.get('ISO3166-2') or '').startswith('AE-'):
        g = shape(f['geometry']).buffer(0).intersection(FRAME.buffer(0.3))
        if not g.is_empty:
            emirates.append({'type': 'Feature', 'properties': slim(p), 'geometry': r5(g.simplify(0.00005))})
print('emirates', [e['properties'].get('name:en') for e in emirates])

# ---------- Communities and areas (admin_level 8 and 10) ----------
osm('tags-filter', metro, 'r/boundary=administrative', '-o', os.path.join(TMP, 'adm.pbf'))
areas = []
for f in export(os.path.join(TMP, 'adm.pbf'), 'polygon'):
    p = f['properties']
    if p.get('admin_level') in ('8', '9', '10'):
        g = shape(f['geometry']).buffer(0)
        areas.append({'type': 'Feature', 'properties': slim(p), 'geometry': r5(g.simplify(0.00004))})
save('admin.geojson', {'type': 'FeatureCollection', 'features': emirates + areas})

# ---------- Land: the coastline closed against the frame ----------
osm('tags-filter', metro, 'w/natural=coastline', '-o', os.path.join(TMP, 'coast.pbf'))
coast = [shape(f['geometry']) for f in export(os.path.join(TMP, 'coast.pbf'), 'linestring,polygon')]
coast = [c.exterior if c.geom_type == 'Polygon' else c for c in coast]
lines = unary_union([c.intersection(FRAME) for c in coast] + [FRAME.exterior])
faces = list(polygonize(lines))
sea = [fc for fc in faces if any(fc.contains(Point(s)) for s in SEA_SEEDS)]
land = unary_union([fc for fc in faces if fc not in sea])
print('coastline faces', len(faces), 'sea faces', len(sea), 'land km²', round(land.area * 101 * 111.2))
save('land.geojson', {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {}, 'geometry': r5(land.simplify(0.00004))}]})

# ---------- Roads ----------
osm('tags-filter', metro, 'w/highway=motorway,trunk,primary,secondary,tertiary,motorway_link,trunk_link', '-o', os.path.join(TMP, 'roads.pbf'))
roads = []
for f in export(os.path.join(TMP, 'roads.pbf'), 'linestring'):
    p = slim(f['properties'])
    roads.append({'type': 'Feature', 'properties': p, 'geometry': r5(shape(f['geometry']).simplify(0.00003))})
save('roads.geojson', {'type': 'FeatureCollection', 'features': roads})

# ---------- Rail: metro, tram, Etihad Rail, the Blue Line under construction, stations ----------
osm('tags-filter', metro, 'w/railway=rail,subway,light_rail,tram,monorail,construction', 'n/railway=station,halt,tram_stop',
    'n/public_transport=station', '-o', os.path.join(TMP, 'rail.pbf'))
rail = []
for f in export(os.path.join(TMP, 'rail.pbf')):
    p = slim(f['properties'])
    if p.get('railway') == 'construction' and not (p.get('construction') or p.get('construction:railway')): continue
    rail.append({'type': 'Feature', 'properties': p, 'geometry': r5(shape(f['geometry']).simplify(0.00002))})
save('rail.geojson', {'type': 'FeatureCollection', 'features': rail})

# ---------- Place nodes ----------
osm('tags-filter', metro, 'n/place', '-o', os.path.join(TMP, 'places.pbf'))
places = []
for f in export(os.path.join(TMP, 'places.pbf'), 'point'):
    p = slim(f['properties'])
    places.append({'name': p.get('name:en') or p.get('name'), 'ar': p.get('name:ar'), 'place': p.get('place'),
                   'at': [round(c, 5) for c in f['geometry']['coordinates']], 'alt': p.get('alt_name:en') or p.get('alt_name')})
save('places.json', places)

# ---------- Points of interest (as points: a way or relation becomes its representative point, area kept) ----------
osm('tags-filter', metro, 'nwr/amenity=hospital,clinic,school,college,university,library,place_of_worship,community_centre,charging_station,taxi,bicycle_rental,theatre,arts_centre,townhall',
    'nwr/leisure=park,sports_centre,stadium,swimming_pool,golf_course,garden,water_park,nature_reserve', 'nwr/natural=beach',
    'nwr/historic', 'nwr/tourism=museum,attraction,theme_park,zoo,aquarium,viewpoint', 'nwr/emergency=yes',
    'nwr/building:levels', 'nwr/height', 'nwr/aeroway=aerodrome', 'nwr/shop=mall', '-o', os.path.join(TMP, 'pois.pbf'))
pois = []
for f in export(os.path.join(TMP, 'pois.pbf'), 'point,polygon'):
    p = slim(f['properties'])
    if not (p.get('name') or p.get('name:en')) and not p.get('leisure') and not p.get('natural'): continue
    g = shape(f['geometry'])
    if g.geom_type != 'Point':
        if g.is_empty: continue
        p['_km2'] = round(g.area * 101 * 111.2, 4)
        if p.get('leisure') in ('park', 'garden', 'golf_course', 'nature_reserve') or p.get('natural') == 'beach':
            p['_shape'] = r5(g.simplify(0.00005))
        g = g.representative_point()
    pois.append({'type': 'Feature', 'properties': p, 'geometry': r5(g)})
save('pois.geojson', {'type': 'FeatureCollection', 'features': pois})
