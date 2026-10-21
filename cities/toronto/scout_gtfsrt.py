"""Scout: the TTC's GTFS-realtime feeds at gtfsrt.ttc.ca (City of Toronto Open Data, "TTC GTFS-Realtime").

Finds the service alert feed URLs from the index page, decodes the subway alerts and saves what a planned
closure looks like, so fetch_subway_alerts.py can read the official open feed instead of the alerts list
behind ttc.ca. Writes cities/toronto/raw/scouting/gtfsrt/. Runs in Actions (scout-toronto.yml).
"""
import json, os, re, subprocess, sys, urllib.request
from datetime import datetime, timezone

subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'gtfs-realtime-bindings'], check=False)
from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw', 'scouting', 'gtfsrt')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Layers.City (go@layers.city)'}


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            return r.status, r.headers.get('Content-Type', ''), r.read()
    except Exception as e:
        return getattr(e, 'code', None), '', str(e).encode()


summary = {}
status, ctype, body = get('https://gtfsrt.ttc.ca/')
html = body.decode('utf-8', 'replace')
open(os.path.join(OUT, 'index.html'), 'w').write(html[:300000])
links = sorted(set(re.findall(r'href="([^"]+)"', html)))
summary['index'] = {'status': status, 'type': ctype, 'links': links[:200]}
print('index', status, len(links), 'links')

cands = [l for l in links if re.search(r'alert|subway', l, re.I)]
cands = [l if l.startswith('http') else 'https://gtfsrt.ttc.ca' + ('' if l.startswith('/') else '/') + l for l in cands]
for guess in ('/alerts/subway', '/alerts/all', '/alerts', '/alerts/subway?format=binary', '/alerts/all?format=binary'):
    cands.append('https://gtfsrt.ttc.ca' + guess)
seen = set()
feeds = {}
for url in cands:
    if url in seen:
        continue
    seen.add(url)
    s, t, b = get(url)
    info = {'status': s, 'type': t, 'bytes': len(b)}
    try:
        m = gtfs_realtime_pb2.FeedMessage()
        m.ParseFromString(b)
        d = MessageToDict(m)
        ents = d.get('entity', [])
        info['entities'] = len(ents)
        info['header'] = d.get('header')
        info['samples'] = ents[:6]
        feeds[url] = d
    except Exception as e:
        info['decode'] = str(e)[:200]
        info['head'] = b[:300].decode('utf-8', 'replace')
    summary[url] = info
    print(url, s, t, len(b), info.get('entities'))

# The richest decoded feed: list every alert's cause/effect, route and period, to see the planned closures.
best = max(feeds.items(), key=lambda kv: len(kv[1].get('entity', [])), default=(None, {}))
rows = []
for e in best[1].get('entity', []):
    a = e.get('alert') or {}
    head = ' '.join(t.get('text', '') for t in (a.get('headerText') or {}).get('translation', [])[:1])
    rows.append({'id': e.get('id'), 'cause': a.get('cause'), 'effect': a.get('effect'),
                 'routes': [x.get('routeId') for x in a.get('informedEntity', []) if x.get('routeId')][:6],
                 'periods': a.get('activePeriod'), 'header': head[:300],
                 'ext': {k: v for k, v in a.items() if k not in ('headerText', 'descriptionText', 'informedEntity', 'activePeriod', 'cause', 'effect')}})
summary['best_feed'] = best[0]
summary['alerts'] = rows
json.dump(summary, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1, ensure_ascii=False)
print('best', best[0], len(rows), 'alerts')
for r in rows:
    if any(str(x) in ('1', '2', '4') for x in r['routes']) or re.search(r'subway|line [124]', r['header'], re.I):
        print(r['effect'], r['routes'], r['periods'], r['header'][:120])
