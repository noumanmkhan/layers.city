"""Build one city's map page: engine/template.html + engine/map.js + cities/<city>/city.json and city.css
-> docs/<city>/index.html, plus a copy of the config at docs/<city>/data/city.json.

Usage: python3 engine/assemble.py <city>

The page stays a single file: Leaflet's stylesheet, the city's colours, its config and the engine
script are all inlined (Leaflet's JavaScript still loads from cdnjs). Text in {{double braces}} in the
template is filled from the city config, e.g. {{title}} or {{scope.outer.name}}."""
import html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: assemble.py <city>')
CITY_DIR = os.path.join(ROOT, 'cities', city)
read = lambda *p: open(os.path.join(*p), encoding='utf-8').read()

cfg = json.loads(read(CITY_DIR, 'city.json'))

def lookup(path):
    v = cfg
    for k in path.split('.'):
        v = v[k]   # a KeyError here names the missing config entry
    return html.escape(str(v), quote=True)

t = read(HERE, 'template.html')
# Canadian cities use the logo with the maple leaf (the "-ca" files from assets/brand/build.py); the rest the plain pin.
t = t.replace('%BRAND%', '-ca' if cfg.get('search', {}).get('country') == 'ca' else '')
t = re.sub(r'\{\{([\w.]+)\}\}', lambda m: lookup(m.group(1)), t)
# The title doubles as a switcher between every city in cities/, plus the maps hub. With one city
# it stays a plain heading.
cities = sorted((json.loads(read(ROOT, 'cities', c, 'city.json')) for c in os.listdir(os.path.join(ROOT, 'cities'))
                 if os.path.isfile(os.path.join(ROOT, 'cities', c, 'city.json'))), key=lambda c: c.get('heading', c['title']))
# A city marked "unlisted" (live but not announced yet) stays out of the other cities' switchers, unless it also
# sets "inSwitcher": true (in the switchers, still no hub card or sitemap entry).
cities = [c for c in cities if not c.get('unlisted') or c.get('inSwitcher') or c['id'] == cfg['id']]
title = html.escape(cfg.get('heading', cfg['title']))   # the panel heading; the page <title> keeps the full title
if len(cities) > 1:
    chev = '<svg class="chev" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    opts = ''.join('<option value="../%s/"%s>%s</option>' % (c['id'], ' selected' if c['id'] == cfg['id'] else '', html.escape(c.get('heading', c['title']))) for c in cities)
    switch = ('<div class="switch"><h1>%s%s</h1><select id="citySwitch" aria-label="Switch map">%s'
              '<option value="../">All maps</option></select></div>') % (title, chev, opts)
else:
    switch = '<h1>%s</h1>' % title
t = t.replace('<!--CITY_SWITCH-->', switch)
t = t.replace('/*LEAFLET_CSS*/', read(ROOT, 'node_modules', 'leaflet', 'dist', 'leaflet.css'))
t = t.replace('/*CITY_CSS*/', read(CITY_DIR, 'city.css'))
# The config sits inside a <script>; escaping "</" keeps a stray "</script>" in any text from ending it.
t = t.replace('/*CITY_CONFIG*/', json.dumps(cfg, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
t = t.replace('/*ENGINE_JS*/', read(HERE, 'map.js'))
t = '<!doctype html>\n<html lang="en">\n<head>\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' + \
    t.replace('<div id="app">', '</head>\n<body>\n<div id="app">', 1) + '\n</body>\n</html>\n'

out = os.path.join(ROOT, 'docs', city, 'index.html')
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, 'w', encoding='utf-8').write(t)
print('assembled docs/%s/index.html' % city, len(t), 'bytes')

# The config is also published on its own, beside the data, for apps that read the map's data
# (see DATA_CONTRACT.md). Its "schema" number goes up only on a breaking change.
# The published copy also carries "palette": every colour variable the page defines (engine and city),
# with its light and dark value, so an app can resolve "--bia" or "--b-oldtoronto" without reading CSS.
def colours(css, selector):
    out = {}
    for block in re.findall(re.escape(selector) + r'\{([^{}]*)\}', css):
        out.update(re.findall(r'(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{3,8})\b', block))
    return out
styles = read(HERE, 'template.html') + '\n' + read(CITY_DIR, 'city.css')
light, dark = colours(styles, ':root'), colours(styles, ':root[data-theme="dark"]')
pub = dict(cfg, palette={k: {'light': v.upper(), 'dark': dark.get(k, v).upper()} for k, v in light.items()})
# "transit": where an app finds the Routes page's data (engine/routes/build.py) and the live arrivals, with the
# settings it needs to word things as the page does (DATA_CONTRACT.md section 15). Only for a city with a
# cities/<city>/routes.json whose page has been built.
rcfg_p = os.path.join(CITY_DIR, 'routes.json')
if os.path.isfile(rcfg_p) and os.path.isfile(os.path.join(ROOT, 'docs', city, 'routes', 'data', 'stops.json')):
    rc = json.loads(read(CITY_DIR, 'routes.json'))
    live = rc.get('live') or {}
    pub['transit'] = {
        'page': '/%s/routes/' % city,
        'stops': '/%s/routes/data/stops.json' % city,
        'route': '/%s/routes/data/r/{route}.json' % city,
        # scheduled times, split by stop id into schedFiles files (DATA_CONTRACT.md section 15)
        'sched': '/%s/routes/data/sched/{bucket}.json' % city if os.path.isfile(os.path.join(ROOT, 'docs', city, 'routes', 'data', 'sched', '0.json')) else None,
        'schedFiles': len([f for f in os.listdir(os.path.join(ROOT, 'docs', city, 'routes', 'data', 'sched')) if f.endswith('.json')]) if os.path.isdir(os.path.join(ROOT, 'docs', city, 'routes', 'data', 'sched')) else 0,
        'live': live.get('api'), 'liveRapid': '&rapid=1', 'liveNone': live.get('none', {}), 'liveSource': live.get('source'),
        'modes': rc.get('modes', []), 'stationKm': rc.get('stationKm', 1), 'nearKm': [0.45, 0.8],
        'regionsWithThe': rc.get('regionsWithThe', []), 'knownWithThe': rc.get('knownWithThe'), 'known': rc.get('known'),
        'title': rc['page'].get('title'), 'credits': rc['page'].get('credits'),
        'badges': {k: v for k, v in (rc.get('badges') or {}).items() if not k.startswith('_')},
        # The city's own wording (DATA_CONTRACT.md section 15, "City wording"); absent keys keep Toronto's defaults.
        'words': {k: rc['page'][k] for k in ('lineNames', 'lineGroups', 'at', 'connectWith', 'connectionsLabel', 'mi', 'changeBare') if k in rc['page']},
    }
cfg_out = os.path.join(ROOT, 'docs', city, 'data', 'city.json')
os.makedirs(os.path.dirname(cfg_out), exist_ok=True)
open(cfg_out, 'w', encoding='utf-8').write(json.dumps(pub, ensure_ascii=False, separators=(',', ':')) + '\n')
print('published docs/%s/data/city.json' % city)

# docs/cities.json: the list of published cities, for apps (DATA_CONTRACT.md section 13), so a new
# city reaches them without an app update. Rebuilt from every published city on each assemble.
cities = []
for cid in sorted(os.listdir(os.path.join(ROOT, 'cities'))):
    src = os.path.join(ROOT, 'cities', cid, 'city.json')
    if not (os.path.isfile(src) and os.path.isfile(os.path.join(ROOT, 'docs', cid, 'data', 'city.json'))):
        continue
    c = json.loads(read(src))
    cities.append({
        'id': c['id'],
        'name': c.get('heading') or c.get('title'),
        'title': c.get('title'),
        'schema': c.get('schema'),
        'country': (c.get('search') or {}).get('country'),
        'listed': not c.get('unlisted', False),
        'region': (c.get('view') or {}).get('region'),
        'data': '/%s/data/' % c['id'],
    })
open(os.path.join(ROOT, 'docs', 'cities.json'), 'w', encoding='utf-8').write(
    json.dumps({'version': 1, 'cities': cities}, ensure_ascii=False, separators=(',', ':')) + '\n')
print('published docs/cities.json', len(cities), 'cities')
