"""Builds the Layers.City logo files from one set of shapes.

The mark: a red map pin holding three stacked sheets (the map's layers). Two versions
(October 16, 2026): "D", the plain pin, is the default everywhere; "D2" adds a maple leaf cut into
the top sheet and is used only on Canadian cities' pages (search.country "ca" in city.json;
engine/assemble.py and engine/places.py pick the "-ca" files). Below about 40 px the leaf and one
sheet are dropped, so the favicon is the same for both. Writes, under docs/:
  logo.svg, logo-ca.svg             the mark, red pin on transparent
  favicon.svg, favicon.ico          small-size mark (16/32/48), for browser tabs, shared by both
  icon-192.png, icon-512.png        white pin on a red square (default only)
  apple-touch-icon.png, apple-touch-icon-ca.png (180)   home-screen icon
  og-layers.png, og-layers-ca.png   1200 x 630 social preview

Needs: pip install cairosvg pillow fonttools brotli. Run from anywhere: python3 assets/brand/build.py
"""
import io, os
import cairosvg
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DOCS = os.path.join(ROOT, 'docs')

RED, WHITE, INK, PAPER, INK2 = '#C8102E', '#FFFFFF', '#1A1414', '#FBF6F5', '#6B5F5D'

PIN = 'M60 112 C60 112 22 74 22 48 A38 38 0 0 1 98 48 C98 74 60 112 60 112 Z'
LEAF = ('M10 0 L11.6 3.2 L13.2 2.4 L12.6 6.6 L15.2 4.2 L15.8 5.8 L18.4 5.2 L17.4 8.2 L19.2 9.2 '
        'L14.6 12.8 L15.2 14.6 L10.6 14 L10.8 18.6 L9.2 18.6 L9.4 14 L4.8 14.6 L5.4 12.8 L0.8 9.2 '
        'L2.6 8.2 L1.6 5.2 L4.2 5.8 L4.8 4.2 L7.4 6.6 L6.8 2.4 L8.4 3.2 Z')


def mark(pin, sheet, leaf=True):
    """The full mark in a 120 x 120 box: pin colour, sheet colour (sheets fade from the top)."""
    s = ('<path d="%s" fill="%s"/>'
         '<polygon points="60,52 84,63 60,74 36,63" fill="%s" fill-opacity="0.42"/>'
         '<polygon points="60,39 84,50 60,61 36,50" fill="%s" fill-opacity="0.72"/>'
         '<polygon points="60,20 90,34 60,48 30,34" fill="%s"/>') % (PIN, pin, sheet, sheet, sheet)
    if leaf:
        s += '<path transform="translate(51,24.5) scale(0.9)" d="%s" fill="%s"/>' % (LEAF, pin)
    return s


def small(pin, sheet):
    """Favicon mark: two bigger sheets, no leaf."""
    return ('<path d="%s" fill="%s"/>'
            '<polygon points="60,42 86,54 60,66 34,54" fill="%s" fill-opacity="0.5"/>'
            '<polygon points="60,24 86,36 60,48 34,36" fill="%s"/>') % (PIN, pin, sheet, sheet)


def svg(body, vb='0 0 120 120', w=None, h=None):
    size = (' width="%s" height="%s"' % (w, h)) if w else ''
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%s"%s>%s</svg>' % (vb, size, body)


def tile(n, leaf=False):
    """App icon: white pin on a full red square (iOS and Android round the corners themselves)."""
    body = '<rect width="120" height="120" fill="%s"/><g transform="translate(60 61) scale(0.74) translate(-60 -61)">%s</g>' % (
        RED, mark(WHITE, RED, leaf))
    return svg(body, w=n, h=n)


def png(svgtext, n, h=None):
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svgtext.encode(), output_width=n,
                                                  output_height=h or n))).convert('RGBA')


def write(name, text):
    open(os.path.join(DOCS, name), 'w').write(text + '\n')
    print('wrote docs/' + name)


write('logo.svg', svg(mark(RED, WHITE, leaf=False), vb='18 6 84 108'))
write('logo-ca.svg', svg(mark(RED, WHITE), vb='18 6 84 108'))
write('favicon.svg', svg(small(RED, WHITE), vb='16 6 88 108'))

fav = svg(small(RED, WHITE), vb='16 6 88 108')
ico = [png(fav, 16), png(fav, 32), png(fav, 48)]
ico[2].save(os.path.join(DOCS, 'favicon.ico'), sizes=[(16, 16), (32, 32), (48, 48)], append_images=ico[:2])
print('wrote docs/favicon.ico')
for name, n, leaf in (('icon-192.png', 192, False), ('icon-512.png', 512, False),
                      ('apple-touch-icon.png', 180, False), ('apple-touch-icon-ca.png', 180, True)):
    png(tile(n, leaf), n).convert('RGB').save(os.path.join(DOCS, name), optimize=True)
    print('wrote docs/' + name)

# Social preview: the mark, the wordmark in Archivo (the hub's font), one line of description.
def font(weight, size):
    f = TTFont(os.path.join(DOCS, 'fonts', 'archivo-latin-%d-normal.woff2' % weight))
    f.flavor = None
    buf = io.BytesIO(); f.save(buf); buf.seek(0)
    return ImageFont.truetype(buf, size)

for name, leaf in (('og-layers.png', False), ('og-layers-ca.png', True)):
    og = Image.new('RGB', (1200, 630), PAPER)
    pin = png(svg(mark(RED, WHITE, leaf), vb='18 6 84 108'), 280, 360)
    og.paste(pin, (110, 135), pin)
    d = ImageDraw.Draw(og)
    big, dot, sub = font(800, 124), font(700, 124), font(700, 40)
    x, y = 450, 205
    d.text((x, y), 'Layers', font=big, fill=INK)
    x += d.textlength('Layers', font=big)
    d.text((x, y), '.City', font=dot, fill=RED)
    d.text((454, 375), 'Interactive maps of every way', font=sub, fill=INK2)
    d.text((454, 425), 'a city is divided', font=sub, fill=INK2)
    og.save(os.path.join(DOCS, name), optimize=True)
    print('wrote docs/' + name)
