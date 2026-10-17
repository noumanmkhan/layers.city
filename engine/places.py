"""Static pages, one per place (Toronto's neighbourhoods, Chicago's community areas), for search engines and
link previews: docs/<city>/<slug>/index.html with its own og.png, an index page per city
(docs/<city>/<plural slug>/), and the site-wide docs/sitemap.xml and docs/robots.txt.

Usage: python3 engine/places.py <city>     (run.sh runs it after assemble; it also rewrites the sitemap)

A page says in plain text what the map's card says about the place, by the card's rules: describe, don't rank;
census rows keep their year and caveats; tiers are the same words the card uses. Its main button opens the map
focused on the place (#focus=<units layer id>:<name>), so nothing about the map, its links or its data changes.
Reads only published files (docs/<city>/data/). Unlisted cities get no pages and stay out of the sitemap.

Needs: pip install shapely pillow fonttools brotli"""
import html, io, json, os, re, sys, unicodedata
from shapely.geometry import shape
from urllib.parse import quote
import math
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DOCS = os.path.join(ROOT, 'docs')
SITE = 'https://layers.city'
city = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: places.py <city>')
D = os.path.join(DOCS, city, 'data')
cfg = json.load(open(os.path.join(D, 'city.json')))
esc = lambda s: html.escape(str(s), quote=True)
if cfg.get('unlisted'): sys.exit(f'{city} is unlisted: no place pages yet')

def slug(s):
    s = re.sub(r"['’]", '', s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()   # O'Hare -> ohare, not o-hare
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def fill(tpl, ctx):
    """The engine's {name} templates, with [optional parts] dropped when a field inside is missing."""
    def sub(s, miss):
        def r(m):
            v = ctx.get(m.group(1))
            if v is None or v == '': miss(); return ''
            return str(v)
        return re.sub(r'\{([\w.]+)\}', r, s)
    def opt(m):
        gone = []
        out = sub(m.group(1), lambda: gone.append(1))
        return '' if gone else out
    missing = []
    out = sub(re.sub(r'\[([^\]]*)\]', opt, tpl), lambda: missing.append(1))
    return '' if missing else out

LAYERS = [it for _, items in cfg['groups'] for it in items]
UNITS = next(it for it in LAYERS if it['kind'] == 'units')
LENS = cfg['lens']
U = cfg.get('units', {'singular': 'Neighbourhood', 'plural': 'neighbourhoods'})
CITY = cfg.get('heading') or cfg['title'].split(' · ')[0]
LIV = cfg['card'].get('living', {})
LOCALE_MI = cfg.get('distance') == 'mi'
INDEX_SLUG = slug(U['plural'])

def gj(name):
    p = os.path.join(D, name + '.geojson')
    return json.load(open(p))['features'] if os.path.exists(p) else []

units = gj(UNITS['file'])
profiles = json.load(open(os.path.join(D, LENS['file']))) if LENS.get('file') else {}
fills = [it for it in LAYERS if it['kind'] == 'fill']
peers = cfg.get('facts', {}).get('peers') or []
peers = [peers] if isinstance(peers, str) else peers
# Containing areas: the fill layers (former cities and Old Toronto areas; Chicago's sides), named on the card.
fill_feats = {it['id']: [(f['properties'], shape(f['geometry'])) for f in gj(it['file'])] for it in fills}
fact_labels = {f.get('layer'): f['label'] for f in cfg['card'].get('facts', []) if f.get('layer')}
names_pts = [(f['properties']['name'], shape(f['geometry'])) for it in LAYERS if it['kind'] == 'knownas' for f in gj(it['file'])]
marks = [(f['properties']['name'], shape(f['geometry'])) for it in LAYERS if it['kind'] == 'landmarks' for f in gj(it['file'])]

TIER = {}
for L in LENS['lenses']:
    for k, label, _ in L['tiers']: TIER[(L['key'], k)] = label
hub = next((L for L in LENS['lenses'] if L.get('minutes')), None)

def money(v):
    return '$' + (('%.1fM' % (v / 1e6)).replace('.0M', 'M') if v >= 1e6 else '%dK' % round(v / 1e3))

def mix(cfgrow, shares, names):
    if not cfgrow or not shares or not names: return None
    words = ' · '.join(f'{n} {v}%' for n, v in zip(names, shares) if v >= 1)
    return (cfgrow['label'], words, cfgrow.get('caveat'))

def living(d):
    """The card's Living here rows, as (label, text, caveat)."""
    rows = []
    tier = lambda key, v: TIER.get((key, v))
    cost = tier('cost', d['cost']); cost += '' if 'cost' in cost.lower() else ' housing cost'   # the card's "Middle" chip needs its noun in a sentence
    hv = ' · '.join(x for x in ((f"Median home {money(d['value'])}" if d.get('value') else ''), (f"renters pay ${d['rent']:,}/mo" if d.get('rent') else '')) if x)
    rows.append(('Housing', f"{cost}. {hv}" if hv else cost, LIV.get('caveat')))   # a ZIP with too few homes for a median has none
    if hub and d.get(hub['minutes']) is not None:
        rows.append((LIV.get('hub', hub['short']), f"{tier(hub['key'], d.get(hub['key']))}. " + fill(LIV.get('hubText', '{minutes} min'), {'minutes': d[hub['minutes']]}), None))
    rows.append(('Getting to work', f"{tier('commute', d['commute'])}. {d['carPct']}% drive · {d['transitPct']}% transit · {d['walkBikePct']}% walk or bike", None))
    rows.append(('Households', f"{tier('tenure', d['tenure'])}. {d['renterPct']}% rent", None))
    if LIV.get('canopy') and d.get('canopy') is not None:
        t = tier('canopyBand', d.get('canopyBand'))
        rows.append((LIV['canopy']['label'], (t + '. ' if t else '') + fill(LIV['canopy']['text'], {'pct': d['canopy']}), LIV['canopy'].get('caveat')))
    for key, field, names in (('homes', 'homes', [t[1] for t in LIV.get('homes', {}).get('types', [])]), ('built', 'built', LIV.get('built', {}).get('bands')),
                              ('ages', 'ages', LIV.get('ages', {}).get('bands'))):
        r = mix(LIV.get(key), d.get(field), names)
        if r: rows.append(r)
    lc = LIV.get('lang')
    if lc and d.get('lang'):
        floor = lc.get('floor', 5)
        top = [x for i, x in enumerate(d['lang']) if i == 0 or x[1] >= floor][:3]
        text = ' · '.join(f'{n} {v}%' for n, v in top) + ('' if len(top) > 1 else ' · ' + lc.get('none', f'No other language above {floor}%'))
        rows.append((lc['label'], text, fill(lc['note'], {'multi': d.get('langMulti')}) if lc.get('note') else None))
    rc = LIV.get('recent')
    if rc and d.get('recent') is not None:
        rows.append((rc['label'], fill(rc['text'], {'pct': d['recent'], 'since': d.get('recentSince', '')}), rc.get('caveat')))
    return rows

# ---------- Social preview image: the place in red on the city's outline, with its name ----------
def font(weight, size, fam='archivo'):
    f = TTFont(os.path.join(DOCS, 'fonts', f'{fam}-latin-{weight}-normal.woff2')); f.flavor = None
    b = io.BytesIO(); f.save(b); b.seek(0)
    return ImageFont.truetype(b, size)
F_BIG = {s: font(800, s) for s in (84, 72, 62, 54, 46, 40)}
F_SUB, F_BRAND, F_BRAND2 = font(700, 34), font(800, 34), font(700, 34)
RED, INK, INK2, PAPER, LAND, EDGE = '#C8102E', '#1A1414', '#5C5251', '#FBF6F5', '#EDE4E2', '#D6C9C6'
geoms = [(u['properties'], shape(u['geometry'])) for u in units]
minx = min(g.bounds[0] for _, g in geoms); miny = min(g.bounds[1] for _, g in geoms)
maxx = max(g.bounds[2] for _, g in geoms); maxy = max(g.bounds[3] for _, g in geoms)
kx = math.cos(math.radians((miny + maxy) / 2))
BOX = (660, 40, 1160, 590)   # map area on the right
sc = min((BOX[2] - BOX[0]) / ((maxx - minx) * kx), (BOX[3] - BOX[1]) / (maxy - miny))
ox = BOX[0] + ((BOX[2] - BOX[0]) - (maxx - minx) * kx * sc) / 2
oy = BOX[1] + ((BOX[3] - BOX[1]) - (maxy - miny) * sc) / 2
proj = lambda x, y: (ox + (x - minx) * kx * sc, oy + (maxy - y) * sc)

def polys(g):
    return list(g.geoms) if g.geom_type == 'MultiPolygon' else [g]

def wrap(d, text, f, width):
    words, lines = text.split(), ['']
    for w in words:
        t = (lines[-1] + ' ' + w).strip()
        if d.textlength(t, font=f) <= width or not lines[-1]: lines[-1] = t
        else: lines.append(w)
    return lines

def og_image(name, target, path, sub=None):
    """target None: every unit in red with paper edges (the index page)."""
    S = 2   # draw at twice the size, then shrink: smooth edges
    im = Image.new('RGB', (1200 * S, 630 * S), PAPER); d = ImageDraw.Draw(im)
    P = lambda x, y: tuple(v * S for v in proj(x, y))
    for _, g in geoms:
        for p in polys(g):
            d.polygon([P(*c) for c in p.exterior.coords], fill=LAND if target else RED, outline=EDGE if target else PAPER, width=S)
    for p in (polys(target) if target else []):
        d.polygon([P(*c) for c in p.exterior.coords], fill=RED, outline=RED, width=S)
    im = im.resize((1200, 630), Image.LANCZOS); d = ImageDraw.Draw(im)
    # Brand line, then the name (largest size that fits in three lines), then what it is.
    d.text((72, 64), 'Layers', font=F_BRAND, fill=INK)
    d.text((72 + d.textlength('Layers', font=F_BRAND), 64), '.City', font=F_BRAND2, fill=RED)
    for s, f in F_BIG.items():
        lines = wrap(d, name, f, 540)
        if len(lines) <= 3 and max(d.textlength(ln, font=f) for ln in lines) <= 560: break
    y = 315 - len(lines) * s * 1.08 / 2
    for ln in lines:
        d.text((72, y), ln, font=f, fill=INK); y += s * 1.08
    d.text((72, y + 18), sub or f"{U['singular']} · {CITY}", font=F_SUB, fill=INK2)
    # A few flat colours and anti-aliased edges: a 48-colour palette keeps each image small.
    im.convert('P', palette=Image.ADAPTIVE, colors=48).save(path, optimize=True)

# ---------- Pages ----------
CSS = """@font-face{font-family:'Archivo';font-weight:800;font-display:swap;src:url(/fonts/archivo-latin-800-normal.woff2) format('woff2')}
@font-face{font-family:'Archivo';font-weight:700;font-display:swap;src:url(/fonts/archivo-latin-700-normal.woff2) format('woff2')}
@font-face{font-family:'IBM Plex Sans';font-weight:400;font-display:swap;src:url(/fonts/ibm-plex-sans-latin-400-normal.woff2) format('woff2')}
@font-face{font-family:'IBM Plex Sans';font-weight:500;font-display:swap;src:url(/fonts/ibm-plex-sans-latin-500-normal.woff2) format('woff2')}
:root{--bg:#F7F4F3;--card:#FFFFFF;--ink:#1A1414;--ink-2:#463D3C;--ink-3:#5C5251;--rule:#D8CFCD;--accent:#C8102E;--soft:rgba(200,16,46,.08);
--display:'Archivo',system-ui,sans-serif;--body:'IBM Plex Sans',system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#161212;--card:#201A1A;--ink:#F3ECEB;--ink-2:#CFC4C2;--ink-3:#A89D9B;--rule:#3A3130;--accent:#E5364F;--soft:rgba(229,54,79,.14)}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);font-size:17px;line-height:1.6}
a{color:var(--accent)}
.wrap{max-width:820px;margin:0 auto;padding:0 20px}
header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:22px 0}
.brand{display:flex;align-items:center;gap:10px;color:var(--ink);text-decoration:none;font-family:var(--display);font-weight:800;font-size:20px}
.brand b{color:var(--accent);font-weight:700}.brand svg{width:26px;height:auto}
.crumbs{font-size:14px;color:var(--ink-3)}.crumbs a{color:var(--ink-2)}
h1{font-family:var(--display);font-weight:800;font-size:clamp(36px,7vw,60px);line-height:1.02;letter-spacing:-.02em;margin:24px 0 10px}
.kind{margin:0;color:var(--ink-2);font-size:18px}
.in{margin:6px 0 0;color:var(--ink-2)}
.go{display:inline-flex;align-items:center;gap:8px;margin:24px 0 8px;min-height:48px;padding:0 22px;border-radius:999px;background:var(--accent);color:#fff;text-decoration:none;font-weight:500;font-size:17px}
.go:focus-visible,.brand:focus-visible{outline:3px solid var(--ink);outline-offset:3px}
section{background:var(--card);border:1.5px solid var(--rule);border-radius:14px;padding:22px 24px;margin:20px 0}
h2{font-family:var(--display);font-weight:700;font-size:22px;margin:0 0 12px}
dl{margin:0}dt{font-weight:500;margin-top:14px}dt:first-child{margin-top:0}dd{margin:2px 0 0;color:var(--ink-2)}
.cav{display:block;font-size:14px;color:var(--ink-3);margin-top:2px}
ul{margin:0;padding-left:20px}li{margin:4px 0}
.chips{display:flex;flex-wrap:wrap;gap:8px;padding:0;list-style:none}.chips li{margin:0}
.chips a,.chips span{display:inline-block;padding:4px 12px;border-radius:999px;background:var(--soft);color:var(--ink);text-decoration:none;font-size:15px}
.chips a:hover{outline:1.5px solid var(--accent)}
.note{font-size:14px;color:var(--ink-3)}
.cols{columns:2 240px;column-gap:28px}.cols h3{font-family:var(--display);font-size:17px;margin:14px 0 4px;break-after:avoid}
.cols ul{list-style:none;padding:0}
footer{padding:28px 0 40px;font-size:14px;color:var(--ink-3)}footer a{color:var(--ink-2)}
@media (max-width:520px){section{padding:18px}h1{margin-top:12px}}"""
PIN = ('<svg viewBox="18 6 84 108" aria-hidden="true"><path d="M60 112 C60 112 22 74 22 48 A38 38 0 0 1 98 48 C98 74 60 112 60 112 Z" fill="#C8102E"/>'
       '<polygon points="60,52 84,63 60,74 36,63" fill="#fff" fill-opacity=".42"/><polygon points="60,39 84,50 60,61 36,50" fill="#fff" fill-opacity=".72"/>'
       '<polygon points="60,20 90,34 60,48 30,34" fill="#fff"/>%s</svg>')
# Canadian cities get the logo with the maple leaf cut into the top sheet; the rest the plain pin.
CA = cfg.get('search', {}).get('country') == 'ca'
BRAND = '-ca' if CA else ''
PIN %= ('<path transform="translate(51,24.5) scale(0.9)" d="M10 0 L11.6 3.2 L13.2 2.4 L12.6 6.6 L15.2 4.2 L15.8 5.8 '
        'L18.4 5.2 L17.4 8.2 L19.2 9.2 L14.6 12.8 L15.2 14.6 L10.6 14 L10.8 18.6 L9.2 18.6 L9.4 14 L4.8 14.6 L5.4 12.8 '
        'L0.8 9.2 L2.6 8.2 L1.6 5.2 L4.2 5.8 L4.8 4.2 L7.4 6.6 L6.8 2.4 L8.4 3.2 Z" fill="#C8102E"/>' if CA else '')

def page(title, desc, canonical, og, body, extra_head=''):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Layers.City">
<meta property="og:url" content="{canonical}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{og}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="/apple-touch-icon{BRAND}.png">
{extra_head}<style>{CSS}</style>
<script src="/stats.js" defer></script>
</head>
<body>
<div class="wrap">
<header><a class="brand" href="/">{PIN}<span>Layers<b>.City</b></span></a>
<nav class="crumbs"><a href="/{city}/">{esc(CITY)} map</a> · <a href="/{city}/{INDEX_SLUG}/">All {esc(U['plural'])}</a></nav></header>
<main>
{body}
</main>
<footer>{esc(re.sub('<[^>]+>', '', cfg['attribution']))}<br><a href="/attributions/">Attributions</a> · <a href="/privacy/">Privacy</a> · <a href="/terms/">Terms</a> · <a href="/">All maps</a></footer>
</div>
</body>
</html>
"""

out_dir = os.path.join(DOCS, city)
existing = {n for n in os.listdir(out_dir) if os.path.isdir(os.path.join(out_dir, n))}
made = {}
for u, (props, g) in zip(units, geoms):
    s = slug(props['name'])
    if s in made: s = f"{s}-{props['code']}"
    made[s] = (props, g)
if INDEX_SLUG in made or 'data' in made: sys.exit(f'slug clash: {INDEX_SLUG} or data')
# Folders this script wrote before (they hold an og.png) can go; anything else under docs/<city>/ must not be touched.
ours = {n for n in existing if os.path.exists(os.path.join(out_dir, n, 'og.png'))} | ({INDEX_SLUG} & existing)
clash = (set(made) | {INDEX_SLUG}) & (existing - ours)
if clash: sys.exit(f'would overwrite folders that are not place pages: {sorted(clash)}')
for gone in ours - set(made) - {INDEX_SLUG}:
    for f in os.listdir(os.path.join(out_dir, gone)): os.remove(os.path.join(out_dir, gone, f))
    os.rmdir(os.path.join(out_dir, gone)); print('removed', gone)

def where(g):
    """[(layer label, feature props)] for each fill layer the place sits in (by its interior point)."""
    pt = g.representative_point(); res = []
    for it in fills:
        hitp = next((p for p, fg in fill_feats[it['id']] if fg.contains(pt)), None)
        if hitp: res.append((fact_labels.get(it['id'], it['name']), hitp))
    return res

index_groups = {}
for s, (props, g) in sorted(made.items()):
    name, code = props['name'], props['code']
    d = profiles.get(str(code), {})
    ins = where(g)
    near = sorted((p['name'], ss) for ss, (p, gg) in made.items() if ss != s and gg.intersects(g.buffer(1e-5)))
    known = sorted({n for n, pt in names_pts if g.contains(pt)})
    lms = sorted({n for n, pt in marks if g.contains(pt)})
    group = ins[-1][1]['name'] if ins else CITY
    index_groups.setdefault(group, []).append((name, s))
    focus = '/' + city + '/#focus=' + UNITS['id'] + ':' + quote(name)
    in_txt = ' · '.join(f"{lab}: {esc(p['name'])}" for lab, p in ins)
    info = next((p for _, p in reversed(ins) if p.get('info')), None)   # the innermost area with a description
    # A unit that isn't one of the city's own (its "park" text says what it is: Stanley Park, the University Endowment Lands).
    other = props.get('park')
    kind_txt = other[:1].upper() + other[1:] if other else f"{U['singular']} in {CITY}"
    parts = [f'<h1>{esc(name)}</h1>', f"<p class=\"kind\">{esc(kind_txt)}" + (f" · #{code}" if not other and UNITS.get('hover', '').count('#{code}') else '') + '</p>']
    if in_txt: parts.append(f'<p class="in">{in_txt}</p>')
    parts.append(f'<a class="go" href="{esc(focus)}">Open {esc(name)} on the map <span aria-hidden="true">→</span></a>')
    parts.append(f'<p class="note">The map shows every boundary here, from wards and ridings to school boards, with what’s nearby. Tap any address in it for its own card.</p>')
    if os.path.exists(os.path.join(out_dir, 'profiles', 'data', s + '.json')):
        parts.append(f'<p class="note"><a href="/{city}/profiles/?n={s}">Fact sheet for {esc(name)}</a>: '
                     f'transit, driving, parking and more on one page, ready to print.</p>')
    if info: parts.append(f'<section><h2>About {esc(info["name"])}</h2><p style="margin:0">{esc(info["info"])}</p></section>')
    if known or lms:
        sec = '<section><h2>Names you’ll hear here</h2>'
        if known: sec += '<ul class="chips">' + ''.join(f'<li><span>{esc(n)}</span></li>' for n in known) + '</ul>'
        if lms: sec += ('<p style="margin:14px 0 6px">Landmarks:</p>' if known else '') + '<ul class="chips">' + ''.join(f'<li><span>{esc(n)}</span></li>' for n in lms) + '</ul>'
        parts.append(sec + '</section>')
    facts = d.get('facts') or []
    if facts:
        parts.append('<section><h2>What stands out</h2><ul>' + ''.join(f"<li>{esc(f['text'])} ({esc(f['value'])})</li>" for f in facts) + '</ul></section>')
    rows = living(d) if d.get('cost') else []
    if rows:
        dl = ''.join(f'<dt>{esc(a)}</dt><dd>{esc(b)}' + (f'<span class="cav">{esc(c)}</span>' if c else '') + '</dd>' for a, b, c in rows)
        foot = fill(LIV.get('footer', ''), {'name': name})
        parts.append(f'<section><h2>Living here</h2><dl>{dl}</dl>' + (f'<p class="note" style="margin:14px 0 0">{esc(foot)}</p>' if foot else '') + '</section>')
    if near:
        parts.append('<section><h2>Next door</h2><ul class="chips">' + ''.join(f'<li><a href="/{city}/{ss}/">{esc(n)}</a></li>' for n, ss in near) + '</ul></section>')
    # Description: what it is and where, then up to two plain facts (never a ranking).
    bits = [(f"{name}: {other}" if other else f"{name} is a {U['singular'].lower()} in {CITY}") + (f" ({', '.join(p['name'] for _, p in ins)})" if ins else '') + '.']
    if known: bits.append('Includes ' + ', '.join(known[:3]) + '.')
    if d.get('value'): bits.append(f"Median home {money(d['value'])}, {d['renterPct']}% of households rent" + (f", about {d[hub['minutes']]} min by transit to {cfg['facts'].get('hub', 'downtown')}" if hub and d.get(hub['minutes']) else '') + '.')
    desc = ' '.join(bits) + ' Boundaries, representatives and more on the map.'
    os.makedirs(os.path.join(out_dir, s), exist_ok=True)
    og_image(name, g, os.path.join(out_dir, s, 'og.png'))
    open(os.path.join(out_dir, s, 'index.html'), 'w').write(
        page(f'{name} · {CITY} · Layers.City', desc, f'{SITE}/{city}/{s}/', f'{SITE}/{city}/{s}/og.png', '\n'.join(parts)))

# Index page: every place, grouped by the innermost containing area.
cols = ''.join(f'<h3>{esc(gname)}</h3><ul>' + ''.join(f'<li><a href="/{city}/{s}/">{esc(n)}</a></li>' for n, s in sorted(items)) + '</ul>'
               for gname, items in sorted(index_groups.items()))
os.makedirs(os.path.join(out_dir, INDEX_SLUG), exist_ok=True)
OWN = sum(1 for p, _ in made.values() if not p.get('park'))   # the city's own units; pages for the others are listed too
idx_title = f"{CITY}’s {OWN} {U['plural']} · Layers.City"
idx_desc = f"Every one of {CITY}’s {OWN} {U['plural']}" + (" and the places beside them" if OWN < len(made) else '') + ": where each sits, the names people use there, and what living there looks like, with a map of every boundary."
og_image(f"{CITY}’s {OWN} {U['plural']}", None, os.path.join(out_dir, INDEX_SLUG, 'og.png'), sub='A page for each, with a map')
open(os.path.join(out_dir, INDEX_SLUG, 'index.html'), 'w').write(page(idx_title, idx_desc, f'{SITE}/{city}/{INDEX_SLUG}/', f'{SITE}/{city}/{INDEX_SLUG}/og.png',
    f"<h1>{esc(CITY)}’s {OWN} {esc(U['plural'])}</h1><p class=\"kind\">{esc(idx_desc)}</p>"
    f"<a class=\"go\" href=\"/{city}/\">Open the {esc(CITY)} map <span aria-hidden=\"true\">→</span></a><section><div class=\"cols\">{cols}</div></section>"))
print(f'{city}: {len(made)} place pages + /{city}/{INDEX_SLUG}/')

# Sitemap and robots, for every listed city whose pages exist.
urls = [f'{SITE}/']
for c in sorted(os.listdir(os.path.join(ROOT, 'cities'))):
    p = os.path.join(DOCS, c, 'data', 'city.json')
    if not os.path.exists(p): continue
    cc = json.load(open(p))
    if cc.get('unlisted'): continue
    urls.append(f'{SITE}/{c}/')
    base = os.path.join(DOCS, c)
    for n in sorted(os.listdir(base)):
        if os.path.exists(os.path.join(base, n, 'og.png')) and os.path.exists(os.path.join(base, n, 'index.html')): urls.append(f'{SITE}/{c}/{n}/')
    if os.path.exists(os.path.join(base, 'profiles', 'index.html')): urls.append(f'{SITE}/{c}/profiles/')
urls += [f'{SITE}/about/', f'{SITE}/privacy/', f'{SITE}/attributions/', f'{SITE}/terms/']
open(os.path.join(DOCS, 'sitemap.xml'), 'w').write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    ''.join(f'  <url><loc>{u}</loc></url>\n' for u in urls) + '</urlset>\n')
open(os.path.join(DOCS, 'robots.txt'), 'w').write(f'User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n')
print('sitemap:', len(urls), 'urls')
