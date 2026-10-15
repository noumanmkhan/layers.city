"""Points for the card's Nearby section: raw/ods/ (fetch_layers.py) + docs/vancouver/data/institutions.geojson and
faith.geojson -> docs/vancouver/data/nearby.json (Toronto's shape).

library    Vancouver Public Library branches (the City's `libraries`).
centre     The Park Board's community centres (the City's `community-centres`).
er         Hospitals with an emergency department, from the institutions layer.
park       The Park Board's parks (`parks`, one point each).
playground, tennis
           Parks that list playgrounds or tennis courts among their facilities (`parks-facilities`): counts parks,
           not courts or play structures, as Toronto's card does.
offleash   Dog off-leash areas (`dog-off-leash-parks`), one point per area.
mosque, gurdwara, synagogue, hindu, buddhist, church
           From the Faith & Community layers (faith.geojson); the card shows the nearest of each only while its layer
           is on. Churches are also listed by family ("church:catholic", ...) for the Churches layer's chips.
Describe only: the card names the nearest of each and counts what is within the radius in city.json; nothing is ranked."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ODS = os.path.join(HERE, 'raw', 'ods')
DATA = os.path.join(HERE, '..', '..', 'docs', 'vancouver', 'data')


def pts(ds):
    for f in json.load(open(os.path.join(ODS, ds + '.geojson')))['features']:
        g = f.get('geometry')
        if not g: continue
        if g['type'] != 'Point':
            from shapely.geometry import shape
            c = shape(g).representative_point(); xy = [c.x, c.y]
        else:
            xy = g['coordinates']
        yield [round(xy[0], 5), round(xy[1], 5)], f['properties']


groups = {k: [] for k in ('library', 'centre', 'er', 'park', 'playground', 'tennis', 'offleash')}
for at, p in pts('libraries'):
    n = p['name'].strip()
    groups['library'].append(at + [n if re.search(r'central|library', n, re.I) else n + ' branch'])
for at, p in pts('community-centres'):
    n = p['name'].strip()
    groups['centre'].append(at + [n if re.search(r'centre|center|house|hall', n, re.I) else n + ' Community Centre'])
park_at = {}
for at, p in pts('parks'):
    park_at[p['parkid']] = at
    groups['park'].append(at)
fac = json.load(open(os.path.join(ODS, 'parks-facilities.json')))
for kind, rx in (('playground', r'^playgrounds?$'), ('tennis', r'^tennis')):
    ids = sorted({r['parkid'] for r in fac if re.search(rx, r['facilitytype'] or '', re.I)})
    groups[kind] = [park_at[i] for i in ids if i in park_at]
    missing = [i for i in ids if i not in park_at]
    if missing: print(f'  {kind}: {len(missing)} parks not in the parks list:', missing[:10])
for at, p in pts('dog-off-leash-parks'):
    groups['offleash'].append(at)
for f in json.load(open(os.path.join(DATA, 'institutions.geojson')))['features']:
    if f['properties'].get('ed'): groups['er'].append(f['geometry']['coordinates'] + [f['properties']['name']])
fp = os.path.join(DATA, 'faith.geojson')
for f in (json.load(open(fp))['features'] if os.path.exists(fp) else []):
    p = f['properties']
    if p['cat'] != 'otherfaith': groups.setdefault(p['cat'], []).append(f['geometry']['coordinates'] + [p['name']])
    if p.get('grp'): groups.setdefault(p['cat'] + ':' + p['grp'], []).append(f['geometry']['coordinates'] + [p['name']])
json.dump({'groups': groups}, open(os.path.join(DATA, 'nearby.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('nearby:', {k: len(v) for k, v in groups.items()})
