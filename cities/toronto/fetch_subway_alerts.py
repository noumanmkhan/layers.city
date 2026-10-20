"""Planned TTC subway closures, for the weekend brief (engine/weekend.py).

Reads the alerts list that ttc.ca's own service advisories page uses (alerts.ttc.ca/api/alerts/list;
not a documented open-data feed, so if it changes or goes away the brief simply has no subway items).
Keeps planned subway closures only: full or early closures with an end date, not slow zones and not
incidents ("Bypass ... due to a security incident" is filed as Planned too, with no end). Planned
closures appear in the list about five days ahead, so a daily run catches each weekend's.

Writes raw/closures/subway.json: {fetched, source, closures: [{id, line, name, from, to, start, end,
effect, text, shuttle}]}, times in Toronto time. Run daily in Actions (*Fetch transit closures*); the
sandbox can't reach ttc.ca.
Usage: python3 cities/toronto/fetch_subway_alerts.py [--file saved.json]
"""
import json, os, re, sys, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'https://alerts.ttc.ca/api/alerts/list'
TZ = ZoneInfo('America/Toronto')
OUT = os.path.join(HERE, 'raw', 'closures')
os.makedirs(OUT, exist_ok=True)

if len(sys.argv) > 2 and sys.argv[1] == '--file':
    data = json.load(open(sys.argv[2]))
else:
    req = urllib.request.Request(URL, headers={'User-Agent': 'Layers.City (go@layers.city)', 'Accept': 'application/json'})
    data = json.loads(urllib.request.urlopen(req, timeout=60).read())


def local(iso):
    if not iso or iso.startswith('0001'):
        return None
    t = datetime.fromisoformat(iso.replace('Z', '+00:00'))
    return t.astimezone(TZ).strftime('%Y-%m-%dT%H:%M')


closures = []
for a in data.get('routes') or []:
    if a.get('routeType') != 'Subway' or a.get('alertType') != 'Planned':
        continue
    effect = a.get('effectDesc') or ''
    end = local((a.get('activePeriod') or {}).get('end'))
    if 'closure' not in effect.lower() or not end:
        continue
    head = a.get('headerText') or ''
    name = head.split(':', 1)[0].strip() if ':' in head else 'Line %s' % a.get('route')
    text = re.sub(r'\s+', ' ', a.get('title') or head).strip()
    closures.append({
        'id': a.get('id'), 'line': a.get('route'), 'name': name,
        'from': a.get('stopStart'), 'to': a.get('stopEnd'),
        'start': local((a.get('activePeriod') or {}).get('start')), 'end': end,
        'effect': effect, 'text': text,
        'shuttle': bool(re.search(r'shuttle', text, re.I)),
    })

json.dump({'fetched': datetime.now(TZ).strftime('%Y-%m-%dT%H:%M'), 'source': URL, 'closures': closures},
          open(os.path.join(OUT, 'subway.json'), 'w'), indent=1, ensure_ascii=False)
print('Toronto:', len(closures), 'planned subway closures')
