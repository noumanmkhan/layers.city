"""Draws each city's outline on a grid, for the maps hub cards: docs/thumbs/<city>.svg.

Reads the "city" feature of docs/<city>/data/base.geojson, so run it after a city's build if its
outline changes. Lake and river edges come out exactly as the map draws them.
Run: python3 assets/brand/outlines.py
"""
import json, math, os
from shapely.geometry import shape

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
W, H, PAD, GRID = 800, 600, 64, 50
RED, TINT, GRIDC, BG = '#C8102E', 'rgba(200,16,46,.09)', 'rgba(26,20,20,.08)', '#FBF8F7'

os.makedirs(os.path.join(ROOT, 'docs', 'thumbs'), exist_ok=True)
for city in sorted(os.listdir(os.path.join(ROOT, 'cities'))):
    src = os.path.join(ROOT, 'docs', city, 'data', 'base.geojson')
    if not os.path.isfile(src):
        continue
    feats = [f for f in json.load(open(src))['features'] if f.get('geometry') and f['properties'].get('kind') == 'city']
    if not feats:
        continue
    geom = shape(feats[0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds
    k = math.cos(math.radians((miny + maxy) / 2))   # squash longitude so the shape isn't stretched
    gw, gh = (maxx - minx) * k, maxy - miny
    s = min((W - 2 * PAD) / gw, (H - 2 * PAD) / gh)
    ox, oy = (W - gw * s) / 2, (H - gh * s) / 2
    geom = geom.simplify(0.6 / s / k)                # about half a pixel
    pt = lambda x, y: '%.1f %.1f' % (ox + (x - minx) * k * s, oy + (maxy - y) * s)
    polys = getattr(geom, 'geoms', [geom])
    d = ''
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            c = list(ring.coords)
            d += 'M' + ' L'.join(pt(x, y) for x, y in c) + 'Z'
    grid = ''.join('<path d="M%d 0V%d"/>' % (x, H) for x in range(GRID, W, GRID)) + \
           ''.join('<path d="M0 %dH%d"/>' % (y, W) for y in range(GRID, H, GRID))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d"><rect width="%d" height="%d" fill="%s"/>'
           '<g stroke="%s" stroke-width="1">%s</g>'
           '<path d="%s" fill="%s" stroke="%s" stroke-width="4.5" stroke-linejoin="round" fill-rule="evenodd"/></svg>\n') % (
        W, H, W, H, BG, GRIDC, grid, d, TINT, RED)
    out = os.path.join(ROOT, 'docs', 'thumbs', city + '.svg')
    open(out, 'w').write(svg)
    print('wrote docs/thumbs/%s.svg' % city, len(svg), 'bytes')
