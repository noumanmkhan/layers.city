"""The "along" block of a city's published city.json (DATA_CONTRACT.md section 18): where an app finds the Along the
way page's files, and a version that changes whenever any of them does, so an app can replace its cached copy.

Written by engine/assemble.py with the rest of city.json, and again by engine/along/build.py after each rebuild
(the scheduled refresh rebuilds Along without re-assembling the map). The engine names no city.
"""
import hashlib, json, os


def along_block(root, city):
    cfg_p = os.path.join(root, 'cities', city, 'along.json')
    d = os.path.join(root, 'docs', city, 'along')
    files = [os.path.join(d, 'data', 'graph.json'), os.path.join(d, 'data', 'pois.json'), os.path.join(d, 'router.js')]
    if not (os.path.isfile(cfg_p) and all(os.path.isfile(f) for f in files)):
        return None
    cfg = json.load(open(cfg_p, encoding='utf-8'))
    h = hashlib.sha1()
    ad = os.path.join(d, 'data', 'about')
    about = sorted(f for f in os.listdir(ad) if f.endswith('.json')) if os.path.isdir(ad) else []
    for f in files + [os.path.join(ad, a) for a in about]:
        h.update(open(f, 'rb').read())
    graph = json.load(open(files[0], encoding='utf-8'))
    pois = json.load(open(files[1], encoding='utf-8'))
    return {
        'page': '/%s/along/' % city,
        'graph': '/%s/along/data/graph.json' % city,
        'pois': '/%s/along/data/pois.json' % city,
        'about': '/%s/along/data/about/{n}.json' % city if pois.get('about') else None,
        'aboutFiles': pois.get('about', 0),
        'router': '/%s/along/router.js' % city,
        'skipModes': cfg.get('skipModes', []),
        'stopRadius': 350, 'endRadius': 700,   # metres: the page's STOP_R and END_R (engine/along/page.html)
        'asof': graph.get('asof'),
        'version': h.hexdigest()[:12],
    }


def write_block(root, city):
    """Put the block into docs/<city>/data/city.json in place (that file is otherwise written by assemble.py)."""
    p = os.path.join(root, 'docs', city, 'data', 'city.json')
    if not os.path.isfile(p):
        return None
    pub = json.load(open(p, encoding='utf-8'))
    b = along_block(root, city)
    if pub.get('along') == b:
        return b
    if b: pub['along'] = b
    else: pub.pop('along', None)
    open(p, 'w', encoding='utf-8').write(json.dumps(pub, ensure_ascii=False, separators=(',', ':')) + '\n')
    return b
