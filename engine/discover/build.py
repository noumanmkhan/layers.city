"""Build a city's discovery places layer: the places a city government has described in its own open data (walking
tours, public art, cultural guides), plus hand-checked viewpoints. Businesses are not part of it (the website shows
none; they're for the iOS app).

Reads cities/<city>/discover.json (which datasets, which columns, how a row gets its kind) and writes
docs/<city>/data/discover.geojson: one point per place with its kind, name, a short word under the name, the
publisher's own description (quoted, never rewritten), the credit to show with it and a link to the publisher's page.
Along the way (engine/along/build.py) reads it; so can the app (DATA_CONTRACT.md).

  python3 engine/discover/build.py <city>           # build from cities/<city>/raw/discover/
  python3 engine/discover/build.py <city> --fetch   # download each source first (the weekly job does this)

The engine names no city: every dataset, column and rule is in discover.json, whose "_about" explains the keys.
"""
import csv, difflib, hashlib, io, json, math, os, re, sys, time, unicodedata, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
UA = {'User-Agent': 'city-layers/1.0 (https://layers.city)'}


def fetch(url, path):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                b = r.read()
            if len(b) < 200: raise RuntimeError(f'only {len(b)} bytes')
            open(path, 'wb').write(b)
            print(f'  discover: fetched {os.path.basename(path)} ({len(b) // 1000} kB)', flush=True)
            return
        except Exception as e:
            print(f'  discover: retry {i + 1} {url}: {e}', flush=True); time.sleep(10 * (i + 1))
    raise RuntimeError(f'could not fetch {url}')


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"['’`]", '', s.replace('&', ' and '))
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def clean(s):
    s = (s or '').replace('\r', '').strip()
    return '' if s.lower() in ('none', 'null', 'n/a') else re.sub(r'[ \t]+', ' ', s)


def metres(a, b):
    kx = 111320 * math.cos(math.radians(a[1]))
    return math.hypot((a[0] - b[0]) * kx, (a[1] - b[1]) * 110540)


def point(row, src):
    if src.get('lat') and src.get('lon'):
        try: return [float(row[src['lon']]), float(row[src['lat']])]
        except (TypeError, ValueError): return None
    try:
        g = json.loads(row[src.get('geometry', 'geometry')])
        c = g['coordinates']
        while isinstance(c[0], list): c = c[0]
        return [float(c[0]), float(c[1])]
    except Exception:
        return None


def kind_of(row, name, src):
    """The first rule in src["kinds"] that matches: {"kind", "match": regex, "field": column (default the name)}."""
    for r in src['kinds']:
        if 'match' not in r: return r['kind']
        v = row.get(r['field'], '') if r.get('field') else name
        if re.search(r['match'], v or ''): return r['kind']
    return None


def word_of(row, kind, src, cfg):
    """The short line under the name: src["word"] is a list of columns joined with ' · ' (empty ones dropped),
    falling back to the kind's word in discover.json "words". Columns in src["flip"] hold "Last, First" names."""
    parts = []
    for c in src.get('word', []):
        v = clean(row.get(c, ''))
        if re.fullmatch(r'(?i)unknown|anonymous|various|n/?a', v): v = ''
        if c in src.get('flip', []) and v.count(',') == 1 and not re.search(r'(?i)\band\b|&|studio|inc\b|ltd', v):
            v = ' '.join(x.strip() for x in reversed(v.split(',')))   # "Belmore, Michael" -> "Michael Belmore"
        if v and v not in parts: parts.append(v)
    return ' · '.join(parts) or cfg.get('words', {}).get(kind, '')


def build(city, do_fetch):
    cdir = os.path.join(ROOT, 'cities', city)
    cfg = json.load(open(os.path.join(cdir, 'discover.json'), encoding='utf-8'))
    raw = os.path.join(cdir, 'raw', 'discover'); os.makedirs(raw, exist_ok=True)
    places = []

    # Viewpoints first: hand-kept and checked, so they win over a dataset's row for the same place.
    vp = cfg.get('viewpoints')
    if vp:
        V = json.load(open(os.path.join(cdir, vp), encoding='utf-8'))
        for v in V['places']:
            places.append({'kind': 'view', 'name': v['name'], 'word': v.get('word') or cfg.get('words', {}).get('view', ''),
                           'text': v['why'], 'credit': V.get('credit', ''), 'link': v.get('link', ''), 'src': 'viewpoints',
                           'checked': v['checked'], 'pt': [v['lon'], v['lat']], 'also': [norm(a) for a in v.get('same_as', [])]})
        print(f"  discover: {len(V['places'])} viewpoints")

    for src in cfg['sources']:
        path = os.path.join(raw, src['id'] + '.csv')
        if do_fetch: fetch(src['url'], path)
        if not os.path.exists(path): print(f"  discover: no {src['id']}.csv (run with --fetch)"); continue
        rows = list(csv.DictReader(io.StringIO(open(path, encoding='utf-8-sig').read())))
        n0, kept = len(places), {}
        for row in rows:
            if any(not re.search(rx, row.get(col, '') or '') for col, rx in src.get('keep', {}).items()): continue
            name = clean(row.get(src['name'], ''))
            if not name or (src.get('skip') and re.search(src['skip'], name)): continue
            pt = point(row, src)
            if not pt or not (-180 <= pt[0] <= 180 and -90 <= pt[1] <= 90) or pt == [0.0, 0.0]: continue
            kind = kind_of(row, name, src)
            if not kind: continue
            link = clean(row.get(src.get('link', ''), ''))
            places.append({'kind': kind, 'name': name, 'word': word_of(row, kind, src, cfg),
                           'text': clean(row.get(src.get('text', ''), '')), 'credit': src['credit'],
                           'link': link if link.startswith('http') else '', 'src': src['id'], 'pt': [round(pt[0], 6), round(pt[1], 6)]})
            kept[kind] = kept.get(kind, 0) + 1
        print(f"  discover: {src['id']}: {len(places) - n0} of {len(rows)} rows {kept}")

    # One place, one point: a later row naming the same place within dedupe_m metres (or a viewpoint's same_as)
    # fills in what the first lacks (text, link, word) and is dropped.
    near = cfg.get('dedupe_m', 150)
    out, cell = [], {}
    def key(pt): return (int(pt[0] / 0.003), int(pt[1] / 0.003))
    for p in places:
        n, hit = norm(p['name']), None
        cx, cy = key(p['pt'])
        for i in range(cx - 2, cx + 3):
            for j in range(cy - 2, cy + 3):
                for q in cell.get((i, j), []):
                    m = metres(p['pt'], q['pt'])
                    if m > max(near, 600 if n in q.get('also', []) else 0): continue
                    qn = norm(q['name'])
                    short, long_ = sorted((n, qn), key=len)
                    # the same name, nearly; or, for the same kind, one name inside the other ("Mindshadows" and
                    # "Catherine Widgery 'Mindshadows'", "Cedar Ridge Creative Centre" and "... and Gardens")
                    if (n in q.get('also', []) or difflib.SequenceMatcher(None, n, qn).ratio() >= 0.86
                            or (p['kind'] == q['kind'] and len(short) >= 5 and re.search(r'\b' + re.escape(short) + r'\b', long_))):
                        hit = q; break
                if hit: break
            if hit: break
        if hit:
            for f in ('text', 'link'):
                if not hit[f] and p[f]: hit[f], hit['credit'] = p[f], hit['credit'] or p['credit']
            if p['word'] and hit['word'] == cfg.get('words', {}).get(hit['kind']) and hit['kind'] == p['kind']: hit['word'] = p['word']
            continue
        cell.setdefault((cx, cy), []).append(p); out.append(p)

    feats = []
    for p in out:
        pid = int(hashlib.sha1(f"{p['src']}|{p['name']}|{p['pt'][0]:.4f},{p['pt'][1]:.4f}".encode()).hexdigest()[:10], 16)
        props = {'id': format(pid, 'x'), 'kind': p['kind'], 'name': p['name'], 'word': p['word'], 'text': p['text'],
                 'credit': p['credit'], 'link': p['link'], 'src': p['src']}
        if p.get('checked'): props['checked'] = p['checked']
        feats.append({'type': 'Feature', 'properties': props, 'geometry': {'type': 'Point', 'coordinates': p['pt']}})
    feats.sort(key=lambda f: (f['properties']['kind'], f['properties']['name']))
    fc = {'type': 'FeatureCollection', 'about': cfg.get('about', ''), 'features': feats}
    dst = os.path.join(ROOT, 'docs', city, 'data', 'discover.geojson')
    json.dump(fc, open(dst, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    counts = {}
    for f in feats: counts[f['properties']['kind']] = counts.get(f['properties']['kind'], 0) + 1
    print(f'  discover: {len(feats)} places {counts} ({len(places) - len(feats)} duplicates merged), '
          f'{os.path.getsize(dst) / 1e6:.2f} MB')


if __name__ == '__main__':
    build(sys.argv[1], '--fetch' in sys.argv[2:])
