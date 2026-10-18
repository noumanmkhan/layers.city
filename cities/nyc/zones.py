"""Build docs/nyc/data/attendance.geojson (the card's Schools section, as Chicago's) from the DOE school zones
(raw/places/school_zones_es/ms/hs.geojson, 2024-25, fetch_places.py) and the school points in the City Planning
Facilities Database (raw/places/facdb.json) for each zoned school's name and building.

A zone names its school by DBN ("20K503": district 20, Brooklyn, school 503). The Facilities Database has no DBN, so
the school is found by its district and number ("P.S. 503 ..." in District 20). A zone with no zoned school (most of
the city at middle and high school: choice by application) gets the DOE's own remark, or a plain line saying so.
Output: one feature per zone with `level` (es, ms, hs), `grades`, `name`, `url` (the school's page on
schools.nyc.gov when it has a DBN), `x`, `y` (the building, when found). Parks with no zone are left out."""
import json, os, re
from shapely.geometry import shape, mapping

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'places')
OUT = os.path.join(HERE, '..', '..', 'docs', 'nyc', 'data', 'attendance.geojson')
BORO = {'1': 'M', '2': 'X', '3': 'K', '4': 'Q', '5': 'R', 'MANHATTAN': 'M', 'BRONX': 'X', 'BROOKLYN': 'K', 'QUEENS': 'Q', 'STATEN ISLAND': 'R'}
GRADES = {'es': 'K–5', 'ms': '6–8', 'hs': '9–12'}
KEEP = {'PS', 'IS', 'MS', 'JHS', 'HS', 'II', 'III', 'IV', 'STEM', 'NYC', 'CUNY', 'K-8', 'K–8', 'P.S.', 'I.S.', 'M.S.', 'J.H.S.'}
SMALL = {'of', 'and', 'at', 'for', 'in', 'on', 'de', 'la'}


def tcase(s):
    out = []
    for i, w in enumerate(s.split()):
        if w.upper() in KEEP or re.match(r'^\d', w): out.append(w.upper())
        elif i and w.lower() in SMALL: out.append(w.lower())
        else: out.append(w[:1].upper() + w[1:].lower())
    return ' '.join(out)


# Schools by (district, borough letter, number) from the Facilities Database.
pts = {}
for r in json.load(open(os.path.join(RAW, 'facdb.json'))):
    if r.get('opname') != 'NYC Department of Education' or not r.get('latitude') or not r.get('schooldist'): continue
    m = re.match(r'^(?:P\.?S\.?|I\.?S\.?|M\.?S\.?|J\.?H\.?S\.?|H\.?S\.?)\s*0*(\d+)\b', r['facname'])
    if not m: continue
    k = (int(float(r['schooldist'])), BORO.get(r.get('boro', ''), ''), int(m.group(1)))
    pts.setdefault(k, (re.sub(r'^(P|I|M|J\.?H|H)\.?S\.?\s*0*', lambda a: a.group(1).replace('.', '') + 'S ', r['facname']), float(r['longitude']), float(r['latitude'])))


def rnd(o):
    return [rnd(x) for x in o] if isinstance(o, (list, tuple)) and o and isinstance(o[0], (list, tuple)) else [round(o[0], 5), round(o[1], 5)]


def school(dbn):
    m = re.match(r'^(\d\d)([MXKQR])(\d{3})$', dbn or '')
    if not m: return None
    return pts.get((int(m.group(1)), m.group(2), int(m.group(3))))


out, stats = [], {}
for level, f in (('es', 'school_zones_es'), ('ms', 'school_zones_ms'), ('hs', 'school_zones_hs')):
    found = none = 0
    for z in json.load(open(os.path.join(RAW, f + '.geojson')))['features']:
        p = z['properties']
        if not z.get('geometry'): continue
        rem = (p.get('remarks') or '').strip()
        if rem.lower() in ('park', 'pelham bay park') or rem.lower().endswith(' park'): continue
        dbns = [d.strip() for d in re.split(r'[,;/ ]+', p.get('dbn') or '') if d.strip()]
        dbn = dbns[0] if dbns else ''
        q = {'level': level, 'grades': GRADES[level]}
        names = []
        for d in dbns:
            s = school(d)
            if s:
                names.append(tcase(s[0]))
                if 'x' not in q: q['x'] = round(s[1], 5); q['y'] = round(s[2], 5)
            elif re.match(r'^\d\d[MXKQR]\d{3}$', d):
                names.append(('PS ' if level == 'es' else 'IS ' if level == 'ms' else 'School ') + str(int(d[3:])))
        if 'x' in q: found += 1
        hs_name = (p.get('sch_name') or '').strip()
        if hs_name and 'choice' not in hs_name.lower():   # high school zones carry the school's own name
            names = [re.sub(r'High Sch$|Highschool', 'High School', tcase(hs_name))]
        if names:
            q['name'] = ' or '.join(names)   # a shared zone names each school
        else:
            q['name'] = 'No zoned school: ' + ('citywide high school choice' if level == 'hs' else 'choice within the district'); none += 1
        if dbn and re.match(r'^\d\d[MXKQR]\d{3}$', dbn): q['url'] = 'https://www.schools.nyc.gov/schools/' + dbn[2:]
        if rem and 'choice' not in q['name'] and rem.lower() != 'citywide high school choice': q['note'] = rem
        g = shape(z['geometry']).buffer(0).simplify(0.00003, preserve_topology=True)
        if g.is_empty: continue
        out.append({'type': 'Feature', 'properties': q, 'geometry': {'type': g.geom_type, 'coordinates': rnd(mapping(g)['coordinates'])}})
    stats[level] = (sum(1 for x in out if x['properties']['level'] == level), found, none)
json.dump({'type': 'FeatureCollection', 'year': '2024–25', 'features': out}, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
print('attendance:', {k: f'{n} zones, {fd} schools placed, {nn} with no zoned school' for k, (n, fd, nn) in stats.items()}, os.path.getsize(OUT) // 1024, 'KB')
