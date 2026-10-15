"""Fetch the input for Vancouver's Faith & Community layers into raw/faith/. Run from GitHub Actions (fetch-vancouver.yml,
and monthly by fetch-vancouver-faith.yml); the sandbox can't reach Overpass.

  worship_osm.json  Every named place of worship in the City of Vancouver, plus those of faiths other than
                    Christianity across Metro Vancouver, from OpenStreetMap (Overpass API): OSM id, centre, name,
                    religion, denomination and address tags. As in Chicago, the wider net is because most of the
                    region's gurdwaras and many of its mosques and mandirs are in Surrey, Burnaby and Richmond.

Halal and kosher shops aren't fetched: no certifier in British Columbia publishes a list of the shops it certifies
(see PARKED.md). Places the overrides add must carry their own lat/lon (faith_overrides.csv)."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_lib as F

OUT = os.path.join(HERE, 'raw', 'faith'); os.makedirs(OUT, exist_ok=True)
CITY = (49.195, -123.235, 49.32, -123.02)        # s, w, n, e: the City, Stanley Park included
WIDE = (49.0, -123.3, 49.45, -122.45)            # Metro Vancouver's built-up area
KEEP = ('name', 'alt_name', 'religion', 'denomination', 'addr:housenumber', 'addr:street', 'addr:city', 'building')
Q = f"""[out:json][timeout:240];
(nwr["amenity"="place_of_worship"]["name"]({CITY[0]},{CITY[1]},{CITY[2]},{CITY[3]});
 nwr["amenity"="place_of_worship"]["name"]["religion"]["religion"!="christian"]({WIDE[0]},{WIDE[1]},{WIDE[2]},{WIDE[3]}););
out tags center;"""

d = F.overpass(Q, 'faith/worship_full.json')
els = []
for el in d.get('elements', []):
    t, c = el.get('tags', {}), (el if el.get('type') == 'node' else el.get('center'))
    if not c or 'lat' not in c: continue
    els.append({'osm': el['type'][0] + str(el['id']), 'at': [round(c['lon'], 5), round(c['lat'], 5)], **{k: t[k] for k in KEEP if k in t}})
os.remove(os.path.join(F.RAW, 'faith', 'worship_full.json'))
els.sort(key=lambda e: (e.get('religion', '~'), e['name']))
json.dump({'source': 'OpenStreetMap contributors (ODbL) via Overpass API', 'bbox': CITY, 'wide': WIDE, 'elements': els},
          open(os.path.join(OUT, 'worship_osm.json'), 'w'), ensure_ascii=False, indent=0)
by = {}
for e in els: by[e.get('religion', '(none)')] = by.get(e.get('religion', '(none)'), 0) + 1
print(len(els), 'named places of worship:', sorted(by.items(), key=lambda kv: -kv[1]))
den = {}
for e in els:
    if e.get('religion') == 'christian': den[e.get('denomination', '(none)')] = den.get(e.get('denomination', '(none)'), 0) + 1
print('christian denominations:', sorted(den.items(), key=lambda kv: -kv[1]))
