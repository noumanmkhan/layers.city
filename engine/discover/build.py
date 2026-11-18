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

csv.field_size_limit(1 << 30)   # some exports carry a whole outline in one column
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
    gv = row.get(src.get('geometry', 'geometry')) or ''
    if re.match(r'\s*(MULTI)?(POINT|POLYGON|LINESTRING)', gv, re.I):   # WKT, as Socrata's CSV exports write it
        try:
            from shapely import wkt
            p = wkt.loads(gv).representative_point()
            return [p.x, p.y]
        except Exception:
            return None
    try:
        g = json.loads(gv)
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
    parts = [src['label']] if src.get('label') else []   # a fixed first part ("Chicago Landmark")
    for c in src.get('word', []):
        v = re.sub(r'\s+', ' ', clean(row.get(c, '')))   # a form's line breaks ("Port\nMinistries with\n…")
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
            text = clean(row.get(src.get('text', ''), ''))
            # a text too short to say anything ("mural"), or a note to the registry rather than about the place, is left
            # out (the place stays): src["minText"] characters, src["textSkip"] a regex
            if len(text) < src.get('minText', 0) or (src.get('textSkip') and re.search(src['textSkip'], text)): text = ''
            places.append({'kind': kind, 'name': name, 'word': word_of(row, kind, src, cfg),
                           'text': text, 'credit': src['credit'],
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
    if cfg.get('map'): for_map(city, cfg, feats)
    dst = os.path.join(ROOT, 'docs', city, 'data', 'discover.geojson')
    json.dump(fc, open(dst, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    counts = {}
    for f in feats: counts[f['properties']['kind']] = counts.get(f['properties']['kind'], 0) + 1
    print(f'  discover: {len(feats)} places {counts} ({len(places) - len(feats)} duplicates merged), '
          f'{os.path.getsize(dst) / 1e6:.2f} MB')


def for_map(city, cfg, feats):
    """The web map's copy (discover.json "map"): the places as small points (docs/<city>/data/discover_pts.geojson,
    {id, cat, name, sub, x: has text}), their words split into shards loaded when a popup opens
    (discover_about/<n>.json, {id: [text, credit, link, checked]}, n = int(id, 16) % shards), and the places that one
    of the map's own layers already shows (map.attach: {kind: {file, cat?, strip?: a regex taken out of both names
    before comparing, such as "Library" and "branch"}}), matched by name within attach_m metres:
    those are left out of the points and listed in discover_attach.json ({file: [[name, lon, lat, id]...]}) so that
    layer's popup can show the words instead."""
    M = cfg['map']; out_dir = os.path.join(ROOT, 'docs', city, 'data'); n_sh = M.get('shards', 32); near = M.get('attach_m', 400)
    targets = {}
    for kind, t in M.get('attach', {}).items():
        path = os.path.join(out_dir, t['file'] + '.geojson')
        if not os.path.exists(path): continue
        fs = []
        for f in json.load(open(path, encoding='utf-8'))['features']:
            pr = f['properties']
            if t.get('cat') and pr.get('cat') != t['cat']: continue
            c = f['geometry']['coordinates']; flat = []
            def walk(c):
                if isinstance(c[0], (int, float)): flat.append(c)
                else: [walk(x) for x in c]
            walk(c)
            xs, ys = [x[0] for x in flat], [x[1] for x in flat]
            nm = pr.get('name') or pr.get('n') or ''
            fs.append((norm(re.sub(t['strip'], ' ', nm) if t.get('strip') else nm), (min(xs), min(ys), max(xs), max(ys)), nm))
        targets[kind] = (t['file'], fs, t.get('strip'))
    def bbox_m(pt, b):   # metres from a point to a box (0 inside)
        x = min(max(pt[0], b[0]), b[2]); y = min(max(pt[1], b[1]), b[3]); return metres(pt, [x, y])
    def same(a, b):
        if not a or not b: return False
        short, long_ = sorted((a, b), key=len)
        # 2: the same name or nearly; 1: the map's name and more of the same place ("Berczy Park & Gooderham Flatiron
        # Building", "Brimley Woods Park"); 0: anything else, such as "High Park Nature Centre" or "32 Gothic Avenue &
        # High Park Mineral Baths", which are other places
        if a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.9: return 2
        rest = long_[len(short):].strip() if long_.startswith(short + ' ') else None
        return 1 if rest is not None and len(short) >= 6 and re.match(r'(and\b|park$|trail$|woods$|beach$|lands$|branch$)', rest) else 0
    pts, attach, shards = [], {}, {}
    for f in feats:
        pr, pt = f['properties'], f['geometry']['coordinates']
        if pr['text'] or pr.get('checked'):
            shards.setdefault(int(pr['id'], 16) % n_sh, {})[pr['id']] = [pr['text'], pr['credit'], pr['link'], pr.get('checked', '')]
        hit = None
        if pr['kind'] in targets:
            file, fs, strip = targets[pr['kind']]; n = norm(re.sub(strip, ' ', pr['name']) if strip else pr['name'])
            best = max(((same(n, x[0]), x) for x in fs if bbox_m(pt, x[1]) <= near), key=lambda y: y[0], default=(0, None))
            hit = best[1] if best[0] else None
            if hit: hit_score = best[0]
        if hit:
            if pr['text']:
                # one text per place on the map: an exact name beats "and more"
                L_ = attach.setdefault(file, []); old = next((i for i, y in enumerate(L_) if y[0] == hit[2] and metres(pt, y[1:3]) < 3000), None)
                row = [hit[2], round(pt[0], 5), round(pt[1], 5), pr['id'], hit_score]
                if old is None: L_.append(row)
                elif L_[old][4] < hit_score: L_[old] = row
            continue
        if pr['kind'] not in M.get('kinds', []): continue
        q = {'id': pr['id'], 'cat': pr['kind'], 'name': pr['name'], 'sub': pr['word']}
        if pr['text'] or pr.get('checked'): q['x'] = 1
        pts.append({'type': 'Feature', 'properties': q, 'geometry': f['geometry']})
    json.dump({'type': 'FeatureCollection', 'shards': n_sh, 'features': pts}, open(os.path.join(out_dir, 'discover_pts.geojson'), 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    sd = os.path.join(out_dir, 'discover_about'); os.makedirs(sd, exist_ok=True)
    for old in os.listdir(sd): os.remove(os.path.join(sd, old))
    for i, d in shards.items(): json.dump(d, open(os.path.join(sd, f'{i}.json'), 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    attach = {k: [r[:4] for r in v] for k, v in attach.items()}
    json.dump({'shards': n_sh, 'm': near, 'files': attach}, open(os.path.join(out_dir, 'discover_attach.json'), 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    kc = {}
    for q in pts: kc[q['properties']['cat']] = kc.get(q['properties']['cat'], 0) + 1
    print(f"  discover: map: {len(pts)} points {kc}, words attached to {', '.join(f'{len(v)} in {k}' for k, v in attach.items())}")


if __name__ == '__main__':
    build(sys.argv[1], '--fetch' in sys.argv[2:])
