"""Universities, colleges and ERs for the institution toggles under Landmarks.
Inputs: raw/institutions/ (fetch_more.py). Output: docs/dallas/data/institutions.geojson

The rules are Toronto's and Chicago's. Describe only: no ratings or rankings.

Universities: from the IPEDS directory, every active, degree-granting, four-year institution whose address is in
  Dallas, public or private nonprofit, never for-profit, with 1,000 or more students (IPEDS size category 2 and up).
  Southern Methodist University is kept although its campus is in University Park, an enclave inside Dallas, because
  IPEDS and SMU itself give a Dallas address. One point per campus, placed by its OpenStreetMap outline.
Colleges: public only, so Dallas College's campuses inside the city (El Centro, Mountain View, Richland). Its campuses
  in Farmers Branch, Lancaster, Mesquite and Irving are outside the city and left out.
ERs: hospitals with an emergency department (CMS "Emergency Services: Yes"), public or nonprofit, in Dallas.
  For-profit ("Proprietary" or "Physician") hospitals are left out, and so is North Central Surgical Center, a surgical
  hospital. Each is placed by its OpenStreetMap outline and shown under its everyday name. The script stops if CMS lists
  a qualifying hospital this file doesn't name, so a new or renamed one gets a look."""
import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'institutions')
OUT = os.path.join(HERE, '..', '..', 'docs', 'dallas', 'data', 'institutions.geojson')

osm = {}
for e in json.load(open(os.path.join(RAW, 'osm.json')))['elements']:
    c = e.get('center') or {'lat': e.get('lat'), 'lon': e.get('lon')}
    if c.get('lat') is not None:
        osm[e['type'][0] + str(e['id'])] = [round(c['lon'], 5), round(c['lat'], 5)]

# IPEDS unit id -> (name shown, sub, OSM id)
UNIS = {
    '224226': ('Dallas Baptist University', 'Mountain Creek', 'w714480333'),
    '224305': ('Dallas Theological Seminary', 'Swiss Avenue', 'w152645547'),
    '228246': ('Southern Methodist University', 'University Park', 'w30894474'),
    '228635': ('UT Southwestern Medical Center', 'Medical District', 'w546226734'),
    '243823': ('Parker University', 'Chiropractic and health sciences', 'w707876199'),
    '484905': ('University of North Texas at Dallas', '', 'w469530466'),
}
COLLEGES = [('El Centro', 'Downtown', 'w616134113'), ('Mountain View', 'Oak Cliff', 'w449158549'), ('Richland', 'Lake Highlands', 'w194248497')]
ERS = {
    '450015': ('Parkland Memorial Hospital', 'Parkland Health', 'w569788827'),
    '450021': ('Baylor University Medical Center', 'Baylor Scott & White', 'w548448654'),
    '450044': ('UT Southwestern Clements University Hospital', 'UT Southwestern', 'r16736109'),
    '450051': ('Methodist Dallas Medical Center', 'Methodist Health System', 'w569499049'),
    '450462': ('Texas Health Presbyterian Hospital Dallas', 'Texas Health Resources', 'w547734061'),
    '45066F': ('Dallas VA Medical Center', 'Veterans Affairs', 'w449158450'),
    '450723': ('Methodist Charlton Medical Center', 'Methodist Health System', 'w452935990'),
    '453302': ("Children's Medical Center Dallas", "Children's hospital", 'w28542840'),
}
LEFT_OUT = {'670049'}   # North Central Surgical Center (see above)

feats = []
pt = lambda p, props: {'type': 'Feature', 'properties': props, 'geometry': {'type': 'Point', 'coordinates': p}}

rows = list(csv.DictReader(open(os.path.join(RAW, 'ipeds_hd.csv'), encoding='utf-8-sig')))
uid = list(rows[0].keys())[0]
unknown = []
for r in rows:
    if r['CITY'].strip().lower() != 'dallas' or r['CYACTIVE'] != '1': continue
    if r['CONTROL'] in ('1', '2') and r['ICLEVEL'] == '1' and r['DEGGRANT'] == '1' and int(r['INSTSIZE']) >= 2:
        if r[uid] == '224615': continue   # Dallas College: its campuses are the colleges below
        if r[uid] not in UNIS:
            unknown.append(f"{r[uid]} {r['INSTNM']}"); continue
        name, sub, oid = UNIS[r[uid]]
        sub = ' · '.join(x for x in (sub, 'Public' if r['CONTROL'] == '1' else 'Private nonprofit') if x)
        feats.append(pt(osm[oid], {'name': name, 'sub': sub, 'cat': 'university'}))
for name, sub, oid in COLLEGES:
    feats.append(pt(osm[oid], {'name': 'Dallas College ' + name, 'sub': sub + ' · Dallas College', 'cat': 'college'}))

for r in csv.DictReader(open(os.path.join(RAW, 'cms_hospitals.csv'), encoding='utf-8')):
    fid = r['Facility ID']
    if r['City/Town'].strip().upper() != 'DALLAS' or r['Emergency Services'] != 'Yes': continue
    if r['Hospital Ownership'] in ('Proprietary', 'Physician') or fid in LEFT_OUT: continue
    if fid not in ERS:
        unknown.append(f"{fid} {r['Facility Name']} ({r['Hospital Ownership']})"); continue
    name, sub, oid = ERS[fid]
    feats.append(pt(osm[oid], {'name': name, 'sub': sub, 'cat': 'hospital', 'ed': True}))
if unknown: raise SystemExit('Qualifying institutions not named in institutions.py: ' + '; '.join(unknown))

json.dump({'type': 'FeatureCollection', 'features': feats}, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
n = lambda c: sum(1 for f in feats if f['properties']['cat'] == c)
print('institutions:', n('university'), 'universities,', n('college'), 'Dallas College campuses,', n('hospital'), 'ERs')
