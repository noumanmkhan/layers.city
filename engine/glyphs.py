"""Signed-distance-field glyph files for the MapLibre map (docs/glyphs/<font>/<start>-<end>.pbf).

MapLibre draws map text on the GPU from SDF glyph sheets, fetched in 256-character ranges. This writes them for the
Inter weights the map uses, from the woff2 files of the @fontsource/inter npm package (SIL Open Font Licence).

Usage: python3 engine/glyphs.py <dir with inter-latin-*.woff2>
Needs: fonttools, brotli, freetype-py, numpy, scipy. Run once; the output is committed."""
import io, os, sys
import numpy as np, freetype
from fontTools.ttLib import TTFont
from scipy.ndimage import distance_transform_edt

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: glyphs.py <fontsource files dir>')
FONTS = {'Inter Regular': '400-normal', 'Inter Medium': '500-normal', 'Inter SemiBold': '600-normal', 'Inter Bold': '700-normal',
         'Inter Medium Italic': '500-italic', 'Inter SemiBold Italic': '600-italic'}
RANGES = [0, 256, 8192]          # Basic Latin + Latin-1, Latin Extended-A, General Punctuation
SIZE, BUFFER, RADIUS, CUTOFF, UP = 24, 3, 8, 0.25, 4

def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n: out.append(b | 0x80)
        else: out.append(b); return bytes(out)
def key(field, wire): return varint(field << 3 | wire)
def ln(field, data): return key(field, 2) + varint(len(data)) + data
def uint(field, n): return key(field, 0) + varint(n)
def sint(field, n): return key(field, 0) + varint((n << 1) ^ (n >> 31) if n >= 0 else ((-n) << 1) - 1)

def sdf(face, code):
    face.set_char_size(SIZE * UP * 64)
    face.load_char(chr(code), freetype.FT_LOAD_RENDER)
    g = face.glyph; bm = g.bitmap
    adv = round(g.advance.x / 64 / UP)
    if bm.width == 0 or bm.rows == 0:
        return dict(width=0, height=0, left=0, top=0, advance=adv, bitmap=b'')
    a = np.array(bm.buffer, dtype=np.uint8).reshape(bm.rows, bm.pitch)[:, :bm.width] > 127
    left, top = g.bitmap_left / UP, g.bitmap_top / UP
    w, h = int(np.ceil(bm.width / UP)), int(np.ceil(bm.rows / UP))
    pad = BUFFER * UP
    big = np.zeros((h * UP + 2 * pad, w * UP + 2 * pad), bool)
    big[pad:pad + a.shape[0], pad:pad + a.shape[1]] = a
    dist = (distance_transform_edt(~big) - distance_transform_edt(big)) / UP   # + outside, - inside, in output pixels
    small = dist[UP // 2::UP, UP // 2::UP][:h + 2 * BUFFER, :w + 2 * BUFFER]
    val = np.clip(255 - 255 * (small / RADIUS + CUTOFF), 0, 255).astype(np.uint8)
    face.set_char_size(SIZE * 64)
    asc = face.size.ascender / 64
    return dict(width=w, height=h, left=int(round(left)), top=int(round(top - asc)), advance=adv, bitmap=val.tobytes())

for name, f in FONTS.items():
    tt = TTFont(os.path.join(SRC, 'inter-latin-%s.woff2' % f)); tt.flavor = None
    buf = io.BytesIO(); tt.save(buf)
    face = freetype.Face(io.BytesIO(buf.getvalue()))
    cmap = tt.getBestCmap()
    out_dir = os.path.join(ROOT, 'docs', 'glyphs', name); os.makedirs(out_dir, exist_ok=True)
    for start in RANGES:
        end = start + 255
        glyphs = b''
        for code in range(start, end + 1):
            if code not in cmap: continue
            m = sdf(face, code)
            body = uint(1, code) + (ln(2, m['bitmap']) if m['bitmap'] else b'') + uint(3, m['width']) + uint(4, m['height']) + \
                sint(5, m['left']) + sint(6, m['top']) + uint(7, m['advance'])
            glyphs += ln(3, body)
        stack = ln(1, name.encode()) + ln(2, ('%d-%d' % (start, end)).encode()) + glyphs
        open(os.path.join(out_dir, '%d-%d.pbf' % (start, end)), 'wb').write(ln(1, stack))
    print(name)
