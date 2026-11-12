"""Build a city's MapLibre GL prototype page: engine/gl/page.html + engine/gl/map-gl.js + the engine's styles
(engine/template.html) and the city's city.json and city.css -> docs/<city>/gl/index.html.

Usage: python3 engine/gl/build.py <city>
The page reads the city's published data from ../data/ and the glyphs from /glyphs/ (engine/gl/glyphs.py)."""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
MAPLIBRE = '5.24.1'
city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: build.py <city>')
read = lambda *p: open(os.path.join(*p), encoding='utf-8').read()
cfg = json.loads(read(ROOT, 'cities', city, 'city.json'))
tpl = read(ROOT, 'engine', 'template.html')
# The engine's main style block (colours, classes), the one after Leaflet's stylesheet.
css = re.findall(r'<style>\n(.*?)</style>', tpl, re.S)
engine_css = max(css, key=len)
t = read(HERE, 'page.html')
t = t.replace('%TITLE%', cfg.get('heading', cfg['title'])).replace('%MLV%', MAPLIBRE)
t = t.replace('/*ENGINE_CSS*/', engine_css).replace('/*CITY_CSS*/', read(ROOT, 'cities', city, 'city.css'))
t = t.replace('/*CITY_CONFIG*/', json.dumps(cfg, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
t = t.replace('/*ENGINE_JS*/', read(HERE, 'map-gl.js'))
out = os.path.join(ROOT, 'docs', city, 'gl', 'index.html')
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, 'w', encoding='utf-8').write(t)
print('built docs/%s/gl/index.html' % city, len(t), 'bytes')
