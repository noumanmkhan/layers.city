"""Planned TTC subway closures, for the weekend brief (engine/weekend.py).

Source: the TTC's GTFS-realtime service alerts for the subway, https://gtfsrt.ttc.ca/alerts/subway
(listed on the City of Toronto Open Data portal as "TTC GTFS-Realtime (GTFS-RT)", Open Government
Licence – Toronto). Planned closures are alerts with cause MAINTENANCE or CONSTRUCTION, effect
NO_SERVICE and an end time; the TTC publishes one alert per night or weekend window, so alerts with
the same line and text are merged into one closure with its windows. Incidents (no end time, or other
causes) and slow zones are left out. Planned closures appear about five days ahead, so a daily run
catches each weekend's.

Writes raw/closures/subway.json: {fetched, source, closures: [{id, line, name, from, to, start, end,
windows: [[start, end]], effect, text, shuttle}]}, times in Toronto time. `effect` is "Full closure"
or "Early closure" (the alert says the line closes early or nightly). Run daily in Actions (*Fetch transit closures*); the
sandbox can't reach ttc.ca.
Needs: pip install gtfs-realtime-bindings
Usage: python3 cities/toronto/fetch_subway_alerts.py [--file saved.pb]
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from google.transit import gtfs_realtime_pb2

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'https://gtfsrt.ttc.ca/alerts/subway?format=binary'
TZ = ZoneInfo('America/Toronto')
OUT = os.path.join(HERE, 'raw', 'closures')
os.makedirs(OUT, exist_ok=True)
NAMES = {'1': 'Line 1 Yonge-University', '2': 'Line 2 Bloor-Danforth', '4': 'Line 4 Sheppard',
         '5': 'Line 5 Eglinton', '6': 'Line 6 Finch West'}
PLANNED = {gtfs_realtime_pb2.Alert.MAINTENANCE, gtfs_realtime_pb2.Alert.CONSTRUCTION}

if len(sys.argv) > 2 and sys.argv[1] == '--file':
    raw = open(sys.argv[2], 'rb').read()
else:
    req = urllib.request.Request(URL, headers={'User-Agent': 'Layers.City (go@layers.city)'})
    raw = urllib.request.urlopen(req, timeout=60).read()
feed = gtfs_realtime_pb2.FeedMessage()
feed.ParseFromString(raw)


def local(ts):
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(TZ).strftime('%Y-%m-%dT%H:%M')


def text(ts):
    return next((t.text for t in ts.translation if t.language in ('en', '')), ts.translation[0].text if ts.translation else '')


merged = {}
for e in feed.entity:
    a = e.alert
    if not e.HasField('alert') or a.cause not in PLANNED or a.effect != gtfs_realtime_pb2.Alert.NO_SERVICE:
        continue
    windows = [(p.start, p.end) for p in a.active_period if p.end]
    routes = sorted({i.route_id for i in a.informed_entity if i.route_id})
    if not windows or len(routes) != 1:
        continue
    line = routes[0]
    head = re.sub(r'\s+', ' ', text(a.header_text)).strip()
    body = head.split(':', 1)[1].strip() if ':' in head[:40] else head
    m = re.search(r'between (.+?) and (.+?) stations?', body)
    key = (line, m.groups() if m else body[:80])
    c = merged.setdefault(key, {'id': e.id, 'line': line, 'name': NAMES.get(line, 'Line %s' % line),
                                'from': m.group(1) if m else None, 'to': m.group(2) if m else None,
                                'windows': [], 'text': body, 'shuttle': bool(re.search(r'shuttle', body, re.I))})
    c['windows'] += windows

closures = []
for c in merged.values():
    ws = sorted(set(c['windows']))
    c['windows'] = [[local(s), local(t)] for s, t in ws]
    c['start'], c['end'] = c['windows'][0][0], max(w[1] for w in c['windows'])
    # The alerts' active periods are when the TTC shows them, a little wider than the closure itself,
    # so whether a closure is nightly comes from its wording ("will end nightly at 11:59 p.m.").
    nightly = re.search(r'nightly|early|end(s)? at 1[01](:\d\d)? ?p\.?m|starting (at )?1[01](:\d\d)? ?p\.?m', c['text'], re.I)
    # Several short windows are nights too (one alert per night).
    nightly = nightly or (len(ws) > 1 and all(t - s < 12 * 3600 for s, t in ws))
    c['effect'] = 'Early closure' if nightly else 'Full closure'
    closures.append(c)
closures.sort(key=lambda c: (c['start'], c['line']))

stamp = feed.header.timestamp or int(datetime.now(timezone.utc).timestamp())
json.dump({'fetched': local(stamp), 'source': URL, 'licence': 'Open Government Licence – Toronto',
           'closures': closures}, open(os.path.join(OUT, 'subway.json'), 'w'), indent=1, ensure_ascii=False)
print('Toronto:', len(closures), 'planned subway closures (GTFS-RT)')
for c in closures:
    print(' ', c['name'], c['from'], '->', c['to'], c['effect'], c['start'], c['end'], len(c['windows']), 'windows')
